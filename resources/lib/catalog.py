# -*- coding: utf-8 -*-
"""Local SQLite copy of categories, channels, movies and series."""
import json
import os
import re
import sqlite3
import time
import uuid

from . import common
from .xtream import XtreamError

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE categories(kind TEXT, id TEXT, name TEXT, pos INTEGER, adult INTEGER);
CREATE TABLE live(stream_id TEXT, num INTEGER, name TEXT, icon TEXT, epg_id TEXT,
                  category_id TEXT, archive INTEGER, archive_days INTEGER, pos INTEGER,
                  adult INTEGER);
CREATE TABLE vod(stream_id TEXT, name TEXT, icon TEXT, rating TEXT, ext TEXT,
                 added TEXT, year TEXT, category_id TEXT, pos INTEGER, adult INTEGER,
                 tmdb TEXT);
CREATE TABLE series(series_id TEXT, name TEXT, cover TEXT, plot TEXT, cast_ TEXT,
                    director TEXT, genre TEXT, release TEXT, rating TEXT,
                    backdrop TEXT, category_id TEXT, pos INTEGER, adult INTEGER,
                    tmdb TEXT, modified INTEGER);
CREATE INDEX i_cat ON categories(kind, pos);
CREATE INDEX i_live ON live(category_id, pos);
CREATE INDEX i_live_id ON live(stream_id);
CREATE INDEX i_vod ON vod(category_id, pos);
CREATE INDEX i_vod_id ON vod(stream_id);
CREATE INDEX i_series ON series(category_id, pos);
CREATE INDEX i_series_id ON series(series_id);
"""

TABLES = {'live': ('live', 'stream_id'), 'vod': ('vod', 'stream_id'),
          'series': ('series', 'series_id')}

_YEAR = re.compile(r'[\(\[](19\d\d|20\d\d)[\)\]]')

SCHEMA_VERSION = '4'

# Group names that mark adult content ("Adult Swim" is a cartoon channel, not adult).
ADULT_GROUP = re.compile(
    r'\bxxx|\bporn|\badults?\b(?!\s*swim)|\b18\s*\+|\+\s*18\b|\berotic|\bsexy?\b'
    r'|\bplayboy|\bhustler|\bbrazzers|\bhentai|\bonlyfans', re.I)
# Item names: only unambiguous markers, so films like "Sexy Beast" are not hidden.
ADULT_NAME = re.compile(r'\bxxx\b|\bporn|\b18\s*\+|\+\s*18\b|\bhentai', re.I)


def _s(v):
    return '' if v is None else str(v)


def _i(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _cats(item):
    ids = item.get('category_ids')
    if isinstance(ids, list) and ids:
        return [_s(i) for i in ids]
    return [_s(item.get('category_id'))]


def _adult(item, adult_cats):
    if _s(item.get('is_adult')) == '1':
        return 1
    if any(cid in adult_cats for cid in _cats(item)):
        return 1
    return 1 if ADULT_NAME.search(_s(item.get('name'))) else 0


def _tmdb(item):
    v = _s(item.get('tmdb') or item.get('tmdb_id')).strip()
    return v if v.isdigit() and v != '0' else ''


def _year(item):
    y = _s(item.get('year')).strip()
    if y[:4].isdigit():
        return y[:4]
    m = _YEAR.search(_s(item.get('name')))
    return m.group(1) if m else ''


def build_catalog(client, db_path, progress=None, abort=None):
    def step(pct, msg):
        if abort and abort():
            raise common.Aborted()
        if progress:
            progress(pct, msg)

    def optional(fn, label):
        # Some lines are live-only and error on VOD/series actions.
        try:
            return fn()
        except XtreamError as e:
            common.log('%s unavailable: %s' % (label, e))
            return []

    step(0, 'Logging in...')
    account = client.account()
    step(5, 'Loading channel groups...')
    live_cats = client.live_categories()
    step(10, 'Loading channels...')
    live = client.live_streams()
    step(35, 'Loading movie categories...')
    vod_cats = optional(client.vod_categories, 'VOD categories')
    step(40, 'Loading movies...')
    vod = optional(client.vod_streams, 'VOD')
    step(65, 'Loading series categories...')
    ser_cats = optional(client.series_categories, 'Series categories')
    step(70, 'Loading series...')
    ser = optional(client.series, 'Series')
    step(90, 'Saving...')

    tmp = '%s.%s.tmp' % (db_path, uuid.uuid4().hex[:8])
    con = sqlite3.connect(tmp)
    try:
        con.execute('PRAGMA journal_mode=OFF')
        con.execute('PRAGMA synchronous=OFF')
        con.executescript(SCHEMA)
        adult = {}
        for kind, cats in (('live', live_cats), ('vod', vod_cats), ('series', ser_cats)):
            rows = []
            adult[kind] = set()
            for pos, c in enumerate(cats):
                if not isinstance(c, dict):
                    continue
                cid, name = _s(c.get('category_id')), _s(c.get('category_name'))
                flag = 1 if (_s(c.get('is_adult')) == '1' or ADULT_GROUP.search(name)) else 0
                if flag:
                    adult[kind].add(cid)
                rows.append((kind, cid, name, pos, flag))
            con.executemany('INSERT INTO categories VALUES (?,?,?,?,?)', rows)

        rows = []
        for pos, s in enumerate(live):
            if not isinstance(s, dict):
                continue
            flag = _adult(s, adult['live'])
            for cid in _cats(s):
                rows.append((_s(s.get('stream_id')), _i(s.get('num')), _s(s.get('name')),
                             _s(s.get('stream_icon')), _s(s.get('epg_channel_id')).strip().lower(),
                             cid, 1 if _s(s.get('tv_archive')) == '1' else 0,
                             _i(s.get('tv_archive_duration')), pos, flag))
        con.executemany('INSERT INTO live VALUES (?,?,?,?,?,?,?,?,?,?)', rows)

        rows = []
        for pos, s in enumerate(vod):
            if not isinstance(s, dict):
                continue
            flag = _adult(s, adult['vod'])
            for cid in _cats(s):
                rows.append((_s(s.get('stream_id')), _s(s.get('name')), _s(s.get('stream_icon')),
                             _s(s.get('rating')), _s(s.get('container_extension')) or 'mp4',
                             _s(s.get('added')), _year(s), cid, pos, flag, _tmdb(s)))
        con.executemany('INSERT INTO vod VALUES (?,?,?,?,?,?,?,?,?,?,?)', rows)

        rows = []
        for pos, s in enumerate(ser):
            if not isinstance(s, dict):
                continue
            backdrop = s.get('backdrop_path')
            if isinstance(backdrop, list):
                backdrop = backdrop[0] if backdrop else ''
            flag = _adult(s, adult['series'])
            for cid in _cats(s):
                rows.append((_s(s.get('series_id')), _s(s.get('name')), _s(s.get('cover')),
                             _s(s.get('plot')), _s(s.get('cast')), _s(s.get('director')),
                             _s(s.get('genre')), _s(s.get('releaseDate') or s.get('release_date')),
                             _s(s.get('rating')), _s(backdrop), cid, pos, flag, _tmdb(s),
                             _i(s.get('last_modified'))))
        con.executemany('INSERT INTO series VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)

        con.executemany('INSERT INTO meta VALUES (?,?)', [
            ('account', json.dumps(account)),
            ('synced_at', str(int(time.time()))),
            ('schema', SCHEMA_VERSION),
        ])
        con.commit()
    finally:
        con.close()
    common.atomic_replace(tmp, db_path)
    return {'live': len(live), 'vod': len(vod), 'series': len(ser)}


def live_rows(cat, cat_id):
    """Channels for a group id: '*' = all, 'fav' = favourites, else category id."""
    if cat_id == 'fav':
        rows = []
        for sid in common.load_favs():
            r = cat.get('live', sid)
            if r is not None:
                rows.append(r)
        return rows
    from .customize import apply_channels
    return apply_channels(cat_id, cat.items('live', None if cat_id in (None, '', '*') else cat_id))


class Catalog(object):
    def __init__(self, path):
        self.path = path
        self._con = None
        self.hide_adult = common.adult_hidden()
        self.hidden = common.load_hidden()

    def exists(self):
        """True if the catalog is present and in the current format."""
        if not os.path.exists(self.path):
            return False
        try:
            rows = self._q("SELECT value FROM meta WHERE key='schema'")
        except sqlite3.Error:
            rows = []
        if rows and rows[0]['value'] == SCHEMA_VERSION:
            return True
        self.close()   # old format: caller rebuilds it
        return False

    def _adult_sql(self, alias=''):
        return (' AND %sadult=0' % alias) if self.hide_adult else ''

    def _q(self, sql, args=()):
        if self._con is None:
            # read-only use; TV mode reads from its timer/worker threads too
            self._con = sqlite3.connect(self.path, check_same_thread=False)
            self._con.row_factory = sqlite3.Row
        return self._con.execute(sql, args).fetchall()

    def close(self):
        if self._con is not None:
            self._con.close()
            self._con = None

    def _hidden_sql(self, kind):
        ids = sorted(self.hidden.get(kind, ()))
        if not ids:
            return '', []
        return ' AND category_id NOT IN (%s)' % ','.join('?' * len(ids)), ids

    def categories(self, kind, archive_only=False, include_hidden=False):
        table, key = TABLES[kind]
        extra = (' AND x.archive=1' if archive_only else '') + self._adult_sql('x.')
        having = ' HAVING cnt > 0' if archive_only else ''
        rows = self._q(
            'SELECT c.id AS id, c.name AS name, COUNT(x.%s) AS cnt '
            'FROM categories c LEFT JOIN %s x ON x.category_id=c.id%s '
            'WHERE c.kind=?%s GROUP BY c.id, c.name, c.pos%s ORDER BY c.pos'
            % (key, table, extra, self._adult_sql('c.'), having), (kind,))
        from .customize import apply_groups
        rows = apply_groups(kind, rows)
        if include_hidden:
            return rows
        hidden = self.hidden.get(kind, set())
        return [r for r in rows if r['id'] not in hidden]

    def items(self, kind, category_id=None, archive_only=False):
        table, key = TABLES[kind]
        where, args = [], []
        if category_id is not None:
            where.append('category_id=?')
            args.append(category_id)
        if archive_only:
            where.append('archive=1')
        if self.hide_adult:
            where.append('adult=0')
        if category_id is None:   # "All": leave out hidden groups
            sql, ids = self._hidden_sql(kind)
            if sql:
                where.append(sql[5:])
                args += ids
        clause = (' WHERE ' + ' AND '.join(where)) if where else ''
        if category_id is not None:
            return self._q('SELECT * FROM %s%s ORDER BY pos' % (table, clause), args)
        return self._q('SELECT *, MIN(pos) AS p FROM %s%s GROUP BY %s ORDER BY p'
                       % (table, clause, key), args)

    def get(self, kind, item_id):
        table, key = TABLES[kind]
        rows = self._q('SELECT * FROM %s WHERE %s=?%s LIMIT 1'
                       % (table, key, self._adult_sql()), (str(item_id),))
        return rows[0] if rows else None

    def search(self, kind, term, limit=300):
        table, key = TABLES[kind]
        hsql, ids = self._hidden_sql(kind)
        return self._q('SELECT *, MIN(pos) AS p FROM %s WHERE name LIKE ?%s%s GROUP BY %s '
                       'ORDER BY name LIMIT %d' % (table, self._adult_sql(), hsql, key, limit),
                       ['%' + term + '%'] + ids)

    def recent(self, kind, limit=100):
        """Newest movies (by date added) or series (by last update)."""
        table, key = TABLES[kind]
        order = 'CAST(added AS INTEGER)' if kind == 'vod' else 'modified'
        hsql, ids = self._hidden_sql(kind)
        return self._q('SELECT *, MAX(%s) AS d FROM %s WHERE 1=1%s%s GROUP BY %s '
                       'ORDER BY d DESC LIMIT %d' % (order, table, self._adult_sql(), hsql, key, limit),
                       ids)

    def find_live_num(self, num):
        """First visible channel with this channel number."""
        hsql, ids = self._hidden_sql('live')
        rows = self._q('SELECT *, MIN(pos) AS p FROM live WHERE num=?%s%s GROUP BY stream_id '
                       'ORDER BY p LIMIT 1' % (self._adult_sql(), hsql), [int(num)] + ids)
        return rows[0] if rows else None

    def category_names(self, kind):
        return {r['id']: r['name'] for r in
                self._q('SELECT id, name FROM categories WHERE kind=?', (kind,))}

    def meta(self, key):
        rows = self._q('SELECT value FROM meta WHERE key=?', (key,))
        if not rows:
            return None
        try:
            return json.loads(rows[0]['value'])
        except ValueError:
            return rows[0]['value']
