# Handoff (state at version 1.13.4)

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
1.13.4: on the real box `LiveRecovery._failed` logged nothing for three
ffmpegdirect failures (callbacks did arrive for onAVStarted, so cause unknown).
`playback.watch_engine(row)` now runs after every live play() (start_live and
zapper): until ffmpegdirect has shown a picture this session, a thread watches up
to 15 s; if nothing is playing after the start-up grace, it sets PROP_FFD_FAILED,
marks the failure handled for LiveRecovery, notifies and replays with Kodi's
player. `_failed` now logs why it skips (retry off / not our channel / already
handled) - look for these in the next log. Test: `tests/ffd_watch_test.py`.

1.13.3: guide search reworked. `EPG.search()` returns (coming, aired) queried and
limited separately (before: one list from 7 days ago, oldest first, LIMIT 300
before filtering, so now/upcoming could be cut off). Results in sections On now /
Coming up / Catch-up (newest first); `epg_pick` plays live on OK for "now" (restart
via context menu `do=restart`), consistent with TV mode and the grid guide.
FFmpeg Direct: on the real box the installed inputstream.ffmpegdirect cannot load
(built against libavcodec.so.63; box has FFmpeg 8.0.1), so every channel failed.
`LiveRecovery._failed` now sets `PROP_FFD_FAILED` if ffmpegdirect has not played
anything this session, and `play_item` stops using it. Deprecated
`inputstreamaddon` property removed. Test: `tests/epg_search_test.py`.
Debug-log timings with fast keys: key -> banner 0.3 s; Kodi closing the old stream
still ~2.9 s (not caused by the banner; Kodi also saves watched state and the
skin's helper scripts refresh widgets on every channel change).

1.13.2: EPG streamed from the HTTP response straight into `epg.build_db`
(`xtream.open_xmltv()`, `epg._Reader` peeks for gzip and counts bytes), so the XML
is never written to storage. If the network read fails part-way
(`epg.STREAM_ERRORS`, or a truncated/invalid XML -> ValueError) sync falls back once
to the old download-to-file path; storage errors (OSError from writing) do not
fall back. Test: `tests/epg_stream_test.py`.

1.13.1 (real-device log: /storage went read-only, EROFS, Kodi's own DB too): the
service died on `save_state` in `do_sync`'s finally. Now saves in do_sync are
non-fatal, the loop body is `tick()` wrapped in try/except, the last attempt is
also kept in memory (`LAST_TRY`) so an unsaveable state.json cannot cause a retry
every 5 s, and `STOP` ends the key-listener thread with the service (Kodi logged
"waiting on thread" for it). Test: `tests/readonly_test.py`.

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
- Channel change timing on the real box (1.13.0 log, `tools/log_timing.py`): add-on
  0.15 s, Kodi closing the old stream ~2.8 s (same from TV mode and from the
  service, so not caused by fast keys), connect 0.2, probe 0.3, first picture 0.6;
  total ~4 s. The close is the target: try `live_engine` = ffmpegdirect and compare.
  One case: a 4.6 s close finished 0.06 s after the next key press arrived - watch
  for that pattern in more logs.
- `fix20` sometimes loses one of 4 very fast presses (banner repeats, e.g. C5, C5),
  on old and new code alike: likely a race between key-press processes reading/
  writing the zap state. Investigate.
- Check real-device timing logs for the new zap path; tune `zap_debounce`.
- Movies/series episodes do not get the "Starting..." note.
- Own Trakt app keys vs. user-supplied keys; Stalker portal support (needs portal format).
- Add a licence (owner to choose) before making the repo public; the Kodi
  repository's update URLs need the repo to be public.
