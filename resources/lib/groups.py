# -*- coding: utf-8 -*-
"""Hiding channel/movie/series groups (e.g. other countries or languages)."""
import re

import xbmcgui

from . import common
from .catalog import Catalog

KINDS = [('live', 'Live TV groups'), ('vod', 'Movie categories'), ('series', 'Series categories')]
_LEAD = re.compile(r'^[^0-9A-Za-z]+')


def _norm(name):
    return _LEAD.sub('', name or '').upper()


def _terms(text):
    return [t.strip().upper() for t in re.split(r'[,;]', text or '') if t.strip()]


def hide_group(kind, cat_id):
    hidden = common.load_hidden()
    hidden.setdefault(kind, set()).add(str(cat_id))
    common.save_hidden(hidden)


def manage(kind=None):
    """Dialog flow. Returns True if anything changed."""
    dialog = xbmcgui.Dialog()
    if kind is None:
        idx = dialog.select('Show/hide groups', [label for _, label in KINDS])
        if idx < 0:
            return False
        kind = KINDS[idx][0]
    cat = Catalog(common.catalog_path())
    if not cat.exists():
        common.notify('Channel list not loaded yet')
        return False
    groups = cat.categories(kind, include_hidden=True)
    cat.close()
    if not groups:
        common.notify('No groups found')
        return False
    hidden = common.load_hidden()
    current = hidden.get(kind, set())
    ids = [g['id'] for g in groups]
    names = [g['name'] for g in groups]
    shown = len([i for i in ids if i not in current])

    choice = dialog.select('%s  (%d of %d shown)' % (dict(KINDS)[kind], shown, len(ids)), [
        'Pick which groups to show...',
        'Show only groups starting with... (e.g. UK, US, CA)',
        'Hide groups containing a word...',
        'Show all groups',
    ])
    if choice < 0:
        return False
    if choice == 0:
        pre = [i for i, gid in enumerate(ids) if gid not in current]
        sel = dialog.multiselect('Groups to show', names, preselect=pre)
        if sel is None:
            return False
        new_hidden = {gid for i, gid in enumerate(ids) if i not in sel}
    elif choice == 1:
        text = dialog.input('Prefixes to keep, separated by commas (e.g. UK, US, CA)')
        terms = _terms(text)
        if not terms:
            return False
        new_hidden = {gid for gid, name in zip(ids, names)
                      if not any(_norm(name).startswith(t) for t in terms)}
        keep = len(ids) - len(new_hidden)
        if keep == 0:
            dialog.ok(common.ADDON_NAME, 'No group starts with %s. Nothing changed.' % ', '.join(terms))
            return False
        if not dialog.yesno(common.ADDON_NAME, 'Show %d groups and hide the other %d?'
                            % (keep, len(new_hidden))):
            return False
    elif choice == 2:
        text = dialog.input('Words to hide, separated by commas (e.g. ARABIC, |FR|)')
        terms = _terms(text)
        if not terms:
            return False
        matches = {gid for gid, name in zip(ids, names)
                   if any(t in (name or '').upper() for t in terms)}
        if not matches:
            dialog.ok(common.ADDON_NAME, 'No group contains %s. Nothing changed.' % ', '.join(terms))
            return False
        new_hidden = set(current) | matches
        common.notify('Hid %d groups' % len(matches - set(current)), 3000)
    else:
        new_hidden = set()
    hidden[kind] = new_hidden
    common.save_hidden(hidden)
    return True
