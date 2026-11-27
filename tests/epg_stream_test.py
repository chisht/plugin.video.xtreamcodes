"""The guide is read straight from the server into epg.db (no xmltv file written).

Run from the repo root: python3 tests/epg_stream_test.py
"""
import errno, gzip, os, sqlite3, sys, tempfile
ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import fake_server, xbmcaddon
MODE = {'gz': True, 'truncate': 0}   # truncate: how many next requests to cut off
orig_send = fake_server.H.send
def send(self, body, gz=False, ctype='application/json'):
    if ctype != 'application/xml':
        return orig_send(self, body, gz, ctype)
    body = gzip.compress(body) if MODE['gz'] else body
    self.send_response(200); self.send_header('Content-Type', ctype)
    self.send_header('Content-Length', str(len(body))); self.end_headers()
    if MODE['truncate']:
        MODE['truncate'] -= 1
        self.wfile.write(body[:len(body) // 2]); self.wfile.flush()
        self.close_connection = True
        return
    self.wfile.write(body)
fake_server.H.send = send
srv = fake_server.start()
xbmcaddon.SETTINGS.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss',
                          epg_enable='true', epg_past_days='1')
from resources.lib import common, sync, xtream
downloads = []
real_dl = xtream.XtreamClient.download_xmltv
def dl(self, *a, **k):
    downloads.append(1); return real_dl(self, *a, **k)
xtream.XtreamClient.download_xmltv = dl
def programmes():
    con = sqlite3.connect(common.epg_path()); n = con.execute('SELECT COUNT(*) FROM programmes').fetchone()[0]; con.close(); return n
def leftovers():
    return sorted(f for f in os.listdir(common.PROFILE) if 'xmltv' in f or f.endswith('.tmp'))
fails = 0
def check(name, ok):
    global fails
    fails += not ok; print('%s %s' % ('PASS' if ok else 'FAIL', name))

r = sync.run_sync('epg')
check('gzip guide streamed: %d programmes, no file download' % r['programmes'], r['programmes'] > 0 and not downloads)
check('nothing left on storage (%s)' % leftovers(), leftovers() == [])
n_gz = programmes()

MODE['gz'] = False; os.remove(common.epg_path())
r = sync.run_sync('epg')
check('plain XML guide streamed: same %d programmes' % r['programmes'], r['programmes'] == n_gz and not downloads)

for gz in (True, False):
    MODE.update(gz=gz, truncate=1); downloads.clear()
    r = sync.run_sync('epg')
    check('%s stream cut off -> falls back to download once, guide complete (%d)' % ('gzip' if gz else 'plain', r['programmes']),
          downloads == [1] and r['programmes'] == n_gz)
    check('  temp files cleaned up (%s)' % leftovers(), leftovers() == [])

# storage failure is not a network problem: no second download
MODE.update(gz=True, truncate=0); downloads.clear()
real_replace = common.atomic_replace
def read_only(src, dst, tries=10):
    raise OSError(errno.EROFS, 'Read-only file system')
common.atomic_replace = read_only
try:
    sync.run_sync('epg'); raised = None
except OSError as e:
    raised = e
common.atomic_replace = real_replace
check('read-only storage: error reported, no fallback download (%r)' % raised, raised is not None and not downloads)
srv.shutdown()
sys.exit(1 if fails else 0)
