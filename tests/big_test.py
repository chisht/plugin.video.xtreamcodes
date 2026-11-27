import os, sys, tempfile, time, json
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.DEAD.clear(); fake_server.HTMLERR.clear()
N=20000
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%i,"stream_id":5000+i,"stream_icon":"","epg_channel_id":"ch%d"%(i%300),"category_id":str(1+i%40),"tv_archive":0} for i in range(N)]
fake_server.LIVE_EXTRA[:] = []
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true',
         check_stream='true', check_timeout='3', tv_autoplay='true', mark_offline='true', show_counts='true')
from resources.lib import sync, tvwindow, common, playback
sync.run_sync('full')
# a previous session: some channels marked offline, last channel watched
playback.set_offline('5003', True); common.save_json('channel_history.json', [{'cat':'*','id':'5010','adult':False}])
calls={'n':0}; orig=xbmcaddon.Addon.getSetting
def counting(self,k): calls['n']+=1; return orig(self,k)
xbmcaddon.Addon.getSetting=counting
t=time.time(); w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); el=time.time()-t
c=w.getControl(200)
print('onInit: %.2fs for %d channels, settings reads during open: %d' % (el, c.size(), calls['n']))
print('offline 5003 greyed:', [i.label for i in c.items if i.props.get('sid')=='5003'], 'playing mark on 5010:', [i.props.get('playing') for i in c.items if i.props.get('sid')=='5010']); print('labels filled at open:', sum(1 for i in c.items if i.l2 or i.props.get('offline')), '| offline item:', c.items[3].label)
time.sleep(0.8); print('autoplay started by worker ->', xbmc.Player.PLAYED[-1][1] if xbmc.Player.PLAYED else None, '| selected', c.sel, '| playing mark', c.items[10].props.get('playing'))
calls['n']=0; w._select_idx(15000); time.sleep(0.6); print('jump to row 15000 -> selected:', c.items[c.sel].label, 'settings reads:', calls['n'])
w.onAction(xbmcgui.Action(92)); print('back closes:', w.closed)
