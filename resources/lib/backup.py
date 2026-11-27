# -*- coding: utf-8 -*-
"""Backup and restore of your own data and the add-on settings."""
import json
import os
import time
import xml.etree.ElementTree as ET

import xbmcgui
import xbmcvfs

from . import common

USER_FILES = ('favourites.json', 'hidden_groups.json', 'customize.json', 'channel_history.json',
              'reminders.json', 'library.json', 'continue_watching.json')


def _settings():
    """Current settings as {id: value}, read from the add-on's settings file."""
    path = os.path.join(common.PROFILE, 'settings.xml')
    out = {}
    try:
        for node in ET.parse(path).getroot().iter('setting'):
            if node.get('id'):
                out[node.get('id')] = node.text or ''
    except (OSError, ET.ParseError):
        pass
    return out


def create():
    folder = xbmcgui.Dialog().browse(3, 'Save the backup in...', 'files')
    if not folder:
        return False
    data = {'addon': common.ADDON_ID, 'created': time.strftime('%Y-%m-%d %H:%M'),
            'settings': _settings(), 'files': {}}
    for name in USER_FILES:
        value = common.load_json(name, None)
        if value is not None:
            data['files'][name] = value
    name = 'xtreamcodes-backup-%s.json' % time.strftime('%Y%m%d-%H%M')
    target = os.path.join(xbmcvfs.translatePath(folder), name)
    try:
        with open(target, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=1)
    except OSError:
        # Network folders (smb:// etc.) need Kodi's own file layer.
        f = xbmcvfs.File(folder.rstrip('/') + '/' + name, 'w')
        f.write(json.dumps(data, indent=1))
        f.close()
    xbmcgui.Dialog().ok('Backup', 'Saved as %s[CR][CR]It includes your login details: keep it '
                        'somewhere private.' % name)
    return True


def restore():
    path = xbmcgui.Dialog().browse(1, 'Choose a backup file', 'files', '.json')
    if not path:
        return False
    try:
        f = xbmcvfs.File(path)
        data = json.loads(f.read())
        f.close()
    except (ValueError, OSError):
        data = None
    if not isinstance(data, dict) or data.get('addon') != common.ADDON_ID:
        xbmcgui.Dialog().ok('Restore', 'That file is not a backup from this add-on.')
        return False
    if not xbmcgui.Dialog().yesno('Restore', 'Restore the backup from %s?[CR]Your current '
                                  'favourites, groups, order and settings are replaced.'
                                  % data.get('created', '?')):
        return False
    addon = common.addon()
    for key, value in (data.get('settings') or {}).items():
        try:
            addon.setSetting(key, value)
        except Exception:
            pass
    for name, value in (data.get('files') or {}).items():
        if name in USER_FILES:
            common.save_json(name, value)
    common.notify('Backup restored', 3000)
    return True
