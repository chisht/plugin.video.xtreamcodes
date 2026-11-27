# Handoff (state at version 1.12.1)

## Layout
- `main.py` - plugin router (menus, play actions, `zap`, Discover, search).
- `service.py` - background service (sync, key handling, LiveRecovery player hooks).
- `resources/lib/`
  - `xtream.py` API client; `catalog.py` SQLite catalogue (schema v4); `epg.py` EPG DB
  - `playback.py` start/restart/catch-up, zap state, LiveRecovery (retry once, then
    previous channel), "Starting..." notes, optional ffmpegdirect engine
  - `tvwindow.py` TV mode (windowed 800-row list, mini player); `guide.py` grid guide
  - `overlay.py` channel banner / number entry; `tmdb.py` TMDb Discover + ratings
  - `trakt.py`, `watching.py`, `library.py`, `reminders.py`, `sync.py`, `common.py`
- `resources/skins/default/1080i/` WindowXML layouts; `resources/keymaps` keymap.
- Cross-process state lives in Home window (10000) properties; each remote key
  press runs the add-on in a separate thread/process.

## Kodi repository (updates)
- `repository.chisht/` is the repository add-on; it points at raw GitHub URLs on the
  `kodi-repo` branch of this repo (works only once the repo is public).
- `tools/build_repo.py [outdir]` builds addons.xml, addons.xml.md5, per-zip .sha256,
  `zips/<id>/<id>-<ver>.zip` and a stable `repository.chisht.zip`.
- `./publish_repo.sh` runs it in a worktree of `kodi-repo`, commits and pushes.
  Release = bump `addon.xml` version, commit, `./publish_repo.sh`.

## Tests
`tests/` has stub Kodi modules (`tests/stubs`), fake Xtream/TMDb/Trakt servers and
scenario scripts (`fix12`..`fix20`, `discover`, `guide`, ...). Scripts currently
hard-code `ADDON='/home/claude/plugin.video.xtreamcodes'` and `/home/claude/test/stubs`;
change these to the repo checkout (`.`) and `tests/stubs`, then run e.g.
`python3 tests/fix20_test.py`. They print results to read; there are no asserts yet
(a good first cleanup: convert to pytest with asserts).

## Latest work
1.12.1: faster zapping. Quick repeated up/down shows each channel's banner at once
and only tunes the one you stop on (setting `zap_debounce`, tenths of a second,
0 = off); timing lines in the Kodi log ("ready to play after", "Picture on screen");
experimental `live_engine` = inputstream.ffmpegdirect (untested on real hardware).
Kodi closes the old stream serially, so it cannot fully match STBEmu.
Advice given: Settings > Player > Videos > Adjust display refresh rate = Off, MPEG-TS.

## Open items / ideas
- Check real-device timing logs for the new zap path; tune `zap_debounce`.
- TV guide search (`epg_pick`) still shows the live/restart popup.
- Movies/series episodes do not get the "Starting..." note.
- Own Trakt app keys vs. user-supplied keys; Stalker portal support (needs portal format).
- Add a licence (owner to choose) before making the repo public; the Kodi
  repository's update URLs need the repo to be public.
