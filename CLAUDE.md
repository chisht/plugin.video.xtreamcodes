# Project notes for Claude

Kodi video add-on `plugin.video.xtreamcodes` (Python 3, Kodi 21/22) for Xtream
Codes providers. See `HANDOFF.md` for architecture, test instructions, history
and open to-dos. Read it first.

Rules (set by the owner):
- Do not use Kodi's IPTV/PVR Simple client.
- Never commit credentials, provider URLs, logs or backups. Never copy Trakt
  keys from other add-ons; treat a Trakt Client Secret like a password.
- Logs the user pastes may contain the provider login: scrub before quoting.
- Target hardware: CoreELEC on Amlogic arm64, Kodi 22 alpha, Python 3.14,
  Confluence skin, CEC remote (arrives as keyboard events).
- Bump `version` in `addon.xml` for each release; run `./build.sh` to package,
  `./publish_repo.sh` to push it to the Kodi repository (`kodi-repo` branch).
- New user-facing strings go in `resources/language/resource.language.en_gb/strings.po`
  (highest id in use: 30157) and settings in `resources/settings.xml`.
