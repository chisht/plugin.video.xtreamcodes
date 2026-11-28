"""Skin setting: the add-on's own windows come from resources/skins/<skin>/.

Checks the theme colours the Python code puts in list labels, the skin folder
picked for STBEmu (and the fallback when it is missing), which layout files a
skin folder holds, and that every theme colour is a usable AARRGGBB string.

Run from the repo root: python3 tests/theme_test.py
"""
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import xbmcaddon, xbmcvfs   # noqa: E402  (stubs)
xbmcvfs.translatePath = lambda p: p.replace('special://userdata', tempfile.mkdtemp())
S = xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:1', username='u', password='p', hide_adult='true')

from resources.lib import common, theme   # noqa: E402
from resources.lib import guide, overlay, tvwindow   # noqa: E402

fails = 0


def check(name, ok):
    global fails
    fails += not ok
    print('%s %s' % ('PASS' if ok else 'FAIL', name))


def win_for(module, theme_obj):
    """A stub WindowXML with the properties the layout would read."""
    win = module.xbmcgui.WindowXML.__new__(module.xbmcgui.WindowXML)
    win._props = {}
    theme.apply(win, theme_obj)
    return win


# ---------------------------------------------------------------- palettes
for name, t in theme.THEMES.items():
    bad = [f for f in theme.FIELDS if not re.match(r'^[0-9A-Fa-f]{8}$', getattr(t, f))]
    check('theme %s: every colour is AARRGGBB' % name, not bad)
check('two skins in the settings list: %s' % ([n for n, _ in theme.SKINS],),
      [n for n, _ in theme.SKINS] == ['default', 'stbemu'])
check('the settings option values match the skins',
      theme.BY_SETTING['0'] == 'default' and theme.BY_SETTING['1'] == 'stbemu'
      and theme.BY_SETTING[''] == 'default')

# ------------------------------------------------------- the selected theme
check('unset setting -> default', theme.current(reload=True) is theme.DEFAULT)
S['skin'] = '1'
check('skin=STBEmu -> the STBEmu palette', theme.current(reload=True) is theme.STBEMU)
check('skin_dir follows the theme', theme.skin_dir(theme.STBEMU) == 'stbemu')
S['skin'] = '0'
check('skin=default -> default folder', theme.skin_dir(theme.current(reload=True)) == 'default')

# the folder picked for a skin (a missing folder falls back to the default layouts)
check('the default skin uses the default folder', theme.skin_dir(theme.DEFAULT) == 'default')
check("the add-on's own stbemu folder is used", theme.skin_dir(theme.STBEMU) == 'stbemu')
real_isdir = os.path.isdir
os.path.isdir = lambda p: 'stbemu' not in p        # pretend the folder is missing
check('folder missing -> default layouts', theme.skin_dir(theme.STBEMU) == 'default')
os.path.isdir = real_isdir
theme._CACHE.clear()

# colours in labels follow the theme
S['skin'] = '1'; theme.current(reload=True)
check('the favourite marker is plain text markup: %s' % common.star(),
      common.star() == '[B]\u2022[/B] ' and '\u2605' not in common.star())
check('offline text uses the theme colour', common.dim('x') == '[COLOR %s]x[/COLOR]' % theme.STBEMU.dim)
S['skin'] = '0'; theme.current(reload=True)
check('and follows it back to default', common.dim('x') == '[COLOR %s]x[/COLOR]' % theme.DEFAULT.dim)

# ...and no label uses a character the skins' fonts cannot draw. Kodi renders a
# list label with the skin's font (Roboto in most skins, Noto in Estuary), so a
# symbol missing from the font shows as an empty box. '\u2605' (star) is such a
# symbol: Roboto has no star, the bullets and arrows below it does have.
FONT_SAFE = '\u2022\u00b7\u2026\u00bb\u00ab\u00d7\u2192'   # bullet, middot, ellipsis, guillemets, times, arrow
extra = {}
for rel in ['main.py', 'service.py'] + ['resources/lib/' + f for f in os.listdir(os.path.join(ADDON, 'resources', 'lib'))
                                        if f.endswith('.py')]:
    text = open(os.path.join(ADDON, rel), encoding='utf-8').read()
    for ch in set(text):
        if ord(ch) > 127 and ch not in FONT_SAFE:
            extra.setdefault(ch, []).append(rel)
for skin in [n for n, _ in theme.SKINS]:
    folder = os.path.join(ADDON, 'resources', 'skins', skin, '1080i')
    for f in os.listdir(folder):
        text = open(os.path.join(folder, f), encoding='utf-8').read()
        for ch in set(text):
            if ord(ch) > 127 and ch not in FONT_SAFE:
                extra.setdefault(ch, []).append('%s/%s' % (skin, f))
