# -*- coding: utf-8 -*-
"""Xtream Codes IPTV - video add-on entry point / router."""
import time as _time
_T0 = _time.time()   # when Kodi started this add-on call

import datetime
import json
import math
import os
import sys
import time
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import common, sync
from resources.lib import library, playback, theme, tmdb, trakt, watching
from resources.lib.playback import play_item
from resources.lib.catalog import Catalog, build_catalog, live_rows
from resources.lib.epg import EPG
from resources.lib.xtream import XtreamClient, XtreamError, b64_text

BASE = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip('-').isdigit() else -1
ARGS = dict(urllib.parse.parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 else {}


# ------------------------------------------------------------------ helpers
def build_url(**kwargs):
    return BASE + '?' + urllib.parse.urlencode({k: v for k, v in kwargs.items() if v is not None})


def add_item(label, query, art=None, info=None, context=None, folder=True, playable=False):
    li = xbmcgui.ListItem(label, offscreen=True)
    art = dict(art or {})
    art.setdefault('fanart', common.FANART)
    li.setArt(art)
    if info:
        common.set_video_info(li, info)
    if playable:
        li.setProperty('IsPlayable', 'true')
    if context:
        li.addContextMenuItems(context)
    xbmcplugin.addDirectoryItem(HANDLE, build_url(**query), li, folder)


def end(content='videos', sorts=None, cache=False):
    xbmcplugin.setContent(HANDLE, content)
    for s in sorts or [xbmcplugin.SORT_METHOD_UNSORTED]:
        xbmcplugin.addSortMethod(HANDLE, s)
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=cache)


def fail():
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def error(msg):
    xbmcgui.Dialog().ok(common.ADDON_NAME, msg)


_SHOW_COUNTS = []


def with_count(name, count):
    if not _SHOW_COUNTS:   # read the setting once, not once per list item
        _SHOW_COUNTS.append(common.setting_bool('show_counts'))
    if _SHOW_COUNTS[0]:
        return '%s  [COLOR grey](%d)[/COLOR]' % (name, count)
    return name


def paginate(rows, page):
    size = common.setting_int('page_size', 500)
    if size <= 0:
        return rows, False
    return rows[page * size:(page + 1) * size], len(rows) > (page + 1) * size


def next_page(action, page, **extra):
    add_item('[B]Next page >>[/B]', dict(action=action, page=page + 1, **extra),
             art={'icon': 'DefaultFolder.png'})


def client():
    return XtreamClient.from_settings()


_WATCHED = []


def watched():
    """Trakt watched lookup, loaded once per plugin call."""
    if not _WATCHED:
        _WATCHED.append(trakt.Watched())
    return _WATCHED[0]


def art_for(url, kind='thumb'):
    return {'thumb': url, 'icon': url, 'poster': url} if url else {'icon': 'DefaultVideo.png'}


def get_catalog():
    """Open the local catalog; build it in the foreground on first run."""
    if not common.is_configured():
        error('Please enter your server, username and password first.')
        common.addon().openSettings()
        return None
    cat = Catalog(common.catalog_path())
    if cat.exists():
        return cat
    dlg = xbmcgui.DialogProgress()
    dlg.create(common.ADDON_NAME, 'Loading channel list...')
    try:
        build_catalog(client(), common.catalog_path(),
                      progress=lambda p, m: dlg.update(max(0, min(p, 100)), m),
                      abort=dlg.iscanceled)
    except common.Aborted:
        return None
    except XtreamError as e:
        error(str(e))
        return None
    finally:
        dlg.close()
    if common.setting_bool('epg_enable'):
        sync.request_background('epg')   # guide follows in the background
    return Catalog(common.catalog_path())


# ---------------------------------------------------------------- playback
def resolve(url, kind='file', info=None):
    xbmcplugin.setResolvedUrl(HANDLE, True, play_item(url, kind, info)[1])


def play_live():
    sid = ARGS['id']
    catalog = Catalog(common.catalog_path())
    row = catalog.get('live', sid) if catalog.exists() else None
    catalog.close()
    if row is None:   # catalog missing/outdated: play by id anyway
        row = {'stream_id': sid, 'name': ARGS.get('title', ''), 'icon': ''}
    # Opened from a group: Up/Down stay in it. From search and other lists that
    # have no group: the channel's own group.
    cat_id = ARGS.get('cat') or playback.own_group(row)
    # Started by the add-on (not resolved through Kodi) so an offline channel
    # gives a short notice instead of Kodi's "playback failed" dialog.
    playback.start_live(row, cat_id)


def zap():
    """Remote keys in fullscreen video (keymap -> RunPlugin); see zapper.handle."""
    from resources.lib import zapper
    zapper.handle(ARGS.get('key', 'up'), ARGS.get('d', '0'), ARGS.get('fb'))


def play_catchup():
    dur = int(ARGS.get('dur', '60')) + common.setting_int('catchup_pad', 5)
    catalog = Catalog(common.catalog_path())
    row = catalog.get('live', ARGS['id']) if catalog.exists() else None
    catalog.close()
    playback.start_catchup(ARGS['id'], ARGS['start'], dur, ARGS.get('title', ''), row=row)


def play_vod():
    title, year = trakt.clean_title(ARGS.get('title', ''))
    trakt.set_now_playing({'type': 'movie', 'id': ARGS['id'], 'tmdb': ARGS.get('tmdb', ''),
                           'title': title, 'year': ARGS.get('year') or year,
                           'name': ARGS.get('title', ''), 'ext': ARGS.get('ext', 'mp4'),
                           'icon': ARGS.get('icon', ''), 'lib': ARGS.get('lib', '')})
    url = client().vod_url(ARGS['id'], ARGS.get('ext', 'mp4'))
    resolve(url, 'file', {'title': ARGS.get('title', ''), 'mediatype': 'movie'})


def play_episode():
    show, year = trakt.clean_title(ARGS.get('show', ''))
    trakt.set_now_playing({'type': 'episode', 'id': ARGS['id'], 'tmdb': ARGS.get('tmdb', ''),
                           'title': show, 'year': ARGS.get('year') or year,
                           'season': ARGS.get('season'), 'episode': ARGS.get('ep'),
                           'name': ARGS.get('title', ''), 'show': ARGS.get('show', ''),
                           'ext': ARGS.get('ext', 'mp4'), 'icon': ARGS.get('icon', ''),
                           'sid': ARGS.get('sid', ''), 'lib': ARGS.get('lib', '')})
    url = client().episode_url(ARGS['id'], ARGS.get('ext', 'mp4'))
    resolve(url, 'file', {'title': ARGS.get('title', ''), 'mediatype': 'episode'})


# -------------------------------------------------------------------- root
def root():
    if not common.is_configured():
        add_item('[B]Set up your account...[/B]', {'action': 'settings'},
                 art={'icon': 'DefaultAddonService.png'}, folder=False)
        return end('files')
    entries = [
        ('TV mode (channels + mini player + guide)', 'tv', 'DefaultAddonPVRClient.png', False),
        ('TV guide (grid)', 'grid', 'DefaultPVRGuide.png', False),
        ('Live TV', 'live_cats', 'DefaultAddonPVRClient.png', True),
        ('Catch-up (TV archive)', 'catchup_cats', 'DefaultYear.png', True),
        ('Movies', 'vod_cats', 'DefaultMovies.png', True),
        ('Series', 'series_cats', 'DefaultTVShows.png', True),
        ('Discover (ratings, trending, popular)', 'discover_menu&kind=all', 'DefaultAddonsSearch.png', True),
        ('Search', 'search_menu&kind=all', 'DefaultAddonsSearch.png', True),
        ('Search the TV guide', 'search_menu&kind=epg', 'DefaultPVRSearch.png', True),
        ('Sleep timer', 'sleep_timer', 'DefaultYear.png', False),
        ('Account and status', 'account', 'DefaultUser.png', False),
        ('Update channels and EPG now', 'refresh', 'DefaultAddonsUpdates.png', False),
        ('Settings', 'settings', 'DefaultAddonProgram.png', False),
    ]
    if trakt.linked():
        entries.insert(4, ('In-progress shows (Trakt)', 'trakt_shows&which=progress',
                           'DefaultInProgressShows.png', True))
    if watching.load():
        entries.insert(4, ('Continue watching', 'continue', 'DefaultInProgressShows.png', True))
    if common.setting_bool('hide_adult') and common.pin_set():
        until = common.adult_unlocked_until()
        entries.insert(len(entries) - 3, (
            'Hide adult content again (shown until %s)' % common.fmt_time(until) if until
            else 'Show adult content (PIN)', 'adult_lock' if until else 'adult_unlock',
            'DefaultAddonService.png', False))
    for label, action, icon, folder in entries:
        query = dict(urllib.parse.parse_qsl('action=' + action))
        add_item(label, query, art={'icon': icon, 'thumb': icon}, folder=folder)
    end('files')


