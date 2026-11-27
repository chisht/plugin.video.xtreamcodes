import os, sys, tempfile, time, json
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
N=40187
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"ch%d"%(i%300),"category_id":str(1+i%1700),"tv_archive":0} for i in range(N)]
fake_server.LIVE_CATS[:]=[{"category_id":str(i),"category_name":"Group %d"%i} for i in range(1,1701)]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true',
         tv_autoplay='false', show_counts='true', zap_recover='true', check_stream='false')
from resources.lib import sync, tvwindow, playback, common, guide
sync.run_sync('full'); P=xbmc.Player
# 1. settings reads while opening TV mode
reads={'n':0}; orig=xbmcaddon.Addon.getSetting
def counting(self,k): reads['n']+=1; return orig(self,k)
xbmcaddon.Addon.getSetting=counting
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.cat_id='1'; w.onInit()
print('1. TV mode open with 1,700 groups -> setting reads:', reads['n'], '| groups:', len(w.groups))
xbmcaddon.Addon.getSetting=orig
# 2. back from fullscreen after zapping there: Kodi restores the old position; onInit fixes it
c=w.getControl(200); rows=w.rows
playback.remember_zap('1', rows[5]['stream_id'], row=rows[5]); P.FILE=w.base+'/live/u/p/%s.ts'%rows[5]['stream_id']; time.sleep(0.6)
playback.remember_zap('1', rows[9]['stream_id'], row=rows[9]); P.FILE=w.base+'/live/u/p/%s.ts'%rows[9]['stream_id']
c.selectItem(w._idx_to_pos(5))      # what Kodi restores when the window comes back
w.onInit(); print('2. back from fullscreen -> cursor on', c.items[c.sel].label.split('  ')[-1], '(expected', rows[9]['name']+')')
time.sleep(0.6); print('   still there after the worker ran:', c.items[c.sel].label.split('  ')[-1])
w.close()
# 3. late onAVStarted from the previous channel must not hide a failed start
rec=playback.LiveRecovery()
playback.remember_zap('*','5100',row={'adult':0}); time.sleep(0.05)
playback.remember_zap('*','5101',row={'adult':0})        # tuned; the previous channel's start arrives late:
xbmcgui.PROPS[playback.PROP_LIVE_OK]='5101|%f'%time.time()
n=len(P.PLAYED); rec.onPlayBackEnded()
print('3. failed start after a late callback -> retried:', len(P.PLAYED)>n and P.PLAYED[-1][1])
# 4. Kodi sends error + ended for one failure: only one retry, no jump back
st=playback.zap_state(); n=len(P.PLAYED); xbmcgui.DIALOGS.clear()
rec._acted=0; rec.onPlayBackError(); rec.onPlayBackEnded()
print('4. error+ended for the retry -> plays now:', [p[1] for p in P.PLAYED[n:]], '(one action: back to Channel 101)')
# 5. guide: first OK plays in the mini player, second goes fullscreen
g=guide.GuideWindow('x',ADDON,'default','1080i'); g.setup('1', None); g.onInit()
row=g.rows[2]; now=time.time(); p={'start':now-60,'stop':now+600,'title':'x','noinfo':True}
xbmc.BUILTINS.clear(); n=len(P.PLAYED)
g._select(0, p) if g.offset==0 and g.rows[0] is row else None
g.offset=2; g._select(0,p); first=P.PLAYED[-1]
P.FILE=g.catalog and playback.client().base+'/live/u/p/%s.ts'%row['stream_id']
g._select(0,p)
print('5. guide OK ->', first[1], 'windowed:', first[2], '| OK again -> fullscreen:', 'ActivateWindow(fullscreenvideo)' in xbmc.BUILTINS, '| replayed:', len(P.PLAYED)-n)
g.close()
