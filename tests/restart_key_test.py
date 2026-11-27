import os, sys, tempfile, json, runpy
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.DEAD.clear(); fake_server.HTMLERR.clear()
srv=fake_server.start(); S=xbmcaddon.SETTINGS; base='http://127.0.0.1:%d'%srv.server_address[1]
S.update(server=base, username='u', password='p@ss', epg_enable='false', hide_adult='true', check_stream='true', check_timeout='3', zap_restart_key='true', catchup_pad='5', live_format='0', zap_enable='true')
from resources.lib import sync, playback
sync.run_sync('full'); P=xbmc.Player
def run(q):
    xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
run('?action=play_live&id=101&cat=*'); P.FILE=P.PLAYED[-1][0]
xbmcgui.Dialog.ANSWERS=[False]; run('?action=zap&key=restart'); print('rewind, answer No ->', P.PLAYED[-1][0].split('|')[0].replace(base,''), [d[:2] for d in xbmcgui.DIALOGS])
xbmcgui.Dialog.ANSWERS=[True]; run('?action=zap&key=restart'); print('rewind, answer Yes ->', P.PLAYED[-1][0].split('|')[0].replace(base,''), '| mode:', playback.zap_state().get('mode'))
P.FILE=P.PLAYED[-1][0]; run('?action=zap&key=restart'); print('rewind again while replaying ->', xbmc.BUILTINS)
run('?action=zap&key=up'); print('Up while replaying ->', P.PLAYED[-1][1], '| mode now:', playback.zap_state().get('mode'))
run('?action=restart&id=101&cat=*'); print('list-mode "Watch from the beginning" ->', P.PLAYED[-1][0].split('|')[0].replace(base,'')[:40])