# ----------------------------------------------------------------- live TV
_FAVS = []


def _favs():
    if not _FAVS:   # read once per list, not once per channel
        _FAVS.append(set(common.load_favs()))
    return _FAVS[0]


def channel_item(row, progs, prefix='', cat_id=None):
    sid = row['stream_id']
    name = row['name']
    label = prefix + name
    if cat_id != 'fav' and sid in _favs():
        label = common.star() + label
    if playback.is_offline(sid):
        label = common.dim('%s  (offline)' % label)
    lines = []
    now = time.time()
    if progs:
        cur = progs[0]
        if cur['start'] <= now < cur['stop']:
            label += '  [COLOR grey]%s[/COLOR]' % cur['title']
        for i, p in enumerate(progs):
            lines.append('[B]%s-%s[/B]  %s' % (common.fmt_time(p['start']),
                                               common.fmt_time(p['stop']), p['title']))
            if i == 0 and p.get('descr'):
                lines.append(p['descr'])
                lines.append('')
    if row['archive']:
        lines.append('[COLOR orange]Catch-up: %d days[/COLOR]' % (row['archive_days'] or 0))
    ctx = [('TV guide', 'Container.Update(%s)' % build_url(action='guide', id=sid))]
    if row['archive']:
        ctx.append(('Watch from the beginning', 'RunPlugin(%s)' % build_url(action='restart', id=sid, cat=cat_id)))
        ctx.append(('Catch-up', 'Container.Update(%s)' % build_url(action='catchup_days', id=sid)))
    ctx.append(('TV guide (grid)', 'RunPlugin(%s)' % build_url(action='grid', id=sid, cat=cat_id)))
    fav = 'Remove from favourites' if sid in _favs() else 'Add to favourites'
    ctx.append((fav, 'RunPlugin(%s)' % build_url(action='fav_toggle', id=sid)))
    if cat_id:
        ctx.append(('Move channel...', 'RunPlugin(%s)' % build_url(action='move_channel', id=sid, cat=cat_id)))
    ctx.append(('Update channels and EPG now', 'RunPlugin(%s)' % build_url(action='refresh')))
    add_item(label, {'action': 'play_live', 'id': sid, 'title': name, 'cat': cat_id},
             art=art_for(row['icon']),
             info={'title': name, 'plot': '\n'.join(lines), 'mediatype': 'video'},
             context=ctx, folder=False, playable=False)


def now_next_for(rows):
    if not common.setting_bool('show_epg_in_list'):
        return {}
    guide = EPG(common.epg_path())
    try:
        return guide.now_next([r['epg_id'] for r in rows])
    finally:
        guide.close()


def group_menu(kind, cat_id):
    return [('Rename group', 'RunPlugin(%s)' % build_url(action='rename_group', kind=kind, id=cat_id)),
            ('Move group...', 'RunPlugin(%s)' % build_url(action='move_group', kind=kind, id=cat_id)),
            ('Hide this group', 'RunPlugin(%s)' % build_url(action='hide_group', kind=kind, id=cat_id)),
            ('Show/hide groups...', 'RunPlugin(%s)' % build_url(action='manage_groups', kind=kind))]


def manage_item(kind):
    add_item('[COLOR grey]Show/hide groups...[/COLOR]', {'action': 'manage_groups', 'kind': kind},
             art={'icon': 'DefaultAddonService.png'}, folder=False)


def live_cats():
    cat = get_catalog()
    if not cat:
        return fail()
    add_item('[B]All channels[/B]', {'action': 'live_list', 'cat': '*'},
             art={'icon': 'DefaultAddonPVRClient.png'})
    add_item(with_count('[B]Favourites[/B]', len(live_rows(cat, 'fav'))),
             {'action': 'live_list', 'cat': 'fav'}, art={'icon': 'DefaultFavourites.png'})
    for c in cat.categories('live'):
        add_item(with_count(c['name'], c['cnt']), {'action': 'live_list', 'cat': c['id']},
                 art={'icon': 'DefaultFolder.png'}, context=group_menu('live', c['id']))
    manage_item('live')
    cat.close()
    end('files')


def live_list():
    cat = get_catalog()
    if not cat:
        return fail()
    cat_id = ARGS.get('cat', '*')
    page = int(ARGS.get('page', '0'))
    rows = live_rows(cat, cat_id)
    cat.close()
    rows, more = paginate(rows, page)
    nn = now_next_for(rows)
    for r in rows:
        channel_item(r, nn.get(r['epg_id']), cat_id=cat_id)
    if more:
        next_page('live_list', page, cat=cat_id)
    end('videos', [xbmcplugin.SORT_METHOD_UNSORTED, xbmcplugin.SORT_METHOD_LABEL])


def _api_listings(sid):
    out = []
    try:
        entries = client().epg_table(sid)
    except XtreamError as e:
        common.log('EPG table failed: %s' % e)
        return out
    for e in entries:
        try:
            start = int(e.get('start_timestamp'))
            stop = int(e.get('stop_timestamp'))
        except (TypeError, ValueError):
            continue
        out.append({'start': start, 'stop': stop, 'title': b64_text(e.get('title')),
                    'descr': b64_text(e.get('description')), 'start_str': e.get('start') or '',
                    'has_archive': str(e.get('has_archive', '0')) == '1'})
    out.sort(key=lambda p: p['start'])
    return out


def _start_str(p):
    # Server-local start time is required for timeshift URLs.
    if p.get('start_str'):
        return p['start_str']
    return time.strftime('%Y-%m-%d:%H-%M', time.localtime(p['start']))


def programme_item(row, p, show_day=True):
    now = time.time()
    when = common.fmt_day_time(p['start']) if show_day else common.fmt_time(p['start'])
    title = p['title'] or 'No title'
    info = {'title': title, 'plot': '%s - %s\n\n%s' % (
        common.fmt_day_time(p['start']), common.fmt_time(p['stop']), p.get('descr') or ''),
        'duration': p['stop'] - p['start'], 'mediatype': 'video'}
    sid = row['stream_id']
    archive_from = now - (row['archive_days'] or 0) * 86400
    if p['start'] <= now < p['stop']:
        add_item('[B]%s  NOW  %s[/B]' % (when, title),
                 {'action': 'play_live', 'id': sid, 'title': row['name']},
                 art=art_for(row['icon']), info=info, folder=False, playable=False)
    elif p['stop'] <= now and row['archive'] and (p.get('has_archive') or p['start'] >= archive_from):
        add_item('%s  %s' % (when, title),
                 {'action': 'play_catchup', 'id': sid, 'start': _start_str(p),
                  'dur': int(math.ceil((p['stop'] - p['start']) / 60.0)), 'title': title},
                 art=art_for(row['icon']), info=info, folder=False, playable=False)
    else:
        add_item('[COLOR grey]%s  %s[/COLOR]' % (when, title), {'action': 'noop'},
                 art=art_for(row['icon']), info=info, folder=False)


