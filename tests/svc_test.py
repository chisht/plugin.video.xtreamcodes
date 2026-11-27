import os, sys, tempfile, runpy
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server, xbmcaddon, xbmc, xbmcgui
srv=fake_server.start()
xbmcaddon.SETTINGS.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='true', epg_past_days='1', bg_enable='true', refresh_hours='12', bg_notify='true')
ticks={'n':0}
def wait(self, t=0):
    ticks['n']+=1; return ticks['n']>4
xbmc.Monitor.waitForAbort=wait
g=runpy.run_path(ADDON+'/service.py')  # defines functions only
g['run']()
import json; st=json.load(open(prof+'/state.json')); print({k:(v if 'creds' not in k else v[:8]) for k,v in st.items()})
print(sorted(os.listdir(prof)), xbmcgui.DIALOGS)
