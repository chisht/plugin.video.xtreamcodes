"""FFmpeg Direct cannot load and no failure callback arrives (as on a real box):
the add-on itself notices and switches to Kodi's player.

Run from the repo root: python3 tests/ffd_watch_test.py
"""
import os, sys, tempfile, threading, time
ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import fake_server, xbmcaddon, xbmcgui, xbmc
srv = fake_server.start()
S = xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss',
         epg_enable='false', check_stream='false', live_engine='1', zap_recover='true')
xbmc.getCondVisibility = lambda c: 'inputstream.ffmpegdirect' in c
xbmc.Monitor.waitForAbort = lambda self, t=0: (time.sleep(t), False)[1]
P = xbmc.Player
VIDEO = {'on': False}
P.isPlayingVideo = lambda self: bool(P.FILE) and VIDEO['on']
real_play = P.play
def play(self, item='', listitem=None, windowed=False, startpos=-1):
    real_play(self, item, listitem, windowed)
    if listitem is not None and listitem.props.get('inputstream') == 'inputstream.ffmpegdirect':
        def die():   # cannot load: playback ends after ~0.6 s, no picture, no callback
            time.sleep(0.6)
            if P.FILE == item:
                P.FILE = ''
        threading.Thread(target=die, daemon=True).start()
    else:
        VIDEO['on'] = True   # Kodi's own player works
P.play = play
from resources.lib import sync, playback
from resources.lib.catalog import Catalog
sync.run_sync('catalog')
c = Catalog(playback.common.catalog_path()); row = c.get('live', '101'); c.close()
fails = 0
def check(name, ok):
    global fails
    fails += not ok; print('%s %s' % ('PASS' if ok else 'FAIL', name))

n = len(P.PLAYED)
playback.start_live(row, '1')
for t in [t for t in threading.enumerate() if t.name == 'ffd-watch']:
    t.join(20)
plays = P.PLAYED[n:]
check('two plays: FFmpeg Direct, then Kodi\'s player (%d)' % len(plays), len(plays) == 2)
check('playing now with Kodi\'s player', VIDEO['on'] and P.FILE.startswith(srv and 'http'))
check('viewer told', any('FFmpeg Direct' in str(d) for d in xbmcgui.DIALOGS))
_, li = playback.live_item(row)
check('rest of the session uses Kodi\'s player', 'inputstream' not in li.props)

# when FFmpeg Direct works, nothing is changed
xbmcgui.PROPS.clear(); xbmcgui.DIALOGS.clear(); VIDEO['on'] = False
P.play = lambda self, item='', listitem=None, windowed=False, startpos=-1: (real_play(self, item, listitem, windowed), VIDEO.__setitem__('on', True))
n = len(P.PLAYED)
playback.start_live(row, '1')
for t in [t for t in threading.enumerate() if t.name == 'ffd-watch']:
    t.join(20)
check('working FFmpeg Direct: one play, kept', len(P.PLAYED) == n + 1 and xbmcgui.PROPS.get(playback.PROP_FFD_OK) == '1'
      and not xbmcgui.PROPS.get(playback.PROP_FFD_FAILED))
srv.shutdown()
sys.exit(1 if fails else 0)
