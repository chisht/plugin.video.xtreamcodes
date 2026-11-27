import os, sys, tempfile, runpy
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc, xbmcplugin
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='true', epg_past_days='1', hide_adult='true', page_size='0', check_stream='false')
from resources.lib import sync
sync.run_sync('full')
asked=[]
xbmcgui.Dialog.input=lambda self,*a,**k: (asked.append(a[0] if a else ''), xbmcgui.Dialog.ANSWERS.pop(0) if xbmcgui.Dialog.ANSWERS else '')[1]
def run(q):
    xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear(); xbmcplugin.ITEMS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
    return [li.label for u,li,f in xbmcplugin.ITEMS]
print('root:', [l for l in run('?') if 'Search' in l], [u.split('?')[1] for u,li,f in xbmcplugin.ITEMS if 'Search' in li.label])
print('search menu (empty):', run('?action=search_menu&kind=all'))
xbmcgui.Dialog.ANSWERS=['news']; run('?action=search_new&kind=all'); print('new search -> keyboard asked:', len(asked), '| goes to:', xbmc.BUILTINS)
target=xbmc.BUILTINS[0][len('Container.Update('):-1].split('?',1)[1]
asked.clear(); print('results:', run('?'+target)); print('back after playing (results re-run) -> keyboard asked:', len(asked), '|', run('?'+target)[:2])
xbmcgui.Dialog.ANSWERS=['sport']; run('?action=search_new&kind=all'); xbmcgui.Dialog.ANSWERS=['NEWS']; run('?action=search_new&kind=all')
print('history (newest first, no duplicates):', run('?action=search_menu&kind=all'))
print('history item context:', [c[0] for c in xbmcplugin.ITEMS[1][1].ctx], '| opens:', xbmcplugin.ITEMS[1][0].split('?')[1], 'folder', xbmcplugin.ITEMS[1][2])
run('?action=search_del&kind=all&q=sport'); print('after removing "sport":', run('?action=search_menu&kind=all'))
xbmcgui.Dialog.ANSWERS=['show 1']; run('?action=search_new&kind=epg'); t2=xbmc.BUILTINS[0][len('Container.Update('):-1].split('?',1)[1]; print('guide search ->', t2, '|', run('?'+t2)[:2])
print('guide history separate:', run('?action=search_menu&kind=epg'))
xbmcgui.Dialog.ANSWERS=[True]; run('?action=search_clear&kind=all'); print('after clear all:', run('?action=search_menu&kind=all'), '| guide history kept:', run('?action=search_menu&kind=epg')[1:2])
asked.clear(); run('?action=search'); print('old shortcut without term -> keyboard asked:', len(asked), '| redirects:', xbmc.BUILTINS)
