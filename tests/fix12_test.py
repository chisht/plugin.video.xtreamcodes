import os, sys, tempfile, time, json
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.DEAD.clear(); fake_server.HTMLERR.clear()
N=40187
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"ch%d"%(i%300),"category_id":str(1+i%40),"tv_archive":0} for i in range(N)]
fake_server.LIVE_EXTRA[:] = []
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', check_stream='false',
         tv_autoplay='false', mark_offline='true', show_counts='false', zap_recover='true', switch_stop_first='true')
from resources.lib import sync, tvwindow, playback, common
sync.run_sync('full'); P=xbmc.Player
t=time.time(); w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); el=time.time()-t
c=w.getControl(200)
print('open: %.2fs | rows %d | items in list %d | first/last: %s / %s' % (el, len(w.rows), c.size(), c.items[0].label, c.items[-1].label))
# scroll to the bottom sentinel -> window moves on
c.sel=c.size()-1; time.sleep(0.6); print('after reaching "[ more ]": list now starts', c.items[1].label if w.top_more else c.items[0].label, '| selected', c.items[c.sel].label)
# number entry far away (channel 38000)
w._digit(3); w._digit(8); w._digit(0); w._digit(0); w._digit(0); w._digit_timer.cancel(); w._digit_go()
print('typed 38000 -> selected', c.items[c.sel].label, '| playing', P.PLAYED[-1][1])
# cursor follows a channel tuned elsewhere even when nothing plays (e.g. failed start in fullscreen)
P.FILE=''; xbmcgui.PROPS[common.PROP_ZAP]=json.dumps({'cat':'*','id':'5100','t':time.time()}); time.sleep(0.6)
print('tuned elsewhere to Channel 101 (not playing) -> cursor on', c.items[c.sel].label)
w.close()
# recovery: Channel 102 fails to start after watching Channel 101
playback.remember_zap('*','5100',row={'adult':0}); playback.remember_zap('*','5101',row={'adult':0})
rec=playback.LiveRecovery(); xbmc.BUILTINS.clear(); n=len(P.PLAYED)
rec.onPlayBackError(); print('1st failure -> retried:', P.PLAYED[-1][1], '| closed Kodi error box:', 'Dialog.Close(okdialog,true)' in xbmc.BUILTINS)
xbmcgui.DIALOGS.clear(); rec._acted=0; rec.onPlayBackError(); print('2nd failure -> back to:', P.PLAYED[-1][1], '| notice:', [d[2] for d in xbmcgui.DIALOGS if d[0]=='notify'], '| 102 marked offline:', playback.is_offline('5101'))
# a channel that started fine and ends later is left alone
playback.remember_zap('*','5102',row={'adult':0}); xbmcgui.PROPS[playback.PROP_LIVE_OK]='5102|%f'%(time.time()+2); rec._acted=0; n=len(P.PLAYED); rec.onPlayBackEnded(); print('ended after a good start -> replayed?', len(P.PLAYED)>n)
# windowed (TV mode) failures replay windowed
playback.remember_zap('*','5103',row={'adult':0}, windowed=True); rec._acted=0; rec.onPlayBackError(); print('TV-mode failure retried windowed:', P.PLAYED[-1][2])
