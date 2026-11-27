# Xtream Codes for Kodi (plugin.video.xtreamcodes)

A Kodi 21/22 video add-on for Xtream Codes IPTV providers. It does **not** use
PVR IPTV Simple; everything runs inside the add-on.

## Features
- **TV mode**: channel groups, channel list with what's on now, mini player and
  programme schedule in one screen. It can open automatically when Kodi starts.
- **Fast zapping**: Up/Down and CH+/CH- while watching fullscreen, with an
  instant channel banner. Number entry; 0 goes back to the previous channel.
- **Grid TV guide** from a full XMLTV download, with time offset correction.
- **Catch-up** for channels with a TV archive, and **watch from the beginning**
  (also on the Rewind key).
- **Movies and series**: categories, recently added, resume, Continue watching,
  optional export to the Kodi library.
- **Discover**: trending, popular, top-rated, by genre and decade, with TMDb
  ratings, listing only what your provider has.
- **Search** for channels, movies and series, plus search of the TV guide.
- **Favourites**, hide, rename and reorder groups, move channels.
- **Reminders** and a **sleep timer**.
- **Trakt** scrobbling and progress.
- **Parental**: adult content hidden, with an optional PIN to show it for 3 hours.
- **Reliable playback**: online check, retry-then-go-back, one-connection-friendly
  switching, a configurable User-Agent, and background updates.
- **Skins**: TV mode, the grid guide and the channel banner come in a dark blue
  default look and an STBEmu / Stalker portal look (black and orange).
- **Backup and restore** of favourites, groups and settings.

See the **[user guide](docs/USER_GUIDE.md)** for how to use everything.

## Install (with automatic updates)
1. Download
   [repository.chisht.zip](https://raw.githubusercontent.com/chisht/plugin.video.xtreamcodes/kodi-repo/repository.chisht.zip)
   and copy it to the Kodi device (USB stick, network share, or the device's
   own storage).
2. Kodi: Settings → System → Add-ons → turn on **Unknown sources**.
3. Add-ons → Install from zip file → pick `repository.chisht.zip`.
4. Add-ons → Install from repository → **chisht Repository** → Video add-ons →
   **Xtream Codes IPTV** → Install.
5. Enter your provider's server, username and password in the add-on settings.

Kodi then checks the repository and installs new versions by itself (Settings
→ System → Add-ons → Updates controls this).

Manual install without updates: run `./build.sh`, then Install from zip file →
`dist/plugin.video.xtreamcodes-<version>.zip`.

Your login is stored only in Kodi's own add-on settings on your device.
Never post logs or backups without removing the username and password.

## Releasing an update
1. Bump `version` in `addon.xml` (and add a line to the changelog if any).
2. Commit, then run `./publish_repo.sh`. It builds the zips, `addons.xml` and
   checksums with `tools/build_repo.py` and pushes them to the `kodi-repo`
   branch. Older versions stay in the branch so users can roll back.

The repository add-on itself lives in `repository.chisht/`; bump its version
only when its URLs change. The update URLs only work while this GitHub repo is
public.

## Development
Tests run against stub Kodi modules and fake servers, with no Kodi needed:
see `tests/` and `HANDOFF.md`.
