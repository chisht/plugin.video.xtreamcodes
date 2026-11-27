# -*- coding: utf-8 -*-
"""Your own group names and the order of groups and channels."""
import xbmcgui

from . import common

FILE = 'customize.json'


def load():
    data = common.load_json(FILE, {}) or {}
    for k in ('group_order', 'group_names', 'channel_order'):
        data.setdefault(k, {})
    return data


def _save(data):
    common.save_json(FILE, data)


def _ordered(items, order, key):
    """Items in the saved order; anything not in it keeps its place after them."""
    if not order:
        return list(items)
    pos = {str(v): i for i, v in enumerate(order)}
    base = len(pos)
    indexed = [(pos.get(str(key(it)), base + n), n, it) for n, it in enumerate(items)]
    return [it for _, _, it in sorted(indexed, key=lambda t: (t[0], t[1]))]


def apply_groups(kind, rows):
    """Category rows -> dicts with your names and order applied."""
    data = load()
    names = data['group_names'].get(kind, {})
    out = []
    for r in rows:
        d = dict(r)
        d['provider_name'] = d['name']
        if str(d['id']) in names:
            d['name'] = names[str(d['id'])]
        out.append(d)
    return _ordered(out, data['group_order'].get(kind), lambda d: d['id'])


def apply_channels(cat_id, rows):
    return _ordered(rows, load()['channel_order'].get(str(cat_id or '*')), lambda r: r['stream_id'])


def rename_group(kind, cat_id, current, provider_name):
    new = xbmcgui.Dialog().input('Group name (leave empty for "%s")' % provider_name,
                                 defaultt=current)
    if new is None:
        return False
    data = load()
    names = data['group_names'].setdefault(kind, {})
    new = new.strip()
    if not new or new == provider_name:
        names.pop(str(cat_id), None)
    else:
        names[str(cat_id)] = new
    _save(data)
    return True


def _move(ids, labels, moving, heading):
    """Ask where to put `moving`; returns the new id list or None."""
    others = [i for i in ids if i != moving]
    olabels = [labels[i] for i in others]
    choice = xbmcgui.Dialog().select(heading, ['[B]To the top[/B]'] + ['Above: %s' % l for l in olabels]
                                     + ['[B]To the bottom[/B]'])
    if choice < 0:
        return None
    if choice == 0:
        return [moving] + others
    if choice == len(others) + 1:
        return others + [moving]
    idx = choice - 1
    return others[:idx] + [moving] + others[idx:]


def move_group(kind, groups, cat_id):
    """groups: current list of dicts (id, name) in display order."""
    ids = [str(g['id']) for g in groups]
    labels = {str(g['id']): g['name'] for g in groups}
    new = _move(ids, labels, str(cat_id), 'Move "%s" to...' % labels.get(str(cat_id), ''))
    if new is None:
        return False
    data = load()
    data['group_order'][kind] = new
    _save(data)
    return True


def move_channel(cat_id, rows, stream_id):
    ids = [str(r['stream_id']) for r in rows]
    labels = {str(r['stream_id']): r['name'] for r in rows}
    new = _move(ids, labels, str(stream_id), 'Move "%s" to...' % labels.get(str(stream_id), ''))
    if new is None:
        return False
    if cat_id == 'fav':
        common.save_json('favourites.json', new)   # favourites keep their own order
    else:
        data = load()
        data['channel_order'][str(cat_id or '*')] = new
        _save(data)
    return True


def reset():
    _save({})
