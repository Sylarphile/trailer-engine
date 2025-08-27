import os, requests, time, shutil, json, yt_dlp
from datetime import datetime, timezone
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
    
    def move_trailer(path, movie_id):
        try:
            filename = os.path.basename(path)
            dst = os.path.join(RELEASED_TRAILERS, filename)
            shutil.move(path, dst)
            if os.path.exists(dst):
                print(f"Successfully moved {filename} to {dst}")
                unreleased[movie_id]["released"] = True
                save_unreleased(unreleased)
        except Exception as e:
            print(f"Error: {e}")


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

    def get_trailer(movie_id):
        resp = requests.get(f"{base_url}/movie/{movie_id}/videos", headers=HEADERS).json()
        results = resp.get("results", [])
        found = False
        for result in results:
            if result["type"] != "Trailer":
                continue
            if result["site"] == "YouTube" and result["name"] == "Official Trailer" and result["official"]:
                found = True
                ydl_opts = {
                    "paths": {
                        "home": UNRELEASED_TRAILERS,
                        "temp": TEMP_FOLDER
                    },
                    "writethumbnail": True,
                    "embedthubmnail": True,
                    "postprocessors": [
                        {"key": "FFmpegMetadata", "add_metadata": True},
                        {"key": "FFmpegVideoConvertor", "preferedformat": "mkv"},
                        {"key": "EmbedThumbnail"},
                    ],
                    "outtmpl": f"{unreleased[movie_id]['title']} ({unreleased[movie_id]['year']}).%(ext)s",
                }

                key = result["key"]
                unreleased[movie_id]["yt_key"] = key
                print("pausing for 10 seconds")
                time.sleep(10)
                with yt_dlp.YoutubeDL(ydl_opts) as ytdl:
                    ytdl.download(f"https://www.youtube.com/watch?v={key}")
                if os.path.exists(os.path.join(UNRELEASED_TRAILERS, unreleased[movie_id]['filename'])):
                    unreleased[movie_id]["downloaded"] = True
                    save_unreleased(unreleased)
                else:
                    print(f"Failed to download trailer for {unreleased[movie_id]['title']}")


        if not found:
            print(f"{unreleased[movie_id]['title']} trailer not found.")

    def check_results(results):
        for result in results:
            year = result["release_date"][:4]
            if int(year) <= (datetime.now().year - 2):
                continue
            movie_id = result["id"]
            if f"{movie_id}" in unreleased:
                continue
            title = result["title"]
            filtered_title = "".join(filter(lambda ch: ch not in r"/\<>*?:'|", title))       
            filename = f"{filtered_title} ({year}).mkv"
            print(f"{title} not in state file. Adding.")

            unreleased[movie_id] = {
                "filename": filename,
                "title": filtered_title, 
                "year": year,
                "releases": get_release_dates(movie_id), 
                "released": False,
                "downloaded": False
                }
            
            save_unreleased(unreleased) 

    def check_unreleased():
        for movie_id, info in unreleased.items():

            if info["released"] == True:
                continue
            
            if info["downloaded"] == False:
                print(f"{info['title']} trailer not downloaded. Attempting to download trailer.")
                get_trailer(movie_id)

            if info["filename"] in os.listdir(UNRELEASED_TRAILERS):
                path = os.path.abspath(os.path.join(UNRELEASED_TRAILERS, info["filename"]))
                if not info["releases"]:
                    info["releases"] = get_release_dates(movie_id)
                if not info["releases"]:
                    continue
                released = is_released(info["releases"])
                if released:
                    move_trailer(path, movie_id)
            else:
                print(f"{info['filename']} not found in {UNRELEASED_TRAILERS}. Setting status to 'released'")
                info["released"] = True
                save_unreleased(unreleased)
        save_unreleased(unreleased)

    def check_now_playing():
        resp = requests.get(f"{base_url}/movie/now_playing", headers=HEADERS, params={"region": "US"}).json()
        results = resp.get("results", [])
        check_results(results) 

    def check_upcoming():
        resp = requests.get(f"{base_url}/movie/upcoming", headers=HEADERS, params={"region": "US"}).json()
        results = resp.get("results", [])
        check_results(results)

    try:
        while True:
            check_upcoming()
            check_now_playing()
            check_unreleased()
            print(f"Check complete. Sleeping for {SLEEP_TIMER / 3600} hours.")
            time.sleep(SLEEP_TIMER)      
            
    except KeyboardInterrupt:
        print("Interrupted")

if __name__ == "__main__":
    main()


