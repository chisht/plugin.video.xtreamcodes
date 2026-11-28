# -*- coding: utf-8 -*-
"""TMDb: ratings, vote counts, trending / popular lists and Discover.

Every list is matched against the provider's own catalog, so only titles you can
actually play are shown. Matching uses the TMDb id the provider stores for a title;
titles without one are matched by cleaned title and year.

This product uses the TMDB API but is not endorsed or certified by TMDB.
"""
import hashlib
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import common
from .trakt import clean_title, title_key

API = 'https://api.themoviedb.org/3'
IMG = 'https://image.tmdb.org/t/p/'
PAGES = 5                      # TMDb pages (20 titles each) read per screen
TTL_LIST, TTL_DETAIL, TTL_GENRE = 6 * 3600, 24 * 3600, 30 * 86400
KEYDB = 'discover_keys.db'

SOURCES = {   # kind -> {source: (path, extra params, label)}
    'movie': {
        'trending': ('trending/movie/week', {}, 'Trending this week'),
        'popular': ('movie/popular', {}, 'Popular'),
        'top': ('movie/top_rated', {}, 'Top rated'),
        'new': ('movie/now_playing', {}, 'New in cinemas'),
    },
    'tv': {
        'trending': ('trending/tv/week', {}, 'Trending this week'),
        'popular': ('tv/popular', {}, 'Popular'),
        'top': ('tv/top_rated', {}, 'Top rated'),
        'new': ('tv/on_the_air', {}, 'On the air now'),
    },
}


class TmdbError(Exception):
    pass


def configured():
    return bool(common.setting('tmdb_key').strip())


# ------------------------------------------------------------------- http
def _cache_path(base, path, params):
    folder = common.profile_file('tmdb_cache')
    os.makedirs(folder, exist_ok=True)
    clean = sorted((k, v) for k, v in params.items() if k != 'api_key')
    name = hashlib.sha1(json.dumps([base, path, clean]).encode()).hexdigest()
    return os.path.join(folder, name + '.json')


def _get(path, params=None, ttl=TTL_LIST):
    key = common.setting('tmdb_key').strip()
    if not key:
        raise TmdbError('Add your TMDb API key in Settings > Discover first.')
    params = {k: str(v) for k, v in (params or {}).items()}
    params.setdefault('language', common.setting('tmdb_lang').strip() or 'en-US')
    base = (common.setting('tmdb_base').strip() or API).rstrip('/')
    cache = _cache_path(base, path, params)
    try:
        if time.time() - os.path.getmtime(cache) < ttl:
            with open(cache, encoding='utf-8') as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    headers = {'Accept': 'application/json', 'User-Agent': common.user_agent()}
    if key.startswith('eyJ'):                # the long "read access token"
        headers['Authorization'] = 'Bearer ' + key
    else:
        params['api_key'] = key
    url = '%s/%s?%s' % (base, path, urllib.parse.urlencode(sorted(params.items())))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
            data = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise TmdbError('TMDb did not accept the API key. Check it in Settings > Discover.')
        if e.code == 404:
            raise TmdbError('Not found on TMDb.')
        raise TmdbError('TMDb error %d' % e.code)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise TmdbError('Could not reach TMDb: %s' % e)
    try:
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except OSError:
        pass
    return data


# ------------------------------------------------------------------ titles
def _norm(kind, d):
    date = d.get('release_date') or d.get('first_air_date') or ''
    poster, back = d.get('poster_path'), d.get('backdrop_path')
    return {
        'id': str(d.get('id')), 'kind': kind,
        'title': d.get('title') or d.get('name') or '',
        'orig': d.get('original_title') or d.get('original_name') or '',
        'year': date[:4],
        'rating': round(float(d.get('vote_average') or 0), 1),
        'votes': int(d.get('vote_count') or 0),
        'popularity': float(d.get('popularity') or 0),
        'plot': d.get('overview') or '',
        'poster': IMG + 'w500' + poster if poster else '',
        'backdrop': IMG + 'w1280' + back if back else '',
    }