def guide():
    cat = get_catalog()
    if not cat:
        return fail()
    row = cat.get('live', ARGS['id'])
    cat.close()
    if not row:
        return fail()
    now = int(time.time())
    if row['archive']:
        progs = _api_listings(row['stream_id'])
        progs = [p for p in progs if p['stop'] > now - 6 * 3600 and p['start'] < now + 36 * 3600]
    else:
        g = EPG(common.epg_path())
        progs = g.listings(row['epg_id'], now - 3 * 3600, now + 48 * 3600)
        g.close()
        if not progs:
            progs = [p for p in _api_listings(row['stream_id'])
                     if p['stop'] > now - 3 * 3600 and p['start'] < now + 48 * 3600]
    if not progs:
        add_item('[COLOR grey]No guide data for this channel[/COLOR]', {'action': 'noop'},
                 folder=False)
    for p in progs:
        programme_item(row, p)
    end('videos')


# ---------------------------------------------------------------- catch-up
def catchup_cats():
    cat = get_catalog()
    if not cat:
        return fail()
    cats = cat.categories('live', archive_only=True)
    if not cats and not cat.items('live', archive_only=True):
        add_item('[COLOR grey]Your server has no channels with catch-up[/COLOR]',
                 {'action': 'noop'}, folder=False)
    else:
        add_item('[B]All catch-up channels[/B]', {'action': 'catchup_list', 'cat': '*'},
                 art={'icon': 'DefaultYear.png'})
        for c in cats:
            add_item(with_count(c['name'], c['cnt']), {'action': 'catchup_list', 'cat': c['id']},
                     art={'icon': 'DefaultFolder.png'}, context=group_menu('live', c['id']))
    cat.close()
    end('files')


def catchup_list():
    cat = get_catalog()
    if not cat:
        return fail()
    cat_id = ARGS.get('cat', '*')
    rows = cat.items('live', None if cat_id == '*' else cat_id, archive_only=True)
    cat.close()
    for r in rows:
        add_item('%s  [COLOR grey](%d days)[/COLOR]' % (r['name'], r['archive_days'] or 0),
                 {'action': 'catchup_days', 'id': r['stream_id']}, art=art_for(r['icon']))
    end('videos', [xbmcplugin.SORT_METHOD_UNSORTED, xbmcplugin.SORT_METHOD_LABEL])


def catchup_days():
    cat = get_catalog()
    if not cat:
        return fail()
    row = cat.get('live', ARGS['id'])
    cat.close()
    if not row:
        return fail()
    today = datetime.date.today()
    for d in range(0, max(1, row['archive_days'] or 1) + 1):
        day = today - datetime.timedelta(days=d)
        label = 'Today' if d == 0 else 'Yesterday' if d == 1 else day.strftime('%A %d %B')
        add_item(label, {'action': 'catchup_progs', 'id': row['stream_id'], 'day': day.isoformat()},
                 art=art_for(row['icon']))
    end('files')


def catchup_progs():
    cat = get_catalog()
    if not cat:
        return fail()
    row = cat.get('live', ARGS['id'])
    cat.close()
    if not row:
        return fail()
    day = datetime.date.fromisoformat(ARGS['day'])
    lo = time.mktime(day.timetuple())
    hi = lo + 86400
    now = time.time()
    progs = [p for p in _api_listings(row['stream_id'])
             if lo <= p['start'] < hi and p['start'] < now]
    if not progs:
        add_item('[COLOR grey]No programmes available for this day[/COLOR]', {'action': 'noop'},
                 folder=False)
    for p in progs:
        programme_item(row, p, show_day=False)
    end('videos')


# ------------------------------------------------------------------ movies
def vod_cats():
    cat = get_catalog()
    if not cat:
        return fail()
    if any(d.get('type') == 'movie' for d in watching.load()):
        add_item('[B]Continue watching[/B]', {'action': 'continue', 'kind': 'movie'},
                 art={'icon': 'DefaultInProgressShows.png'})
    add_item('[B]Discover[/B]  [COLOR FF8A94A8](ratings, trending, popular)[/COLOR]',
             {'action': 'discover_menu', 'kind': 'movie'}, art={'icon': 'DefaultAddonsSearch.png'})
    add_item('[B]Recently added[/B]', {'action': 'recent', 'kind': 'vod'},
             art={'icon': 'DefaultRecentlyAddedMovies.png'})
    add_item('[B]All movies[/B]', {'action': 'vod_list', 'cat': '*'},
             art={'icon': 'DefaultMovies.png'})
    for c in cat.categories('vod'):
        add_item(with_count(c['name'], c['cnt']), {'action': 'vod_list', 'cat': c['id']},
                 art={'icon': 'DefaultFolder.png'}, context=group_menu('vod', c['id']))
    manage_item('vod')
    cat.close()
    end('files')


def library_menu(kind, item_id):
    if library.is_exported(kind, item_id):
        return ('Remove from library', 'RunPlugin(%s)' % build_url(action='lib_remove', kind=kind, id=item_id))
    return ('Add to library', 'RunPlugin(%s)' % build_url(action='lib_add', kind=kind, id=item_id))


def tmdb_menu(kind, r):
    """Context entries for a title (only when a TMDb key is set)."""
    if not tmdb.configured():
        return []
    year = (r['year'] if kind == 'movie' else (r['release'] or '')[:4]) or None
    q = dict(kind=kind, tmdb=r['tmdb'] or None, title=r['name'], year=year)
    return [('Ratings and details (TMDb)', 'RunPlugin(%s)' % build_url(action='tm_info', **q)),
            ('More like this (TMDb)', 'Container.Update(%s)' % build_url(
                action='discover_list', src='similar', **q))]


def with_tmdb(label, art, info, tm):
    """Show TMDb's title, rating, votes, plot and artwork for an item."""
    label = tm['title'] + (' (%s)' % tm['year'] if tm['year'] else '')
    if tmdb.star(tm):
        label = '%s  %s' % (tmdb.star(tm), label)
    if tm['votes']:
        label += '  [COLOR FF8A94A8](%s votes)[/COLOR]' % tmdb.fmt_votes(tm['votes'])
    info.update(rating=tm['rating'], votes=tm['votes'])
    if tm['plot']:
        info['plot'] = tm['plot']
    if tm['year']:
        info['year'] = tm['year']
    if tm['poster']:
        art.update(poster=tm['poster'], thumb=tm['poster'], icon=tm['poster'])
    if tm['backdrop']:
        art['fanart'] = tm['backdrop']
    return label


def movie_item(r, prefix='', progress=None, tm=None):
    ctx = [('Movie information', 'RunPlugin(%s)' % build_url(
        action='vod_info', id=r['stream_id'], tmdb=r['tmdb'] or None, title=r['name'],
        year=r['year'] or None)),
           library_menu('vod', r['stream_id'])] + tmdb_menu('movie', r)
    seen = watched().movie(r['tmdb'], r['name'], r['year'])
    progress = progress if progress is not None else watching.get('movie', r['stream_id'])
    label = prefix + r['name']
    art = art_for(r['icon'])
    info = {'title': r['name'], 'year': r['year'], 'rating': r['rating'],
            'playcount': 1 if seen else 0, 'mediatype': 'movie'}
    if tm:
        label = prefix + with_tmdb(label, art, info, tm)
    if progress:
        label += '  [COLOR FF8A94A8]- %s[/COLOR]' % watching.label_suffix(progress)
        info.update(resume=progress['position'], duration=progress['total'])
        ctx.append(('Remove from Continue watching',
                    'RunPlugin(%s)' % build_url(action='cw_remove', kind='movie', id=r['stream_id'])))
    add_item(label,
             {'action': 'play_vod', 'id': r['stream_id'], 'ext': r['ext'], 'title': r['name'],
              'tmdb': r['tmdb'] or None, 'year': r['year'] or None, 'icon': r['icon'] or None},
             art=art, info=info, context=ctx, folder=False, playable=True)


def vod_list():
    cat = get_catalog()
    if not cat:
        return fail()
    cat_id = ARGS.get('cat', '*')
    page = int(ARGS.get('page', '0'))
    rows = cat.items('vod', None if cat_id == '*' else cat_id)
    cat.close()
    rows, more = paginate(rows, page)
    for r in rows:
        movie_item(r)
    if more:
        next_page('vod_list', page, cat=cat_id)
    end('movies', [xbmcplugin.SORT_METHOD_UNSORTED, xbmcplugin.SORT_METHOD_LABEL,
                   xbmcplugin.SORT_METHOD_VIDEO_YEAR, xbmcplugin.SORT_METHOD_VIDEO_RATING])


