import os
import json
import re
import pyautogui
from core.browser_manager import browser_manager
from core.search_manager import search_manager
from memory import remember, recall, all_memory
from pathlib import Path
from ui.overlay_manager import overlay_manager
from rapidfuzz import process
from core.session import session
from core.folder_operations import create_folder
import psutil
import pygetwindow as gw
from file_manager import (
    format_results,
    format_document_results,
    format_universal_results,
    open_file,
    open_file_path,
    found_files,

    format_folder_results,
    open_folder
)

from app_indexer import (
    load_apps,
    build_app_index
)

APPS_DB = load_apps()

NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20"
}
    
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

SMART_DOCUMENT_WORDS = {
    "document",
    "documents",
    "pdf",
    "pdfs",
    "word",
    "doc",
    "docx",
    "excel",
    "xlsx",
    "sheet",
    "spreadsheet",
    "powerpoint",
    "ppt",
    "pptx",
    "presentation",
    "presentations",
    "slide",
    "slides",
}

SMART_FOLDER_WORDS = {
    "folder",
    "folders",
    "directory",
    "directories",
}

SMART_IGNORE_WORDS = {
    "find",
    "show",
    "display",
    "search",
    "open",
    "my",
    "the",
    "a",
    "an",
    "please",
}

def extract_search_keyword(query):

    words = []

    for word in query.lower().split():
        if word in SMART_IGNORE_WORDS:
            continue

        if word in SMART_DOCUMENT_WORDS:
            continue

        if word in SMART_FOLDER_WORDS:
            continue

        words.append(word)

    return " ".join(words)