def fetch(kind, path, params=None, page=0):
    """Titles from TMDb pages page*PAGES+1 .. (page+1)*PAGES.

    Returns (titles, more) - `more` is True if TMDb has further pages.
    """
    first = page * PAGES + 1
    numbers = list(range(first, first + PAGES))

    def one(n):
        try:
            p = dict(params or {})
            p['page'] = n
            return _get(path, p)
        except TmdbError as e:
            return e
    with ThreadPoolExecutor(max_workers=PAGES) as pool:
        results = list(pool.map(one, numbers))
    good = [r for r in results if isinstance(r, dict)]
    if not good:
        raise next(r for r in results if isinstance(r, TmdbError))
    seen, titles = set(), []
    for r in good:
        for d in r.get('results') or []:
            t = _norm(kind, d)
            if t['id'] not in seen and t['title']:
                seen.add(t['id'])
                titles.append(t)
    total = max(int(r.get('total_pages') or 1) for r in good)
    return titles, total > numbers[-1] and total > first


def source(kind, name, **opts):
    """(path, params, label) for a Discover list."""
    kind = 'tv' if kind in ('tv', 'series') else 'movie'
    if name in SOURCES[kind]:
        return SOURCES[kind][name]
    if name == 'genre':
        return ('discover/' + kind, {'with_genres': opts['genre'], 'sort_by': 'popularity.desc',
                                     'vote_count.gte': 30}, 'Genre')
    if name == 'decade':
        a, b = int(opts['decade']), int(opts['decade']) + 9
        field = 'primary_release_date' if kind == 'movie' else 'first_air_date'
        return ('discover/' + kind, {field + '.gte': '%d-01-01' % a, field + '.lte': '%d-12-31' % b,
                                     'sort_by': 'popularity.desc', 'vote_count.gte': 30},
                '%ds' % a)
    if name == 'similar':
        return ('%s/%s/recommendations' % (kind, opts['id']), {}, 'More like this')
    raise TmdbError('Unknown list')


def genres(kind):
    kind = 'tv' if kind in ('tv', 'series') else 'movie'
    data = _get('genre/%s/list' % kind, ttl=TTL_GENRE)
    return [(str(g['id']), g['name']) for g in data.get('genres') or []]


def details(kind, tid):
    kind = 'tv' if kind in ('tv', 'series') else 'movie'
    return _get('%s/%s' % (kind, tid), {'append_to_response': 'credits'}, ttl=TTL_DETAIL)


def find_id(kind, name, year=None):
    """TMDb id for a provider title that carries none."""
    kind = 'tv' if kind in ('tv', 'series') else 'movie'
    title, y = clean_title(name)
    year = year or y
    params = {'query': title}
    if year:
        params['year' if kind == 'movie' else 'first_air_date_year'] = year
    results = _get('search/' + kind, params, ttl=TTL_DETAIL).get('results') or []
    if not results and year:
        params.pop('year', None)
        params.pop('first_air_date_year', None)
        results = _get('search/' + kind, params, ttl=TTL_DETAIL).get('results') or []
    return str(results[0]['id']) if results else ''


