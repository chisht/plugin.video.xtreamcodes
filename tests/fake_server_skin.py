"""Fake Xtream server for the STBEmu skin test: a small, tidy lineup.

  python3 tests/fake_server_skin.py   # start it on a port and print it

The other fake servers mirror real providers (huge lists, dead channels, adult
groups); this one is only meant to look like a normal subscription so the skin
can be exercised end to end.
"""
import base64
import gzip
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SEEN_UA = []
NOW = int(time.time()) // 3600 * 3600
PASSWORD = 'p@ss'

LIVE = [
    {"num": 1, "name": "News One", "stream_id": 101, "stream_icon": "http://x/n1.png",
     "epg_channel_id": "News1.uk", "category_id": "1", "tv_archive": 1,
     "tv_archive_duration": "3"},
    {"num": 2, "name": "Movie Box", "stream_id": 102, "stream_icon": "http://x/mb.png",
     "epg_channel_id": "movie.box", "category_id": "1", "tv_archive": 0},
    {"num": 3, "name": "Sport HD", "stream_id": 103, "stream_icon": "http://x/s3.png",
     "epg_channel_id": "sport.hd", "category_id": "2", "tv_archive": 1,
     "tv_archive_duration": "3"},
    {"num": 4, "name": "Kids", "stream_id": 104, "stream_icon": "http://x/k4.png",
     "epg_channel_id": "kids", "category_id": "2", "tv_archive": 0},
]
CATS = [{"category_id": "1", "category_name": "News"},
        {"category_id": "2", "category_name": "Sport"}]


def b64(s):
    return base64.b64encode(s.encode()).decode()


def xmltv():
    out = ['<?xml version="1.0" encoding="UTF-8"?><tv>']
    for c in LIVE:
        out.append('<channel id="%s"><display-name>%s</display-name></channel>'
                   % (c["epg_channel_id"], c["name"]))
    for ch in [c["epg_channel_id"] for c in LIVE]:
        for h in range(-30, 30):
            s, e = NOW + h * 3600, NOW + (h + 1) * 3600
            out.append('<programme start="%s +0000" stop="%s +0000" channel="%s">'
                       '<title>%s at %d</title><desc>Test programme.</desc></programme>'
                       % (time.strftime('%Y%m%d%H%M%S', time.gmtime(s)),
                          time.strftime('%Y%m%d%H%M%S', time.gmtime(e)), ch, ch, h))
    out.append('</tv>')
    return '\n'.join(out).encode()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, gz=False, ctype='application/json'):
        if gz:
            body = gzip.compress(body)
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        if gz:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        SEEN_UA.append(self.headers.get('User-Agent'))
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == '/xmltv.php':
            return self.send(xmltv(), gz=True, ctype='application/xml')
        if u.path.startswith('/live/'):      # a stream that answers at once
            return self.send(b'\x47' + b'\x00' * 512, ctype='video/mp2t')
        if q.get('password') != PASSWORD:
            return self.send(json.dumps({"user_info": {"auth": 0}}).encode())
        a = q.get('action')
        if not a:
            r = {"user_info": {"username": "u", "auth": 1, "status": "Active",
                               "exp_date": "1900000000", "active_cons": "0",
                               "max_connections": "1",
                               "allowed_output_formats": ["ts", "m3u8"]},
                 "server_info": {"timezone": "Europe/London"}}
        elif a == 'get_live_categories':
            r = CATS
        elif a == 'get_live_streams':
            r = LIVE
        elif a == 'get_vod_categories':
            r = [{"category_id": "10", "category_name": "Movies"}]
        elif a == 'get_vod_streams':
            r = [{"name": "Beach Movie (2021)", "stream_id": 555, "container_extension": "mp4",
                  "rating": "7.1", "category_id": "10"}]
        elif a == 'get_series_categories':
            r = [{"category_id": "20", "category_name": "Drama"}]
        elif a == 'get_series':
            r = [{"name": "Beach Show", "series_id": 77, "category_id": "20"}]
        elif a == 'get_simple_data_table':
            r = {"epg_listings": [
                {"title": b64("Archived %d" % h), "description": b64("d"),
                 "start": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(NOW + h * 3600)),
                 "start_timestamp": str(NOW + h * 3600),
                 "stop_timestamp": str(NOW + h * 3600 + 3600),
                 "has_archive": 1 if h < 0 else 0} for h in range(-50, 10)]}
        else:
            r = []
        self.send(json.dumps(r).encode())


def start():
    s = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


if __name__ == '__main__':
    srv = start()
    print('http://127.0.0.1:%d  (user u, password %s)' % (srv.server_address[1], PASSWORD))
    while True:
        time.sleep(60)