def run_command(query):

    global APPS_DB

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
        
        pattern = r"\b" + re.escape(old) + r"\b"

        query = re.sub(
            pattern,
            new,
            query
        )

    apps_db = APPS_DB

    # ==========================
    # PLAY VIDEO / SONG
    # ==========================

    if query.startswith("play "):
        media = query.replace("play ", "").strip()
        success = browser_manager.play(media)
        if success:
            return f"Playing {media}"
        
        return f"Unable to play {media}"

    # ==========================
    # SEARCH YOUTUBE
    # ==========================

    if query.startswith("search youtube "):
        term = query.replace("search youtube ", "").strip()
        browser_manager.youtube_search(term)
        return f"Searching YouTube for {term}"

    # ==========================
    # GOOGLE SEARCH
    # ==========================

    if query.startswith("search "):
        search_term = query.replace("search ", "").strip()
        browser_manager.google_search(search_term)
        return f"Searching for {search_term}"

    # ==========================
    # REFRESH APPS
    # ==========================
    if query == "refresh apps":


        count = build_app_index()

        APPS_DB = load_apps()

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
    # OPEN FOUND FOLDER
    # ==========================

    if query.startswith("open folder "):

        value = query.replace(
            "open folder ",
            ""
        ).strip().lower()

        value = NUMBER_WORDS.get(value, value)

        if session.is_active():

            try:

                index = int(value) - 1

                item = session.get(index)

                if item:

                    if open_folder(item["name"]):
                        return "Opening folder."
                    
            except ValueError:
                pass

        if open_folder(value):
            return "Opening folder."
        
        return "I couldn't find that folder."

    # ==========================
    # OPEN FOUND FILE
    # ==========================

    if query.startswith("open file "):

        value = query.replace(
             "open file ",
             ""
        ).strip().lower()

        value = NUMBER_WORDS.get(value, value)

        if session.is_active():

            try:
                index = int(value) - 1

                item = session.get(index)

                if item:

                    if open_file_path(item["path"]):
                        return "Opening."

            except ValueError:
              pass

        if open_file(value):
            return "Opening."

        return "I couldn't find that file."
    
    # ==========================
    # CREATE FOLDER
    # ==========================

    if (
        query.startswith("create folder ")
        or query.startswith("make folder ")
        or query.startswith("new folder ")
    ):
        
        if query.startswith("create folder "):
            name = query.replace("create folder ", "")

        elif query.startswith("make folder "):
            name = query.replace("make folder ", "")

        else:
            name = query.replace("new folder ", "")

        success, message = create_folder(name.strip())

        return message
    
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
            browser_manager.open_url(websites[item])
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
        browser_manager.open_url(url)
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
    # RECENT FILES
    # ==========================

    if query in {
        "recent files",
        "show recent files",
        "recent documents"
    }:
        
        results = search_manager.search_recent(limit=20)

        if not results:
            return "You have no recent files."
        
        return format_results(results)
    
    # ==========================
    # UNIVERSAL SEARCH
    # ==========================

    if query.startswith("find everything "):

        keyword = query.replace(
            "find everything ",
            ""
        ).strip()

        results = search_manager.search(
            keyword,
            limit=20
        )

        if not results:
            return"I couldn't find anything."
        
        return format_universal_results(results)

    # ==========================
    # DOCUMENT CONTENT SEARCH
    # ==========================

    if query.startswith("find documents containing "):

        # --------------------------
        # SMART DOCUMENT SEARCH
        # --------------------------

        words = query.split()

        if any(word in SMART_DOCUMENT_WORDS for word in words):
            keyword = extract_search_keyword(query)

            if keyword:
                results = search_manager.search_documents(
                    keyword,
                    limit=20
                )

                if results:
                    return format_document_results(results)
        # --------------------------
        # Normal Document Search
        # --------------------------
        
        keyword = query.replace(
            "find documents containing ",
            ""
        ).strip()

        results = search_manager.search_documents(
            keyword,
            limit=20  
        )

        if not results:
            return "no matching documents found."
        
        return format_document_results(results)

    # ==========================
    # FILE SEARCH
    # ==========================

    COMMAND_WORDS = {
        "find",
        "pull",
        "show",
        "display",
        "list"
    }

    IGNORE_WORDS = {
        "file",
        "files",
        "document",
        "documents",
        "all",
        "my"
    }

    FOLDER_WORDS = {
        "folder",
        "folders",
        "directory",
        "directories"
    }

    words = query.split()

    if words and words[0] in COMMAND_WORDS:

        # ----------------------------------
        # Detect folder search
        # ----------------------------------

        is_folder_search = any(
            word in FOLDER_WORDS
            for word in words
        )

        # ----------------------------------
        # Build search keyword
        # ----------------------------------

        search_words = []

        for word in words[1:]:

            if word in IGNORE_WORDS:
                continue

            if word in FOLDER_WORDS:
                continue

            search_words.append(word)

        keyword = " ".join(search_words).strip()

        # ----------------------------------
        # Folder Search
        # ----------------------------------

        if is_folder_search:

            results = search_manager.search_folders(
                keyword,
                limit=500
            )

            if not results:

                if keyword:
                    return f"I couldn't find any folders named {keyword}."

                return "I couldn't find any folders."

            return format_folder_results(results)

        # ----------------------------------
        # File Search
        # ----------------------------------

        results = search_manager.search_files(
            keyword,
            limit=500
        )

        if not results:         

            if keyword:
                return f"Could not find any {keyword}."

            return "What would you like me to search for?"

        return format_results(results)

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
    # MEDIA CONTROL
    # ==========================

    if query in [
        "pause",
        "pause song"
    ]:
        pyautogui.press("playpause")
        return "Pausing"
    
    if query in [
        "resume",
        "resume song",
        "play"
    ]:
        pyautogui.press("playpause")
        return "Resuming"
    
    if query in [
        "next",
        "next song",
        "skip",
        "skip song"
    ]:
        pyautogui.press("nexttrack")
        return "Next song"
    
    if query in [
        "previous",
        "previous song",
        "last song"
    ]:
        pyautogui.press("prevtrack")
        return "Previous song"

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