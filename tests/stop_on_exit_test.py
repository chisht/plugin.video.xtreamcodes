"""Stop playback when the viewer leaves the add-on, from every window.

TV mode already stopped the channel on Back; the grid guide and a channel that
was started from one of the add-on's lists (Kodi resolves those, so nothing of
the add-on stays on screen) did not. Checks the window bookkeeping, the guide
that must NOT stop a channel it is sitting on, and the service watchdog that
catches the cases the add-on cannot see.

Run from the repo root: python3 tests/stop_on_exit_test.py
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
fake_server.LIVE[:] = [{"num": i + 1, "name": "Channel %d" % (i + 1), "stream_id": 7000 + i,
                        "stream_icon": "", "epg_channel_id": "c%d" % i,
                        "category_id": "1", "tv_archive": 0} for i in range(4)]
fake_server.LIVE_CATS[:] = [{"category_id": "1", "category_name": "News"}]
srv = fake_server.start()
S = xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss',
         epg_enable='false', page_size='0', check_stream='false', show_counts='false',
         tv_stop_on_exit='true', tv_autoplay='false', zap_debounce='0')

from resources.lib import sync, playback, guide, tvwindow                        # noqa: E402
from resources.lib.catalog import Catalog, live_rows                             # noqa: E402

fails = 0


def check(name, ok):
    global fails
    fails += not ok
    print('%s %s' % ('PASS' if ok else 'FAIL', name))


def playing(row, age=30):
    """Put one of our live channels 'on air' and backdate the tuning time."""
    path, li = playback.live_item(row)
    xbmc.Player.FILE = path
    xbmc.Player.PLAYED.append((path, li.label, False))
    playback.remember_zap('1', row['stream_id'], row=row)
    when = time.time() - age
    st = playback.zap_state() or {}
    st['t'] = when
    xbmcgui.Window(10000).setProperty(playback.common.PROP_ZAP, playback.common.json.dumps(st))
    xbmcgui.Window(10000).setProperty(playback.PROP_TUNE_T, '%f' % when)
    return path


sync.run_sync('full')
P = xbmc.Player
cat = Catalog(playback.common.catalog_path())
rows = live_rows(cat, '1')
cat.close()

# ------------------------------------------------------------------ TV mode
P.FILE = ''
playback.UI_OPEN[0] = 0
w = tvwindow.TVWindow(tvwindow.theme.TV_XML, ADDON, tvwindow.theme.skin_dir(), '1080i')
w.onInit()
check('opening TV mode marks a window open (%d)' % playback.UI_OPEN[0], playback.UI_OPEN[0] == 1)
playing(rows[0])
w.onAction(xbmcgui.Action(92))                      # Back out of TV mode
check('Back out of TV mode stops the channel', P.FILE == '' and P.STOPPED)
check('window bookkeeping is back to zero', playback.UI_OPEN[0] == 0)

S['tv_stop_on_exit'] = 'false'
P.STOPPED = False
w = tvwindow.TVWindow(tvwindow.theme.TV_XML, ADDON, tvwindow.theme.skin_dir(), '1080i')
w.onInit()
playing(rows[0])
w.onAction(xbmcgui.Action(92))
check('with the setting off TV mode leaves the channel playing', bool(P.FILE) and not P.STOPPED)
S['tv_stop_on_exit'] = 'true'

# --------------------------------------------------------------- grid guide
# opened from the add-on's own menu (nothing playing yet): leaving it stops
P.FILE = ''
playback.UI_OPEN[0] = 0
g = guide.GuideWindow(guide.theme.GUIDE_XML, ADDON, guide.theme.skin_dir(), '1080i')
g.setup('*', None)
g.keep_playing = False
g.onInit()
playing(rows[1])
g.onAction(xbmcgui.Action(92))                      # Back out of the guide
check('Back out of the guide (opened from the add-on) stops the channel',
      P.FILE == '' and P.STOPPED)
check('guide window bookkeeping back to zero', playback.UI_OPEN[0] == 0)

# Back reaches close() twice (onAction, then doModal returning): the second one
# must not ask Kodi for the previous window again, or the guide takes the window
# it was opened over with it - out of the add-on, to Kodi's home screen.
closes = []
real_wm_close = xbmcgui.WindowXML.close
xbmcgui.WindowXML.close = lambda self: closes.append(self)
try:
    g = guide.GuideWindow(guide.theme.GUIDE_XML, ADDON, guide.theme.skin_dir(), '1080i')
    g.setup('*', None)
    g.onInit()
    g.onAction(xbmcgui.Action(92))       # Back
    g.close()                            # doModal's finally, as in open_guide()
    check('the guide closes the window once, not twice (%d)' % len(closes), len(closes) == 1)
    closes[:] = []
    w = tvwindow.TVWindow(tvwindow.theme.TV_XML, ADDON, tvwindow.theme.skin_dir(), '1080i')
    w.onInit()
    w.onAction(xbmcgui.Action(92))
    w.close()
    check('TV mode closes the window once, not twice (%d)' % len(closes), len(closes) == 1)
finally:
    xbmcgui.WindowXML.close = real_wm_close

# opened over a playing channel: Back returns to the picture, so it keeps playing
def guide_over_video():
    P.FILE = playing(rows[2])
    xbmc.FULLSCREEN.on = True            # Kodi's fullscreen video window is up
    opened = {}
    real_modal = xbmcgui.WindowXML.doModal

    def modal(self):
        opened['keep'] = getattr(self, 'keep_playing', None)
        self.onInit()
        self.close()          # the viewer pressed Back at once
    xbmcgui.WindowXML.doModal = modal
    try:
        guide.open_guide('1', rows[2]['stream_id'])
    finally:
        xbmcgui.WindowXML.doModal = real_modal
    return opened


P.PLAYED.clear()
P.STOPPED = False
opened = guide_over_video()
check('guide opened over the picture keeps it playing (%s)' % opened, opened.get('keep') is True)
check('the channel is still on after closing that guide', bool(P.FILE) and not P.STOPPED)
xbmc.FULLSCREEN.on = None

# opened while a channel plays with no picture (started from a list, the viewer
# is on our menu): closing the guide must not leave the channel playing
P.FILE = playing(rows[3])
P.isPlayingVideo = lambda self: True    # a background stream still reports video
xbmc.FULLSCREEN.on = False              # ...but no fullscreen video window is up
opened = {}
real_modal = xbmcgui.WindowXML.doModal


def modal(self):
    opened['keep'] = getattr(self, 'keep_playing', None)
    self.onInit()
    self.close()
xbmcgui.WindowXML.doModal = modal
try:
    guide.open_guide('1', rows[3]['stream_id'])
finally:
    xbmcgui.WindowXML.doModal = real_modal
check('a guide over a pictureless stream does not keep it playing (%s)' % opened,
      opened.get('keep') is False)
check('that channel is stopped when the guide closes', P.FILE == '' and P.STOPPED)
xbmc.FULLSCREEN.on = None
P.isPlayingVideo = lambda self: bool(P.FILE)

# ------------------------------------------------------- the service watchdog
S['tv_stop_on_exit'] = 'true'
P.FILE = ''
P.STOPPED = False
P.isPlayingVideo = lambda self: bool(P.FILE)
playback.UI_OPEN[0] = 0
xbmcgui.Window(10000).clearProperty(playback.common.PROP_UI_OPEN)
playing(rows[0])
P.isPlayingVideo = lambda self: False     # sound only: the picture is gone
check('a channel with only sound left (nothing of the add-on on screen) is caught',
      playback.left_addon() is True)
xbmc.FULLSCREEN.on = False
check('the same, while Player.isPlayingVideo() still says video is playing',
      playback.left_addon() is True)
xbmc.FULLSCREEN.on = None
xbmc.WINDOWS['Container.FolderPath'] = ''
xbmc.WINDOWS['System.CurrentWindow'] = 'Home'
P.STOPPED = False
check('nothing else playing', playback.stop_playback('test'))
check('the watchdog stops it (and the log says why)',
      P.FILE == '' and P.STOPPED and any('left the add-on' in m for m in xbmc.LOG))

P.FILE = playing(rows[1])
P.isPlayingVideo = lambda self: True          # the picture is up: fine
check('a channel on screen is never stopped by the watchdog', playback.left_addon() is False)

playback.ui_opened()                      # TV mode is on screen
P.isPlayingVideo = lambda self: False
check('TV mode on screen is never stopped by the watchdog', playback.left_addon() is False)
playback.ui_closed(keep_playing=True)

st = playback.zap_state() or {}
xbmcgui.Window(10000).setProperty(playback.PROP_TUNE_T, '%f' % time.time())
check('a channel that was just tuned is given time to show its picture',
      playback.left_addon() is False)

check('the service ticks the watchdog', 'left_addon' in
      open(os.path.join(ADDON, 'service.py'), encoding='utf-8').read())

srv.shutdown()
sys.exit(1 if fails else 0)
