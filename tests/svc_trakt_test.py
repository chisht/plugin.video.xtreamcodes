import os, sys, tempfile, runpy
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_trakt_xc as fake_server, fake_trakt, xbmcaddon, xbmc
srv=fake_server.start(); tsrv=fake_trakt.start()
xbmcaddon.SETTINGS.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', bg_enable='true', refresh_hours='12', trakt_client_id='CID', trakt_client_secret='S')
from resources.lib import trakt, common
trakt.API='http://127.0.0.1:%d'%tsrv.server_address[1]
common.save_json('trakt_token.json', {'access_token':'tok1','refresh_token':'r','expires_in':86400,'created_at':__import__('time').time()})
ticks={'n':0}
def wait(self, t=0): ticks['n']+=1; return ticks['n']>3
xbmc.Monitor.waitForAbort=wait
g=runpy.run_path(ADDON+'/service.py'); g['run']()
print('service synced Trakt:', bool(common.load_state().get('trakt_sync')), '| shows cached:', len(common.load_json('trakt_watched.json',{}).get('shows',[])))