def vod_info():
    try:
        data = client().vod_info(ARGS['id'])
    except XtreamError as e:
        return error(str(e))
    info = data.get('info') or {}
    if not isinstance(info, dict):
        info = {}
    lines = []
    for key, label in (('name', 'Title'), ('releasedate', 'Released'), ('genre', 'Genre'),
                       ('duration', 'Duration'), ('rating', 'Rating'),
                       ('director', 'Director'), ('cast', 'Cast')):
        if info.get(key):
            lines.append('[B]%s:[/B] %s' % (label, info[key]))
    if info.get('plot') or info.get('description'):
        lines += ['', info.get('plot') or info.get('description')]
    if tmdb.configured():
        try:
            tid = ARGS.get('tmdb') or str(info.get('tmdb_id') or info.get('tmdb') or '')
            if not tid.isdigit() or tid == '0':
                tid = tmdb.find_id('movie', ARGS.get('title') or info.get('name') or '', ARGS.get('year'))
            if tid:
                _, extra = tmdb.summary_lines('movie', tid)
                extra = extra[:extra.index('')] if '' in extra else extra
                lines = extra[:1] + lines + [''] + extra[1:]
        except tmdb.TmdbError as e:
            lines += ['', '[COLOR grey]TMDb: %s[/COLOR]' % e]
    xbmcgui.Dialog().textviewer(info.get('name') or common.ADDON_NAME,
                                '\n'.join(lines) or 'No information available.')


# ------------------------------------------------------------------ series
def series_cats():
    cat = get_catalog()
    if not cat:
        return fail()
    if trakt.linked():
        add_item('[B]In progress[/B]  [COLOR FF8A94A8](Trakt)[/COLOR]', {'action': 'trakt_shows', 'which': 'progress'},
                 art={'icon': 'DefaultInProgressShows.png'})
        add_item('[B]Watched[/B]  [COLOR FF8A94A8](Trakt)[/COLOR]', {'action': 'trakt_shows', 'which': 'watched'},
                 art={'icon': 'DefaultTVShows.png'})
    if any(d.get('type') == 'episode' for d in watching.load()):
        add_item('[B]Continue watching[/B]', {'action': 'continue', 'kind': 'episode'},
                 art={'icon': 'DefaultInProgressShows.png'})
    add_item('[B]Discover[/B]  [COLOR FF8A94A8](ratings, trending, popular)[/COLOR]',
             {'action': 'discover_menu', 'kind': 'tv'}, art={'icon': 'DefaultAddonsSearch.png'})
    add_item('[B]Recently updated[/B]', {'action': 'recent', 'kind': 'series'},
             art={'icon': 'DefaultRecentlyAddedEpisodes.png'})
    add_item('[B]All series[/B]', {'action': 'series_list', 'cat': '*'},
             art={'icon': 'DefaultTVShows.png'})
    for c in cat.categories('series'):
        add_item(with_count(c['name'], c['cnt']), {'action': 'series_list', 'cat': c['id']},
                 art={'icon': 'DefaultFolder.png'}, context=group_menu('series', c['id']))
    manage_item('series')
    cat.close()
    end('files')


def series_item(r, prefix='', suffix=None, tm=None):
    art = art_for(r['cover'])
    if r['backdrop']:
        art['fanart'] = r['backdrop']
    label = prefix + r['name']
    info = {'title': r['name'], 'tvshowtitle': r['name'], 'plot': r['plot'],
            'genre': r['genre'], 'director': r['director'], 'cast': r['cast_'],
            'rating': r['rating'], 'premiered': r['release'],
            'year': (r['release'] or '')[:4], 'mediatype': 'tvshow'}
    if tm:
        label = prefix + with_tmdb(label, art, info, tm)
    if suffix is None:
        n = len(watched().episodes(r['tmdb'], r['name'], (r['release'] or '')[:4]))
        suffix = ('%d watched' % n) if n else ''
    if suffix:
        label += '  [COLOR FF8A94A8]- %s[/COLOR]' % suffix
    add_item(label, {'action': 'seasons', 'id': r['series_id'], 'tmdb': r['tmdb'] or None}, art=art,
             context=[library_menu('series', r['series_id'])] + tmdb_menu('tv', r), info=info)


def series_list():
    cat = get_catalog()
    if not cat:
        return fail()
    cat_id = ARGS.get('cat', '*')
    page = int(ARGS.get('page', '0'))
    rows = cat.items('series', None if cat_id == '*' else cat_id)
    cat.close()
    rows, more = paginate(rows, page)
    for r in rows:
        series_item(r)
    if more:
        next_page('series_list', page, cat=cat_id)
    end('tvshows', [xbmcplugin.SORT_METHOD_UNSORTED, xbmcplugin.SORT_METHOD_LABEL,
                    xbmcplugin.SORT_METHOD_VIDEO_YEAR])


