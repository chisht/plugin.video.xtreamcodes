import os, sys, tempfile, json, runpy, urllib.parse, xml.etree.ElementTree as ET
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof; ud=tempfile.mkdtemp()
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import xbmcvfs; xbmcvfs.translatePath=lambda p: p.replace('special://userdata', ud)
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc, xbmcplugin
fake_server.DEAD.clear(); fake_server.HTMLERR.clear()
srv=fake_server.start(); S=xbmcaddon.SETTINGS; base='http://127.0.0.1:%d'%srv.server_address[1]
S.update(server=base, username='u', password='p@ss', epg_enable='false', zap_enable='true', zap_restart_key='true', check_stream='false', live_format='0')
km=os.path.join(ud,'keymaps'); os.makedirs(km)
open(os.path.join(km,'gen.xml'),'w').write('<keymap><FullscreenVideo><keyboard><zero>Number0</zero><f mod="ctrl">Noop</f></keyboard></FullscreenVideo></keymap>')
open(os.path.join(km,'xstream_pvr.xml'),'w').write('<keymap><FullscreenVideo><keyboard><zero>RunPlugin(plugin://plugin.video.xstream-pro/?mode=recall&amp;x=1)</zero><up>ChannelUp</up></keyboard><remote><zero>RunPlugin(plugin://plugin.video.xstream-pro/?mode=recall)</zero></remote></FullscreenVideo></keymap>')
open(os.path.join(km,'plugin.video.xtreamcodes.xml'),'w').write('<keymap/>')   # old name from v1.11
from resources.lib import keymap, sync, overlay
overlay.BANNER_SECONDS=0.1; overlay.DIGIT_WAIT=0.2
print('changed:', keymap.apply(), '| files now:', sorted(os.listdir(km)), '| reload:', xbmc.BUILTINS[-1:])
print('loads last:', sorted(os.listdir(km))[-1] == keymap.FILENAME)
root=ET.parse(keymap._path()).getroot()
kb={k.tag: k.text for k in root.find('FullscreenVideo/keyboard')}
print('keyboard keys:', len(kb), '| numpad zero mapped:', 'numpadzero' in kb, '| zero ->', kb['zero'][-95:])
print('up fallback ->', urllib.parse.parse_qs(kb['up'].split('?',1)[1].rstrip(')')).get('fb'))
print('down (no other mapping) has fb:', 'fb=' in kb['down'])
sync.run_sync('full'); P=xbmc.Player
def press(section, key):
    root=ET.parse(keymap._path()).getroot(); action=root.find('FullscreenVideo/%s/%s' % (section, key)).text
    q=action[action.index('?'):-1]; xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear()
    sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
# an Xstream Pro stream is playing: our keys hand over to Xstream Pro's mappings
P.FILE='http://other-provider/live/a/b/5.ts'
press('keyboard','zero'); print('Xstream stream, 0 ->', xbmc.BUILTINS)
press('remote','zero'); print('Xstream stream, remote 0 ->', xbmc.BUILTINS)
press('keyboard','up'); print('Xstream stream, Up ->', xbmc.BUILTINS)
press('keyboard','down'); print('Xstream stream, Down ->', xbmc.BUILTINS)
# our channels: 0 recalls
sys.argv=['plugin://plugin.video.xtreamcodes/','1','?action=play_live&id=101&cat=*']; runpy.run_path(ADDON+'/main.py', run_name='__main__'); P.FILE=P.PLAYED[-1][0]
sys.argv=['plugin://plugin.video.xtreamcodes/','1','?action=play_live&id=102&cat=*']; runpy.run_path(ADDON+'/main.py', run_name='__main__'); P.FILE=P.PLAYED[-1][0]
press('keyboard','zero'); print('our channel, 0 -> recall played:', P.PLAYED[-1][1]); P.FILE=P.PLAYED[-1][0]
press('keyboard','numpadzero'); print('our channel, keypad 0 -> recall played:', P.PLAYED[-1][1])
