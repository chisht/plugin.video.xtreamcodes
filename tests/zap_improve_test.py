"""Zapping: CH+/CH-, group hopping, channel preview and the faster zap order.

Run from the repo root: python3 tests/zap_improve_test.py
"""
import os
import sys
import tempfile
import time

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import fake_server_live as fake_server                                     # noqa: E402
import xbmcaddon, xbmcgui, xbmc                                            # noqa: E402

fake_server.LIVE_EXTRA[:] = []
fake_server.LIVE[:] = [{"num": i + 1, "name": "Channel %d" % (i + 1), "stream_id": 6000 + i,
                        "stream_icon": "", "epg_channel_id": "c%d" % i,
                        "category_id": "1" if i < 2 else "2", "tv_archive": 0}
                       for i in range(6)]
fake_server.LIVE_CATS[:] = [{"category_id": "1", "category_name": "News"},
                            {"category_id": "2", "category_name": "Sport"}]
srv = fake_server.start()
S = xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss',
         epg_enable='false', page_size='0', check_stream='false', zap_reverse='false',
         zap_debounce='0', show_counts='true', switch_stop_first='true', zap_resume='true',
         tv_autoplay='false', tv_preview='false', tv_stop_on_exit='true', hide_adult='false',
         mark_offline='true')

from resources.lib import sync, playback, overlay, tvwindow, zapper   # noqa: E402
from resources.lib.catalog import Catalog, live_rows                  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    fails += not ok
    print('%s %s' % ('PASS' if ok else 'FAIL', name))


sync.run_sync('full')
P = xbmc.Player
cat = Catalog(playback.common.catalog_path())
rows = live_rows(cat, '1')
cat.close()
overlay.show_banner = lambda row, extra='', during=None: during and during()

# ------------------------------------------------- the order of a channel change
order = []
real_check, real_free = playback.check_live, playback.free_connection


def fake_check(row, fresh=False):
    order.append(('check %s' % row['name'], bool(P.FILE)))
    return True


def fake_free():
    order.append(('stop', bool(P.FILE)))
    P.FILE = ''
    return True


playback.check_live, playback.free_connection = fake_check, fake_free
real_start_live = playback.start_live
playback.start_live(rows[0], '1')
P.FILE = playback.live_item(rows[0])[0]           # channel 1 plays
order[:] = []
playback.start_live(rows[1], '1', announce=False)
check('the stream is stopped before the check (one-connection plans: %s)' % (order,),
      order[:2] == [('stop', True), ('check Channel 2', False)])
playback.start_live = real_start_live
playback.check_live, playback.free_connection = real_check, real_free

# a channel that just played is not probed again; a forced check still is
playback.forget_checks()
probes = []
real_probe = playback.probe
playback.probe = lambda url, timeout: (probes.append(url), (True, ''))[1]
S['check_stream'] = 'true'
playback.check_live(rows[0], fresh=True)
n = len(probes)
playback.check_live(rows[0])
check('a channel checked a moment ago is not probed again (%d probe)' % (len(probes) - n),
      len(probes) == n)
playback.check_live(rows[0], fresh=True)
check('fresh=True probes it anyway', len(probes) == n + 1)
playback.probe = lambda url, timeout: (probes.append(url), (False, 'HTTP 403'))[1]
playback.check_live(rows[1], fresh=True)                                # a failure...
n = len(probes)
check('a failed channel is not probed again either (%d)' % (n,),
      playback.check_live(rows[1]) is False and len(probes) == n)
playback.probe = real_probe
S['check_stream'] = 'false'
playback.forget_checks()
check('forget_checks() clears the marks', not playback.check_cached(rows[0]['stream_id'])[0])

# a channel that really started playing drops any wrong 'offline' mark
playback.set_offline(rows[0]['stream_id'], True)
check('channel marked offline', playback.is_offline(rows[0]['stream_id']))
st = {'id': rows[0]['stream_id'], 'cat': '1', 't': time.time()}
xbmcgui.Window(10000).setProperty(playback.common.PROP_ZAP, playback.common.json.dumps(st))
playback.LiveRecovery().onAVStarted()
check('playing clears the mark (and the channel is trusted for 10 min)',
      not playback.is_offline(rows[0]['stream_id'])
      and playback.check_cached(rows[0]['stream_id']) == (True, True))

# --------------------------------------------------------- zapping with CH+/CH-
P.PLAYED.clear()
P.FILE = playback.live_item(rows[0])[0]
playback.remember_zap('1', '6000')
zapper.handle('chup')
check('CH+ tunes the next channel (%s)' % P.PLAYED[-1][1], P.PLAYED[-1][1] == '2  Channel 2')
zapper.handle('chdown')
check('CH- goes back (%s)' % P.PLAYED[-1][1], P.PLAYED[-1][1] == '1  Channel 1')
zapper.handle('up')
check('Up still works next to CH+ (%s)' % P.PLAYED[-1][1], P.PLAYED[-1][1] == '2  Channel 2')

# ------------------------------------------------------------------- TV mode
w = tvwindow.TVWindow(tvwindow.theme.TV_XML, ADDON, tvwindow.theme.skin_dir(), '1080i')
w.onInit()
time.sleep(0.4)
c = w.getControl(200)
check('TV mode list built (%s)' % [i.label for i in c.items],
      [i.label for i in c.items] == ['1  Channel 1', '2  Channel 2'])
P.PLAYED.clear()
w.onAction(xbmcgui.Action(184))                   # CH+ from the first row
check('CH+ in TV mode tunes the highlighted channel (%s)' % (P.PLAYED[-1:] or None,),
      bool(P.PLAYED) and P.PLAYED[-1][1] == '2  Channel 2')
w.onAction(xbmcgui.Action(185))                   # CH-
check('CH- in TV mode tunes the one above (%s)' % (P.PLAYED[-1:] or None,),
      P.PLAYED[-1][1] == '1  Channel 1')
w.onAction(xbmcgui.Action(5))                     # PageUp -> next group
check('PageUp moves to the next group (%s)' % w._props['header'],
      'Sport' in w._props['header'] and w.cat_id == '2')
w.onAction(xbmcgui.Action(6))                     # PageDown -> back
check('PageDown goes back to the first group', w.cat_id == '1')
w._stop.set()
w.close()

# ----------------------------------------------------------------- preview
S['tv_preview'] = 'true'
real_wait = tvwindow.PREVIEW_WAIT
tvwindow.PREVIEW_WAIT = 0.4
w = tvwindow.TVWindow(tvwindow.theme.TV_XML, ADDON, tvwindow.theme.skin_dir(), '1080i')
w.onInit()
time.sleep(0.4)
check('preview is on for this window', w.preview_on)
P.PLAYED.clear()
w.chan_ctl.selectItem(1)                          # rest on Channel 2
time.sleep(2.0)
check('resting on a channel previews it in the mini player (%s)' % (P.PLAYED[-1:] or None,),
      bool(P.PLAYED) and P.PLAYED[-1][1] == '2  Channel 2')
played_before = len(P.PLAYED)
w.preview_on = False
w.chan_ctl.selectItem(0)
time.sleep(1.0)
check('with preview off, moving the cursor does not open a stream',
      len(P.PLAYED) == played_before)
tvwindow.PREVIEW_WAIT = real_wait
w._stop.set()
w.close()

srv.shutdown()
sys.exit(1 if fails else 0)