def load_series(series_id):
    """get_series_info, cached on disk for 6 hours."""
    folder = common.profile_file('series_cache')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, '%s.json' % series_id)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 6 * 3600:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    data = client().series_info(series_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    return data


def _episodes_by_season(data):
    eps = data.get('episodes') or {}
    seasons = {}
    if isinstance(eps, dict):
        for key, lst in eps.items():
            for e in lst or []:
                seasons.setdefault(str(e.get('season') or key), []).append(e)
    elif isinstance(eps, list):   # some panels: list of lists
        for lst in eps:
            for e in (lst if isinstance(lst, list) else [lst]):
                if isinstance(e, dict):
                    seasons.setdefault(str(e.get('season') or '1'), []).append(e)
    return seasons


def series_tmdb(data):
    info = data.get('info') or {}
    v = str(info.get('tmdb_id') or info.get('tmdb') or ARGS.get('tmdb') or '').strip()
    return v if v.isdigit() and v != '0' else ''


def _season_key(s):
    try:
        return int(s)
    except ValueError:
        return 9999


def seasons():
    try:
        data = load_series(ARGS['id'])
    except XtreamError as e:
        error(str(e))
        return fail()
    info = data.get('info') or {}
    show = info.get('name') or ''
    tmdb = series_tmdb(data)
    seen = watched().episodes(tmdb, show, (info.get('releaseDate') or info.get('release_date') or '')[:4])
    covers = {str(s.get('season_number')): s.get('cover_big') or s.get('cover')
              for s in data.get('seasons') or [] if isinstance(s, dict)}
    by_season = _episodes_by_season(data)
    for num in sorted(by_season, key=_season_key):
        art = art_for(covers.get(num) or info.get('cover'))
        total = len(by_season[num])
        done = len([e for e in by_season[num]
                    if '%s:%s' % (common._int(num), common._int(e.get('episode_num'))) in seen])
        label = 'Season %s' % num
        if done:
            label += '  [COLOR FF8A94A8](%d/%d)[/COLOR]' % (done, total)
        add_item(label, {'action': 'episodes', 'id': ARGS['id'], 'season': num, 'tmdb': tmdb or None},
                 art=art, info={'title': 'Season %s' % num, 'tvshowtitle': show,
                                'season': num, 'plot': info.get('plot'), 'mediatype': 'season',
                                'playcount': 1 if total and done >= total else 0})
    end('seasons')


def episodes():
    try:
        data = load_series(ARGS['id'])
    except XtreamError as e:
        error(str(e))
        return fail()
    info = data.get('info') or {}
    show = info.get('name') or ''
    year = (info.get('releaseDate') or info.get('release_date') or '')[:4]
    tmdb = series_tmdb(data)
    seen = watched().episodes(tmdb, show, year)
    season = common._int(ARGS['season'])
    eps = _episodes_by_season(data).get(ARGS['season'], [])
    eps.sort(key=lambda e: common._int(e.get('episode_num')))
    for e in eps:
        ei = e.get('info') if isinstance(e.get('info'), dict) else {}
        title = e.get('title') or 'Episode %s' % e.get('episode_num')
        num = common._int(e.get('episode_num'))
        icon = ei.get('movie_image') or ei.get('cover_big') or info.get('cover')
        prog = watching.get('episode', e.get('id'))
        extra = {}
        label = title
        if prog:
            label += '  [COLOR FF8A94A8]- %s[/COLOR]' % watching.label_suffix(prog)
            extra = {'resume': prog['position'], 'duration': prog['total']}
        add_item(label,
                 {'action': 'play_episode', 'id': e.get('id'),
                  'ext': e.get('container_extension') or 'mp4', 'title': title,
                  'show': show, 'tmdb': tmdb or None, 'year': year or None,
                  'season': season, 'ep': num, 'sid': ARGS['id'], 'icon': icon or None},
                 art=art_for(icon),
                 info={'title': title, 'tvshowtitle': show, 'season': ARGS['season'],
                       'episode': e.get('episode_num'), 'plot': ei.get('plot'),
                       'duration': ei.get('duration_secs'), 'rating': ei.get('rating'),
                       'premiered': ei.get('releasedate') or ei.get('air_date'),
                       'playcount': 1 if '%d:%d' % (season, num) in seen else 0,
                       'mediatype': 'episode', **extra},
                 folder=False, playable=True)
    end('episodes', [xbmcplugin.SORT_METHOD_EPISODE, xbmcplugin.SORT_METHOD_LABEL])


# ------------------------------------------------------------------ search
SEARCH_KINDS = {'all': ('search', 'Search channels, movies and series'),
                'epg': ('search_epg', 'Search programme titles in the TV guide')}
HISTORY_FILE = 'search_history.json'
HISTORY_KEEP = 30


def _history():
    data = common.load_json(HISTORY_FILE, {}) or {}
    return {k: [t for t in data.get(k, []) if isinstance(t, str)] for k in SEARCH_KINDS}


def _save_history(data):
    common.save_json(HISTORY_FILE, data)


def search_menu():
    """New search + previous searches (newest first)."""
    kind = ARGS.get('kind', 'all')
    action = SEARCH_KINDS.get(kind, SEARCH_KINDS['all'])[0]
    add_item('[B]New search...[/B]', {'action': 'search_new', 'kind': kind},
             art={'icon': 'DefaultAddonsSearch.png'}, folder=False)
    terms = _history()[kind]
    for term in terms:
        add_item(term, {'action': action, 'q': term}, art={'icon': 'DefaultFolder.png'},
                 context=[('Remove from history', 'RunPlugin(%s)' % build_url(action='search_del', kind=kind, q=term)),
                          ('Clear search history', 'RunPlugin(%s)' % build_url(action='search_clear', kind=kind))])
    if terms:
        add_item('[COLOR grey]Clear search history[/COLOR]', {'action': 'search_clear', 'kind': kind},
                 art={'icon': 'DefaultAddonService.png'}, folder=False)
    end('files')


def search_new():
    """Ask for a term, remember it, and open its results page.

    The results page has the term in its address, so Back from a channel, movie or
    series returns to the results instead of asking again.
    """
    kind = ARGS.get('kind', 'all')
    action, heading = SEARCH_KINDS.get(kind, SEARCH_KINDS['all'])
    term = (xbmcgui.Dialog().input(heading) or '').strip()
    if not term:
        return
    data = _history()
    data[kind] = [term] + [t for t in data[kind] if t.lower() != term.lower()][:HISTORY_KEEP - 1]
    _save_history(data)
    xbmc.executebuiltin('Container.Update(%s)' % build_url(action=action, q=term))


def search_del():
    data = _history()
    kind = ARGS.get('kind', 'all')
    data[kind] = [t for t in data[kind] if t != ARGS.get('q')]
    _save_history(data)
    xbmc.executebuiltin('Container.Refresh')


def search_clear():
    kind = ARGS.get('kind', 'all')
    if not xbmcgui.Dialog().yesno(common.ADDON_NAME, 'Clear the search history?'):
        return
    data = _history()
    data[kind] = []
    _save_history(data)
    xbmc.executebuiltin('Container.Refresh')


def _redirect_to_menu(kind):
    """Old-style call without a term (e.g. a saved shortcut): show the search menu."""
    fail()
    xbmc.executebuiltin('Container.Update(%s,replace)' % build_url(action='search_menu', kind=kind))


def search():
    term = ARGS.get('q')
    if not term:
        return _redirect_to_menu('all')
    cat = get_catalog()
    if not cat:
        return fail()
    live = cat.search('live', term)
    vod = cat.search('vod', term)
    ser = cat.search('series', term)
    cat.close()
    nn = now_next_for(live)
    for r in live:
        channel_item(r, nn.get(r['epg_id']), prefix='[COLOR lightblue][TV][/COLOR] ')
    for r in vod:
        movie_item(r, prefix='[COLOR lightgreen][Movie][/COLOR] ')
    for r in ser:
        series_item(r, prefix='[COLOR orange][Series][/COLOR] ')
    if not (live or vod or ser):
        add_item('[COLOR grey]Nothing found for "%s"[/COLOR]' % term, {'action': 'noop'},
                 folder=False)
    end('videos')


# ------------------------------------------------------------ misc actions
def account():
    lines = []
    try:
        data = client().account()
    except XtreamError as e:
        data = None
        lines.append('[COLOR red]%s[/COLOR]' % e)
    if data:
        ui = data.get('user_info') or {}
        si = data.get('server_info') or {}
        exp = ui.get('exp_date')
        try:
            expiry = datetime.datetime.fromtimestamp(int(exp)).strftime('%Y-%m-%d %H:%M')
        except (TypeError, ValueError):
            expiry = 'Unlimited'
        lines += ['[B]Username:[/B] %s' % ui.get('username', ''),
                  '[B]Status:[/B] %s' % ui.get('status', ''),
                  '[B]Expires:[/B] %s' % expiry,
                  '[B]Trial:[/B] %s' % ('Yes' if str(ui.get('is_trial')) == '1' else 'No'),
                  '[B]Connections:[/B] %s active / %s max' % (
                      ui.get('active_cons', '?'), ui.get('max_connections', '?')),
                  '[B]Formats:[/B] %s' % ', '.join(ui.get('allowed_output_formats') or []),
                  '[B]Server time zone:[/B] %s' % si.get('timezone', '')]
    state = common.load_state()
    lines.append('')
    lines.append('[B]User-Agent:[/B] %s' % common.user_agent())
    for key, label in (('last_sync', 'Channel list updated'), ('last_epg', 'EPG updated')):
        ts = state.get(key)
        lines.append('[B]%s:[/B] %s' % (
            label, time.strftime('%Y-%m-%d %H:%M', time.localtime(ts)) if ts else 'never'))
    if trakt.linked():
        ts = state.get('trakt_sync')
        lines.append('[B]Trakt:[/B] linked%s, synced %s' % (
            (' as ' + trakt.token().get('username')) if trakt.token().get('username') else '',
            time.strftime('%Y-%m-%d %H:%M', time.localtime(ts)) if ts else 'never'))
    else:
        lines.append('[B]Trakt:[/B] not linked')
    from resources.lib import reminders
    at = reminders.sleep_at()
    if at:
        lines.append('[B]Sleep timer:[/B] stops at %s' % common.fmt_time(at))
    rem = reminders.load()
    if rem:
        lines.append('[B]Reminders:[/B]')
        lines += ['   %s  %s (%s)' % (common.fmt_day_time(r['start']), r['title'], r['channel'])
                  for r in rem[:10]]
    g = EPG(common.epg_path())
    lines.append('[B]EPG entries:[/B] %d' % g.programme_count())
    g.close()
    if sync.is_syncing():
        lines.append('[COLOR yellow]An update is running now[/COLOR]')
    if state.get('last_error'):
        lines.append('[B]Last error:[/B] %s' % state['last_error'])
    xbmcgui.Dialog().textviewer(common.ADDON_NAME, '\n'.join(lines))


def refresh():
    if not common.is_configured():
        return error('Please set up your account first.')
    if sync.is_syncing():
        return common.notify('An update is already running')
    sync.request_background('full')
    common.notify('Update started in the background')


def fav_toggle():
    added = common.toggle_fav(ARGS['id'])
    common.notify('Added to favourites' if added else 'Removed from favourites', 2500)
    xbmc.executebuiltin('Container.Refresh')


def trakt_shows():
    """In-progress or watched shows from Trakt that the provider has."""
    which = ARGS.get('which', 'progress')
    w = watched()
    if not w.ok:
        error('Trakt history is not downloaded yet. Use "Sync Trakt now" in Settings > Trakt.')
        return fail()
    cat = get_catalog()
    if not cat:
        return fail()
    rows = cat.items('series')
    cat.close()
    by_tmdb, by_key, by_title = {}, {}, {}
    for r in rows:
        if r['tmdb']:
            by_tmdb.setdefault(r['tmdb'], r)
        k, y = trakt.title_key(r['name'])
        y = y or (r['release'] or '')[:4]
        by_key.setdefault('%s|%s' % (k, y), r)
        by_title.setdefault(k, []).append(r)
    shows = sorted(w.shows, key=lambda s: s.get('last') or '', reverse=True)
    count = 0
    for s in shows:
        done, aired = len(s['_eps']), s.get('aired') or 0
        finished = aired and done >= aired
        if (which == 'watched') != bool(finished):
            continue
        k = trakt.title_key(s.get('t'))[0]
        r = (by_tmdb.get(s.get('tmdb')) or by_key.get('%s|%s' % (k, s.get('y')))
             or (by_title.get(k)[0] if len(by_title.get(k) or []) == 1 else None))
        if r is None:
            continue   # not available from this provider
        if finished:
            suffix = 'all %d watched' % done
        else:
            nxt = trakt.next_episode(s['_eps'])
            suffix = ('%d/%d' % (done, aired) if aired else '%d watched' % done) + \
                     ('  next %s' % nxt if nxt else '')
        series_item(r, suffix=suffix)
        count += 1
    if not count:
        add_item('[COLOR grey]No %s shows found on this provider[/COLOR]'
                 % ('in-progress' if which == 'progress' else 'watched'), {'action': 'noop'},
                 folder=False)
    end('tvshows')


def sleep_timer():
    from resources.lib import reminders
    at = reminders.sleep_at()
    options = [('Off', 0), ('15 minutes', 15), ('30 minutes', 30), ('45 minutes', 45),
               ('1 hour', 60), ('1.5 hours', 90), ('2 hours', 120), ('End of current programme', -1)]
    heading = 'Sleep timer' + ('  (stops at %s)' % common.fmt_time(at) if at else '')
    c = xbmcgui.Dialog().select(heading, [o[0] for o in options])
    if c < 0:
        return
    minutes = options[c][1]
    if minutes == 0:
        reminders.set_sleep(0)
        return common.notify('Sleep timer off', 2500)
    if minutes > 0:
        target = time.time() + minutes * 60
    else:
        state = playback.playing_context() or {}
        catalog = Catalog(common.catalog_path())
        row = catalog.get('live', state.get('id')) if state.get('id') else None
        catalog.close()
        progs = None
        if row is not None:
            guide = EPG(common.epg_path())
            progs = guide.now_next([row['epg_id']]).get(row['epg_id'])
            guide.close()
        now = time.time()
        cur = next((p for p in progs or [] if p['start'] <= now < p['stop']), None)
        if cur is None:
            return error('No live programme is playing, so "end of programme" is unknown.')
        target = cur['stop'] + 60
    reminders.set_sleep(target)
    common.notify('Sleep timer: playback stops at %s' % common.fmt_time(target), 4000)


def search_epg():
    term = ARGS.get('q')
    if not term:
        return _redirect_to_menu('epg')
    cat = get_catalog()
    if not cat:
        return fail()
    channels = {}
    for r in cat.items('live'):
        if r['epg_id']:
            channels.setdefault(r['epg_id'], r)
    cat.close()
    guide = EPG(common.epg_path())
    if not guide.ok:
        guide.close()
        error('The TV guide is not downloaded yet.')
        return fail()
    now = time.time()
    coming, aired = guide.search(term, now - 7 * 86400, now=now)
    guide.close()
    from resources.lib import reminders
    reminded = reminders.keys()
    sections = {'now': [], 'next': [], 'past': []}
    for p in coming + aired:
        row = channels.get(p['channel'])
        if row is None:
            continue
        if p['stop'] <= now:
            if not (row['archive'] and p['start'] >= now - (row['archive_days'] or 0) * 86400):
                continue   # aired and not available on catch-up
            sections['past'].append((p, row))
        else:
            sections['now' if p['start'] <= now else 'next'].append((p, row))
    count = 0
    for key, heading, ok_does in (('now', 'On now', 'OK: watch live'),
                                  ('next', 'Coming up', 'OK: set a reminder, watch the channel now, or open the TV guide'),
                                  ('past', 'Catch-up (already aired)', 'OK: watch this programme')):
        if not sections[key]:
            continue
        add_item('[B][COLOR FF8A94A8]%s[/COLOR][/B]' % heading, {'action': 'noop'}, folder=False)
        for p, row in sections[key]:
            _epg_hit(p, row, key, ok_does, reminders.key(row['stream_id'], p['start']) in reminded)
            count += 1
    if not count:
        add_item('[COLOR grey]Nothing found for "%s"[/COLOR]' % term, {'action': 'noop'}, folder=False)
    end('videos')


def _epg_hit(p, row, kind, ok_does, has_reminder):
    """One guide search result. kind: 'now', 'next' or 'past'."""
    when = common.fmt_when(p['start'])
    if kind == 'next':
        tag = '  [COLOR FF8A94A8](%s%s)[/COLOR]' % (
            common.fmt_until(p['start']), ', reminder set' if has_reminder else '')
    elif kind == 'past':
        tag = '  [COLOR %s](recording)[/COLOR]' % theme.playing()
    else:
        tag = '  [COLOR %s](on now)[/COLOR]' % theme.accent()
    label = '%s  %s  [COLOR FF8A94A8]- %s[/COLOR]%s' % (when, p['title'], playback.channel_label(row), tag)
    q = {'action': 'epg_pick', 'id': row['stream_id'], 'start': p['start'], 'stop': p['stop'],
         'title': p['title']}
    ctx = []
    if kind == 'now':
        if row['archive']:
            ctx.append(('Watch from the beginning', 'RunPlugin(%s)' % build_url(**dict(q, do='restart'))))
    elif kind == 'next':
        ctx.append(('Remove reminder' if has_reminder else 'Set reminder',
                    'RunPlugin(%s)' % build_url(**dict(q, do='reminder'))))
    ctx.append(('Watch %s live' % row['name'], 'RunPlugin(%s)' % build_url(**dict(q, do='live'))))
    ctx.append(('TV guide (grid)', 'RunPlugin(%s)' % build_url(action='grid', id=row['stream_id'])))
    add_item(label, q, art=art_for(row['icon']), context=ctx,
             info={'title': p['title'], 'plot': '[B]%s[/B][CR]%s - %s  %s[CR][CR]%s' % (
                 ok_does, when, common.fmt_time(p['stop']), row['name'], p.get('descr') or ''),
                 'mediatype': 'video'}, folder=False)


def epg_pick():
    """A guide search result: on now -> watch live (restart is in the context
    menu, as in TV mode and the grid guide), aired -> catch-up, later -> reminder."""
    from resources.lib import reminders
    catalog = Catalog(common.catalog_path())
    row = catalog.get('live', ARGS['id'])
    catalog.close()
    if row is None:
        return
    p = {'start': int(ARGS['start']), 'stop': int(ARGS['stop']), 'title': ARGS.get('title', '')}
    now = time.time()
    cat = playback.own_group(row)
    do = ARGS.get('do')
    if do == 'live':
        return playback.start_live(row, cat)
    if do == 'restart' and row['archive']:
        return playback.restart(row, cat)
    if p['start'] <= now < p['stop']:
        return playback.start_live(row, cat)
    if p['stop'] <= now:
        return playback.play_programme(row, p)
    if do != 'reminder':
        # Not on yet: ask, instead of quietly setting a reminder.
        has = reminders.has(row['stream_id'], p['start'])
        options = ['Remove reminder' if has else 'Set reminder for %s' % common.fmt_day_time(p['start']),
                   'Watch %s now' % playback.channel_label(row), 'TV guide (grid)']
        choice = xbmcgui.Dialog().contextmenu(options)
        if choice == 1:
            return playback.start_live(row, cat)
        if choice == 2:
            from resources.lib.guide import open_guide
            return open_guide(cat, row['stream_id'])
        if choice != 0:
            return
    reminders.toggle(row, p)
    xbmc.executebuiltin('Container.Refresh')


def clear_cache():
    from resources.lib import reminders
    if not xbmcgui.Dialog().yesno(common.ADDON_NAME, 'Delete the downloaded channel lists, TV guide '
                                  'and other cached data? Favourites, hidden groups, history, '
                                  'logins and settings are kept.[CR]Everything is downloaded again '
                                  'in the background.'):
        return
    reminders.clear_cache()
    sync.request_background('full')
    common.notify('Cache cleared - downloading again in the background', 4000)


def continue_list():
    """Movies and episodes stopped partway, newest first."""
    kind = ARGS.get('kind')
    cat = get_catalog()
    if not cat:
        return fail()
    items = [d for d in watching.load() if not kind or d.get('type') == kind]
    for d in items:
        if d['type'] == 'movie':
            row = cat.get('vod', d['id'])
            if row is not None:
                movie_item(row, progress=d)
            continue
        label = '%s  S%02dE%02d  %s  [COLOR FF8A94A8]- %s[/COLOR]' % (
            d.get('show') or d.get('title'), common._int(d.get('season')),
            common._int(d.get('episode')), d.get('name') or '', watching.label_suffix(d))
        add_item(label, {'action': 'play_episode', 'id': d['id'], 'ext': d.get('ext'),
                         'title': d.get('name'), 'show': d.get('show'), 'tmdb': d.get('tmdb') or None,
                         'year': d.get('year') or None, 'season': d.get('season'),
                         'ep': d.get('episode'), 'sid': d.get('sid') or None,
                         'icon': d.get('icon') or None},
                 art=art_for(d.get('icon')),
                 info={'title': d.get('name') or '', 'tvshowtitle': d.get('show') or '',
                       'season': d.get('season'), 'episode': d.get('episode'),
                       'resume': d['position'], 'duration': d['total'], 'mediatype': 'episode'},
                 context=[('Remove from Continue watching', 'RunPlugin(%s)' % build_url(
                     action='cw_remove', kind='episode', id=d['id']))],
                 folder=False, playable=True)
    cat.close()
    if not items:
        add_item('[COLOR grey]Nothing in progress[/COLOR]', {'action': 'noop'}, folder=False)
    end('videos')


def cw_remove():
    watching.remove(ARGS['kind'], ARGS['id'])
    xbmc.executebuiltin('Container.Refresh')


def recent():
    kind = ARGS.get('kind', 'vod')
    cat = get_catalog()
    if not cat:
        return fail()
    rows = cat.recent(kind)
    cat.close()
    for r in rows:
        if kind == 'vod':
            movie_item(r)
        else:
            series_item(r)
    end('movies' if kind == 'vod' else 'tvshows')


def lib_add():
    kind, item_id = ARGS['kind'], ARGS['id']
    catalog = Catalog(common.catalog_path())
    row = catalog.get(kind, item_id)
    catalog.close()
    if row is None:
        return
    state = common.load_state()
    if not state.get('library_told'):
        movies, shows = library.folders()
        xbmcgui.Dialog().ok('Add to library', 'One-time setup: in Kodi go to Videos > Files > '
                            'Add videos and add these two folders, choosing "Movies" and "TV shows" '
                            'as content:[CR][CR]%s[CR]%s' % (movies, shows))
        state['library_told'] = True
        common.save_state(state)
    try:
        if kind == 'vod':
            library.add_movie(row)
            common.notify('Added to library: %s' % row['name'], 3000)
        else:
            new = library.add_series(row)
            common.notify('Added to library: %s (%d episodes)' % (row['name'], new), 4000)
    except XtreamError as e:
        return error(str(e))
    library.scan()
    xbmc.executebuiltin('Container.Refresh')


def lib_remove():
    if library.remove(ARGS['kind'], ARGS['id']):
        common.notify('Removed from library (run "Clean library" in Kodi to tidy up)', 4000)
    xbmc.executebuiltin('Container.Refresh')


def lib_update():
    try:
        added = library.update_all()
    except XtreamError as e:
        return error(str(e))
    common.notify('Library: %d new episodes' % added, 3000)
    if added:
        library.scan()


def rename_group():
    from resources.lib import customize
    catalog = Catalog(common.catalog_path())
    groups = catalog.categories(ARGS['kind'], include_hidden=True)
    catalog.close()
    g = next((x for x in groups if str(x['id']) == ARGS['id']), None)
    if g and customize.rename_group(ARGS['kind'], g['id'], g['name'], g['provider_name']):
        xbmc.executebuiltin('Container.Refresh')


def move_group():
    from resources.lib import customize
    catalog = Catalog(common.catalog_path())
    groups = catalog.categories(ARGS['kind'])
    catalog.close()
    if customize.move_group(ARGS['kind'], groups, ARGS['id']):
        xbmc.executebuiltin('Container.Refresh')


def move_channel():
    from resources.lib import customize
    catalog = Catalog(common.catalog_path())
    rows = live_rows(catalog, ARGS.get('cat') or '*')
    catalog.close()
    if customize.move_channel(ARGS.get('cat') or '*', rows, ARGS['id']):
        xbmc.executebuiltin('Container.Refresh')


def adult_unlock():
    if common.unlock_adult():
        xbmc.executebuiltin('Container.Refresh')


def adult_lock():
    common.lock_adult()
    xbmc.executebuiltin('Container.Refresh')


def backup_create():
    from resources.lib import backup
    backup.create()


def backup_restore():
    from resources.lib import backup
    if backup.restore():
        xbmc.executebuiltin('Container.Refresh')


def reset_custom():
    from resources.lib import customize
    if xbmcgui.Dialog().yesno(common.ADDON_NAME, 'Forget your group names and custom order of '
                              'groups and channels?'):
        customize.reset()
        common.notify('Order and names reset', 2500)


def grid():
    cat = get_catalog()
    if not cat:
        return
    cat.close()
    state = playback.zap_state() or {}
    from resources.lib.guide import open_guide
    open_guide(ARGS.get('cat') or state.get('cat') or '*', ARGS.get('id') or state.get('id'),
               before_show=close_dialogs)


def restart():
    catalog = Catalog(common.catalog_path())
    row = catalog.get('live', ARGS['id']) if catalog.exists() else None
    catalog.close()
    if row is not None:
        playback.restart(row, ARGS.get('cat') or playback.own_group(row))


def recall():
    playback.recall()


def trakt_link():
    if trakt.link():
        trakt_sync()


def trakt_unlink():
    if xbmcgui.Dialog().yesno('Trakt', 'Unlink your Trakt account from this add-on?'):
        trakt.unlink()


def trakt_sync():
    if not trakt.linked():
        return error('Link your Trakt account first (Settings > Trakt).')
    try:
        movies, shows = trakt.sync_watched()
    except trakt.TraktError as e:
        return error(str(e))
    state = common.load_state()
    state['trakt_sync'] = time.time()
    common.save_state(state)
    common.notify('Trakt: %d watched movies, %d shows' % (movies, shows))
    xbmc.executebuiltin('Container.Refresh')


def hide_group():
    from resources.lib import groups
    groups.hide_group(ARGS['kind'], ARGS['id'])
    common.notify('Group hidden. Use "Show/hide groups..." to bring it back.', 4000)
    xbmc.executebuiltin('Container.Refresh')


def manage_groups():
    from resources.lib import groups
    if groups.manage(ARGS.get('kind')):
        xbmc.executebuiltin('Container.Refresh')


def settings():
    common.addon().openSettings()


def close_dialogs():
    """Kodi refuses to open a window while a pop-up (e.g. Favourites) is still open,
    and a Favourites shortcut runs while that pop-up is showing."""
    xbmc.executebuiltin('Dialog.Close(all,true)')
    monitor = xbmc.Monitor()
    for _ in range(30):
        if not xbmc.getCondVisibility('System.HasActiveModalDialog'):
            break
        if monitor.waitForAbort(0.1):
            break


def tv():
    cat = get_catalog()
    if not cat:
        return
    cat.close()
    from resources.lib.tvwindow import open_tv
    # Everything is ready: close Favourites (or any dialog) and show TV mode at
    # once, so there is no empty gap between the two.
    common.log('TV mode: add-on ready %.1fs after it was started' % (time.time() - _T0))
    open_tv(before_show=close_dialogs)


# ---------------------------------------------------------------- discover
KIND_NAME = {'movie': 'Movies', 'tv': 'Series'}


def _need_key():
    """True if there is no TMDb key yet (tells the user how to get one)."""
    if tmdb.configured():
        return False
    if xbmcgui.Dialog().yesno(
            common.ADDON_NAME, 'Discover shows ratings, votes and what is popular, using TMDb. '
            'It needs a free API key:[CR]1. Sign up at themoviedb.org[CR]2. Open Settings > API and '
            'copy the "API Key"[CR]3. Paste it in this add-on\'s settings under Discover.',
            yeslabel='Open settings', nolabel='Later'):
        common.addon().openSettings()
    return True


def discover_menu():
    if _need_key():
        return fail()
    kind = ARGS.get('kind', 'all')
    if kind == 'all':
        for k in ('movie', 'tv'):
            add_item('[B]%s[/B]' % KIND_NAME[k], {'action': 'discover_menu', 'kind': k},
                     art={'icon': 'DefaultMovies.png' if k == 'movie' else 'DefaultTVShows.png'})
        return end('files')
    for name, (path, params, label) in tmdb.SOURCES[kind].items():
        add_item(label, {'action': 'discover_list', 'kind': kind, 'src': name},
                 art={'icon': 'DefaultFolder.png'})
    add_item('By genre', {'action': 'discover_genres', 'kind': kind}, art={'icon': 'DefaultGenre.png'})
    add_item('By decade', {'action': 'discover_decades', 'kind': kind}, art={'icon': 'DefaultYear.png'})
    add_item('[COLOR FF8A94A8]Only titles your provider has are shown. Ratings by TMDb.[/COLOR]',
             {'action': 'noop'}, folder=False)
    end('files')


def discover_genres():
    kind = ARGS['kind']
    try:
        for gid, name in tmdb.genres(kind):
            add_item(name, {'action': 'discover_list', 'kind': kind, 'src': 'genre', 'genre': gid},
                     art={'icon': 'DefaultGenre.png'})
    except tmdb.TmdbError as e:
        error(str(e))
        return fail()
    end('files')


def discover_decades():
    kind = ARGS['kind']
    for dec in range(2020, 1950, -10):
        add_item('%ds' % dec, {'action': 'discover_list', 'kind': kind, 'src': 'decade', 'decade': dec},
                 art={'icon': 'DefaultYear.png'})
    end('files')


def discover_list():
    kind = 'tv' if ARGS.get('kind') in ('tv', 'series') else 'movie'
    src, page = ARGS.get('src', 'popular'), int(ARGS.get('page', '0'))
    opts = {k: ARGS.get(k) for k in ('genre', 'decade', 'id')}
    try:
        if src == 'similar' and not (opts['id'] or '').isdigit():
            opts['id'] = ARGS.get('tmdb') if (ARGS.get('tmdb') or '').isdigit() else \
                tmdb.find_id(kind, ARGS.get('title', ''), ARGS.get('year'))
            if not opts['id']:
                common.notify('Not found on TMDb', 3000)
                return fail()
        path, params, label = tmdb.source(kind, src, **opts)
        titles, more = tmdb.fetch(kind, path, params, page)
    except (tmdb.TmdbError, KeyError) as e:
        error(str(e))
        return fail()
    cat = get_catalog()
    if not cat:
        return fail()
    matched = tmdb.match(cat, kind, titles)
    cat.close()
    for tm, row in matched:
        if kind == 'movie':
            movie_item(row, tm=tm)
        else:
            series_item(row, tm=tm)
    if not matched:
        msg = ('None of these %d titles are on your provider%s' % (len(titles), ' - try the next page' if more else '')
               ) if titles else 'TMDb has nothing for this'
        add_item('[COLOR grey]%s[/COLOR]' % msg, {'action': 'noop'}, folder=False)
    if more:
        extra = {k: v for k, v in dict(kind=kind, src=src, genre=opts['genre'], decade=opts['decade'],
                                       id=opts['id'], tmdb=ARGS.get('tmdb'), title=ARGS.get('title'),
                                       year=ARGS.get('year')).items() if v}
        next_page('discover_list', page, **extra)
    end('movies' if kind == 'movie' else 'tvshows',
        [xbmcplugin.SORT_METHOD_UNSORTED, xbmcplugin.SORT_METHOD_VIDEO_RATING,
         xbmcplugin.SORT_METHOD_VIDEO_YEAR, xbmcplugin.SORT_METHOD_LABEL])


def tm_info():
    kind = 'tv' if ARGS.get('kind') in ('tv', 'series') else 'movie'
    try:
        tid = ARGS.get('tmdb') if (ARGS.get('tmdb') or '').isdigit() else \
            tmdb.find_id(kind, ARGS.get('title', ''), ARGS.get('year'))
        if not tid:
            return common.notify('Not found on TMDb', 3000)
        title, lines = tmdb.summary_lines(kind, tid)
    except tmdb.TmdbError as e:
        return error(str(e))
    xbmcgui.Dialog().textviewer(title or ARGS.get('title', ''), '\n'.join(lines) or 'No information.')


ROUTES = {
    'discover_menu': discover_menu, 'discover_list': discover_list, 'tm_info': tm_info,
    'discover_genres': discover_genres, 'discover_decades': discover_decades,
    'root': root, 'tv': tv, 'settings': settings, 'refresh': refresh, 'account': account,
    'live_cats': live_cats, 'live_list': live_list, 'guide': guide,
    'catchup_cats': catchup_cats, 'catchup_list': catchup_list,
    'catchup_days': catchup_days, 'catchup_progs': catchup_progs,
    'vod_cats': vod_cats, 'vod_list': vod_list, 'vod_info': vod_info,
    'series_cats': series_cats, 'series_list': series_list,
    'seasons': seasons, 'episodes': episodes, 'search': search,
    'play_live': play_live, 'play_catchup': play_catchup,
    'play_vod': play_vod, 'play_episode': play_episode,
    'zap': zap, 'fav_toggle': fav_toggle, 'hide_group': hide_group,
    'manage_groups': manage_groups, 'trakt_shows': trakt_shows, 'trakt_link': trakt_link,
    'trakt_unlink': trakt_unlink, 'trakt_sync': trakt_sync, 'grid': grid,
    'restart': restart, 'recall': recall, 'sleep_timer': sleep_timer,
    'search_epg': search_epg, 'epg_pick': epg_pick, 'clear_cache': clear_cache,
    'search_menu': search_menu, 'search_new': search_new, 'search_del': search_del,
    'search_clear': search_clear,
    'continue': continue_list, 'cw_remove': cw_remove, 'recent': recent, 'lib_add': lib_add,
    'lib_remove': lib_remove, 'lib_update': lib_update, 'rename_group': rename_group,
    'move_group': move_group, 'move_channel': move_channel, 'adult_unlock': adult_unlock,
    'adult_lock': adult_lock, 'backup_create': backup_create, 'backup_restore': backup_restore,
    'reset_custom': reset_custom, 'noop': lambda: None,
}


def router():
    action = ARGS.get('action', 'root')
    handler = ROUTES.get(action)
    if handler is None:
        common.log('Unknown action %s' % action, xbmc.LOGWARNING)
        return
    try:
        handler()
    except XtreamError as e:
        error(str(e))
        if action in ('play_vod', 'play_episode'):
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


if __name__ == '__main__':
    router()
