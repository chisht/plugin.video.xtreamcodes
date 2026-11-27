import os, sys, tempfile, json, runpy, time, threading, sqlite3
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof; ud=tempfile.mkdtemp()
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import xbmcvfs; xbmcvfs.translatePath=lambda p: p.replace('special://userdata', ud)
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc, xbmcplugin
fake_server.DEAD.clear(); fake_server.HTMLERR.clear()
srv=fake_server.start(); S=xbmcaddon.SETTINGS; base='http://127.0.0.1:%d'%srv.server_address[1]
S.update(server=base, username='u', password='p@ss', epg_enable='true', epg_past_days='2', hide_adult='true', check_stream='true', check_timeout='3', live_format='0',
         zap_enable='true', zap_restart_key='true', switch_stop_first='true', reminder_lead='1', page_size='0', show_counts='false')
from resources.lib import sync, playback, overlay, reminders, keymap, epg, common
overlay.BANNER_SECONDS=0.2; overlay.DIGIT_WAIT=0.4
sync.run_sync('full'); P=xbmc.Player
def run(q):
    xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear(); xbmcplugin.ITEMS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
    return [li.label for u,li,f in xbmcplugin.ITEMS]
notes=lambda: [d[2] for d in xbmcgui.DIALOGS if d[0]=='notify']
keymap.apply(); km=open(keymap._path()).read(); print('keymap has digits/info:', all(k in km for k in ('<one>','<nine>','<zero>','key=digit&amp;d=5','<info>','<i>')))
run('?action=play_live&id=101&cat=*'); P.FILE=P.PLAYED[-1][0]
xbmcgui.OVERLAYS.clear(); run('?action=zap&key=up'); b=xbmcgui.OVERLAYS[-1]
print('zap banner:', {k:b._props.get(k) for k in ('num','name','now','next','extra')}, 'bar', b.getControl(10).width, '| closed', b.closed, '| notifications:', notes())
P.FILE=P.PLAYED[-1][0]; xbmcgui.OVERLAYS.clear(); run('?action=zap&key=info'); print('info key banner:', xbmcgui.OVERLAYS[-1]._props.get('name'))
# fullscreen digits: single "7"
run('?action=zap&key=digit&d=7'); print('typed 7 -> number box', [o._props.get('digits') for o in xbmcgui.OVERLAYS if o._props.get('digits')][-1:], '-> playing', P.PLAYED[-1][1], '| banner', xbmcgui.OVERLAYS[-1]._props.get('name'))
P.FILE=P.PLAYED[-1][0]
# two quick presses "6" then "1" in separate "processes" -> first gives way, second looks up 61 (none)
xbmcgui.OVERLAYS.clear(); out=[]
t1=threading.Thread(target=lambda: out.append(('first', overlay.digit('6', lambda n: None)))); t1.start(); time.sleep(0.1)
r2=overlay.digit('1', lambda n: {'name':'Ch %d'%n}); t1.join(); print('6 then 1:', out, '| second ->', r2, '| boxes', [o._props.get('digits') for o in xbmcgui.OVERLAYS])
# lone 0 -> recall
n=len(P.PLAYED); run('?action=zap&key=digit&d=0'); print('lone 0 -> recall played', P.PLAYED[-1][1] if len(P.PLAYED)>n else None, '| banner extra', xbmcgui.OVERLAYS[-1]._props.get('extra'))
# movie playing: digits fall back to Kodi
P.FILE=base+'/movie/u/p/555.mkv'; run('?action=zap&key=digit&d=4'); print('digit during movie ->', xbmc.BUILTINS)
# sleep timer
P.FILE=P.PLAYED[-1][0]; xbmcgui.Dialog.ANSWERS=[2]; run('?action=sleep_timer'); at=reminders.sleep_at(); print('sleep 30 min -> stops in %.0f min' % ((at-time.time())/60), notes())
xbmcgui.PROPS[reminders.PROP_SLEEP]=str(time.time()+30); reminders.check_sleep(); print('1-minute warning:', notes()[-1:])
xbmcgui.PROPS[reminders.PROP_SLEEP]=str(time.time()-1); P.STOPPED=False; reminders.check_sleep(); print('timer reached -> stopped:', P.STOPPED, '| timer cleared:', not reminders.sleep_at())
xbmcgui.Dialog.ANSWERS=[7]; P.FILE=base+'/live/u/p%40ss/101.ts'; xbmcgui.PROPS['plugin.video.xtreamcodes.zap']=json.dumps({'cat':'*','id':'101'}); run('?action=sleep_timer'); print('end of programme ->', common.fmt_time(reminders.sleep_at()), notes())
# reminders via guide search and service firing
items=run('?action=search_epg&q=show 2'); print('guide search "show 2":', items[:4])
fut=[u for u,li,f in xbmcplugin.ITEMS if 'show 2 ' in li.label or li.label.split('  ')[1].endswith('show 2')][0] if xbmcplugin.ITEMS else None
u=[u for u,li,f in xbmcplugin.ITEMS if 'NOW' not in li.label and 'CATCH-UP' not in li.label][0]; run('?'+u.split('?',1)[1]); print('pick future programme ->', notes(), '| saved:', [(r['channel'], r['title']) for r in reminders.load()])
print('search again shows:', [l for l in run('?action=search_epg&q=show 2') if 'reminder' in l][:1])
r=reminders.load()[0]; r['start']=int(time.time())+30; r['stop']=r['start']+1800; common.save_json('reminders.json',[r])
due=reminders.take_due(1); print('due within 1 min:', [d['title'] for d in due], '| left:', reminders.load())
xbmcgui.Dialog.ANSWERS=[True]; n=len(P.PLAYED); reminders.fire(due[0]); print('reminder "Watch" ->', P.PLAYED[-1][1] if len(P.PLAYED)>n else None, [d[:2] for d in xbmcgui.DIALOGS if d[0]=='ask'][-1:])
# guide: future programme OK toggles reminder
from resources.lib import guide as G
w=G.GuideWindow('x',ADDON,'default','1080i'); w.setup('*','101'); w.onInit()
for _ in range(3): w.onAction(xbmcgui.Action(2))
r_,i_,p_=w._current(); w.onClick(w.getFocusId()); r_,i_,p_=w._current(); print('guide OK on future:', p_['title'], '| button label:', w.cells[r_][i_][0].label, '|', w._props['p_time'].split('|')[-1]); w.close()
# EPG offset: rebuild with +60 min shifts times
db=common.epg_path(); con=sqlite3.connect(db); s0=con.execute("select min(start) from programmes where channel='news1.uk'").fetchone()[0]; con.close()
xml=common.profile_file('x.xml'); open(xml,'w').write(fake_server.xmltv().decode()); epg.build_db(xml, db+'2', 2, offset_min=60)
con=sqlite3.connect(db+'2'); s1=con.execute("select min(start) from programmes where channel='news1.uk'").fetchone()[0]; con.close(); print('offset +60 min shifts start by', (s1-s0)//60, 'min')
# temp cleanup + clear cache keeps user data
open(common.profile_file('epg.db.dead.tmp'),'w').write('x'); open(common.profile_file('xmltv.xml.part'),'w').write('x'); print('temp files removed:', reminders.clean_temp_files())
common.save_json('favourites.json',['101']); xbmcgui.Dialog.ANSWERS=[True]; run('?action=clear_cache')
print('after clear cache:', sorted(os.listdir(prof)), '| request:', xbmcgui.PROPS.get(common.PROP_REQUEST), '|', notes())
