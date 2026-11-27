"""Guide search: sections (on now / coming up / catch-up), OK = live when on now,
and the FFmpeg Direct engine falls back to Kodi's player when it cannot play.

Run from the repo root: python3 tests/epg_search_test.py
"""
import os, re, sys, tempfile, runpy, time, urllib.parse
ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import fake_server, xbmcaddon, xbmcplugin, xbmcgui, xbmc
srv = fake_server.start()
S = xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss',
         epg_enable='true', epg_past_days='7', check_stream='false', zap_recover='true')
from resources.lib import sync, playback
sync.run_sync('full')
fails = 0
def check(name, ok):
    global fails
    fails += not ok; print('%s %s' % ('PASS' if ok else 'FAIL', name))
def run(q):
    sys.argv = ['plugin://plugin.video.xtreamcodes/', '1', q]
    runpy.run_path(os.path.join(ADDON, 'main.py'), run_name='__main__')

xbmcplugin.ITEMS.clear(); run('?action=search_epg&q=show')
labels = [li.label for _, li, _ in xbmcplugin.ITEMS]
heads = [l for l in labels if l.startswith('[B][COLOR')]
names = [re.sub(r'\[[^\]]*\]', '', h) for h in heads]
check('sections in order: %s' % names, names == ['On now', 'Coming up', 'Catch-up (already aired)'])
i_now = labels.index(heads[0]); i_next = labels.index(heads[1]); i_past = labels.index(heads[2])
now_items = xbmcplugin.ITEMS[i_now + 1:i_next]
check('on now: both channels (%d)' % len(now_items), len(now_items) == 2)
past_items = xbmcplugin.ITEMS[i_past + 1:]
starts = [int(dict(urllib.parse.parse_qsl(u.split('?', 1)[1]))['start']) for u, _, _ in past_items]
check('catch-up: %d items, newest first' % len(starts), starts and starts == sorted(starts, reverse=True))
check('catch-up only from the archive channel', all('News One' in li.label for _, li, _ in past_items))
check('info says what OK does', now_items[0][1].tag.d.get('plot', '').startswith('[B]OK: watch live'))
ctx = dict(now_items[0][1].ctx)
check('context menu has restart for the archive channel', any('Watch from the beginning' in k for k, _ in now_items[0][1].ctx + now_items[1][1].ctx))

# OK on a programme on now: plays live straight away, no popup
url = [u for u, li, _ in now_items if 'News One' in li.label][0]
xbmcgui.DIALOGS.clear(); n = len(xbmc.Player.PLAYED)
run(url[url.index('?'):])
check('OK on "on now" plays live without a question', len(xbmc.Player.PLAYED) == n + 1 and '/live/' in xbmc.Player.PLAYED[-1][0]
      and not [d for d in xbmcgui.DIALOGS if d[0] == 'contextmenu'])

# FFmpeg Direct cannot load: first failure switches to Kodi's player for the session
S['live_engine'] = '1'
xbmc.getCondVisibility = lambda c: 'inputstream.ffmpegdirect' in c
from resources.lib.catalog import Catalog
c = Catalog(playback.common.catalog_path()); row = c.get('live', '101'); c.close()
_, li = playback.live_item(row)
check('ffmpegdirect used when selected', li.props.get('inputstream') == 'inputstream.ffmpegdirect' and 'inputstreamaddon' not in li.props)
playback.start_live(row, '1')
rec = playback.LiveRecovery(); n = len(xbmc.Player.PLAYED); xbmcgui.DIALOGS.clear()
rec.onPlayBackError()
retried = xbmc.Player.PLAYED[n:]
check('after it fails: retried once (%d)' % len(retried), len(retried) == 1)
_, li = playback.live_item(row)
check('ffmpegdirect no longer used this session', 'inputstream' not in li.props)
check('viewer told', any('FFmpeg Direct' in str(d) for d in xbmcgui.DIALOGS))
srv.shutdown()
sys.exit(1 if fails else 0)
