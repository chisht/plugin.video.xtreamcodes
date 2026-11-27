import os, sys, tempfile, runpy, time
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fs, fake_tmdb, xbmcaddon, xbmcgui, xbmc, xbmcplugin
fs.VOD_LIST[:]=[
 {"name":"Alpha Movie (2010)","stream_id":601,"container_extension":"mkv","category_id":"10","tmdb":"1000","rating":"5"},   # by id
 {"name":"Bravo Movie (2011)","stream_id":602,"container_extension":"mp4","category_id":"10"},                              # by title
 {"name":"EN - Charlie Movie (2012)","stream_id":603,"container_extension":"mp4","category_id":"10"},                       # tag stripped
 {"name":"Le Film (2013)","stream_id":604,"container_extension":"mp4","category_id":"10"},                                  # original title
 {"name":"Bravo Movie (1960)","stream_id":605,"container_extension":"mp4","category_id":"10"},                              # wrong year: must not match
 {"name":"Movie 2005","stream_id":606,"container_extension":"mp4","category_id":"10"}]
fs.SERIES_LIST[:]=[{"name":"Beach Show","series_id":77,"cover":"c","plot":"p","releaseDate":"2020-05-01","rating":"8","category_id":"20","tmdb":"3000"}]
srv=fs.start(); tm=fake_tmdb.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', page_size='0', check_stream='false',
         tmdb_base='http://127.0.0.1:%d/3'%tm.server_address[1])
from resources.lib import sync
sync.run_sync('full')
def run(q):
    xbmcplugin.ITEMS.clear(); xbmcgui.DIALOGS.clear(); xbmc.BUILTINS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
    return [(li.label, u.split('?')[1] if '?' in u else '', li) for u,li,f in xbmcplugin.ITEMS]
S['tmdb_key']=''; xbmcgui.Dialog.ANSWERS[:] = [False]
run('?action=discover_menu&kind=all'); print('1. no key -> explains + nothing listed:', [d[0] for d in xbmcgui.DIALOGS], len(xbmcplugin.ITEMS))
S['tmdb_key']='wrong'; xbmcgui.Dialog.ANSWERS[:]=[]; run('?action=discover_list&kind=movie&src=popular'); print('2. wrong key ->', [d for d in xbmcgui.DIALOGS][:1])
S['tmdb_key']='abc123'
print('3. menu:', [l for l,_,_ in run('?action=discover_menu&kind=all')])
print('   movie menu:', [l for l,_,_ in run('?action=discover_menu&kind=movie')][:7])
items=run('?action=discover_list&kind=movie&src=popular')
print('4. popular (provider has 4 of the first 100 titles):')
for l,q,li in items: print('   ', l, '| rating/votes:', li.tag.d.get('rating'), '| poster:', li.art.get('poster','')[-8:], '| plays', q.split('&')[1] if 'play_vod' in q else q[:30])
print('   Bravo 1960 not matched:', not any('1960' in q for _,q,_ in items), '| "Movie 2005" (id 2005, year ok):', any('Movie 2005' in l for l,_,_ in items))
# --- paging, cache
n=len(fake_tmdb.HITS); items=run('?action=discover_list&kind=movie&src=popular&page=0'); print('5. same list again -> TMDb requests:', len(fake_tmdb.HITS)-n, '(cached)')
nxt=[q for l,q,_ in items if 'Next page' in l][0]; items2=run('?'+nxt); print('   page 2 (TMDb pages 6+): ', [l[-60:] for l,_,_ in items2][:3], '| more pages:', any('Next page' in l for l,_,_ in items2))
# --- series
items=run('?action=discover_list&kind=tv&src=trending'); print('6. series trending:', [(l, q.split('&')[0]) for l,q,_ in items])
# --- genre / decade
print('7. genres:', [l for l,_,_ in run('?action=discover_genres&kind=movie')], '| decades:', [l for l,_,_ in run('?action=discover_decades&kind=movie')][:3])
items=run('?action=discover_list&kind=movie&src=genre&genre=99'); print('   genre with nothing on provider ->', [l for l,_,_ in items])
print('   decade 2010s ->', len(run('?action=discover_list&kind=movie&src=decade&decade=2010')), 'items')
# --- more like this: by tmdb id, and by title when the provider has no id
print('8. similar (title lookup, no id):', [l[-45:] for l,_,_ in run('?action=discover_list&kind=movie&src=similar&title=Bravo+Movie&year=2011')])
# --- context menu entries on a normal movie list + info screens
vod=run('?action=vod_list&cat=10'); ctx=[c[0] for c in vod[0][2].ctx]; print('9. normal movie list context:', ctx)
run('?action=tm_info&kind=movie&tmdb=1000&title=Alpha'); d=[x for x in xbmcgui.DIALOGS if x[0]=='textviewer' or x[0].startswith('text')]; print('   ratings dialog:', xbmcgui.DIALOGS[-1][1:] if xbmcgui.DIALOGS else None)
run('?action=vod_info&id=601&tmdb=1000&title=Alpha+Movie+%282010%29&year=2010'); print('   movie information:', xbmcgui.DIALOGS[-1][2].split('\n')[:5])
# --- long read-access token (Bearer) and hidden groups
fake_tmdb.KEY='eyJlongtoken'; S['tmdb_key']='eyJlongtoken'
import shutil; shutil.rmtree(os.path.join(prof,'tmdb_cache'), ignore_errors=True)
print('10. read-access token ->', len(run('?action=discover_list&kind=movie&src=popular')), 'rows (Bearer header used, no api_key in URL:', all('api_key' not in h for h in fake_tmdb.HITS[-3:]), ')')
from resources.lib import common
common.save_hidden({'vod': {'10'}})
print('11. provider group hidden (Action) ->', [l for l,_,_ in run('?action=discover_list&kind=movie&src=popular')][:2])
