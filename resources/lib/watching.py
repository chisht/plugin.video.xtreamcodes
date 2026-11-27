# -*- coding: utf-8 -*-
"""Continue watching: playback positions of movies and episodes played here."""
import time

from . import common

FILE = 'continue_watching.json'
KEEP = 50
FINISHED = 92.0      # % at which an item counts as watched to the end
MIN_SECONDS = 60     # ignore items stopped in the first minute


def _key(item):
    return '%s:%s' % (item.get('type'), item.get('id'))


def load():
    data = common.load_json(FILE, [])
    return [d for d in data if isinstance(d, dict)]


def _save(items):
    common.save_json(FILE, items[:KEEP])


def get(kind, item_id):
    k = '%s:%s' % (kind, item_id)
    return next((d for d in load() if _key(d) == k), None)


def update(item, position, total):
    """Record progress; removes the entry once (nearly) finished."""
    if not item or total <= 0:
        return
    items = [d for d in load() if _key(d) != _key(item)]
    pct = position * 100.0 / total
    if pct < FINISHED and position >= MIN_SECONDS:
        entry = dict(item)
        entry.update(position=int(position), total=int(total), updated=int(time.time()))
        items.insert(0, entry)
    _save(items)


def remove(kind, item_id):
    k = '%s:%s' % (kind, item_id)
    _save([d for d in load() if _key(d) != k])


def label_suffix(entry):
    if not entry or not entry.get('total'):
        return ''
    return '%d%% watched' % int(entry['position'] * 100 / entry['total'])
