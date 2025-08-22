import os, requests, time, shutil, json, yt_dlp
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timezone
from difflib import SequenceMatcher
from config import *

def main():

    def load_unreleased():
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_unreleased(unreleased):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(unreleased, f, indent=2)

    base_url = "https://api.themoviedb.org/3"

    unreleased = load_unreleased()

    def similar(a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def move_trailer(path):
        shutil.move(path, os.path.join(RELEASED_TRAILERS, os.path.basename(path)))
        unreleased[get_key(path)]["released"] = True
        save_unreleased(unreleased)

    def get_key(path):
            #Assumes a file format of: "Title (year) - Trailer.ext"
        filename = os.path.basename(path)
        title = os.path.splitext(filename)[0]
        title = title[:-10]
        return title    
    
    def get_title(path):
            #Assumes a file format of: "Title (year) - Trailer.ext"
        filename = os.path.basename(path)
        title = os.path.splitext(filename)[0]
        title = title[:-17]
        return title

    def get_id(title):
        resp = requests.get(f"{base_url}/search/movie", headers=HEADERS, params={"query": title}).json()
        results = resp.get("results", [])
        if not results:
            return None
        candidates = [r for r in results if not r.get("video", False)]
        if not candidates:
            candidates = results
        candidates.sort(key=lambda r: similar(title, r["title"]), reverse=True)
        for r in candidates:
            print(f"- {r['title']} (id={r['id']}, video={r['video']})")

        best_match = candidates[0]
        return best_match["id"]


    def get_release_dates(movie_id):
        releases = set()
        resp = requests.get(f"{base_url}/movie/{movie_id}/release_dates", headers=HEADERS).json()
        results = resp.get("results", [])
        if results:
            for result in results:
                for release in result.get("release_dates", []): 
                    if release["type"] not in [4, 5, 6]:
                        continue
                    releases.add(release["release_date"])
        return list(releases)

    def is_released(releases):
        released = False
        now = datetime.now(timezone.utc)
        parsed_releases = set()
        for release in releases:
            parsed_releases.add(datetime.fromisoformat(release.replace("Z", "+00:00")))
        for parsed_release in parsed_releases:
            if parsed_release <= now:
                released = True
                break
        return released

    def get_trailer(movie_id, title, year):
        resp = requests.get(f"{base_url}/movie/{movie_id}/videos", headers=HEADERS).json()
        results = resp.get("results", [])
        for result in results:
            if result["type"] != "Trailer":
                continue
            if result["site"] == "YouTube" and result["name"] == "Official Trailer" and result["official"]:
                ydl_opts = {
                    "paths": {
                        "home": rf"{UNRELEASED_TRAILERS}",
                        "temp": rf"{TEMP_FOLDER}",
                        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
                        "writethumbnail": True,
                        "writesubtitles": True,
                        "writeautomaticsub": True
                    },
                    "outtmpl": f"{title} ({year}) - Trailer.%(ext)s",
                }
                key = result["key"]

                with yt_dlp.YoutubeDL(ydl_opts) as ytdl:
                    ytdl.download(f"https://www.youtube.com/watch?v={key}")

    class TrailerHandler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                path = os.path.abspath(event.src_path)
                handle_trailer(path)

    def handle_trailer(path):
        key = get_key(path)
        title = get_title(path)
        if not unreleased[key]:    
            movie_id = get_id(title)
            releases = get_release_dates(movie_id)
            unreleased[title] = {"title": title, "movie_id": movie_id, "releases": releases, "released": False}
            save_unreleased(unreleased)
        if is_released(unreleased[key]["releases"]):
            move_trailer(path)


    def check_unreleased():
        for title, info in list(unreleased.items()):

            if info["released"] == True:
                continue

            matching_files = [
                f for f in os.listdir(UNRELEASED_TRAILERS)
                if os.path.splitext(f)[0] == f"{title} - Trailer"
            ]

            if not matching_files:
                info["released"] == True
                continue

            path = os.path.abspath(os.path.join(UNRELEASED_TRAILERS, matching_files[0]))

            if not info["releases"]:
                info["releases"] = get_release_dates(info["movie_id"])
                if not info["releases"]:
                    continue
            released = is_released(info["releases"])
            if released:
                move_trailer(path)
                
        save_unreleased(unreleased) 

    def check_new():
        resp = requests.get(f"{base_url}/movie/now_playing", headers=HEADERS, params={"region": "US"}).json()
        results = resp.get("results", [])
        for result in results:
            title = result["title"]
            movie_id = result["id"]
            year = result["release_date"][:4]

            try:
                if unreleased[f"{title} ({year})"]["movie_id"] == movie_id:
                    continue
            except Exception as e:
                print("Movie not found. Attmepting to get trailer.")

            unreleased[f"{title} ({year})"] = {"title": title, "movie_id": movie_id, "releases": get_release_dates(movie_id), "released": False}
            save_unreleased(unreleased) 
            get_trailer(movie_id, title, year)

    observer = Observer()
    observer.schedule(TrailerHandler(), UNRELEASED_TRAILERS, recursive=False)
    observer.start()

    try:
        while True:
            check_unreleased()
            check_new()
            print(f"Check complete. Sleeping for {SLEEP_TIMER / 3600} hours.")
            time.sleep(SLEEP_TIMER)      
            
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
