import os, sys, runpy, tempfile, shutil, importlib
ADDON = '/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server, xbmcaddon, xbmcplugin, xbmcgui, xbmc
srv=fake_server.start(); port=srv.server_address[1]
xbmcaddon.SETTINGS.update(server='127.0.0.1:%d/player_api.php'%port, username='u', password='p@ss', timeout='10',
    show_epg_in_list='true', show_counts='true', page_size='1', epg_enable='true', hide_adult='true', epg_past_days='2', live_format='0', catchup_pad='5', catchup_style='0', bg_notify='true')
def run(q):
    xbmcplugin.ITEMS.clear(); xbmcplugin.RESOLVED.clear(); xbmcgui.DIALOGS.clear()
    sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]
    runpy.run_path(ADDON+'/main.py', run_name='__main__')
    return xbmcplugin.ITEMS
def show(title, items):
    print('==',title); [print('  ', 'D' if f else 'I', li.label, '|', li.tag.d.get('plot','')[:60].replace('\n',' / '), '|', u.split('?')[1][:90]) for u,li,f in items]
show('root', run('?'))
show('live cats (first run builds catalog)', run('?action=live_cats'))
print('request prop:', xbmcgui.PROPS)
# service-style sync
from resources.lib import sync
print('sync:', sync.run_sync('full', progress=lambda p,m: None))
print('profile files:', sorted(os.listdir(prof)))
show('live list News page0', run('?action=live_list&cat=1'))
show('live list News page1', run('?action=live_list&cat=1&page=1'))
show('all channels', run('?action=live_list&cat=*'))
show('guide archive ch (first 5)', run('?action=guide&id=101')[:5])
show('guide non-archive ch (first 3)', run('?action=guide&id=102')[:3])
show('catchup cats', run('?action=catchup_cats'))
show('catchup days', run('?action=catchup_days&id=101'))
items=run('?action=catchup_progs&id=101&day=%s'%__import__('datetime').date.today().isoformat()); show('catchup today (first 2)', items[:2])
run('?'+items[0][0].split('?')[1]); print('catchup URL:', xbmc.Player.PLAYED[-1][0])
run('?action=play_live&id=101'); print('live URL:', xbmc.Player.PLAYED[-1][0])
xbmcaddon.SETTINGS.update(live_format='1'); run('?action=play_live&id=101'); print('hls URL:', xbmc.Player.PLAYED[-1][0]); xbmcaddon.SETTINGS['live_format']='0'
xbmcaddon.SETTINGS.update(custom_ua_enable='true', custom_ua='MyUA/1.0'); run('?action=play_vod&id=555&ext=mkv'); print('vod URL:', xbmcplugin.RESOLVED[0][1].path); xbmcaddon.SETTINGS['custom_ua_enable']='false'
show('vod list', run('?action=vod_list&cat=10'))
run('?action=vod_info&id=555'); print('vod info:', xbmcgui.DIALOGS)
show('series list', run('?action=series_list&cat=20'))
show('seasons', run('?action=seasons&id=77'))
show('episodes', run('?action=episodes&id=77&season=1'))
show('search', run('?action=search'))
run('?action=account'); print(xbmcgui.DIALOGS[0][2])
run('?action=refresh'); print('refresh prop:', xbmcgui.PROPS, xbmcgui.DIALOGS)
print('UAs seen by server:', sorted(set(fake_server.SEEN_UA)))
xbmcaddon.SETTINGS['password']='bad'; os.remove(prof+'/catalog.db'); run('?action=live_cats'); print('bad login dialog:', xbmcgui.DIALOGS, 'ended:', xbmcplugin.ENDED[-1])
print('log:', [l for l in xbmc.LOG if 'fail' in l.lower() or 'error' in l.lower()])
