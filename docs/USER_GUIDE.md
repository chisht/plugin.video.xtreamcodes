# Xtream Codes IPTV for Kodi: user guide

This guide covers installing the add-on, setting it up, and using it every day
with a TV remote. Menu names are as they appear in Kodi's Confluence skin.

**Contents**
1. [Install](#1-install)
2. [First setup](#2-first-setup)
3. [The main menu](#3-the-main-menu)
4. [TV mode](#4-tv-mode)
5. [Watching live TV fullscreen (remote keys)](#5-watching-live-tv-fullscreen-remote-keys)
6. [TV guide (grid)](#6-tv-guide-grid)
7. [Catch-up and "watch from the beginning"](#7-catch-up-and-watch-from-the-beginning)
8. [Movies and series](#8-movies-and-series)
9. [Discover (TMDb)](#9-discover-tmdb)
10. [Search](#10-search)
11. [Favourites, groups and channel order](#11-favourites-groups-and-channel-order)
12. [Reminders and sleep timer](#12-reminders-and-sleep-timer)
13. [Adult content and PIN](#13-adult-content-and-pin)
14. [Trakt](#14-trakt)
15. [Kodi library](#15-kodi-library)
16. [Backup and restore](#16-backup-and-restore)
17. [Settings reference](#17-settings-reference)
18. [Troubleshooting](#18-troubleshooting)

---

## 1. Install

### With automatic updates (recommended)
1. Download
   [repository.chisht.zip](https://raw.githubusercontent.com/chisht/plugin.video.xtreamcodes/kodi-repo/repository.chisht.zip)
   and copy it to the Kodi device: USB stick, network share, or the device's
   own storage.
2. In Kodi, go to **Settings → System → Add-ons** and turn on **Unknown sources**.
3. Go to **Add-ons → Install from zip file** and pick `repository.chisht.zip`.
4. Go to **Add-ons → Install from repository → chisht Repository → Video
   add-ons → Xtream Codes IPTV → Install**.

Kodi now installs new versions by itself. You can change this under
**Settings → System → Add-ons → Updates**.

### From a zip file (no updates)
Install `plugin.video.xtreamcodes-<version>.zip` with **Add-ons → Install from
zip file**. You will need to install each new version by hand.

### Optional add-ons
- **InputStream Adaptive**, if you choose HLS as the live stream format.
- **inputstream.ffmpegdirect**, for the experimental faster live TV player.

## 2. First setup

1. Open the add-on (**Add-ons → Video add-ons → Xtream Codes IPTV**). The first
   time, it only shows **Set up your account...**.
2. Enter what your provider gave you:
   - **Server URL**: for example `http://example.com:8080`. Include the port.
     Do not add `player_api.php` or anything else after it.
   - **Username** and **Password**.
3. Go back to the add-on. It downloads the channel list and then the full TV
   guide (EPG) in the background. On a large provider the guide can take a few
   minutes the first time. A progress notice shows how far it has got.

Your login is stored only in Kodi's add-on settings on your own device.

**Tip, to make the box behave like a TV:** turn on **Settings → TV mode → Open
TV mode when Kodi starts**. After power-on, Kodi goes straight to your
channels and starts playing the last one you watched.

## 3. The main menu

| Entry | What it does |
|---|---|
| TV mode | Full-screen channel list with a mini player and the programme schedule. The best way to watch live TV. |
| TV guide (grid) | Classic grid guide: channels down the side, time across the top. |
| Live TV | Browse channel groups as normal Kodi lists, with what's on now. |
| Continue watching | Movies and episodes you stopped part-way through. Only shown when there are some. |
| In-progress shows (Trakt) | Shows you are watching, from your Trakt account. Only shown once Trakt is linked. |
| Catch-up (TV archive) | Channels with an archive: pick a day, then a programme. |
| Movies / Series | Your provider's VOD and series, by category, plus Recently added. |
| Discover | Trending, popular and top-rated titles from TMDb that your provider has. |
| Search | Search channels, movies and series. |
| Search the TV guide | Find a programme by title across all channels. |
| Sleep timer | Stop playback after a set time, or at the end of the current programme. |
| Account and status | Expiry date, connections in use and allowed, formats, and when the channels and guide were last updated. |
| Update channels and EPG now | Download the channel list and guide again straight away. |
| Settings | The add-on settings. |

## 4. TV mode

TV mode has three parts: **groups** on the left, **channels** in the middle (each
with what's on now), and the **mini player** with the **schedule** for the
selected channel.

| Key | In TV mode |
|---|---|
| Up / Down | Move through the list. Long lists scroll smoothly; any number of channels is fine. |
| CH+ / CH− | Tune the next / previous channel in the list (same as OK on it). |
| PageUp / PageDown | Move to the next / previous group. |
| Left / Right | Move between groups, channels and schedule. |
| OK on a group | Show that group's channels. |
| OK on a channel | Play it in the mini player. Press OK again on the playing channel to go fullscreen. |
| OK on a schedule entry | Now: watch live. Earlier (catch-up channels): watch that programme. Later: set or remove a reminder. |
| Number keys | Type a channel number. It tunes after 2 seconds. **0** on its own goes back to the previous channel. |
| Info | Open the grid guide. |
| Menu / long-press OK | Options for the selected channel or group (see below). |
| Back | Cancel a half-typed number, otherwise leave TV mode. |

**Channel options:** add to or remove from favourites, watch fullscreen, TV
guide (grid), sleep timer, move channel, and watch from the beginning (catch-up
channels).

**Group options:** rename group, move group, hide this group, show/hide groups,
and show or hide adult content (when a PIN is set).

When you leave the add-on the stream stops, unless you turn off **Settings → TV
mode → Stop playback when leaving the add-on**. Leaving means Back out of TV
mode, out of the grid guide, or out of any list (Live TV, catch-up, search, a
reminder pop-up) while one of this add-on's channels is playing. Kodi otherwise
keeps a stream started from a list playing in the background — with this on it
stops, so your connection is free for another device. A channel that plays with
no picture on screen (started from a list, then Back out of fullscreen) is
stopped too, instead of playing on with only sound behind the menu.

The colours and layout of TV mode (and of the grid guide and the channel banner)
come from **Settings → Display → Skin** — see
[Skin](#skin) for the STBEmu / Stalker portal look.

With **Settings → TV mode → Preview the highlighted channel** on, stopping on a
channel in the list tunes it in the mini player after a moment (as an STBEmu /
Stalker box does), instead of waiting for OK. It is off by default because every
channel you rest on is opened, which counts towards your connection limit.

## 5. Watching live TV fullscreen (remote keys)

While one of this add-on's live channels is playing fullscreen, these keys
work. The add-on installs a small keymap for them.

| Key | Action |
|---|---|
| Up / Down, CH+ / CH- | Next or previous channel in the group you started from. The channel banner shows at once. |
| Number keys | Type a channel number. **0** on its own goes back to the previous channel. |
| Info | Show the channel banner with the current programme. |
| Guide (or **E** on a keyboard) | Open the grid guide. |
| Rewind (or **R** on a keyboard) | On a catch-up channel, offers to watch the current programme from its beginning. |

In movies, series, catch-up and other add-ons, these keys keep doing what they
normally do. If another keymap (Keymap Editor, other add-ons) already used a
key, that mapping is kept for everything except this add-on's live TV.

**Fast channel switching.** Press Up or Down several times quickly: each
channel's banner shows straight away, but only the channel you stop on is
opened. The waiting time is set by **Settings → Playback → Channel up/down: wait
before tuning** (in tenths of a second; 0 turns it off).

**Fast remote keys.** The keys are handled by the add-on's background service,
which is already running, so the banner appears straight away. If the channel
keys ever stop working, turn off **Settings → Playback → Fast remote keys**: the
add-on is then started for each key press instead (slower, about a second on
small boxes).

After the banner, the picture usually takes another 1 to 3 seconds (sometimes
up to 8 on busy channels): that is Kodi closing the old stream and your
provider sending the new one.

**When a channel fails.** Offline channels show a short notice instead of
Kodi's error. If a channel fails to start, the add-on tries once more and then
goes back to the channel you were watching. Offline channels are greyed out for
10 minutes. While zapping, the add-on skips offline channels (or stays put, if
you choose so in settings).

To turn all of this off, turn off **Settings → Playback → Up/Down changes channel
while watching live TV**. The keymap is then removed.

## 6. TV guide (grid)

Open it from the main menu, from TV mode (Info), or with the Guide key while
watching.

| Key | In the grid guide |
|---|---|
| Arrows | Move between programmes and channels. Going left past the start shows earlier hours. |
| Page up / down, CH+ / CH- | Scroll a page of channels. |
| OK on what's on now | Watch live. |
| OK on an earlier programme | Watch it (catch-up channels, within the archive). |
| OK on a later programme | Set or remove a reminder. |
| Menu / long-press OK | Watch live, watch from the beginning, set a reminder, jump to now, add to favourites, watch fullscreen. |
| Back | Close the guide and go back to what was underneath (TV mode, or the list you opened it from). |

If all guide times are off by an hour or more, set **Settings → Background
updates → EPG time offset**.

## 7. Catch-up and "watch from the beginning"

Channels whose provider keeps an archive (TV archive) support:
- **Catch-up**: main menu **Catch-up (TV archive)**, then pick a channel, a day
  and a programme. You can also use **Catch-up** in a channel's context menu, or
  pick an earlier programme in TV mode or the grid guide.
- **Watch from the beginning**: start the programme that's on now from its
  start. It's in the channel's context menu, the grid guide's menu, and on the
  Rewind key while watching live.

While a recording plays, **Info** shows the channel banner with the
recording's title, and **Guide** (or **E**) opens the TV guide at that
channel. Up/Down and the other keys keep their normal job (seeking).

Programmes play a few extra minutes past their listed end, so you don't miss
the ending (**Settings → Playback → Catch-up: extra minutes after programme
end**). If catch-up doesn't play, try the other **Catch-up URL style**.

## 8. Movies and series

- Browse by category, **All movies / All series**, or **Recently added /
  Recently updated**.
- If you stop part-way through, the item resumes where you left off and shows up
  in **Continue watching**. Remove an item from there with its context menu.
- Context menu on a movie or series:
  - **Ratings and details (TMDb)**
  (These two need a TMDb key, see [Discover](#9-discover-tmdb).)
  - **More like this (TMDb)**: similar titles, only ones your provider has.
  - **Add to library / Remove from library** (see [Kodi library](#15-kodi-library)).

## 9. Discover (TMDb)

Discover shows what's trending, popular and top rated, using TMDb ratings. It
only lists titles your provider actually has, so everything in it can be
played.

It needs a free TMDb API key:
1. Sign up at themoviedb.org.
2. Open **Settings → API** there and copy the **API Key**.
3. Paste it in **Settings → Discover (TMDb) → TMDb API key**.

Lists for movies: Trending this week, Popular, Top rated, New in cinemas, By
genre, By decade. For series: Trending this week, Popular, Top rated, On the
air now, By genre, By decade. Set **TMDb language** (for example `en-US` or
`fr-CA`) for titles and descriptions in your language.

## 10. Search

- **Search** looks through channels, movies and series. Earlier searches are
  kept. Remove one, or clear the history, from the context menu.
- **Search the TV guide** finds programmes by title across all channels.
  Main menu → **Search the TV guide** → **New search...**, type part of a
  title (for example `news` or `simpsons`). Results come in three sections:
  - **On now**: OK watches the channel live. On catch-up channels, the context
    menu has **Watch from the beginning**.
  - **Coming up**: OK asks what you want: **Set reminder** (or remove it),
    **Watch <channel> now**, or **TV guide (grid)** at that channel.
    "(reminder set)" shows on those you already picked.
  - **Catch-up (already aired)**: newest first. OK plays the programme. Only
    channels with a TV archive appear here.

  Each result shows the day (Today, Tomorrow, Yesterday or the date), the
  channel number and name, and a note: **(on now)**, **(in 25 min)** for
  upcoming ones, or **(recording)** for catch-up. The info panel of each
  result says what OK will do. The context menu also
  has **Watch live** and **TV guide (grid)** for that channel.

## 11. Favourites, groups and channel order

- **Favourites**: add a channel from its context menu (or in TV mode or the
  guide). Favourites get a star and their own group at the top.
- **Hide groups** you never use, such as other countries or languages: use
  **Show/hide groups...** in a group's context menu, or **Settings → Parental →
  Show/hide groups...**. This works for live, movie and series categories.
- **Rename** a group or **move** it up or down in the list from its context
  menu. **Move channel...** reorders channels inside a group.
- To undo renames and reordering, use **Settings → Backup → Reset group names and
  order**.

## 12. Reminders and sleep timer

- **Reminders**: pick a programme that hasn't started yet, in TV mode's
  schedule or the grid guide. Shortly before it starts, Kodi asks
  "Watch it now?". Choose **Watch** to switch to the channel. Set how early under **Settings → TV mode →
  Reminders: minutes before the start**.
- **Sleep timer**: main menu, or the channel menu in TV mode. Choose 15, 30 or
  45 minutes, 1, 1.5 or 2 hours, or **End of current programme**. Choose
  **Off** to cancel it.

## 13. Adult content and PIN

Adult groups, channels, movies and series are hidden by default (**Settings →
Parental → Hide adult content**). The add-on finds them from the provider's
adult flags and from group names such as Adult, XXX or 18+.

If you set a **PIN**, you can show adult content for 3 hours from the main
menu or from TV mode's group menu. **Hide adult content again** hides it before
the 3 hours are up. If others could change the add-on settings, protect Kodi's
settings with a master lock.

## 14. Trakt

Trakt keeps track of what you've watched across devices.
1. Create a free API app at trakt.tv/oauth/applications, with Redirect URI
   `urn:ietf:wg:oauth:2.0:oob`.
2. Paste its **Client ID** and **Client Secret** in **Settings → Trakt**. Keep
   the secret private, like a password.
3. Choose **Link Trakt account**, open the web address it shows on a phone or
   computer, and enter the code.

After that, movies and episodes you watch here are marked watched on Trakt once
you pass 80% (live TV is not sent). **In progress** and **Watched** lists appear
under Series, and **Sync Trakt now** fetches your watched history.

## 15. Kodi library

**Add to library** on a movie or series creates entries in Kodi's own
library. You then get Kodi's movie and TV show views, widgets, watched marks
and resume points.
1. Optionally choose a **Library folder** in **Settings → Library**. If you leave
   it empty, the add-on's own data folder is used.
2. Add the **Movies** and **TV Shows** subfolders of that folder to Kodi as video
   sources once, with the content type set (movies / TV shows).
3. New episodes of library series are added automatically, or straight away
   with **Update library now**.

## 16. Backup and restore

**Settings → Backup → Back up favourites, groups and settings** saves your
favourites, hidden groups, group names and order, reminders, library list,
Continue watching and all settings to a file. Use **Restore from a backup** on
a new box or after a reinstall.

The backup includes your provider login, so keep it private and don't post it
anywhere.

## 17. Settings reference

**Account**: server URL, username, password.

**Network**
- *Use a custom User-Agent / Custom User-Agent*: by default the add-on identifies
  itself like TiviMate. Change this only if your provider asks for something
  else.
- *Request timeout*: how long to wait for the server.

**Playback**
- *Live stream format*: MPEG-TS (.ts, recommended) or HLS (.m3u8).
- *Use InputStream Adaptive for HLS*.
- *Up/Down changes channel while watching live TV*, *Reverse Up/Down direction*.
- *Fast remote keys (handled by the background service)*: on by default.
- *Rewind button restarts the current show*.
- *If a channel fails to start, retry once, then go back*.
- *Channel up/down: wait before tuning*: see [fast channel switching](#5-watching-live-tv-fullscreen-remote-keys).
- *Live TV player engine*: Kodi default, or inputstream.ffmpegdirect (experimental).
  If FFmpeg Direct cannot play anything (on some boxes it does not even load),
  the add-on switches back to Kodi's player by itself and tells you.
- *Close the current stream before opening the next*: keep this on if your plan
  allows only one connection. The add-on closes the stream, checks the new channel
  and opens it: checking while the old stream is still open makes a
  single-connection provider refuse the check, which marks good channels offline
  and makes the next channel change slow.
- *Check channel is online before playing*, *Online check timeout*, *When Up/Down
  reaches an offline channel*, *Mark offline channels*. A channel that played a
  moment ago is not checked again for 10 minutes, and a check that failed is
  dropped as soon as the channel does play (or when the add-on retries it), so a
  refusal while another stream was open cannot stick.
- *Catch-up URL style*, *Catch-up: extra minutes after programme end*.

**Parental**: hide adult content, PIN, show/hide groups.

**Trakt**: client ID and secret, link and unlink, scrobble, sync now.

**Discover (TMDb)**: API key, language.

**Library**: library folder, add new episodes automatically, update now.

**Backup**: back up, restore, reset group names and order.

**TV mode**: *Preview the highlighted channel*, start playing the last channel when
TV mode opens, reminder lead time, stop playback when leaving the add-on, open TV mode when
Kodi starts.

**Display**: *Skin* (see below), show what's on now in channel lists, show item
counts on groups, items per page (0 = all).

#### Skin

**Settings → Display → Skin** changes how TV mode, the grid guide and the
channel banner look.

| Skin | What it gives you |
|---|---|
| Default (dark blue) | The look the add-on has always had: dark blue, light text, orange "playing" marks. |
| STBEmu / Stalker portal | The look of STBEmu (the Stalker portal / Ministra boxes) on Android: black background, grey text, orange highlights, a narrower channel column, a smaller video window and a black banner along the bottom. |

Each skin is a palette plus a folder of window layouts in
`resources/skins/<name>/`, so the two are always in step: switching the skin
changes both the colours the add-on draws in Python and the layouts it loads.

**Background updates**: update channel lists in the background and how often,
download the full EPG, how many past days to keep (for catch-up), EPG time
offset, show progress and notifications, clear cached data, update now.

## 18. Troubleshooting

| Problem | Try this |
|---|---|
| "Set up your account" won't go away / login fails | Check the server URL includes `http://` and the port, with nothing after it. Check **Account and status**. |
| A new channel won't start after switching (HTTP 403) | Your plan allows a limited number of connections. Keep **Close the current stream before opening the next** on, and check **Account and status** for active connections. |
| Channel switching feels slow | In Kodi, set **Settings → Player → Videos → Adjust display refresh rate** to **Off**. Use MPEG-TS. Try a lower **wait before tuning** value. |
| Every channel shows as offline | Turn off **Check channel is online before playing**. Some single-connection providers refuse the check. |
| Guide times are wrong | Set **EPG time offset**. |
| Guide is empty or out of date | **Update channels and EPG now**. If it's still wrong, **Clear cached data** (favourites, groups and settings are kept). |
| Catch-up doesn't play | Switch **Catch-up URL style**. Make sure the programme is within the channel's archive days. |
| Up/Down does something odd in other add-ons | It shouldn't: the keys fall back to their normal action. If it does, turn **Up/Down changes channel** off and on again to rebuild the keymap. |
| Discover asks for a key | See [Discover (TMDb)](#9-discover-tmdb). |

When asking for help with a Kodi log, **remove your server address, username
and password from it first.**
