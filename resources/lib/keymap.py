# -*- coding: utf-8 -*-
"""Keymap for fullscreen live TV.

Up/Down and CH+/CH- change channel, number keys tune (0 alone recalls the previous
channel), Info shows the channel banner, Guide opens the grid guide and Rewind
restarts the current show.

Every key only calls the add-on's 'zap' action, which checks whether one of this
add-on's live channels is playing. If not, it performs what the key did before:
the mapping from another add-on's keymap if there was one (Xstream Pro, Keymap
Editor, ...), otherwise Kodi's normal action. Kodi loads keymaps alphabetically
and the last one wins, so this file is named to load last.
"""
import glob
import os
import urllib.parse
import xml.etree.ElementTree as ET

import xbmc
import xbmcvfs

from . import common

KEYMAP_DIR = 'special://userdata/keymaps/'
FILENAME = 'zz_%s.xml' % common.ADDON_ID          # sorts after other keymaps
OLD_FILENAMES = ('%s.xml' % common.ADDON_ID,)     # versions up to 1.11
ZAP = 'RunPlugin(plugin://%s/?action=zap&amp;key=%s%s)'

DIGIT_NAMES = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine')
NUMPAD_NAMES = tuple('numpad' + n for n in DIGIT_NAMES)


def _keys(restart):
    """(section, key name, zap key) for every mapped button."""
    keys = [('keyboard', 'up', 'up'), ('keyboard', 'down', 'down'),
            ('keyboard', 'pageup', 'chup'), ('keyboard', 'pagedown', 'chdown'),
            ('keyboard', 'i', 'info'), ('keyboard', 'e', 'guide'),
            ('remote', 'up', 'up'), ('remote', 'down', 'down'),
            ('remote', 'pageplus', 'chup'), ('remote', 'pageminus', 'chdown'),
            ('remote', 'info', 'info'), ('remote', 'guide', 'guide')]
    for i, name in enumerate(DIGIT_NAMES):
        keys += [('keyboard', name, 'digit&amp;d=%d' % i), ('remote', name, 'digit&amp;d=%d' % i)]
    for i, name in enumerate(NUMPAD_NAMES):   # some CEC/IR remotes send keypad digits
        keys.append(('keyboard', name, 'digit&amp;d=%d' % i))
    if restart:
        keys += [('keyboard', 'r', 'restart'), ('remote', 'reverse', 'restart')]
    return keys


def _dir():
    return xbmcvfs.translatePath(KEYMAP_DIR)


def _path():
    return os.path.join(_dir(), FILENAME)


def other_mappings():
    """FullscreenVideo mappings from the user's other keymaps, as Kodi would resolve them."""
    found = {}
    for path in sorted(glob.glob(os.path.join(_dir(), '*.xml'))):
        name = os.path.basename(path)
        if name == FILENAME or name in OLD_FILENAMES:
            continue
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for window in root:
            if window.tag.lower() != 'fullscreenvideo':
                continue
            for section in window:
                for key in section:
                    if key.attrib.get('mod') or not (key.text or '').strip():
                        continue
                    found[(section.tag.lower(), key.tag.lower())] = key.text.strip()
    return found


def build(restart):
    others = other_mappings()
    sections = {'keyboard': [], 'remote': []}
    for section, name, zap in _keys(restart):
        fb = others.get((section, name))
        extra = '&amp;fb=%s' % urllib.parse.quote(fb, safe='') if fb else ''
        sections[section].append('      <%s>%s</%s>' % (name, ZAP % (common.ADDON_ID, zap, extra), name))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!-- Created by %s. Turn off "Up/Down changes channel" in its settings to remove. -->\n'
            '<keymap>\n  <FullscreenVideo>\n    <keyboard>\n%s\n    </keyboard>\n'
            '    <remote>\n%s\n    </remote>\n  </FullscreenVideo>\n</keymap>\n'
            % (common.ADDON_NAME, '\n'.join(sections['keyboard']), '\n'.join(sections['remote'])))


def apply():
    """Write or remove the keymap to match the setting. Returns True if changed."""
    changed = False
    for old in OLD_FILENAMES:
        old_path = os.path.join(_dir(), old)
        if os.path.exists(old_path):
            os.remove(old_path)
            changed = True
    path = _path()
    if common.setting_bool('zap_enable'):
        content = build(common.setting_bool('zap_restart_key'))
        try:
            with open(path, 'r', encoding='utf-8') as f:
                same = f.read() == content
        except OSError:
            same = False
        if not same:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            common.log('Channel-switch keymap installed: %s' % path)
            changed = True
    elif os.path.exists(path):
        os.remove(path)
        common.log('Channel-switch keymap removed')
        changed = True
    if changed:
        xbmc.executebuiltin('Action(reloadkeymaps)')
    return changed
