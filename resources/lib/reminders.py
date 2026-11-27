# -*- coding: utf-8 -*-
"""Programme reminders and the sleep timer (both checked by the service)."""
import glob
import os
import shutil
import time

import xbmc
import xbmcgui

from . import common

FILE = 'reminders.json'
PROP_SLEEP = common.ADDON_ID + '.sleep_at'
PROP_SLEEP_WARNED = common.ADDON_ID + '.sleep_warned'


# ------------------------------------------------------------ reminders
def load():
    return [r for r in common.load_json(FILE, []) if isinstance(r, dict)]


def _save(items):
    common.save_json(FILE, items)


def key(stream_id, start):
    return '%s:%d' % (stream_id, int(start))


def keys():
    return {key(r['sid'], r['start']) for r in load()}


def has(stream_id, start):
    return key(stream_id, start) in keys()


def toggle(row, p):
    """Add or remove a reminder for programme p on channel row. Returns True if added."""
    items = load()
    k = key(row['stream_id'], p['start'])
    kept = [r for r in items if key(r['sid'], r['start']) != k]
    if len(kept) != len(items):
        _save(kept)
        common.notify('Reminder removed', 2500)
        return False
    kept.append({'sid': str(row['stream_id']), 'channel': row['name'], 'title': p.get('title') or '',
                 'start': int(p['start']), 'stop': int(p['stop'])})
    _save(sorted(kept, key=lambda r: r['start']))
    common.notify('Reminder set: %s at %s' % (p.get('title') or row['name'],
                                              common.fmt_day_time(p['start'])), 3000)
    return True


def take_due(lead_minutes=1):
    """Reminders whose programme is about to start; removes them and expired ones."""
    now = time.time()
    items = load()
    due = [r for r in items if r['start'] - lead_minutes * 60 <= now < r['stop']]
    keep = [r for r in items if r not in due and r['stop'] > now]
    if len(keep) != len(items):
        _save(keep)
    return due


def fire(reminder):
    """Ask whether to switch; called by the service."""
    from .catalog import Catalog
    from . import playback
    msg = '"%s" starts at %s on %s.' % (reminder['title'] or 'Programme',
                                       common.fmt_time(reminder['start']), reminder['channel'])
    if not xbmcgui.Dialog().yesno('Reminder', msg + '[CR]Watch it now?', nolabel='Ignore',
                                  yeslabel='Watch', autoclose=30000):
        return
    cat = Catalog(common.catalog_path())
    row = cat.get('live', reminder['sid']) if cat.exists() else None
    cat.close()
    if row is not None:
        playback.start_live(row, playback.own_group(row))


# --------------------------------------------------------- sleep timer
def sleep_at():
    try:
        return float(xbmcgui.Window(10000).getProperty(PROP_SLEEP) or 0)
    except ValueError:
        return 0.0


def set_sleep(at):
    win = xbmcgui.Window(10000)
    win.clearProperty(PROP_SLEEP_WARNED)
    if at:
        win.setProperty(PROP_SLEEP, str(at))
    else:
        win.clearProperty(PROP_SLEEP)


def check_sleep():
    """Called by the service every few seconds."""
    at = sleep_at()
    if not at:
        return
    win = xbmcgui.Window(10000)
    now = time.time()
    if now >= at:
        set_sleep(0)
        if xbmc.Player().isPlaying():
            xbmc.Player().stop()
            common.notify('Sleep timer: playback stopped', 5000)
    elif at - now <= 60 and not win.getProperty(PROP_SLEEP_WARNED):
        win.setProperty(PROP_SLEEP_WARNED, '1')
        common.notify('Sleep timer: stopping in 1 minute', 6000)


# ------------------------------------------------------------- caches
CACHE_FILES = ('catalog.db', 'epg.db', 'xmltv.xml', 'xmltv.xml.gz', 'trakt_watched.json')


def clean_temp_files():
    """Leftovers of an update interrupted by a crash or power-off."""
    removed = 0
    for pattern in ('*.tmp', '*.part'):
        for path in glob.glob(os.path.join(common.PROFILE, pattern)):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    if removed:
        common.log('Removed %d leftover temporary files' % removed)
    return removed


def clear_cache():
    """Delete downloaded data; keeps favourites, hidden groups, history, logins, settings."""
    for name in CACHE_FILES:
        try:
            os.remove(common.profile_file(name))
        except OSError:
            pass
    shutil.rmtree(common.profile_file('series_cache'), ignore_errors=True)
    clean_temp_files()
    xbmcgui.Window(10000).clearProperty(common.PROP_OFFLINE)
    state = common.load_state()
    for k in ('last_sync', 'last_epg', 'trakt_sync', 'last_error', 'epg_offset_built'):
        state.pop(k, None)
    common.save_state(state)
