# Handoff (state at version 1.13.0)

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
1.13.0: fast remote keys. Zap logic moved from main.py to `resources/lib/zapper.py`
(`handle(key, d, fb)`). With setting `zap_fast` (default on) the keymap sends
`NotifyAll(plugin.video.xtreamcodes,zap.<section>.<key>)`; `service.KeyListener`
(own thread, since Kodi delivers Monitor callbacks to the creating thread while it
waits in waitForAbort) resolves it via `keymap.resolve()` and runs zapper in a
thread per press. Saves starting the add-on per key (interpreter + compiling
main.py + imports, ~1 s on Amlogic). Off = old RunPlugin keymap. `_zap_tune` now
shows the banner first and calls play() from the banner's `during` callback.
Not yet verified on the real box: check that keys work and the banner is instant.
Tests: `tests/fast_keys_test.py`, `tests/zap_opening_test.py`, `tests/svc_test.py`
(now relative paths).

1.12.4: keys pressed while a just-tuned channel is still opening were lost (Kodi
reports no video for 1-2 s, so `playing_context()` was None and the key fell back
to Kodi's action). `playback.zap_context()` also accepts that state for 15 s after
tuning if nothing else is playing/opening. Test: `python3 tests/zap_opening_test.py`
(asserts, relative paths, exit code; a model for converting the other tests).

1.12.3 (from a real-device log): `common.save_json/save_state` now use a temp
file unique per process/thread (a shared `.tmp` name made concurrent writers fail:
"TV window worker stopped: No such file ... channel_history.json.tmp").
`playback.start_live` now sets `PROP_TUNE_T` and logs "Opening <name>", so
"Picture on screen" is timed correctly for TV mode / guide starts (before, it was
measured from the last Up/Down, giving 24-41 s). Real-device timings from that log:
OpenFile -> picture 0.7-8 s depending on the channel (provider side).

1.12.2: no code changes. New addon.xml summary/description/news, README feature
list, and a user guide in `docs/USER_GUIDE.md` (keep it in step with new features).

1.12.1: faster zapping. Quick repeated up/down shows each channel's banner at once
and only tunes the one you stop on (setting `zap_debounce`, tenths of a second,
0 = off); timing lines in the Kodi log ("ready to play after", "Picture on screen");
experimental `live_engine` = inputstream.ffmpegdirect (untested on real hardware).
Kodi closes the old stream serially, so it cannot fully match STBEmu.
Advice given: Settings > Player > Videos > Adjust display refresh rate = Off, MPEG-TS.

## Open items / ideas
- `fix20` sometimes loses one of 4 very fast presses (banner repeats, e.g. C5, C5),
  on old and new code alike: likely a race between key-press processes reading/
  writing the zap state. Investigate.
- Check real-device timing logs for the new zap path; tune `zap_debounce`.
- TV guide search (`epg_pick`) still shows the live/restart popup.
- Movies/series episodes do not get the "Starting..." note.
- Own Trakt app keys vs. user-supplied keys; Stalker portal support (needs portal format).
- Add a licence (owner to choose) before making the repo public; the Kodi
  repository's update URLs need the repo to be public.
