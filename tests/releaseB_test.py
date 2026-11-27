import os, sys, tempfile, json, runpy, time
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_b as fake_server, fake_trakt, xbmcaddon, xbmcgui, xbmc, xbmcplugin
srv=fake_server.start(); tsrv=fake_trakt.start(); S=xbmcaddon.SETTINGS; base='http://127.0.0.1:%d'%srv.server_address[1]
S.update(server=base, username='u', password='p@ss', epg_enable='false', hide_adult='true', page_size='0', show_counts='false', check_stream='false',
         trakt_client_id='CID', trakt_client_secret='S', trakt_scrobble='true', lib_auto_update='true')
from resources.lib import sync, trakt, watching, library, common
trakt.API='http://127.0.0.1:%d'%tsrv.server_address[1]
common.save_json('trakt_token.json', {'access_token':'tok1','refresh_token':'r','expires_in':86400,'created_at':time.time()})
sync.run_sync('full'); P=xbmc.Player
def run(q):
    xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear(); xbmcplugin.ITEMS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; g=runpy.run_path(ADDON+'/main.py', run_name='__main__')
    return [li.label for u,li,f in xbmcplugin.ITEMS]
clean=lambda l: [x.replace('[COLOR FF8A94A8]','').replace('[/COLOR]','') for x in l]
sc=trakt.Scrobbler()
def watch(q, upto, total=3000, end=False):
    run(q); P.FILE=xbmcplugin.RESOLVED[-1][1].path; P.TOTAL=total; P.TIME=10; sc.onAVStarted(); P.TIME=upto; sc.tick()
    sc.onPlayBackEnded() if end else sc.onPlayBackStopped()
print('recently added movies:', clean(run('?action=recent&kind=vod'))[:3])
print('recently updated series:', clean(run('?action=recent&kind=series'))[:3])
n=len(fake_trakt.LOG)
watch('?action=play_vod&id=601&ext=mp4&title=Unwatched Film (2019)&tmdb=777&icon=x.png', 1200)
eps=run('?action=episodes&id=78&season=1'); u=[u for u,li,f in xbmcplugin.ITEMS if li.label.startswith('Bag')][0]
watch('?'+u.split('?',1)[1], 600, 2400)
print('continue watching:', [(d['type'], d.get('name'), d['position']) for d in watching.load()])
print('root has entry:', [l for l in run('?') if 'Continue' in l], '| movies menu:', clean(run('?action=vod_cats'))[:3])
cw=clean(run('?action=continue')); print('continue list:', cw)
it=xbmcplugin.ITEMS[0][1]; print('resume point on item:', it.tag.d.get('resumepoint'), '| context:', [c[0] for c in it.ctx])
print('episode list label:', [l for l in clean(run('?action=episodes&id=78&season=1')) if 'watched' in l])
watch('?action=play_vod&id=601&ext=mp4&title=Unwatched Film (2019)&tmdb=777', 2950)
print('after finishing the movie:', [(d['type'], d.get('name')) for d in watching.load()])
print('trakt scrobbles sent:', len([1 for m,p,b,a,k in fake_trakt.LOG[n:] if p.startswith('/scrobble/')]))
# library
xbmcgui.Dialog.ANSWERS=[]; run('?action=lib_add&kind=vod&id=601'); print('lib movie:', [d[:2] for d in xbmcgui.DIALOGS][:2], '| scan:', xbmc.BUILTINS)
run('?action=lib_add&kind=series&id=78'); print('lib series:', [d[2] for d in xbmcgui.DIALOGS if d[0]=='notify'])
movies, shows = library.folders()
for root,dirs,files in os.walk(library.root()):
    for f in sorted(files): print('   ', os.path.relpath(os.path.join(root,f), library.root()), '->', open(os.path.join(root,f)).read().strip()[:110])
print('context now offers:', [c[0] for c in xbmcplugin.ITEMS[0][1].ctx] if run('?action=series_list&cat=*') else '', '|', [x for x in run('?action=vod_list&cat=*')][:1])
fake_server.EXTRA_EP.append({"id":"8104","episode_num":4,"title":"New one","container_extension":"mkv","season":1})
print('update_all adds new episode:', library.update_all(), os.path.exists(os.path.join(shows,'Breaking Bad (2008)','Season 01','Breaking Bad S01E04.strm')))
# play from library (lib=1): progress tracked, no Trakt scrobble from us
n=len(fake_trakt.LOG); strm=open(os.path.join(shows,'Breaking Bad (2008)','Season 01','Breaking Bad S01E04.strm')).read()
watch('?'+strm.split('?',1)[1], 500, 2400); print('library playback -> trakt scrobbles from us:', len([1 for m,p,b,a,k in fake_trakt.LOG[n:] if p.startswith('/scrobble/')]), '| continue entry lib flag:', watching.load()[0].get('lib'))
run('?action=lib_remove&kind=series&id=78'); print('removed series folder exists:', os.path.exists(os.path.join(shows,'Breaking Bad (2008)')))
