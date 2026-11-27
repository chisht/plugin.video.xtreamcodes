"""Storage turns read-only: the service must survive and not retry every pass.

Run from the repo root: python3 tests/readonly_test.py
"""
import errno, os, sys, tempfile, runpy, threading, time
ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import fake_server, xbmcaddon, xbmc
srv = fake_server.start()
xbmcaddon.SETTINGS.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss',
                          epg_enable='false', bg_enable='true', refresh_hours='12', bg_notify='false')
from resources.lib import common, sync
def read_only(*a, **k):
    raise OSError(errno.EROFS, 'Read-only file system')
common._write_json = read_only
syncs = []
real_sync = sync.run_sync
sync.run_sync = lambda *a, **k: (syncs.append(1), real_sync(*a, **k))[1]
passes = {'n': 0}
def wait(self, t=0):
    if threading.current_thread() is not threading.main_thread():
        time.sleep(0.01); return passes['n'] > 8
    passes['n'] += 1; return passes['n'] > 8
xbmc.Monitor.waitForAbort = wait
g = runpy.run_path(os.path.join(ADDON, 'service.py'))
crashed = None
try:
    g['run']()
except Exception as e:
    crashed = e
fails = 0
for name, ok in [('service survives read-only storage (%r)' % crashed, crashed is None),
                 ('loop kept running (%d passes)' % passes['n'], passes['n'] > 8),
                 ('update tried once, not every pass (%d)' % len(syncs), len(syncs) == 1),
                 ('key thread told to stop', g['STOP'].is_set())]:
    fails += not ok; print('%s %s' % ('PASS' if ok else 'FAIL', name))
srv.shutdown()
sys.exit(1 if fails else 0)
