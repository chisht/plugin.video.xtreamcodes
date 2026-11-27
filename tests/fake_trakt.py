import json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
LOG = []; STATE = {'polls': 0}
MOVIES = [{"plays":1,"movie":{"title":"Inception","year":2010,"ids":{"tmdb":27205}}},
          {"plays":1,"movie":{"title":"Beach Movie","year":2021,"ids":{"tmdb":555000}}}]
def show(title, year, tmdb, aired, eps, last):
    seasons = {}
    for s, e in eps: seasons.setdefault(s, []).append({"number": e, "plays": 1})
    return {"last_watched_at": last, "show": {"title": title, "year": year, "ids": {"tmdb": tmdb}, "aired_episodes": aired},
            "seasons": [{"number": s, "episodes": v} for s, v in seasons.items()]}
SHOWS = [show("Beach Show", 2020, 111, 2, [(1,1)], "2026-11-20T10:00:00.000Z"),
         show("Breaking Bad", 2008, 1396, 62, [(1,1),(1,2)], "2026-11-24T10:00:00.000Z"),
         show("Lost", 2004, 4607, 2, [(1,1),(1,2)], "2026-10-01T10:00:00.000Z"),
         show("Not On Provider", 2015, 999, 10, [(1,1)], "2026-11-25T10:00:00.000Z")]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def reply(self, code, body=None):
        raw = json.dumps(body).encode() if body is not None else b''
        self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def body(self):
        n = int(self.headers.get('Content-Length') or 0); return json.loads(self.rfile.read(n) or b'{}')
    def do_POST(self):
        b = self.body(); LOG.append(('POST', self.path, b, self.headers.get('Authorization'), self.headers.get('trakt-api-key')))
        if self.path == '/oauth/device/code': return self.reply(200, {"device_code":"dev123","user_code":"ABCD1234","verification_url":"https://trakt.tv/activate","expires_in":600,"interval":5})
        if self.path == '/oauth/device/token':
            STATE['polls'] += 1
            return self.reply(400) if STATE['polls'] < 2 else self.reply(200, {"access_token":"tok1","refresh_token":"ref1","expires_in":86400,"created_at":__import__('time').time()})
        if self.path == '/oauth/token': return self.reply(200, {"access_token":"tok2","refresh_token":"ref2","expires_in":86400})
        if self.path.startswith('/scrobble/'): return self.reply(201, {"action": self.path.rsplit('/',1)[1]})
        if self.path == '/oauth/revoke': return self.reply(200, {})
        self.reply(404)
    def do_GET(self):
        LOG.append(('GET', self.path, None, self.headers.get('Authorization'), self.headers.get('trakt-api-key')))
        if self.headers.get('Authorization') not in ('Bearer tok1', 'Bearer tok2'): return self.reply(401)
        if self.path == '/users/settings': return self.reply(200, {"user": {"username": "sam"}})
        if self.path == '/sync/watched/movies': return self.reply(200, MOVIES)
        if self.path.startswith('/sync/watched/shows'): return self.reply(200, SHOWS)
        self.reply(404)
def start():
    s = ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=s.serve_forever, daemon=True).start(); return s