check('labels and layouts only use characters the fonts have%s'
      % (': ' + ', '.join('U+%04X in %s' % (ord(c), v[0]) for c, v in extra.items()) if extra else ''),
      not extra)

# the windows draw the colours themselves: no colour markup in their labels
S['skin'] = '1'; theme.current(reload=True)
t = theme.current()
win = win_for(tvwindow, t)
fake = tvwindow.TVWindow.__new__(tvwindow.TVWindow)
fake.rows = [{'stream_id': '1', 'num': 5, 'name': 'Channel'}]
fake._favs = set()
check('tv mode: channel names are plain for the theme layouts (no markup)',
      '[COLOR' not in fake._name(0) and fake._name(0) == '5  Channel')
check('banner markup helper says plain labels', theme.markup() is False)
check('window properties carry the palette (%s)' % win._props.get('accent'),
      win._props['accent'] == 'FFE08A1E' and win._props['menu_bg'] == 'FF000000'
      and win._props['dim'] == 'FF6E6E6E')

# no colours left hard-coded in the code that builds labels for our own windows
for src in ('tvwindow.py', 'guide.py'):
    text = open(os.path.join(ADDON, 'resources', 'lib', src), encoding='utf-8').read()
    stale = [c for c in ('FF5A6478', 'FF2A6FDB', 'FF0B0F18', 'FF111827', 'FFFF9F1C') if c in text]
    check('%s: colours come from the theme, not from constants %s' % (src, stale or ''),
          not stale)

# ------------------------------------------------------ skin layout folders
WINDOWS = {'1080i': ('script-xtreamcodes-tv.xml', 'script-xtreamcodes-guide.xml',
                     'script-xtreamcodes-banner.xml')}
MEDIA = ('white.png', 'guide_btn.png', 'guide_now.png', 'guide_focus.png')
for skin in [n for n, _ in theme.SKINS]:
    folder = os.path.join(ADDON, 'resources', 'skins', skin)
    check('%s: has 1080i layouts and media' % skin,
          all(os.path.exists(os.path.join(folder, '1080i', f)) for f in WINDOWS['1080i'])
          and all(os.path.exists(os.path.join(folder, 'media', f)) for f in MEDIA))
    for f in WINDOWS['1080i']:
        try:
            ET.parse(os.path.join(folder, '1080i', f))
            ok = True
        except ET.ParseError:
            ok = False
        check('%s/%s is valid XML' % (skin, f), ok)

# the layouts must hold the control ids the code looks for
IDS = {'script-xtreamcodes-tv.xml': {100, 101, 200, 201, 300, 405, 406, 500},
       'script-xtreamcodes-guide.xml': {110, 120, 201, 300, 9000},
       'script-xtreamcodes-banner.xml': {10}}
for skin in [n for n, _ in theme.SKINS]:
    for f, needed in IDS.items():
        ids = {int(c.get('id')) for c in
               ET.parse(os.path.join(ADDON, 'resources', 'skins', skin, '1080i', f)).getroot().iter()
               if c.get('id') and c.get('id').isdigit()}
        check('%s/%s has the controls the code uses (%s)' % (skin, f, sorted(needed)),
              needed <= ids)

# ...and the STBEmu guide must put the blocks where guide.py does
g = ET.parse(os.path.join(ADDON, 'resources', 'skins', 'stbemu', '1080i',
                          'script-xtreamcodes-guide.xml')).getroot()
pos = {c.get('id'): (int(c.findtext('left') or -1), int(c.findtext('top') or -1))
       for c in g.iter() if c.get('id') in ('110', '201', '300')}
check('STBEmu guide: first channel row where guide.py draws it (%s)' % (pos.get('110'),),
      pos.get('110') == (30, guide.Y0 + 16))
check('STBEmu guide: time columns start where guide.py draws them',
      pos.get('201')[0] == guide.X0 + 8)

# the banner is read by overlay.py with the theme's folder
banner = overlay._Overlay.__new__(overlay._Overlay)
banner._props = {}
banner._theme = theme.current()
check('banner window gets the skin folder name',
      overlay.theme.BANNER_XML == 'script-xtreamcodes-banner.xml')

# ------------------------------------------------------------ image media
for skin in [n for n, _ in theme.SKINS]:
    media = os.path.join(ADDON, 'resources', 'skins', skin, 'media')
    for f in MEDIA:
        head = open(os.path.join(media, f), 'rb').read(8)
        check('%s/%s is a PNG' % (skin, f), head == b'\x89PNG\r\n\x1a\n')

sys.exit(1 if fails else 0)
