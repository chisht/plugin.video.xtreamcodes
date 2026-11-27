"""Fast remote keys: keymap sends NotifyAll, the service changes channel.

Run from the repo root: python3 tests/fast_keys_test.py
"""
import os, sys, tempfile, runpy, threading, time
ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmc, xbmcvfs
fake_server.LIVE[:] = [{"num": i + 1, "name": "Channel %d" % (i + 1), "stream_id": 5000 + i, "stream_icon": "",
                        "epg_channel_id": "c%d" % i, "category_id": "1", "tv_archive": 0} for i in range(5)]
fake_server.LIVE_CATS[:] = [{"category_id": "1", "category_name": "G"}]
srv = fake_server.start(); S = xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss', epg_enable='false',
         page_size='0', check_stream='false', zap_reverse='false', zap_debounce='0',
         zap_enable='true', zap_restart_key='true', zap_fast='true')
from resources.lib import sync, playback, overlay, keymap
from resources.lib.catalog import Catalog, live_rows
sync.run_sync('full'); P = xbmc.Player
banners = []
overlay.show_banner = lambda row, extra='', during=None: (banners.append(row['name']), during and during())
fails = 0
def check(name, ok):
    global fails
    fails += not ok
    print('%s %s' % ('PASS' if ok else 'FAIL', name))

# keymap: another add-on maps keyboard 'up' already -> kept as fallback
kmdir = xbmcvfs.translatePath(keymap.KEYMAP_DIR); os.makedirs(kmdir, exist_ok=True)
open(os.path.join(kmdir, 'other.xml'), 'w').write(
    '<keymap><FullscreenVideo><keyboard><up>Action(BigStepForward)</up></keyboard></FullscreenVideo></keymap>')
keymap.apply(); km = open(keymap._path()).read()
check('fast keymap uses NotifyAll', 'NotifyAll(plugin.video.xtreamcodes,zap.remote.up)' in km and 'RunPlugin' not in km)
check('resolve remote up', keymap.resolve('zap.remote.up') == ('up', '0', None))
check('resolve keyboard up keeps other add-on fallback', keymap.resolve('zap.keyboard.up') == ('up', '0', 'Action(BigStepForward)'))
check('resolve digit 7', keymap.resolve('zap.remote.seven')[:2] == ('digit', '7'))
check('resolve unknown -> None', keymap.resolve('zap.remote.nosuchkey') is None and keymap.resolve('other') is None)
S['zap_fast'] = 'false'; keymap.apply(); km = open(keymap._path()).read()
check('slow keymap uses RunPlugin', 'RunPlugin(plugin://plugin.video.xtreamcodes/?action=zap&amp;key=up' in km and 'NotifyAll' not in km)

# service: a NotifyAll from the keymap changes channel
svc = runpy.run_path(os.path.join(ADDON, 'service.py'))
listener = svc['KeyListener']()
c = Catalog(playback.common.catalog_path()); rows = live_rows(c, '1'); c.close()
playback.start_live(rows[0], '1')
def notify(method, sender='plugin.video.xtreamcodes'):
    before = set(threading.enumerate())
    listener.onNotification(sender, method, 'null')
    for t in set(threading.enumerate()) - before:
        t.join(10)
n = len(P.PLAYED); t0 = time.time(); notify('Other.zap.remote.up')
check('service: Up -> Channel 2 (%.2fs)' % (time.time() - t0), len(P.PLAYED) == n + 1 and P.PLAYED[-1][1] == 'Channel 2')
check('service: banner shown', banners[-1:] == ['Channel 2'])
n = len(P.PLAYED); notify('Other.zap.remote.down')
check('service: Down -> Channel 1', len(P.PLAYED) == n + 1 and P.PLAYED[-1][1] == 'Channel 1')
n = len(P.PLAYED); notify('Other.zap.remote.up', sender='someone.else'); notify('Other.unrelated')
check('service ignores other senders/messages', len(P.PLAYED) == n)
P.FILE = 'http://127.0.0.1/movie/u/p/1.mkv'; xbmc.BUILTINS.clear(); notify('Other.zap.keyboard.up')
check('service: not our live TV -> fallback action', xbmc.BUILTINS == ['Action(BigStepForward)'])
srv.shutdown()
sys.exit(1 if fails else 0)
