import json, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HITS = []
KEY = 'abc123'
def movie(i, title=None, orig=None, year=None, rating=None, votes=None):
    return {"id": i, "title": title or "Movie %d" % i, "original_title": orig or title or "Movie %d" % i,
            "release_date": "%s-05-01" % (year or 2000 + i % 24), "vote_average": rating if rating is not None else 5 + (i % 50) / 10.0,
            "vote_count": votes if votes is not None else 100 * i, "popularity": 50.0, "overview": "Plot %d" % i,
            "poster_path": "/p%d.jpg" % i, "backdrop_path": "/b%d.jpg" % i}
def show(i, name, year):
    return {"id": i, "name": name, "original_name": name, "first_air_date": "%d-01-01" % year, "vote_average": 8.2,
            "vote_count": 4321, "popularity": 90.0, "overview": "Show plot", "poster_path": "/s%d.jpg" % i, "backdrop_path": None}
SPECIAL = [movie(1000, "Alpha Movie", year=2010, rating=7.8, votes=12345), movie(1001, "Bravo Movie", year=2011, rating=6.4, votes=950),
           movie(1002, "Charlie Movie", year=2012, rating=8.1, votes=250000), movie(1003, "The Film", "Le Film", year=2013, rating=7.0, votes=1500000)]
MOVIES = SPECIAL + [movie(2000 + i) for i in range(116)]      # 120 titles, 6 pages of 20
SHOWS = [show(3000, "Beach Show", 2020), show(3001, "Other Show", 2019)]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = dict(urllib.parse.parse_qsl(u.query)); HITS.append(u.path + '?' + u.query)
        if q.get('api_key') != KEY and 'Bearer ' + KEY not in (self.headers.get('Authorization') or ''):
            self.send_response(401); self.end_headers(); self.wfile.write(b'{}'); return
        p = u.path.replace('/3/', '', 1); page = int(q.get('page', 1)); r = None
        if p in ('movie/popular', 'trending/movie/week', 'movie/top_rated', 'movie/now_playing') or p == 'discover/movie' or p.endswith('/recommendations') and p.startswith('movie/'):
            items = MOVIES if not p.endswith('/recommendations') else MOVIES[3:9]
            if p == 'discover/movie' and q.get('with_genres') == '99': items = MOVIES[2000-2000:0]
            r = {"page": page, "results": items[(page - 1) * 20: page * 20], "total_pages": (len(items) + 19) // 20}
        elif p in ('tv/popular', 'trending/tv/week', 'tv/top_rated', 'tv/on_the_air', 'discover/tv'):
            r = {"page": page, "results": SHOWS if page == 1 else [], "total_pages": 1}
        elif p == 'genre/movie/list': r = {"genres": [{"id": 28, "name": "Action"}, {"id": 99, "name": "Documentary"}]}
        elif p == 'search/movie':
            hit = [m for m in MOVIES if m['title'].lower() == q.get('query', '').lower()]
            r = {"results": hit}
        elif p.startswith('movie/') and p.count('/') == 1:
            m = [x for x in MOVIES if str(x['id']) == p.split('/')[1]][0]
            r = dict(m, tagline="A tagline", runtime=118, genres=[{"name": "Action"}, {"name": "Drama"}], status="Released",
                     credits={"cast": [{"name": "Actor %d" % i} for i in range(10)]})
        if r is None: self.send_response(404); self.end_headers(); self.wfile.write(b'{}'); return
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps(r).encode())
def start():
    s = ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=s.serve_forever, daemon=True).start(); return s
