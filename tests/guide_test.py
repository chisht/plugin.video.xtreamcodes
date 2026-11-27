import os, sys, tempfile, time, json, runpy
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc, xbmcplugin
fake_server.DEAD.clear(); fake_server.HTMLERR.clear()
srv=fake_server.start(); S=xbmcaddon.SETTINGS; base='http://127.0.0.1:%d'%srv.server_address[1]
S.update(server=base, username='u', password='p@ss', epg_enable='true', epg_past_days='2', hide_adult='true', check_stream='true', check_timeout='3',
         zap_restart_key='true', catchup_pad='5', catchup_style='0', live_format='0', show_counts='false', tv_autoplay='false', zap_enable='true')
from resources.lib import sync, guide, playback, keymap, tvwindow
sync.run_sync('full')
P=xbmc.Player; A=xbmcgui.Action
w=guide.GuideWindow('x',ADDON,'default','1080i'); w.setup('*','102'); w.onInit()
def focused():
    r,i,p=w._current(); return '%s | %s' % (w.rows[w.offset+r]['name'], p['title'])
print('channels:', [w.getControl(120+i).label for i in range(4)], '| times:', [w.getControl(201+k).label for k in range(4)], w._props['day'])
print('buttons:', len(w.buttons), '| row widths:', [b.w for b,_ in w.cells[0]], '| now line:', w.getControl(300).pos)
print('focus at open:', focused(), '|', w._props['p_time'])
w.onAction(A(2)); print('right ->', focused()); w.onAction(A(2)); w.onAction(A(2)); w.onAction(A(2)); print('right x4 (window scrolled) ->', focused(), '| times now', w.getControl(201).label)
w.onAction(A(3)); print('up ->', focused()); w.onAction(A(1)); print('left ->', focused())
for _ in range(6): w.onAction(A(1))
print('left x6 (into the past) ->', focused(), '| colour:', [b.kw['textColor'] for b,p in w.cells[w.focus_row] if p['title'] in focused()][:1], '|', w._props['p_time'])
w.onClick(w.getFocusId()); print('OK on past archive programme ->', P.PLAYED[-1][0].split('|')[0].replace(base,''))
# jump to now and choose "from the beginning"
xbmcgui.Dialog.CTX = 1; w.onAction(A(117)); print('jump to now ->', focused())
r,i,p=w._current(); xbmcgui.Dialog.CTX = 1; w.onClick(w.getFocusId())
print('OK on NOW + "from the beginning" ->', P.PLAYED[-1][0].split('|')[0].replace(base,''), '| zap state:', playback.zap_state())
# recall: watch 101 live then 102 live, then 0
xbmcgui.Dialog.CTX = 0; w.onClick(w.getFocusId())   # watch live (current row channel)
r0=w.rows[w.offset+w.focus_row]['name']; w.onAction(A(4)); w.onClick(w.getFocusId()); r1=w.rows[w.offset+w.focus_row]['name']
P.FILE=P.PLAYED[-1][0]; print('watched', r0, 'then', r1, '| state prev:', playback.zap_state().get('prev'))
def run(q):
    xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
run('?action=zap&key=recall'); print('0 (recall) ->', P.PLAYED[-1][1]); P.FILE=P.PLAYED[-1][0]
run('?action=zap&key=recall'); print('0 again ->', P.PLAYED[-1][1]); P.FILE=P.PLAYED[-1][0]
# rewind on live catch-up channel -> confirm -> restart; Up during restart -> next live channel
xbmcgui.Dialog.ANSWERS=[True]; run('?action=zap&key=restart'); print('rewind on live', playback.zap_state()['id'], '->', P.PLAYED[-1][0].split('|')[0].replace(base,'')[:45], [d[:2] for d in xbmcgui.DIALOGS])
P.FILE=P.PLAYED[-1][0]; run('?action=zap&key=restart'); print('rewind while replaying ->', xbmc.BUILTINS)
run('?action=zap&key=up'); print('Up during restart ->', P.PLAYED[-1][1], P.PLAYED[-1][0].split('|')[0].replace(base,''))
# a movie playing: keys fall back
P.FILE=base+'/movie/u/p/555.mkv'; [run('?action=zap&key=%s'%k) or print('movie', k, '->', xbmc.BUILTINS) for k in ('restart','recall','guide')]
# plain catch-up from menu after a restart: Up/Down must not zap
xbmcgui.PROPS['plugin.video.xtreamcodes.zap']=json.dumps({'cat':'*','id':'101','mode':'restart'})
run('?action=play_catchup&id=101&start=2026-11-25 10:00:00&dur=60&title=X'); P.FILE=P.PLAYED[-1][0]; run('?action=zap&key=up'); print('Up during plain catch-up ->', xbmc.BUILTINS)
w.onAction(A(92)); print('guide closed:', w.closed)
# keymap content
S['zap_restart_key']='true'; keymap.apply(); km=open(keymap._path()).read(); print('keymap keys:', [k for k in ('<zero>','<guide>','<e>','<r>','<reverse>') if k in km])
S['zap_restart_key']='false'; keymap.apply(); km=open(keymap._path()).read(); print('restart key off ->', '<reverse>' in km, '<r>' in km)
# TV mode: 0 recall + Info opens guide
P.FILE=''; P.PLAYED.clear()
tv=tvwindow.TVWindow('x',ADDON,'default','1080i'); tv.onInit(); c=tv.getControl(200)
c.sel=0; tv.onClick(200); c.sel=2; tv.onClick(200); P.FILE=P.PLAYED[-1][0]
tv.onAction(A(58)); print('TV mode typed 0:', tv._props['digits_name']); time.sleep(2.3); print('-> recall played', P.PLAYED[-1][1], '| selected', tv.rows[c.sel]['name'])
import resources.lib.guide as G; opened=[]; G.open_guide=lambda cat, sel: opened.append((cat, sel))
tv.onAction(A(11)); print('Info in TV mode opens guide:', opened); tv.close()
