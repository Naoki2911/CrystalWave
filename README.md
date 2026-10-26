# CrystalWave

A small desktop music player that streams audio from YouTube. Built with
customtkinter, VLC and yt-dlp.

## Features

- Search and stream songs, with selectable audio quality
- Playlists you can rearrange by dragging songs
- The whole UI recolors itself from the cover of the song that's playing
- Synced lyrics (from [lrclib.net](https://lrclib.net))
- Crossfade, shuffle and repeat
- Favorites: heart a song to add it to a Favorites playlist
- Play Next and Add to Queue from the right-click menu, plus an Up Next panel to jump, reorder or remove
- Recently Played list (last 100 songs)
- Export a playlist to a file, or import one from a file or a YouTube playlist link
- Mini player: a small always-on-top window with the cover and basic controls
- Media keys (play/pause, next, previous) that work while the app is in the background (Windows)
- Sleep timer: 15 to 60 minutes, or at the end of the current song
- Listening stats: top songs, top artists, streaks, last 7 days
- Three themes: Crystal Purple, High Contrast and Light
- Keyboard shortcuts
- 
## Fonts

CrystalWave uses the nicest font it can find, in this order: Poppins, Inter, Montserrat,
Nunito, Manrope, Segoe UI Variable, Segoe UI. To get one of the first ones without installing it
system-wide, create a `fonts` folder next to `CrystalWave.py` and drop the `.ttf` or `.otf` files in it
(for example Poppins-Regular.ttf and Poppins-Bold.ttf from Google Fonts). Check the font's license
before committing it to your repo.

## Shortcuts

| Key | Action |
| --- | --- |
| Space | Play / pause |
| Left / Right | Seek 5 seconds |
| Ctrl + Left / Right | Previous / next track |
| Up / Down | Volume |
| M | Mute |
| S / R | Shuffle / repeat |
| F | Favorite the current song |
| Q | Show / hide the Up Next panel |
| Ctrl + M | Mini player |
| L | Lyrics |
| Esc | Close lyrics, or leave a text box |
| Ctrl + 1 to 4 | Search, Playlists, Stats, Settings |
| Ctrl + F | Focus search |
| Enter / Delete | Play / remove the selected song |
| Ctrl + Up / Down | Move the selected playlist song |

Plain-letter shortcuts are ignored while you're typing in a text box. In a song list,
Up and Down move the selection instead of changing the volume.

## Notes

Settings, playlists and stats are stored as JSON files in your home folder.
