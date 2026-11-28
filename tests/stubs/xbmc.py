LOGINFO, LOGWARNING, LOGERROR, LOGDEBUG = 1, 2, 3, 0
LOG = []
def log(msg, level=1): LOG.append(msg)
WINDOWS = {'System.CurrentWindow': 'FullScreenVideo', 'Container.FolderPath': ''}
def getInfoLabel(l):
    return WINDOWS.get(l, '')
class Actor:
    def __init__(self, name='', *a): self.name = name
class Monitor:
    def abortRequested(self): return False
    def waitForAbort(self, t=0): return False
BUILTINS = []
def executebuiltin(c, wait=False): BUILTINS.append(c)
class Player:
    FILE = ''; PLAYED = []
    def isPlayingVideo(self): return bool(Player.FILE)
    def getPlayingFile(self): return Player.FILE
    def play(self, item='', listitem=None, windowed=False, startpos=-1):
        Player.FILE = item; Player.PLAYED.append((item, listitem.label if listitem else '', windowed))
Player.isPlaying = lambda self: bool(Player.FILE)
def _stop(self): Player.FILE = ''; Player.STOPPED = True
Player.stop = _stop
Player.TIME = 0.0; Player.TOTAL = 0.0
Player.getTime = lambda self: Player.TIME
Player.getTotalTime = lambda self: Player.TOTAL
# Window.IsActive(fullscreenvideo): None = follow Player.isPlayingVideo() (what most
# tests mean by "the picture is up"); a test can set .on to model a stream that plays
# with no picture on screen (started from a list, then Back out of fullscreen).
class _Fullscreen:
    on = None
FULLSCREEN = _Fullscreen()
def getCondVisibility(c):
    if 'fullscreenvideo' in c:
        return Player().isPlayingVideo() if FULLSCREEN.on is None else bool(FULLSCREEN.on)
    return False