# ----------------------------------------------------------------- display
def fmt_votes(n):
    n = int(n or 0)
    if n >= 1000000:
        return '%.1fM' % (n / 1000000.0)
    if n >= 1000:
        return '%.1fk' % (n / 1000.0) if n < 10000 else '%dk' % (n // 1000)
    return str(n)


def star(t):
    """'7.8' in gold, or '' if nobody rated it yet. The rating goes in front of
    the title, so a line with no rating stays as it was."""
    if not t or not t.get('rating'):
        return ''
    return '[COLOR FFFFC107]%.1f/10[/COLOR]' % t['rating']


def summary_lines(kind, tid):
    """Text lines about a title for the information screens."""
    d = details(kind, tid)
    lines = []
    rating = float(d.get('vote_average') or 0)
    if rating:
        lines.append('[B]TMDb rating:[/B] %.1f / 10  (%s votes)' % (rating, fmt_votes(d.get('vote_count'))))
    pop = d.get('popularity')
    if pop:
        lines.append('[B]Popularity:[/B] %.0f' % pop)
    if d.get('tagline'):
        lines.append('[I]%s[/I]' % d['tagline'])
    names = [g['name'] for g in d.get('genres') or []]
    if names:
        lines.append('[B]Genres:[/B] ' + ', '.join(names))
    runtime = d.get('runtime') or (d.get('episode_run_time') or [None])[0]
    if runtime:
        lines.append('[B]Runtime:[/B] %d min' % runtime)
    if d.get('number_of_seasons'):
        lines.append('[B]Seasons:[/B] %s   [B]Episodes:[/B] %s' % (d['number_of_seasons'],
                                                                 d.get('number_of_episodes', '?')))
    if d.get('status'):
        lines.append('[B]Status:[/B] ' + d['status'])
    cast = [c['name'] for c in (d.get('credits') or {}).get('cast', [])[:8]]
    if cast:
        lines.append('[B]Cast:[/B] ' + ', '.join(cast))
    if d.get('overview'):
        lines += ['', d['overview']]
    return d.get('title') or d.get('name') or '', lines


# ---------------------------------------------------------------- matching
def _kind_table(kind):
    return ('vod', 'stream_id', 'year') if kind == 'movie' else ('series', 'series_id', 'substr(release,1,4)')


def _keydb(cat, kind):
    """Cleaned titles of the provider's catalog, for matching titles without an id.

    Built once per catalog download (it takes a moment on large catalogs)."""
    path = common.profile_file(KEYDB)
    try:
        st = os.stat(common.catalog_path())
        stamp = '%d:%d:%s' % (st.st_mtime, st.st_size, kind)
    except OSError:
        stamp = ''
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)')
    row = con.execute('SELECT v FROM meta WHERE k=?', ('stamp_' + kind,)).fetchone()
    if row is None or row[0] != stamp:
        table, idcol, ycol = _kind_table(kind)
        con.execute('CREATE TABLE IF NOT EXISTS k(kind TEXT, key TEXT, year TEXT, id TEXT)')
        con.execute('DELETE FROM k WHERE kind=?', (kind,))
        data = []
        for r in cat._q('SELECT %s AS id, name, %s AS y FROM %s' % (idcol, ycol, table)):
            key, year = title_key(r['name'])
            if key:
                data.append((kind, key, (r['y'] or year or '')[:4], r['id']))
        con.executemany('INSERT INTO k VALUES (?,?,?,?)', data)
        con.execute('CREATE INDEX IF NOT EXISTS i_k ON k(kind, key)')
        con.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('stamp_' + kind, stamp))
        con.commit()
    return con


def _years_close(a, b):
    try:
        return abs(int(a) - int(b)) <= 1
    except (TypeError, ValueError):
        return True      # one side has no usable year: the title decides


def _visible(cat, kind, row):
    ck = 'vod' if kind == 'movie' else 'series'
    if row is None:
        return False
    if cat.hide_adult and row['adult']:
        return False
    return row['category_id'] not in cat.hidden.get(ck, ())


def match(cat, kind, titles):
    """[(title, catalog row)] for the titles the provider has, in TMDb order."""
    kind = 'tv' if kind in ('tv', 'series') else 'movie'
    table, idcol, _ = _kind_table(kind)
    found = {}
    ids = [t['id'] for t in titles]
    hsql, hids = cat._hidden_sql('vod' if kind == 'movie' else 'series')
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        sql = 'SELECT * FROM %s WHERE tmdb IN (%s)%s%s ORDER BY pos' % (
            table, ','.join('?' * len(chunk)), cat._adult_sql(), hsql)
        for row in cat._q(sql, chunk + hids):
            found.setdefault(row['tmdb'], row)
    missing = [t for t in titles if t['id'] not in found]
    if missing:
        con = _keydb(cat, kind)
        try:
            for t in missing:
                keys = {title_key(t['title'])[0], title_key(t['orig'])[0]} - {''}
                for key in keys:
                    for kid, year in con.execute('SELECT id, year FROM k WHERE kind=? AND key=?',
                                                 (kind, key)).fetchall():
                        if not _years_close(t['year'], year):
                            continue
                        rows = cat._q('SELECT * FROM %s WHERE %s=? LIMIT 1' % (table, idcol), (kid,))
                        if rows and _visible(cat, kind, rows[0]):
                            found[t['id']] = rows[0]
                            break
                    if t['id'] in found:
                        break
        finally:
            con.close()
    return [(t, found[t['id']]) for t in titles if t['id'] in found]
