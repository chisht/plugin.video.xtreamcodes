import os, sys, tempfile, json
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import xbmcaddon
from resources.lib import playback, common
playback.remember_zap('1', '101', row={'adult': 0})
for i in range(100):                      # 100 adult channel changes afterwards
    playback.remember_zap('3', str(1000 + i), row={'adult': 1})
h = common.load_json('channel_history.json', [])
print('entries kept:', len(h), '| adult:', sum(1 for e in h if e['adult']), '| newest normal:', [e['id'] for e in h if not e['adult']])
