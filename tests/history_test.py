import os, sys, tempfile, json, time
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.DEAD.clear(); fake_server.HTMLERR.clear()
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='false',
         check_stream='true', check_timeout='3', tv_autoplay='true', tv_stop_on_exit='true', show_counts='false')
from resources.lib import sync, tvwindow, common
sync.run_sync('full'); P=xbmc.Player
def open_tv():
    w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); time.sleep(0.5); return w
def pick(w, name):
    c=w.getControl(200); c.sel=[r['name'] for r in w.rows].index(name); w.onClick(200)
# old version left a last_channel.json pointing at an adult channel
common.save_json('last_channel.json', {'cat':'*','id':'103'})
w=open_tv(); print('legacy file = adult channel -> autoplay:', P.PLAYED[-1][1] if P.PLAYED else None); w.close()
w=open_tv(); pick(w,'News One'); pick(w,'UK Ent'); pick(w,'Hot XXX'); print('last watched:', P.PLAYED[-1][1]); w.onAction(xbmcgui.Action(92))
print('history:', [(e['id'], e['adult']) for e in common.load_json('channel_history.json', [])])
P.PLAYED.clear(); w=open_tv(); print('reopen (adult shown) ->', P.PLAYED[-1][1], 'selected:', w.rows[w.getControl(200).sel]['name']); w.close()
S['hide_adult']='true'; P.PLAYED.clear(); w=open_tv(); print('reopen (adult hidden) ->', P.PLAYED[-1][1]); w.close()
# only adult in history -> nothing autoplays
common.save_json('channel_history.json', [{'cat':'3','id':'103','adult':True}]); os.remove(prof+'/last_channel.json') if os.path.exists(prof+'/last_channel.json') else None
S['hide_adult']='false'; P.PLAYED.clear(); w=open_tv(); print('only adult in history -> autoplay:', P.PLAYED); w.close()
