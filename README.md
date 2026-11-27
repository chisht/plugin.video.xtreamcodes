# Xtream Codes for Kodi (plugin.video.xtreamcodes)

A Kodi 21/22 video add-on for Xtream Codes IPTV providers. It does **not** use
PVR IPTV Simple; everything runs inside the add-on.

Features: live TV with a TV mode (channel list, mini player, programme
schedule, zapping with up/down, number entry, favourites, recall), a grid TV
guide, catch-up/restart, VOD and series, search, TMDb "Discover" (ratings,
trending, popular), Trakt, reminders, hidden groups and adult filtering,
configurable User-Agent, and background catalogue/EPG download.

## Install
Run `./build.sh`, then in Kodi: Add-ons → Install from zip file →
`dist/plugin.video.xtreamcodes-<version>.zip`. Enter your provider's server,
username and password in the add-on settings.

Your login is stored only in Kodi's own add-on settings on your device.
Never post logs or backups without removing the username and password.

## Development
Tests run against stub Kodi modules and fake servers, with no Kodi needed:
see `tests/` and `HANDOFF.md`.
