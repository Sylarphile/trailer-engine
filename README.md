The goal of this project is to download and determine which movie trailers correspond with movies that are available for home viewing. It uses the TMBD API, so you will need to provide your own API key in a config.py file placed in the same directory as trailer-engine.py, format specified below. Currently, it only checks for new trailers from TMDB's Now Playing and Upcoming.

API information here: https://developer.themoviedb.org/docs/getting-started

requires ffmpeg.

config.py format:

```
HEADERS = {
    "accept": "application/json",
    "Authorization": "Bearer API_Read_Access_Token"
}
TEMP_FOLDER = "path/to/temp"                           # This folder is important for yt-dlp. Do not make it the same folder as UNRELEASED_TRAILERS.
UNRELEASED_TRAILERS = "path/to/unreleased_trailers"
RELEASED_TRAILERS = "path/to/released_trailers"
STATE_FILE = "path/to/state_file.json"                 # This file will be created automatically at the specified location.
SLEEP_TIMER = 86400                                    # This program is intended to constantly run in the background, checking trailers once every x seconds.
```
