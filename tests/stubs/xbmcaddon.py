import os
SETTINGS = {}
class Addon:
    def __init__(self, id=None): pass
    def getAddonInfo(self, k):
        return {'name':'Xtream Codes IPTV','path':os.environ['ADDON_DIR'],'profile':os.environ['PROFILE_DIR']}[k]
    def getSetting(self, k): return SETTINGS.get(k, '')
    def openSettings(self): pass
def _set(self, k, v): SETTINGS[k] = v
Addon.setSetting = _set
