# Handoff (state at version 1.14.3)

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
scenario scripts (`fix12`..`fix20`, `discover`, `guide`, `theme`, `skin_stbemu`, ...).
Every script finds the add-on from its own path (no hard-coded checkout) and exits
non-zero on failure, so the whole suite is one command from the repo root:

    sh tests/run_all.sh            # all of them, ~2.5 min
    sh tests/run_all.sh guide      # only tests whose name contains "guide"

Add new tests as `tests/<name>_test.py` printing `PASS`/`FAIL` lines and calling
`sys.exit(1 if fails else 0)`; `run_all.sh` picks them up by itself.

## Latest work
1.14.3: stop playback when leaving the add-on, from every window. Before, only
`TVWindow.close()` stopped the stream; the grid guide cleared `PROP_UI_OPEN`
without stopping, and a channel started from a list (Live TV, search, catch-up,
a reminder) is resolved by Kodi, so leaving the add-on left only sound.
`playback.UI_OPEN` (in-process counter) + `ui_opened()`/`ui_closed(keep_playing=)`
now own the `PROP_UI_OPEN` property and call `stop_on_exit()` when the last window
closes; both windows guard with `_ui_done` because Back can reach `close()` twice.
A guide opened over fullscreen video (`keep_playing`, i.e. video playing and the
zap state has no `w` mini-player flag) hands back to the picture and does not
stop it. `left_addon()` is the service watchdog for exits the add-on cannot see:
our stream playing, no fullscreen video, no add-on window, `Container.FolderPath`
not under `plugin://plugin.video.xtreamcodes`, tuned more than `SETTLE` (6 s) ago
and no modal dialog; `service.tick()` calls it. Setting `tv_stop_on_exit` (was
"leaving TV mode") relabelled 30087 + help 30170. Only our own stream is ever
stopped (`our_live_playing()` matches the panel base URL), so library playback is
never touched. Test: `tests/stop_on_exit_test.py`.

1.14.2: zapping timing fixed after a report that it got *slower* after turning on
"close the current stream before opening the next one" and stayed slow when turned
off. Cause: 1.14.1's `zap_resume` ran the online check while our own stream was
open, so a one-connection provider refused it (HTTP 403), `set_offline` marked a
good channel offline for 10 min, and the next Up/Down skipped/probed channels
until it found one. Reverted (`zap_resume` removed); as before, the stream is
closed first, then checked, then opened. Two changes keep that path fast:
`probe()` now uses HEAD (no stream opened on the server) falling back to
open-and-read for 405/501, and `playback.check_cached/mark_checked`
(`PROP_CHECKED`, 10 min) skip a repeated probe for a channel that just played or
just failed. `LiveRecovery.onAVStarted` clears the offline mark and trusts the
channel; a failed retry re-checks afresh; "Clear cached data" calls
`playback.forget_checks()`. Test: `tests/zap_improve_test.py`.

1.14.1: zapping. TV mode gained CH+/CH- (`_hop`: tune the next/previous channel in
the list) and PageUp/PageDown (`_hop_group`: next/previous group); `tv_preview`
(Settings > TV mode, off by default) makes the worker tune the highlighted channel
after `tvwindow.PREVIEW_WAIT` (2 s) of quiet, STBEmu style, skipping offline rows.
`zap_resume` (Settings > Playback, on, level 1) moves the online check in
`playback.start_live` and `zapper._zap_tune` **before** `free_connection()`, so the
check runs while the old stream plays and the picture only stops for the actual
open (off = old order, for providers that count the check as a connection).
`_zap_tune` no longer calls `free_connection()` up front (it did, before knowing
which channel it would open). Test: `tests/zap_improve_test.py`.

1.14.0: skins. `resources/lib/theme.py` holds a palette per skin and the skin
folder the layouts are loaded from; **Settings > Display > Skin** picks
`default` (the old dark blue look, unchanged layouts) or `stbemu` (STBEmu /
Stalker portal: black, grey text, orange highlights, narrower channel column,
smaller video window, black bottom banner). A skin is a palette in `theme.py`
plus a folder `resources/skins/<name>/1080i/<the three XMLs>` and
`.../media/` (guide block textures, `tools/make_media.py` makes them), so adding
one is a new folder plus a `SKINS` entry. `theme.apply(win)` still hands the
palette to a window as properties for the layouts. Timing: the TV mode worker
loop now sleeps 0.5 s while video plays, 0.12 s just after a cursor move and
0.3 s otherwise (was a flat 0.25 s); the guide moves its "now" line every 10 s
and only rebuilds the grid (hundreds of buttons) when "now" leaves the window or
after `guide.MIN_REDRAW` seconds. Tests: `tests/theme_test.py` (palette, skin
folder, XML control ids, no stale colour constants) and
`tests/skin_stbemu_test.py` (TV mode, grid guide and banner end to end on
`tests/fake_server_skin.py`).

1.13.6: guide search labels use `common.fmt_when` (Today/Tomorrow/Yesterday) and
`fmt_until` ("in 25 min"), tag (on now)/(recording), and show the channel number.
The owner clicked what looked like an upcoming result and got a recording
playing; likely a catch-up result misread as upcoming (unconfirmed, no log).

1.13.5: `playback.channel_label(row)` ("num  name") used for live ListItems and
catch-up ("num  name: programme"; `start_catchup(..., row=)`). `PROP_RECORDING`
remembers the catch-up being played; `playback.recording()` returns it while a
/timeshift/ file plays, and `zapper._recording_key` makes Info (banner with
"Recording: ...") and Guide (our grid at that channel) work during recordings;
other keys keep Kodi's behaviour. Guide search: OK on "Coming up" asks (reminder /
watch now / grid); context-menu reminder passes `do=reminder`.

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
- Channel change timing on the real box: 1.14.2 log (`uploads/kodi.log`, Kodi 22
  alpha, CoreELEC, skin stbemu) medians over 10 channel changes: key -> OpenFile
  0.15 s (max 1.95), OpenFile -> InputStream 1.91 s (max 4.98 = Kodi closing the
  old stream), connect 0.21, probe 0.37, decoder -> picture 0.32; key -> picture
  median 3.31 s, max 5.77. No errors from the add-on. The "add-on ready 23.1 s" on
  the first TV mode open is Kodi's `CAddonDatabase::SetLastUsed` (5.2 s) plus ~6 s
  between launching the plugin and the root listing while it was fetched - not the
  add-on. Still the target: Kodi closing the old stream (~2-5 s). Try
  `live_engine` = ffmpegdirect and compare.
- `fix20` sometimes loses one of 4 very fast presses (banner repeats, e.g. C5, C5),
  on old and new code alike: likely a race between key-press processes reading/
  writing the zap state. Investigate.
- Check real-device timing logs for the new zap path; tune `zap_debounce`.
- Movies/series episodes do not get the "Starting..." note.
- Own Trakt app keys vs. user-supplied keys; Stalker portal support (needs portal format).
- Add a licence (owner to choose) before making the repo public; the Kodi
  repository's update URLs need the repo to be public.
