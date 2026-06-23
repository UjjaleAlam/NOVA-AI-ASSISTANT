import os
import json
import webbrowser
import urllib.parse
import pyautogui
import pywhatkit
from memory import remember, recall, all_memory
from rapidfuzz import process
import psutil
import pygetwindow as gw


def load_apps():
    try:
        with open("apps.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
    
def find_best_match(text, choices):

    if not choices:
        return None
    
    match = process.extractOne(
        text,
        choices
    )

    if match and match[1] > 70:
        return match[0]
    
    return None


# FIX 1: Moved out of load_apps() — was incorrectly nested inside it
def close_app(app_name):
    print(f"\nTrying to closee {app_name}")

    found = False

    for proc in psutil.process_iter(["pid", "name"]):

        try:
            name = proc.info["name"]

            if not name:
                continue

            if app_name.lower() in name.lower():

                print("MATCH:", name)

                proc.kill()

                found = True
        except Exception as e:
            
            print("ERROR", e)

    # FIX 2: return False moved outside the for loop (was indented inside, making it
    # return False on the first iteration without ever checking remaining processes)
    return found


# FIX 3: Moved out of load_apps() and close_app() — was doubly nested
def switch_to_window(app_name):
    try:
        windows = gw.getAllTitles()
        for title in windows:
            if app_name.lower() in title.lower():
                win = gw.getWindowsWithTitle(title)[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                return True
    except:
        pass
    return False


def run_command(query):

    query = query.lower().strip()

    # =========================
    # MEMORY
    # =========================

    if query.startswith("remember "):
        text = query.replace("remember ", "").strip()
        if " is " in text:
            key, value = text.split(" is ", 1)
            remember(key.strip(), value.strip())
            return f"I will remember that {key} is {value}"
        return "Please say remember something is something"

    if query.startswith("what is "):
        key = query.replace("what is ", "").strip()
        value = recall(key)
        if value:
            return f"{key} is {value}"
        return f"I don't know what {key} is"

    if query == "what do you know about me":
        memory = all_memory()
        if not memory:
            return "i don't know anything about you yet"
        items = []
        for k, v in memory.items():
            items.append(f"{k} is {v}")
        return ". ".join(items)

    # ==========================
    # SPEECH CORRECTIONS
    # ==========================

    replacements = {
        # Edge
        "m s edge": "ms edge",
        "ms hedge": "ms edge",
        "ms age": "ms edge",
        "edge browser": "edge",
        "micro soft edge": "microsoft edge",
        "microsoft age": "microsoft edge",
        "microsoft hedge": "microsoft edge",

        # VS Code
        "vs code": "vscode",
        "visual studio": "visual studio code",

        # Websites
        "you tube": "youtube",
        "git hub": "github",
        "chat gpt": "chatgpt",

        # Explorer
        "file manager": "file explorer",
        "windows explorer": "file explorer",

        # Music
        "english song": "english songs",
        "hindi song": "hindi songs",
        "nepali song": "nepali songs",
        "gym song": "gym songs",
        "workout song": "workout songs",
        "love song": "romantic songs",
        "lo fi": "lofi",
        "low fi": "lofi",

        # Misc
        "command prompt": "cmd",
        "change to": "switch to",
        "go to app": "switch to"

    }

    for old, new in replacements.items():
        query = query.replace(old, new)

    apps_db = load_apps()

    # ==========================
    # PLAY VIDEO / SONG
    # ==========================

    if query.startswith("play "):
        video = query.replace("play ", "").strip()
        try:
            pywhatkit.playonyt(video)
            return f"Playing {video}"
        except Exception:
            return f"Unable to play {video}"

    # ==========================
    # SEARCH YOUTUBE
    # ==========================

    if query.startswith("search youtube "):
        term = query.replace("search youtube ", "").strip()
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(term)
        webbrowser.open(url)
        return f"Searching YouTube for {term}"

    # ==========================
    # GOOGLE SEARCH
    # ==========================

    if query.startswith("search "):
        search_term = query.replace("search ", "").strip()
        url = "https://www.google.com/search?q=" + urllib.parse.quote(search_term)
        webbrowser.open(url)
        return f"Searching for {search_term}"

    # ==========================
    # REFRESH APPS
    # ==========================

    if query == "refresh apps":
        from app_indexer import build_app_index
        count = build_app_index()
        return f"Indexed {count} applications"

    # ==========================
    # LIST APPS
    # ==========================

    if query == "what apps do you know":
        if not apps_db:
            return "No applications indexed yet."
        app_list = sorted(list(apps_db.keys()))[:20]
        return "I know these applications: " + ", ".join(app_list)

    # ==========================
    # WEBSITES
    # ==========================

    websites = {
        "youtube": "https://youtube.com",
        "github": "https://github.com",
        "chatgpt": "https://chatgpt.com",
        "gmail": "https://mail.google.com",
        "linkedin": "https://linkedin.com",
        "instagram": "https://instagram.com",
        "facebook": "https://facebook.com",
        "reddit": "https://reddit.com",
        "stackoverflow": "https://stackoverflow.com",
        "netflix": "https://netflix.com",
        "spotify": "https://open.spotify.com"
    }

    fallback_apps = {
        "edge": "start msedge",
        "ms edge": "start msedge",
        "microsoft edge": "start msedge",

        "chrome": "start chrome",
        "google chrome": "start chrome",
        "firefox": "start firefox",

        "vscode": "start code",
        "visual studio code": "start code",

        "explorer": "start explorer",
        "file explorer": "start explorer",

        "notepad": "start notepad",
        "calculator": "start calc",
        "paint": "start mspaint",
        "cmd": "start cmd",
        "powershell": "start powershell",

        "steam": "start steam",
        "discord": "start discord",
        "spotify": "start spotify"
    }

    # ==========================
    # OPEN
    # ==========================

    if query.startswith("open "):
        item = query.replace("open ", "").strip()

        all_apps = list(apps_db.keys())

        best_match = find_best_match(
            item,
            all_apps
        )

        if best_match:
            item = best_match

        if item in websites:
            webbrowser.open(websites[item])
            return f"Opening {item}"

        if item in apps_db:
            try:
                os.startfile(apps_db[item])
                return f"Opening {item}"
            except Exception:
                return f"Failed to open {item}"

        if item in fallback_apps:
            os.system(fallback_apps[item])
            return f"Opening {item}"

        return f"I couldn't find {item}"

    # ==========================
    # GO TO WEBSITE
    # ==========================

    if query.startswith("go to "):
        site = query.replace("go to ", "").strip()
        site = site.replace(" ", "")
        url = f"https://www.{site}.com"
        webbrowser.open(url)
        return f"Opening {site}"

    # ==========================
    # UNIVERSAL CLOSE
    # ==========================

    # FIX 4: Typo — "startwith" → "startswith"
    if query.startswith("close "):
        app = query.replace("close ", "").strip()
        
        running_apps =[]

        for proc in psutil.process_iter(["name"]):

            try:

                if proc.info["name"]:
                    running_apps.append(
                        proc.info["name"]
                    )

            except:
                pass
        
        best_match = find_best_match(
            app,
            running_apps
        )

        if best_match:
            app = best_match

        if close_app(app):
            return f"Closing {app}"
        return f"Could not find {app}"

    # ==========================
    # SWITCH APPLICATION
    # ==========================

    if query.startswith("switch to "):
        app = query.replace("switch to ", "").strip()
        if switch_to_window(app):
            return f"Switching to {app}"
        return f"Could not find {app}"

    # ==========================
    # SCREENSHOT
    # ==========================

    if query == "take screenshot":
        from datetime import datetime
        folder = "Screenshots"
        os.makedirs(folder, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.png")
        path = os.path.join(folder, filename)
        pyautogui.screenshot(path)
        return "Screenshot saved"

    # ==========================
    # WINDOW CONTROL
    # ==========================

    if query == "maximize window":
        pyautogui.hotkey("win", "up")
        return "Maximizing window"

    if query == "minimize window":
        pyautogui.hotkey("win", "down")
        return "Minimizing window"

    # ==========================
    # POWERPOINT
    # ==========================

    if query == "next slide":
        pyautogui.press("right")
        return "Next slide"

    if query == "previous slide":
        pyautogui.press("left")
        return "Previous slide"

    if query == "start slideshow":
        pyautogui.press("f5")
        return "Starting slideshow"

    if query == "end slideshow":
        pyautogui.press("esc")
        return "Ending slideshow"

    # ==========================
    # VOLUME
    # ==========================

    if query == "volume up":
        pyautogui.press("volumeup")
        return "Increasing volume"

    if query == "volume down":
        pyautogui.press("volumedown")
        return "Decreasing volume"

    if query == "mute":
        pyautogui.press("volumemute")
        return "Muting volume"

    return None