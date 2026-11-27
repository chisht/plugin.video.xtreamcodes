"""Up pressed while a just-tuned channel is still opening must change channel.

Run from the repo root: python3 tests/zap_opening_test.py
"""
import os, sys, tempfile, runpy, time
ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.LIVE[:] = [{"num": i + 1, "name": "Channel %d" % (i + 1), "stream_id": 5000 + i, "stream_icon": "",
                        "epg_channel_id": "c%d" % i, "category_id": "1", "tv_archive": 0} for i in range(5)]
fake_server.LIVE_CATS[:] = [{"category_id": "1", "category_name": "G"}]
srv = fake_server.start(); S = xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss', epg_enable='false',
         page_size='0', check_stream='false', zap_reverse='false', zap_debounce='0')
from resources.lib import sync, playback, overlay
from resources.lib.catalog import Catalog, live_rows
sync.run_sync('full'); P = xbmc.Player
overlay.show_banner = lambda *a, **k: None

def press(key='up'):
    xbmc.BUILTINS.clear()
    sys.argv = ['plugin://plugin.video.xtreamcodes/', '1', '?action=zap&key=' + key]
    runpy.run_path(os.path.join(ADDON, 'main.py'), run_name='__main__')

c = Catalog(playback.common.catalog_path()); rows = live_rows(c, '1'); c.close()
OPENING = {'on': False}
P.isPlayingVideo = lambda self: bool(P.FILE) and not OPENING['on']
fails = 0
def check(name, ok):
    global fails
    fails += not ok
    print('%s %s' % ('PASS' if ok else 'FAIL', name))

# Channel 1 just tuned, Kodi still opening it (no video yet).
playback.start_live(rows[0], '1'); OPENING['on'] = True
n = len(P.PLAYED); press()
check('Up while channel is opening -> Channel 2', len(P.PLAYED) == n + 1 and P.PLAYED[-1][1] == 'Channel 2')

# Long after tuning, nothing playing: the key keeps Kodi's normal action.
P.FILE = ''; win = xbmcgui.Window(10000)
win.setProperty(playback.PROP_TUNE_T, '%f' % (time.time() - 60))
st = playback.zap_state(); st['t'] = time.time() - 60
win.setProperty(playback.common.PROP_ZAP, playback.json.dumps(st))
n = len(P.PLAYED); press()
check('Up long after tuning with nothing playing -> Kodi action', len(P.PLAYED) == n and xbmc.BUILTINS == ['Action(ChapterOrBigStepForward)'])

# Just tuned, but a movie is opening instead: not ours.
playback.start_live(rows[0], '1'); P.FILE = 'http://127.0.0.1/movie/u/p/1.mkv'
n = len(P.PLAYED); press()
check('Up while a movie opens -> Kodi action', len(P.PLAYED) == n and xbmc.BUILTINS == ['Action(ChapterOrBigStepForward)'])

# Normal case: channel playing.
OPENING['on'] = False; playback.start_live(rows[2], '1')
n = len(P.PLAYED); press()
check('Up while channel plays -> Channel 4', len(P.PLAYED) == n + 1 and P.PLAYED[-1][1] == 'Channel 4')
srv.shutdown()
sys.exit(1 if fails else 0)
