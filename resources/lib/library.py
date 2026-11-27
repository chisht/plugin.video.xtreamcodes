# -*- coding: utf-8 -*-
"""Kodi library export: .strm files for chosen movies and series.

Each .strm holds a plugin:// link back to this add-on, so playback still goes
through the provider. Kodi's scraper identifies the titles (a .nfo with the TMDb
link is written when the provider supplies the id), and from then on they are
normal library items: watched state, resume points, widgets and the Trakt
add-on all work. New episodes of exported series are added on every update.
"""
import os
import re
import shutil
import urllib.parse

import xbmc
import xbmcvfs

from . import common
from .trakt import clean_title
from .xtream import XtreamClient, XtreamError

STORE = 'library.json'
_BAD = re.compile(r'[\\/:*?"<>|]+')


def root():
    custom = common.setting('library_path').strip()
    path = xbmcvfs.translatePath(custom) if custom else common.profile_file('library')
    return path


def folders():
    return os.path.join(root(), 'Movies'), os.path.join(root(), 'TV Shows')


def _safe(name):
    name = _BAD.sub(' ', name or '').strip().strip('.')
    return re.sub(r'\s+', ' ', name)[:120] or 'Untitled'


def _plugin(**params):
    params['lib'] = '1'   # played from the library: the Trakt add-on scrobbles those
    return 'plugin://%s/?%s' % (common.ADDON_ID, urllib.parse.urlencode(
        {k: v for k, v in params.items() if v not in (None, '')}))


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return True


def _store():
    data = common.load_json(STORE, {}) or {}
    data.setdefault('movies', {})
    data.setdefault('series', {})
    return data


def is_exported(kind, item_id):
    return str(item_id) in _store()['movies' if kind == 'vod' else 'series']


def _title_year(name, year=''):
    title, y = clean_title(name)
    y = str(year or y or '')[:4]
    return title, (y if y.isdigit() else '')


# ----------------------------------------------------------------- movies
def add_movie(row):
    title, year = _title_year(row['name'], row['year'])
    base = _safe('%s (%s)' % (title, year) if year else title)
    folder = os.path.join(folders()[0], base)
    _write(os.path.join(folder, base + '.strm'), _plugin(
        action='play_vod', id=row['stream_id'], ext=row['ext'], title=row['name'],
        tmdb=row['tmdb'], year=year))
    if row['tmdb']:
        _write(os.path.join(folder, base + '.nfo'), 'https://www.themoviedb.org/movie/%s\n' % row['tmdb'])
    data = _store()
    data['movies'][str(row['stream_id'])] = {'name': row['name'], 'folder': folder}
    common.save_json(STORE, data)
    return folder


# ----------------------------------------------------------------- series
def _episodes(info):
    eps = info.get('episodes') or {}
    out = []
    if isinstance(eps, dict):
        for key, lst in eps.items():
            for e in lst or []:
                if isinstance(e, dict):
                    out.append((common._int(e.get('season') or key), e))
    elif isinstance(eps, list):
        for lst in eps:
            for e in (lst if isinstance(lst, list) else [lst]):
                if isinstance(e, dict):
                    out.append((common._int(e.get('season') or 1), e))
    return out


def _write_series(series_id, name, year, tmdb, client):
    """Write .strm files for all episodes. Returns how many were new."""
    info = client.series_info(series_id)
    show = info.get('info') or {}
    tmdb = tmdb or str(show.get('tmdb_id') or show.get('tmdb') or '').strip()
    tmdb = tmdb if tmdb.isdigit() and tmdb != '0' else ''
    title, year = _title_year(name or show.get('name'), year or (show.get('releaseDate') or '')[:4])
    base = _safe('%s (%s)' % (title, year) if year else title)
    folder = os.path.join(folders()[1], base)
    if tmdb:
        _write(os.path.join(folder, 'tvshow.nfo'), 'https://www.themoviedb.org/tv/%s\n' % tmdb)
    new = 0
    for season, e in _episodes(info):
        num = common._int(e.get('episode_num'))
        if season <= 0 or num <= 0:
            continue
        fname = '%s S%02dE%02d.strm' % (_safe(title), season, num)
        path = os.path.join(folder, 'Season %02d' % season, fname)
        if os.path.exists(path):
            continue
        _write(path, _plugin(action='play_episode', id=e.get('id'),
                             ext=e.get('container_extension') or 'mp4',
                             title=e.get('title') or '', show=title, tmdb=tmdb, year=year,
                             season=season, ep=num))
        new += 1
    return new, folder, tmdb


def add_series(row):
    client = XtreamClient.from_settings()
    year = (row['release'] or '')[:4]
    new, folder, tmdb = _write_series(row['series_id'], row['name'], year, row['tmdb'], client)
    data = _store()
    data['series'][str(row['series_id'])] = {'name': row['name'], 'year': year,
                                             'tmdb': tmdb, 'folder': folder}
    common.save_json(STORE, data)
    return new


def remove(kind, item_id):
    data = _store()
    bucket = data['movies' if kind == 'vod' else 'series']
    entry = bucket.pop(str(item_id), None)
    if entry and entry.get('folder', '').startswith(root()):
        shutil.rmtree(entry['folder'], ignore_errors=True)
    common.save_json(STORE, data)
    return entry is not None


def update_all():
    """Add new episodes of exported series. Returns how many files were added."""
    data = _store()
    if not data['series']:
        return 0
    client = XtreamClient.from_settings()
    added = 0
    for sid, s in list(data['series'].items()):
        try:
            new, folder, tmdb = _write_series(sid, s.get('name'), s.get('year'), s.get('tmdb'), client)
            added += new
        except XtreamError as e:
            common.log('Library update for %s failed: %s' % (s.get('name'), e), xbmc.LOGWARNING)
    return added


def scan():
    xbmc.executebuiltin('UpdateLibrary(video)')
