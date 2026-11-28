# -*- coding: utf-8 -*-
"""Look of the add-on's own screens: TV mode, the grid guide and the channel
banner.

Every colour and the skin folder the layouts are loaded from live here, so a skin
is a palette plus a folder of window layouts under resources/skins/. Settings >
Display > Skin picks one:

  default   the add-on's own dark blue look, with the layouts it always had
  stbemu    the look of STBEmu (Stalker portal / Ministra middleware) on Android:
            black and orange, a wider channel bar, a smaller video window.

Colours are only read once per process (a settings read is ~0.1 s on a slow box),
so screens should take `t = theme.current()` once and use `t.accent` etc.
"""
import os

SKIN_DEFAULT, SKIN_STBEMU = 'default', 'stbemu'
SKINS = ((SKIN_DEFAULT, 'Default (dark blue)'),
         (SKIN_STBEMU, 'STBEmu / Stalker portal (grey + orange)'))
# Setting ids (settings.xml 'skin'): 0 = default, 1 = STBEmu
BY_SETTING = {'0': SKIN_DEFAULT, '1': SKIN_STBEMU, '': SKIN_DEFAULT}

# Names of the window layouts (the same in every skin folder).
TV_XML = 'script-xtreamcodes-tv.xml'
GUIDE_XML = 'script-xtreamcodes-guide.xml'
BANNER_XML = 'script-xtreamcodes-banner.xml'
COVER_XML = 'script-xtreamcodes-cover.xml'

FIELDS = ('menu_bg', 'sel_bg', 'sel_mark', 'panel', 'head_bg', 'accent', 'playing',
          'catchup', 'fav', 'dim', 'grey', 'text', 'text_sel')


class Theme(object):
    """A palette of Kodi AARRGGBB colours."""

    def __init__(self, name, label, **kw):
        self.name = name
        self.label = label
        for key in FIELDS:
            setattr(self, key, kw[key])


DEFAULT = Theme(
    SKIN_DEFAULT, 'Default',
    menu_bg='FF0B0F18', panel='FF111827', head_bg='FF111827',
    sel_bg='FF2A6FDB', sel_mark='FF4FA3FF',
    accent='FF4FA3FF', playing='FFFF9F1C', catchup='FFFFC27A',
    fav='FFFFC107', dim='FF5A6478', grey='FF8A94A8',
    text='FFE6EAF2', text_sel='FFFFFFFF')

STBEMU = Theme(
    SKIN_STBEMU, 'STBEmu',
    menu_bg='FF000000', panel='FF141414', head_bg='FF0A0A0A',
    sel_bg='FFE08A1E', sel_mark='FFE08A1E',
    accent='FFE08A1E', playing='FFE08A1E', catchup='FFE0C07A',
    fav='FFFFC107', dim='FF6E6E6E', grey='FFB8B8B8',
    text='FFE6E6E6', text_sel='FF1A1A1A')

THEMES = {DEFAULT.name: DEFAULT, STBEMU.name: STBEMU}

_CACHE = {}


def setting_skin():
    from . import common
    return common.setting('skin').strip()


def current(reload=False):
    """The theme chosen in the settings, read once per process."""
    if reload or 'theme' not in _CACHE:
        from . import common
        name = BY_SETTING.get(setting_skin(), SKIN_DEFAULT)
        _CACHE['theme'] = THEMES.get(name, DEFAULT)
    return _CACHE['theme']


def name():
    return current().name


def skin_dir(theme_obj=None):
    """Folder under resources/skins/ holding the window layouts.

    The default skin is the `default` folder; every other skin is its own folder,
    named after the theme (so a new skin is a new folder, nothing to code). If the
    folder is missing (an incomplete install) the default layouts are used, so the
    add-on still opens.
    """
    from . import common
    t = theme_obj or current()
    if t.name == SKIN_DEFAULT:
        return SKIN_DEFAULT
    if os.path.isdir(os.path.join(common.ADDON_PATH, 'resources', 'skins', t.name)):
        return t.name
    return SKIN_DEFAULT


def markup():
    """The add-on's own windows draw list labels in the theme's colours, so Python
    keeps labels plain there; in Kodi's own lists the colour goes in the label."""
    return False


def apply(win, theme_obj=None):
    """Give a window the palette as window properties: our layouts read a few of
    them (the guide's headings), and it makes the colours inspectable in a log."""
    t = theme_obj or current()
    for key in FIELDS:
        try:
            win.setProperty(key, getattr(t, key))
        except Exception:
            pass


# short cuts used where a colour goes into a label
def dim(theme_obj=None):
    return (theme_obj or current()).dim


def grey(theme_obj=None):
    return (theme_obj or current()).grey


def accent(theme_obj=None):
    return (theme_obj or current()).accent


def catchup(theme_obj=None):
    return (theme_obj or current()).catchup


def fav(theme_obj=None):
    return (theme_obj or current()).fav


def playing(theme_obj=None):
    return (theme_obj or current()).playing
