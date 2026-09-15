import os
import json
import re
import pyautogui
from datetime import datetime
from core.browser_manager import browser_manager
from core.search_manager import search_manager
from memory import remember, recall, all_memory, search_memory_facts, forget
from pathlib import Path
from ui.overlay_manager import overlay_manager
from rapidfuzz import process
from core.session import session
from core.folder_operations import create_folder
from core.vision.vision_command import vision_commands
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

PULL_MAP = {
    "pdfs": [".pdf"],
    "pdf": [".pdf"],
    "word files": [".doc", ".docx"],
    "word file": [".doc", ".docx"],
    "word": [".doc", ".docx"],
    "documents": [".doc", ".docx"],
    "docs": [".doc", ".docx"],
    "excel files": [".xls", ".xlsx", ".csv"],
    "excel file": [".xls", ".xlsx", ".csv"],
    "excel": [".xls", ".xlsx", ".csv"],
    "spreadsheets": [".xls", ".xlsx", ".csv"],
    "sheets": [".xls", ".xlsx", ".csv"],
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg", ".heic"],
    "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg", ".heic"],
    "photos": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg", ".heic"],
    "pictures": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".svg", ".heic"],
    "videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".m4v", ".3gp"],
    "video": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".m4v", ".3gp"],
    "movies": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".m4v", ".3gp"],
    "python files": [".py"],
    "python file": [".py"],
    "python": [".py"],
    "py files": [".py"],
    "code files": [".py", ".js", ".ts", ".java", ".cpp", ".c", ".cs", ".go", ".rs"],
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
            return value
        return f"I don't know what {key} is"

    if query == "what do you know about me":
        memory = all_memory()
        if not memory:
            return "i don't know anything about you yet"
        items = []
        for k, v in memory.items():
            items.append(f"{k} is {v}")
        return ". ".join(items)

    if query.startswith("search memory ") or query.startswith("find in memory "):
        search_query = query.replace("search memory ", "").replace("find in memory ", "").strip()
        results = search_memory_facts(search_query, n_results=5)
        if not results:
            return "No matching memories found."
        response = "I found these relevant memories: "
        for r in results:
            response += f"{r['text']}. "
        return response

    if query == "forget all memories":
        from memory import load_memory, save_memory
        from core.semantic_memory import collection
        save_memory({})
        if collection:
            ids = collection.get()["ids"]
            if ids:
                collection.delete(ids=ids)
        return "All memories cleared."

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

    if query.startswith("search for "):
        keyword = query.replace("search for ", "").strip()
        results = search_manager.search_files(keyword, limit=20)
        if not results:
            return f"Could not find any {keyword}."
        return format_results(results)

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

        # Handle "open 1", "open 2", etc. - open by index from found_files
        item_normalized = NUMBER_WORDS.get(item, item)
        if item_normalized.isdigit():
            path = found_files.get(item_normalized)
            if path:
                if open_file_path(path):
                    return "Opening."
            return "I couldn't find that file."

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
        "list",
        "get",
        "search"
    }

    IGNORE_WORDS = {
        "file",
        "files",
        "document",
        "documents",
        "all",
        "my",
        "for"
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

        # Handle "pull pdfs", "pull images", etc. using PULL_MAP
        pull_extensions = None
        if words[0] == "pull":
            for key, exts in PULL_MAP.items():
                if keyword == key or keyword.startswith(key + " "):
                    pull_extensions = exts
                    keyword = keyword.replace(key, "").strip()
                    break

        if pull_extensions:
            from core.search_filter import SearchFilter
            search_filter = SearchFilter()
            search_filter.keyword = keyword
            search_filter.extensions = pull_extensions
            search_filter.limit = 500
            from core.search_engine import search_engine
            rows = search_engine.search(search_filter)
            results = []
            for name, path, extension in rows:
                results.append({
                    "name": name,
                    "stem": Path(name).stem,
                    "path": path,
                    "extension": extension,
                })
        else:
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

    # ============================
    # VISION
    # ============================

    if query in [
        "read my screen",
        "what is on my screen",
        "read screen",
    ]:
        return vision_commands.read_screen()

    # ============================
    # AI VISION (Phase 7)
    # ============================

    if query.startswith("describe screen"):
        detail = query.replace("describe screen", "").strip()
        return vision_commands.describe_screen(detail)

    if query.startswith("describe window"):
        detail = query.replace("describe window", "").strip()
        return vision_commands.describe_window(detail)

    if query.startswith("ask about screen ") or query.startswith("ask screen "):
        question = query.replace("ask about screen ", "").replace("ask screen ", "").strip()
        return vision_commands.ask_about_screen(question)

    if query in [
        "read screen text",
        "extract screen text",
        "get screen text",
    ]:
        return vision_commands.read_screen_text()

    if query.startswith("find on screen ") or query.startswith("locate on screen "):
        desc = query.replace("find on screen ", "").replace("locate on screen ", "").strip()
        return vision_commands.find_on_screen(desc)

    if query in [
        "analyze code",
        "read code",
        "explain code on screen",
    ]:
        return vision_commands.analyze_code()

    if query in [
        "analyze error",
        "read error",
        "what is the error",
    ]:
        return vision_commands.analyze_error()

    # ============================
    # CONTEXT ENGINE (Phase 8)
    # ============================

    if query in [
        "show context",
        "what is my context",
        "session context",
    ]:
        from core.context_engine import get_current_session, build_context_for_llm
        sid = get_current_session()
        return build_context_for_llm(sid)

    if query.startswith("remember fact ") or query.startswith("learn fact "):
        fact_text = query.replace("remember fact ", "").replace("learn fact ", "").strip()
        if " is " in fact_text:
            key, value = fact_text.split(" is ", 1)
            from core.context_engine import add_knowledge_fact
            add_knowledge_fact(key.strip(), value.strip(), source="user", confidence=1.0)
            return f"Learned: {key} is {value}"
        return "Say 'remember fact key is value'"

    if query.startswith("what do you know about "):
        topic = query.replace("what do you know about ", "").strip()
        from core.context_engine import search_knowledge_facts
        results = search_knowledge_facts(topic, limit=5)
        if not results:
            return f"I don't have any facts about {topic}."
        response = f"Here's what I know about {topic}: "
        for r in results:
            response += f"{r['fact_key']} is {r['fact_value']}. "
        return response

    if query in [
        "list tasks",
        "show tasks",
        "my tasks",
    ]:
        from core.context_engine import get_current_session, get_active_tasks
        sid = get_current_session()
        tasks = get_active_tasks(sid)
        if not tasks:
            return "No active tasks."
        response = "Active tasks: "
        for t in tasks:
            response += f"{t['task_type']}: {t['description']}. "
        return response

    if query.startswith("start task "):
        task_desc = query.replace("start task ", "").strip()
        from core.context_engine import get_current_session, create_task
        sid = get_current_session()
        task_id = create_task(sid, "general", task_desc)
        return f"Started task #{task_id}: {task_desc}"

    if query.startswith("complete task "):
        task_id_str = query.replace("complete task ", "").strip()
        if task_id_str.isdigit():
            from core.context_engine import update_task
            update_task(int(task_id_str), status="completed")
            return f"Task #{task_id_str} marked complete."
        return "Say 'complete task <number>'"

    if query in [
        "show project",
        "current project",
        "project info",
    ]:
        from core.context_engine import get_recent_projects
        projects = get_recent_projects(1)
        if not projects:
            return "No project context."
        p = projects[0]
        return f"Project: {p['project_name']} ({p['language']}, {p['framework']}) - last file: {p['last_file']}"

    if query in [
        "list projects",
        "recent projects",
    ]:
        from core.context_engine import get_recent_projects
        projects = get_recent_projects(5)
        if not projects:
            return "No recent projects."
        response = "Recent projects: "
        for p in projects:
            response += f"{p['project_name']} ({p['language']}). "
        return response

    # ============================
    # CODING AGENT (Phase 9)
    # ============================

    if query.startswith("generate code ") or query.startswith("write code "):
        prompt = query.replace("generate code ", "").replace("write code ", "").strip()
        if " in " in prompt:
            parts = prompt.rsplit(" in ", 1)
            prompt = parts[0].strip()
            language = parts[1].strip()
        else:
            language = "python"
        from core.coding_agent import coding_agent
        code = coding_agent.generate_code(prompt, language)
        return f"Here's the {language} code:\n{code}"

    if query.startswith("explain code") or query.startswith("explain this code"):
        from core.coding_agent import coding_agent
        # Get code from clipboard or last file
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        explanation = coding_agent.explain_code(code)
        return explanation

    if query.startswith("review code"):
        from core.coding_agent import coding_agent
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        review = coding_agent.review_code(code)
        return review

    if query.startswith("fix code"):
        from core.coding_agent import coding_agent
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        error = query.replace("fix code", "").strip()
        if not error:
            return "What error should I fix? Say 'fix code <error message>'"
        fixed = coding_agent.fix_code(code, error)
        return f"Fixed code:\n{fixed}"

    if query.startswith("refactor code"):
        from core.coding_agent import coding_agent
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        instruction = query.replace("refactor code", "").strip()
        if not instruction:
            return "How should I refactor? Say 'refactor code <instruction>'"
        refactored = coding_agent.refactor_code(code, instruction)
        return f"Refactored code:\n{refactored}"

    if query.startswith("generate tests"):
        from core.coding_agent import coding_agent
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        tests = coding_agent.generate_tests(code)
        return f"Tests:\n{tests}"

    if query.startswith("generate docs") or query.startswith("document code"):
        from core.coding_agent import coding_agent
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        docs = coding_agent.generate_docs(code)
        return f"Documented code:\n{docs}"

    if query.startswith("analyze file "):
        file_path = query.replace("analyze file ", "").strip()
        from core.coding_agent import coding_agent
        result = coding_agent.analyze_file(file_path)
        if "error" in result:
            return result["error"]
        return f"File: {result['file_path']}\nLanguage: {result['language']}\nLines: {result['lines']}\nAnalysis: {result['analysis']}"

    if query.startswith("find bugs"):
        from core.coding_agent import coding_agent
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        bugs = coding_agent.find_bugs(code)
        return bugs

    if query.startswith("optimize code"):
        from core.coding_agent import coding_agent
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        optimized = coding_agent.optimize_code(code)
        return f"Optimized code:\n{optimized}"

    if query.startswith("convert code"):
        from core.coding_agent import coding_agent
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        parts = query.replace("convert code", "").strip().split(" to ")
        if len(parts) != 2:
            return "Say 'convert code <from> to <to>'"
        from_lang = parts[0].strip()
        to_lang = parts[1].strip()
        converted = coding_agent.convert_code(code, from_lang, to_lang)
        return f"Converted to {to_lang}:\n{converted}"

    # ============================
    # WIDGETS
    # ============================

    if query in [
        "show system info",
        "system info",
        "system status",
        "hardware info",
    ]:
        from ui.overlay_manager import overlay_manager
        overlay_manager.show_system_info()
        return "Showing system information"

    if query in [
        "show notifications",
        "test notification",
    ]:
        from ui.overlay_manager import overlay_manager
        overlay_manager.show_notification("Test notification from Nova", "✓", "#4ECC4E", 5)
        return "Notification sent"

    if query in [
        "show progress",
        "test progress",
    ]:
        from ui.overlay_manager import overlay_manager
        progress = overlay_manager.show_progress("Testing progress widget")
        import time
        def update_progress():
            for i in range(101):
                progress.update_progress(i, f"Processing... {i}%")
                time.sleep(0.02)
            progress.complete("Test complete!")
        import threading
        threading.Thread(target=update_progress, daemon=True).start()
        return "Showing progress test"

    # ============================
    # RESEARCH AGENT (Phase 10)
    # ============================

    if query.startswith("research ") or query.startswith("look up "):
        topic = query.replace("research ", "").replace("look up ", "").strip()
        depth = "standard"
        if " deep" in topic:
            depth = "deep"
            topic = topic.replace(" deep", "")
        elif " quick" in topic:
            depth = "quick"
            topic = topic.replace(" quick", "")
        from core.research_agent import research_agent
        result = research_agent.research(topic, depth=depth)
        response = f"Research on '{topic}':\n\n{result.summary}\n\n"
        if result.key_findings:
            response += "Key findings:\n" + "\n".join(f"• {f}" for f in result.key_findings[:5])
        if result.sources:
            response += "\n\nSources:\n" + "\n".join(f"• {s.title} ({s.url})" for s in result.sources[:3])
        return response

    if query.startswith("quick fact ") or query.startswith("fact check "):
        topic = query.replace("quick fact ", "").replace("fact check ", "").strip()
        from core.research_agent import research_agent
        return research_agent.quick_fact(topic)

    if query.startswith("compare ") and " vs " in query:
        parts = query.replace("compare ", "").split(" vs ")
        topic_a = parts[0].strip()
        rest = parts[1].strip()
        topic_b = rest
        aspect = ""
        if " on " in rest:
            topic_b, aspect = rest.split(" on ", 1)
            topic_b = topic_b.strip()
            aspect = aspect.strip()
        from core.research_agent import research_agent
        result = research_agent.compare(topic_a, topic_b, aspect)
        response = f"Comparison: {topic_a} vs {topic_b}\n\n{result.summary}"
        if result.key_findings:
            response += "\n\nKey points:\n" + "\n".join(f"• {f}" for f in result.key_findings[:5])
        return response

    if query.startswith("latest news ") or query.startswith("news about "):
        topic = query.replace("latest news ", "").replace("news about ", "").strip()
        from core.research_agent import research_agent
        result = research_agent.latest_news(topic)
        response = f"Latest news on '{topic}':\n\n{result.summary}"
        if result.key_findings:
            response += "\n\nKey updates:\n" + "\n".join(f"• {f}" for f in result.key_findings[:5])
        return response

    if query.startswith("technical research ") or query.startswith("deep research "):
        topic = query.replace("technical research ", "").replace("deep research ", "").strip()
        from core.research_agent import research_agent
        result = research_agent.technical_research(topic)
        response = f"Technical research on '{topic}':\n\n{result.summary}"
        if result.key_findings:
            response += "\n\nKey findings:\n" + "\n".join(f"• {f}" for f in result.key_findings[:5])
        if result.sources:
            response += "\n\nSources:\n" + "\n".join(f"• {s.title} ({s.url})" for s in result.sources[:3])
        return response

    # ============================
    # WRITING AGENT (Phase 11)
    # ============================

    if query.startswith("write ") or query.startswith("generate text "):
        prompt = query.replace("write ", "").replace("generate text ", "").strip()
        style = WritingStyle.FORMAL
        length = "medium"
        if "casual" in prompt.lower():
            style = WritingStyle.CASUAL
            prompt = prompt.replace("casual", "").strip()
        elif "technical" in prompt.lower():
            style = WritingStyle.TECHNICAL
            prompt = prompt.replace("technical", "").strip()
        elif "creative" in prompt.lower():
            style = WritingStyle.CREATIVE
            prompt = prompt.replace("creative", "").strip()
        if "short" in prompt.lower():
            length = "short"
            prompt = prompt.replace("short", "").strip()
        elif "long" in prompt.lower():
            length = "long"
            prompt = prompt.replace("long", "").strip()
        from core.writing_agent import writing_agent, WritingStyle
        return writing_agent.generate(prompt, style=style, length=length)

    if query.startswith("edit text ") or query.startswith("improve text "):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No text in clipboard. Copy text first."
        except:
            return "Could not access clipboard."
        instruction = query.replace("edit text ", "").replace("improve text ", "").strip()
        from core.writing_agent import writing_agent
        return writing_agent.edit(content, instruction)

    if query.startswith("rewrite "):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No text in clipboard. Copy text first."
        except:
            return "Could not access clipboard."
        style_str = query.replace("rewrite ", "").strip()
        style = WritingStyle.FORMAL
        if "casual" in style_str:
            style = WritingStyle.CASUAL
        elif "technical" in style_str:
            style = WritingStyle.TECHNICAL
        elif "creative" in style_str:
            style = WritingStyle.CREATIVE
        from core.writing_agent import writing_agent, WritingStyle
        return writing_agent.rewrite(content, style=style)

    if query.startswith("summarize "):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No text in clipboard. Copy text first."
        except:
            return "Could not access clipboard."
        length = "short"
        if "medium" in query:
            length = "medium"
        elif "long" in query:
            length = "long"
        from core.writing_agent import writing_agent
        return writing_agent.summarize(content, length=length)

    if query.startswith("expand text "):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No text in clipboard. Copy text first."
        except:
            return "Could not access clipboard."
        from core.writing_agent import writing_agent
        return writing_agent.expand(content)

    if query.startswith("outline "):
        topic = query.replace("outline ", "").strip()
        from core.writing_agent import writing_agent
        return writing_agent.outline(topic)

    if query.startswith("fix grammar") or query.startswith("check grammar"):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No text in clipboard. Copy text first."
        except:
            return "Could not access clipboard."
        from core.writing_agent import writing_agent
        return writing_agent.fix_grammar(content)

    if query.startswith("change tone "):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No text in clipboard. Copy text first."
        except:
            return "Could not access clipboard."
        tone = query.replace("change tone ", "").strip()
        style = WritingStyle.FORMAL
        if "casual" in tone:
            style = WritingStyle.CASUAL
        elif "technical" in tone:
            style = WritingStyle.TECHNICAL
        elif "creative" in tone:
            style = WritingStyle.CREATIVE
        elif "business" in tone:
            style = WritingStyle.BUSINESS
        from core.writing_agent import writing_agent, WritingStyle
        return writing_agent.change_tone(content, style)

    # Templates
    if query.startswith("write email "):
        prompt = query.replace("write email ", "").strip()
        from core.writing_agent import writing_agent
        return writing_agent.write_email(prompt)

    if query.startswith("write report "):
        prompt = query.replace("write report ", "").strip()
        from core.writing_agent import writing_agent
        return writing_agent.write_report(prompt)

    if query.startswith("write blog "):
        prompt = query.replace("write blog ", "").strip()
        from core.writing_agent import writing_agent
        return writing_agent.write_blog(prompt)

    if query.startswith("write readme "):
        prompt = query.replace("write readme ", "").strip()
        from core.writing_agent import writing_agent
        return writing_agent.write_readme(prompt)

    if query.startswith("write docstring"):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        from core.writing_agent import writing_agent
        return writing_agent.write_docstring(content)

    if query.startswith("write commit"):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No changes in clipboard. Copy git diff first."
        except:
            return "Could not access clipboard."
        from core.writing_agent import writing_agent
        return writing_agent.write_commit(content)

    if query.startswith("write pr") or query.startswith("write pull request"):
        import pyperclip
        try:
            content = pyperclip.paste()
            if not content or len(content) < 10:
                return "No changes in clipboard. Copy git diff first."
        except:
            return "Could not access clipboard."
        from core.writing_agent import writing_agent
        return writing_agent.write_pr_description(content)

    # ============================
    # OFFICE AGENT (Phase 12)
    # ============================

    if query.startswith("create document ") or query.startswith("new document "):
        parts = query.replace("create document ", "").replace("new document ", "").split(" ", 1)
        doc_type = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        from core.office_agent import office_agent, DocumentType
        type_map = {
            "word": DocumentType.WORD, "docx": DocumentType.WORD,
            "excel": DocumentType.EXCEL, "xlsx": DocumentType.EXCEL, "spreadsheet": DocumentType.EXCEL,
            "powerpoint": DocumentType.POWERPOINT, "pptx": DocumentType.POWERPOINT, "presentation": DocumentType.POWERPOINT,
            "csv": DocumentType.CSV,
            "json": DocumentType.JSON,
            "markdown": DocumentType.MARKDOWN, "md": DocumentType.MARKDOWN,
        }
        if doc_type not in type_map:
            return f"Unknown document type: {doc_type}. Supported: word, excel, powerpoint, csv, json, markdown"
        file_path = f"{doc_type}_document.{type_map[doc_type].value}"
        if doc_type in ["word", "docx"]:
            file_path = "document.docx"
        elif doc_type in ["excel", "xlsx", "spreadsheet"]:
            file_path = "spreadsheet.xlsx"
        elif doc_type in ["powerpoint", "pptx", "presentation"]:
            file_path = "presentation.pptx"
        elif doc_type == "csv":
            file_path = "data.csv"
        elif doc_type == "json":
            file_path = "data.json"
        elif doc_type in ["markdown", "md"]:
            file_path = "document.md"
        result = office_agent.create_document(type_map[doc_type], file_path, title=rest or "New Document")
        return result.message

    if query.startswith("read document ") or query.startswith("open document "):
        file_path = query.replace("read document ", "").replace("open document ", "").strip()
        from core.office_agent import office_agent
        result = office_agent.read_document(file_path)
        if not result.success:
            return result.message
        data = result.data
        if isinstance(data, dict) and "data" in data:
            return f"Read {file_path}:\n{str(data['data'])[:500]}"
        return f"Read {file_path}:\n{str(data)[:500]}"

    if query.startswith("file info ") or query.startswith("document info "):
        file_path = query.replace("file info ", "").replace("document info ", "").strip()
        from core.office_agent import office_agent
        result = office_agent.get_document_info(file_path)
        if not result.success:
            return result.message
        info = result.data
        return f"File: {info['name']}\nType: {info['type']}\nSize: {info['size']} bytes\nModified: {info['modified']}"

    if query.startswith("create spreadsheet ") or query.startswith("new spreadsheet"):
        from core.office_agent import office_agent
        name = query.replace("create spreadsheet ", "").replace("new spreadsheet", "").strip()
        file_path = f"{name}.xlsx" if name else "spreadsheet.xlsx"
        result = office_agent.create_excel(file_path)
        return result.message

    if query.startswith("create presentation ") or query.startswith("new presentation"):
        from core.office_agent import office_agent
        name = query.replace("create presentation ", "").replace("new presentation", "").strip()
        file_path = f"{name}.pptx" if name else "presentation.pptx"
        result = office_agent.create_powerpoint(file_path)
        return result.message

    if query.startswith("convert to csv"):
        file_path = query.replace("convert to csv", "").strip()
        from core.office_agent import office_agent
        result = office_agent.excel_to_csv(file_path)
        return result.message

    if query.startswith("convert to excel"):
        file_path = query.replace("convert to excel", "").strip()
        from core.office_agent import office_agent
        result = office_agent.csv_to_excel(file_path)
        return result.message

    # ============================
    # OFFLINE INTELLIGENCE (Phase 13)
    # ============================

    if query in ["list models", "show models", "available models"]:
        from core.offline_intelligence import list_models
        models = list_models()
        if not models:
            return "No models found."
        response = f"Available models ({len(models)}):\n"
        for m in models:
            response += f"• {m.name} ({m.size})"
            if m.quantization:
                response += f" [{m.quantization}]"
            if m.parameters:
                response += f" {m.parameters}"
            if m.family:
                response += f" ({m.family})"
            response += "\n"
        return response

    if query.startswith("pull model ") or query.startswith("download model "):
        name = query.replace("pull model ", "").replace("download model ", "").strip()
        from core.offline_intelligence import pull_model
        def progress_cb(status, msg):
            print(f"[{status.value}] {msg}")
        success = pull_model(name, progress_cb)
        return f"Model '{name}' {'downloaded' if success else 'failed'}."

    if query.startswith("remove model ") or query.startswith("delete model "):
        name = query.replace("remove model ", "").replace("delete model ", "").strip()
        from core.offline_intelligence import remove_model
        success = remove_model(name)
        return f"Model '{name}' {'removed' if success else 'not found'}."

    if query.startswith("benchmark model "):
        name = query.replace("benchmark model ", "").strip()
        from core.offline_intelligence import benchmark_model
        result = benchmark_model(name)
        if result["successful"] == 0:
            return f"Benchmark failed for {name}"
        return (f"Benchmark: {name}\n"
                f"Avg TPS: {result['avg_tokens_per_sec']:.1f}\n"
                f"Total tokens: {result['total_tokens']}\n"
                f"Total time: {result['total_time']:.1f}s\n"
                f"Successful prompts: {result['successful']}/{result['total_prompts']}")

    if query.startswith("compare models"):
        models_str = query.replace("compare models", "").strip()
        if not models_str:
            return "Say 'compare models model1, model2, model3'"
        models = [m.strip() for m in models_str.split(",")]
        from core.offline_intelligence import compare_models
        results = compare_models(models)
        response = "Model Comparison (by TPS):\n"
        for i, r in enumerate(results, 1):
            response += f"{i}. {r['model']}: {r['avg_tokens_per_sec']:.1f} TPS\n"
        return response

    if query.startswith("set model ") or query.startswith("use model "):
        name = query.replace("set model ", "").replace("use model ", "").strip()
        from core.offline_intelligence import inference_engine, InferenceConfig
        inference_engine.set_config(InferenceConfig(model=name))
        return f"Active model set to: {name}"

    if query in ["inference stats", "model stats", "performance stats"]:
        from core.offline_intelligence import inference_engine
        stats = inference_engine.get_stats()
        return (f"Inference Stats:\n"
                f"Requests: {stats['total_requests']}\n"
                f"Total tokens: {stats['total_tokens']}\n"
                f"Total time: {stats['total_time']:.1f}s\n"
                f"Avg TPS: {stats['avg_tokens_per_sec']:.1f}")

    if query in ["reset stats", "clear stats"]:
        from core.offline_intelligence import inference_engine
        inference_engine.reset_stats()
        return "Performance stats reset."

    if query.startswith("set temperature "):
        try:
            val = float(query.replace("set temperature ", "").strip())
            from core.offline_intelligence import inference_engine, InferenceConfig
            cfg = inference_engine.get_config()
            cfg.temperature = val
            inference_engine.set_config(cfg)
            return f"Temperature set to {val}"
        except:
            return "Invalid temperature value (0.0-2.0)"

    if query.startswith("set context ") or query.startswith("context length "):
        try:
            val = int(query.replace("set context ", "").replace("context length ", "").strip())
            from core.offline_intelligence import inference_engine, InferenceConfig
            cfg = inference_engine.get_config()
            cfg.num_ctx = val
            inference_engine.set_config(cfg)
            return f"Context length set to {val}"
        except:
            return "Invalid context length"

    if query.startswith("set gpu layers "):
        try:
            val = int(query.replace("set gpu layers ", "").strip())
            from core.offline_intelligence import inference_engine, InferenceConfig
            cfg = inference_engine.get_config()
            cfg.num_gpu = val
            inference_engine.set_config(cfg)
            return f"GPU layers set to {val} (-1 = all)"
        except:
            return "Invalid GPU layers value"

    # ============================
    # PERSONAL CONTEXT ENGINE (Phase 14)
    # ============================

    if query in ["show preferences", "my preferences", "learned preferences"]:
        from core.personal_context import get_user_preferences
        prefs = get_user_preferences(0.5)
        if not prefs:
            return "No learned preferences yet. Use Nova more to build your profile."
        response = "Your learned preferences:\n"
        for key, pref in prefs.items():
            val = pref["value"]
            if isinstance(val, dict):
                val = str(val)[:100]
            response += f"• {key}: {val} (conf: {pref['confidence']:.0%}, src: {pref['source']})\n"
        return response

    if query.startswith("set preference ") or query.startswith("prefer "):
        text = query.replace("set preference ", "").replace("prefer ", "").strip()
        if " is " in text or " = " in text:
            sep = " is " if " is " in text else " = "
            key, value = text.split(sep, 1)
            from core.personal_context import set_user_preference
            set_user_preference(key.strip(), value.strip(), confidence=1.0, source="explicit")
            return f"Preference set: {key} = {value}"
        return "Say 'set preference key is value' or 'prefer key = value'"

    if query in ["show habits", "my habits", "detected habits"]:
        from core.personal_context import personal_context
        habits = personal_context.detect_habits()
        if not habits:
            return "No habits detected yet."
        response = "Detected habits:\n"
        for h in habits:
            response += f"• {h['name']} (freq: {h['frequency']}, strength: {h['strength']:.0%})\n"
        return response

    if query in ["show suggestions", "my suggestions", "proactive suggestions"]:
        from core.personal_context import get_suggestions
        suggestions = get_suggestions()
        if not suggestions:
            return "No suggestions at this time."
        response = "Proactive suggestions:\n"
        for s in suggestions:
            response += f"• {s['content']} (priority: {s['priority']})\n"
        return response

    if query in ["adaptive config", "my config", "personalized config"]:
        from core.personal_context import get_adaptive_config
        config = get_adaptive_config()
        if not config:
            return "No adaptive configuration yet."
        response = "Adaptive configuration:\n"
        for k, v in config.items():
            response += f"• {k}: {v}\n"
        return response

    if query in ["export context", "backup context", "save context"]:
        from core.personal_context import export_personal_context
        path = export_personal_context()
        return f"Context exported to: {path}"

    if query.startswith("import context "):
        path = query.replace("import context ", "").strip()
        from core.personal_context import import_personal_context
        success = import_personal_context(path)
        return f"Context {'imported' if success else 'failed to import'}."

    # ============================
    # LECTURE INTELLIGENCE (Phase 15)
    # ============================

    if query in ["start lecture", "begin lecture", "record lecture"]:
        title = ""
        if "start lecture " in query:
            title = query.replace("start lecture ", "").strip()
        elif "begin lecture " in query:
            title = query.replace("begin lecture ", "").strip()
        elif "record lecture " in query:
            title = query.replace("record lecture ", "").strip()
        from core.lecture_intelligence import start_lecture
        session = start_lecture(title)
        return f"Lecture started: {session.title} (ID: {session.id})"

    if query in ["pause lecture", "pause recording"]:
        from core.lecture_intelligence import pause_lecture
        pause_lecture()
        return "Lecture paused."

    if query in ["resume lecture", "resume recording", "continue lecture"]:
        from core.lecture_intelligence import resume_lecture
        resume_lecture()
        return "Lecture resumed."

    if query in ["end lecture", "stop lecture", "finish lecture", "stop recording"]:
        from core.lecture_intelligence import end_lecture
        session = end_lecture()
        if not session:
            return "No active lecture to end."
        response = f"Lecture ended: {session.title}\n"
        response += f"Duration: {int((session.ended_at - session.started_at) / 60)} minutes\n"
        if session.summary:
            response += f"\nSummary: {session.summary[:200]}..."
        if session.key_topics:
            response += f"\nKey topics: {', '.join(session.key_topics[:5])}"
        if session.action_items:
            response += f"\nAction items: {len(session.action_items)} found"
        return response

    if query.startswith("lecture summary") or query.startswith("summarize lecture"):
        session_id = query.replace("lecture summary", "").replace("summarize lecture", "").strip()
        from core.lecture_intelligence import get_lecture
        session = get_lecture(session_id) if session_id else None
        if not session:
            # Get most recent
            from core.lecture_intelligence import list_lectures
            sessions = list_lectures(1)
            if sessions:
                session = get_lecture(sessions[0]["id"])
        if not session:
            return "No lecture found."
        return f"Summary: {session.summary}"

    if query.startswith("lecture topics") or query.startswith("lecture key topics"):
        session_id = query.replace("lecture topics", "").replace("lecture key topics", "").strip()
        from core.lecture_intelligence import get_lecture, list_lectures
        session = get_lecture(session_id) if session_id else None
        if not session:
            sessions = list_lectures(1)
            if sessions:
                session = get_lecture(sessions[0]["id"])
        if not session:
            return "No lecture found."
        if not session.key_topics:
            return "No key topics extracted."
        return "Key topics:\n" + "\n".join(f"• {t}" for t in session.key_topics)

    if query.startswith("lecture actions") or query.startswith("lecture action items"):
        session_id = query.replace("lecture actions", "").replace("lecture action items", "").strip()
        from core.lecture_intelligence import get_lecture, list_lectures
        session = get_lecture(session_id) if session_id else None
        if not session:
            sessions = list_lectures(1)
            if sessions:
                session = get_lecture(sessions[0]["id"])
        if not session:
            return "No lecture found."
        if not session.action_items:
            return "No action items found."
        return "Action items:\n" + "\n".join(f"• {a}" for a in session.action_items)

    if query.startswith("lecture notes"):
        session_id = query.replace("lecture notes", "").strip()
        from core.lecture_intelligence import get_lecture, list_lectures
        session = get_lecture(session_id) if session_id else None
        if not session:
            sessions = list_lectures(1)
            if sessions:
                session = get_lecture(sessions[0]["id"])
        if not session:
            return "No lecture found."
        if not session.notes:
            return "No notes available."
        response = f"Notes for {session.title}:\n"
        for note in session.notes[-20:]:  # Last 20 notes
            tag_str = f" [{', '.join(note.tags)}]" if note.tags else ""
            response += f"[{note.timestamp_str}] {note.topic}{tag_str}: {note.content[:100]}\n"
        return response

    if query in ["list lectures", "show lectures", "my lectures"]:
        from core.lecture_intelligence import list_lectures
        sessions = list_lectures(10)
        if not sessions:
            return "No lectures recorded."
        response = "Recent lectures:\n"
        for s in sessions:
            dt = datetime.fromtimestamp(s["started_at"]).strftime('%Y-%m-%d %H:%M')
            duration = ""
            if s["ended_at"]:
                duration = f" ({int((s['ended_at'] - s['started_at']) / 60)} min)"
            response += f"• {s['title']} - {dt}{duration} [{s['state']}]\n  ID: {s['id']}\n"
        return response

    if query.startswith("export lecture "):
        parts = query.replace("export lecture ", "").split(" ")
        session_id = parts[0]
        format = "markdown"
        if len(parts) > 1:
            format = parts[1]
        from core.lecture_intelligence import export_lecture
        path = export_lecture(session_id, format)
        if path:
            return f"Lecture exported to: {path}"
        return "Export failed. Check session ID."

    # ============================
    # NATURAL LANGUAGE UNDERSTANDING (Phase 16)
    # ============================

    if query.startswith("parse ") or query.startswith("nlu ") or query.startswith("analyze text "):
        text = query.replace("parse ", "").replace("nlu ", "").replace("analyze text ", "").strip()
        from core.nlu import nlu_debug
        return nlu_debug(text)

    if query.startswith("extract entities ") or query.startswith("entities in "):
        text = query.replace("extract entities ", "").replace("entities in ", "").strip()
        from core.nlu import extract_entities
        entities = extract_entities(text)
        if not entities:
            return "No entities found."
        response = "Entities found:\n"
        for e in entities:
            response += f"• {e.type}: '{e.value}' [{e.confidence:.0%}]\n"
        return response

    if query.startswith("classify intent ") or query.startswith("intent of "):
        text = query.replace("classify intent ", "").replace("intent of ", "").strip()
        from core.nlu import classify_intent
        intent = classify_intent(text)
        return f"Intent: {intent.name} ({intent.category.value}) [{intent.confidence:.0%}]\nSlots: {intent.slots}"

    if query in ["dialogue context", "conversation context", "context summary"]:
        from core.nlu import get_dialogue_context
        return get_dialogue_context()

    if query in ["clear context", "reset dialogue", "clear dialogue"]:
        from core.nlu import clear_dialogue_context
        clear_dialogue_context()
        return "Dialogue context cleared."

    # ============================
    # EXPLANATION ENGINE (Phase 17)
    # ============================

    if query.startswith("explain ") or query.startswith("why ") or query.startswith("reason "):
        text = query.replace("explain ", "").replace("why ", "").replace("reason ", "").strip()
        exp_type = "step_by_step"
        if "counterfactual" in text:
            exp_type = "counterfactual"
            text = text.replace("counterfactual", "").strip()
        elif "confidence" in text:
            exp_type = "confidence"
            text = text.replace("confidence", "").strip()
        elif "alternative" in text:
            exp_type = "alternative"
            text = text.replace("alternative", "").strip()
        from core.explanation_engine import explanation_debug
        return explanation_debug(text, exp_type)

    if query.startswith("trace decision ") or query.startswith("decision trace "):
        text = query.replace("trace decision ", "").replace("decision trace ", "").strip()
        # Expect format: "decision | option1, option2, option3"
        parts = text.split("|")
        if len(parts) < 2:
            return "Say 'trace decision <question> | option1, option2, option3'"
        decision = parts[0].strip()
        options_str = parts[1].strip()
        options = [{"name": o.strip()} for o in options_str.split(",")]
        from core.explanation_engine import trace_decision, format_decision_trace
        trace = trace_decision(decision, options)
        return format_decision_trace(trace)

    if query.startswith("explain confidence "):
        text = query.replace("explain confidence ", "").strip()
        # Format: "prediction | confidence% | factor1, factor2"
        parts = text.split("|")
        if len(parts) < 2:
            return "Say 'explain confidence <prediction> | <confidence> | <factors>'"
        prediction = parts[0].strip()
        try:
            confidence = float(parts[1].strip().replace("%", "")) / 100
        except:
            confidence = 0.5
        factors = []
        if len(parts) > 2:
            factors = [f.strip() for f in parts[2].split(",")]
        from core.explanation_engine import explain_confidence, format_explanation
        explanation = explain_confidence(prediction, confidence, factors)
        return format_explanation(explanation)

    if query.startswith("alternatives for ") or query.startswith("other options "):
        text = query.replace("alternatives for ", "").replace("other options ", "").strip()
        # Format: "question | current_answer"
        parts = text.split("|")
        if len(parts) < 2:
            return "Say 'alternatives for <question> | <current_answer>'"
        question = parts[0].strip()
        current_answer = parts[1].strip()
        from core.explanation_engine import suggest_alternatives, format_explanation
        explanation = suggest_alternatives(question, current_answer)
        return format_explanation(explanation)

    if query.startswith("counterfactual ") or query.startswith("what if "):
        text = query.replace("counterfactual ", "").replace("what if ", "").strip()
        # Format: "question | actual_outcome"
        parts = text.split("|")
        if len(parts) < 2:
            return "Say 'counterfactual <question> | <actual_outcome>'"
        question = parts[0].strip()
        actual_outcome = parts[1].strip()
        from core.explanation_engine import counterfactual, format_explanation
        explanation = counterfactual(question, actual_outcome)
        return format_explanation(explanation)

    # ============================
    # INTERRUPT SYSTEM (Phase 18)
    # ============================

    if query in ["interrupt status", "task status", "running tasks"]:
        from core.interrupt_system import interrupt_debug
        return interrupt_debug()

    if query.startswith("cancel task ") or query.startswith("cancel interrupt "):
        task_id = query.replace("cancel task ", "").replace("cancel interrupt ", "").strip()
        from core.interrupt_system import interrupt_manager
        success = interrupt_manager.cancel(task_id)
        return f"Task {task_id} {'cancelled' if success else 'not found'}."

    if query.startswith("pause task ") or query.startswith("pause interrupt "):
        task_id = query.replace("pause task ", "").replace("pause interrupt ", "").strip()
        from core.interrupt_system import interrupt_manager
        success = interrupt_manager.pause(task_id)
        return f"Task {task_id} {'paused' if success else 'not found or cannot pause'}."

    if query.startswith("resume task ") or query.startswith("resume interrupt "):
        task_id = query.replace("resume task ", "").replace("resume interrupt ", "").strip()
        from core.interrupt_system import interrupt_manager
        success = interrupt_manager.resume(task_id)
        return f"Task {task_id} {'resumed' if success else 'not found or cannot resume'}."

    if query in ["list tasks", "list interrupts", "all tasks"]:
        from core.interrupt_system import interrupt_manager, InterruptState
        all_tasks = interrupt_manager.list_interrupts()
        if not all_tasks:
            return "No tasks."
        response = f"Tasks ({len(all_tasks)}):\n"
        for t in all_tasks:
            runtime = f" ({t['runtime']:.1f}s)" if t.get('runtime', 0) > 0 else ""
            response += f"• {t['interrupt_id']}: {t['name']} [{t['priority']}] {t['state']}{runtime}\n"
        return response

    if query.startswith("task info ") or query.startswith("interrupt info "):
        task_id = query.replace("task info ", "").replace("interrupt info ", "").strip()
        from core.interrupt_system import interrupt_manager
        info = interrupt_manager.get_status(task_id)
        if not info:
            return f"Task {task_id} not found."
        return f"Task {info['interrupt_id']}: {info['name']}\nPriority: {info['priority']}\nState: {info['state']}\nRuntime: {info['runtime']:.1f}s\nResult: {info['result']}\nError: {info['error']}"

    if query in ["enable preemption", "preemption on"]:
        from core.interrupt_system import interrupt_manager
        interrupt_manager.set_preemption(True)
        return "Preemption enabled."

    if query in ["disable preemption", "preemption off"]:
        from core.interrupt_system import interrupt_manager
        interrupt_manager.set_preemption(False)
        return "Preemption disabled."

    if query in ["interrupt stats", "task stats"]:
        from core.interrupt_system import interrupt_manager
        stats = interrupt_manager.get_stats()
        return f"Interrupt Stats:\nTotal: {stats['total_interrupts']}\nPreemptions: {stats['preemptions']}\nContext Switches: {stats['context_switches']}\nCompleted: {stats['completed']}\nFailed: {stats['failed']}\nCancelled: {stats['cancelled']}"

    # ============================
    # PROJECT AWARENESS (Phase 19)
    # ============================

    if query in ["open project", "switch project", "load project"]:
        if query == "open project" or query == "switch project" or query == "load project":
            return "Say 'open project <path>' to load a project."
        path = query.replace("open project ", "").replace("switch project ", "").replace("load project ", "").strip()
        from core.project_awareness import open_project
        project = open_project(path)
        return f"Opened project: {project.name} ({project.language}) at {project.path}"

    if query in ["list projects", "show projects", "my projects"]:
        from core.project_awareness import list_projects
        projects = list_projects()
        if not projects:
            return "No projects discovered."
        response = f"Projects ({len(projects)}):\n"
        for p in projects:
            response += f"• {p.name} ({p.language}, {p.framework}) - {p.path}\n"
        return response

    if query in ["discover projects", "find projects", "scan projects"]:
        from core.project_awareness import discover_projects
        projects = discover_projects()
        if not projects:
            return "No projects found."
        response = f"Discovered {len(projects)} projects:\n"
        for p in projects[:10]:
            response += f"• {p.name} ({p.language}) - {p.path}\n"
        return response

    if query in ["analyze project", "project analysis", "scan project"]:
        from core.project_awareness import analyze_project
        result = analyze_project()
        if "error" in result:
            return result["error"]
        proj = result["project"]
        struct = result["structure"]
        git = result["git"]
        health = result["health"]
        todos = result["todos"]
        response = f"Project: {proj.name}\nLanguage: {proj.language}\nFramework: {proj.framework}\n"
        response += f"Files: {struct['total_files']}, Lines: {struct['total_lines']}, Size: {struct['total_size']/1024:.1f} KB\n"
        if git:
            response += f"Git: {git.get('branch', 'unknown')} branch, {len(git.get('recent_commits', []))} recent commits\n"
        response += f"Health: {health.get('overall', 'unknown')} - {health.get('summary', '')}\n"
        response += f"TODOs: {len(todos)}"
        return response

    if query in ["git status", "git status"]:
        from core.project_awareness import get_git_status
        status = get_git_status()
        if "error" in status:
            return status["error"]
        response = "Git Status:\n"
        for k, v in status.items():
            if v:
                response += f"  {k}: {', '.join(v[:5])}{'...' if len(v) > 5 else ''}\n"
        return response or "Working tree clean."

    if query in ["recent commits", "git log", "commits"]:
        from core.project_awareness import get_commits
        commits = get_commits(10)
        if not commits:
            return "No commits found."
        response = "Recent commits:\n"
        for c in commits:
            dt = datetime.fromtimestamp(c["timestamp"]).strftime('%Y-%m-%d %H:%M')
            response += f"• {c['short_hash']} {dt} - {c['message'][:60]}\n"
        return response

    if query in ["dependencies", "deps", "packages"]:
        from core.project_awareness import get_dependencies
        deps = get_dependencies()
        if not deps:
            return "No dependencies found."
        response = f"Dependencies ({len(deps)}):\n"
        for d in deps[:20]:
            dev = " (dev)" if d["is_dev"] else ""
            response += f"• {d['name']}@{d['version']} [{d['type']}]{dev}\n"
        return response

    if query in ["health report", "project health", "health check"]:
        from core.project_awareness import get_health_report
        health = get_health_report()
        if "error" in health:
            return health["error"]
        response = f"Health: {health['overall']} - {health['summary']}\n"
        for m in health["metrics"]:
            status_emoji = "✓" if m["status"] == "good" else "⚠" if m["status"] == "warning" else "✗"
            response += f"  {status_emoji} {m['type']}: {m['value']:.1f} (threshold: {m['threshold']})\n"
        return response

    if query in ["todos", "todo list", "fixmes", "code todos"]:
        from core.project_awareness import get_todos
        todos = get_todos()
        if not todos:
            return "No TODOs found."
        response = f"Code TODOs ({len(todos)}):\n"
        for t in todos[:20]:
            response += f"• [{t['tag']}] {t['file']}:{t['line']} - {t['content'][:80]}\n"
        return response

    if query.startswith("file history ") or query.startswith("history of "):
        file_path = query.replace("file history ", "").replace("history of ", "").strip()
        from core.project_awareness import get_file_history
        history = get_file_history(file_path)
        if not history:
            return f"No history for {file_path}."
        response = f"History for {file_path}:\n"
        for h in history[:10]:
            dt = datetime.fromtimestamp(h["timestamp"]).strftime('%Y-%m-%d %H:%M')
            response += f"• {h['hash']} {dt} - {h['message'][:80]}\n"
        return response

    # ============================
    # SECOND BRAIN (Phase 20)
    # ============================

    if query.startswith("create note ") or query.startswith("new note "):
        content = query.replace("create note ", "").replace("new note ", "").strip()
        # Format: "title | content #tag1 #tag2"
        parts = content.split("|")
        title = parts[0].strip() if parts else "Untitled"
        body = parts[1].strip() if len(parts) > 1 else ""
        tags = re.findall(r'#(\w+)', content)
        from core.second_brain import create_node
        node = create_node("note", title, body, tags)
        return f"Created note: {node.title} (ID: {node.id})"

    if query.startswith("create concept ") or query.startswith("new concept "):
        content = query.replace("create concept ", "").replace("new concept ", "").strip()
        parts = content.split("|")
        title = parts[0].strip() if parts else "Untitled"
        body = parts[1].strip() if len(parts) > 1 else ""
        tags = re.findall(r'#(\w+)', content)
        from core.second_brain import create_node
        node = create_node("concept", title, body, tags)
        return f"Created concept: {node.title} (ID: {node.id})"

    if query.startswith("link ") or query.startswith("connect "):
        # Format: "link <source_id> to <target_id> as <relation>"
        text = query.replace("link ", "").replace("connect ", "").strip()
        match = re.match(r'(\w+)\s+(?:to|->)\s+(\w+)(?:\s+as\s+(\w+))?', text)
        if match:
            source_id, target_id, relation = match.groups()
            relation = relation or "links_to"
            from core.second_brain import link_nodes
            edge = link_nodes(source_id, target_id, relation)
            return f"Linked {source_id} -> {target_id} as {relation}"
        return "Say 'link <source_id> to <target_id> as <relation>'"

    if query.startswith("search notes ") or query.startswith("find notes "):
        search_query = query.replace("search notes ", "").replace("find notes ", "").strip()
        from core.second_brain import search_nodes
        nodes = search_nodes(search_query, node_type="note", limit=10)
        if not nodes:
            return "No notes found."
        response = "Notes found:\n"
        for n in nodes:
            response += f"• {n.title} (ID: {n.id}) - {n.content[:80]}\n"
        return response

    if query.startswith("search concepts ") or query.startswith("find concepts "):
        search_query = query.replace("search concepts ", "").replace("find concepts ", "").strip()
        from core.second_brain import search_nodes
        nodes = search_nodes(search_query, node_type="concept", limit=10)
        if not nodes:
            return "No concepts found."
        response = "Concepts found:\n"
        for n in nodes:
            response += f"• {n.title} (ID: {n.id}) - {n.content[:80]}\n"
        return response

    if query.startswith("backlinks ") or query.startswith("who links to "):
        node_id = query.replace("backlinks ", "").replace("who links to ", "").strip()
        from core.second_brain import get_backlinks
        backlinks = get_backlinks(node_id)
        if not backlinks:
            return "No backlinks found."
        response = f"Backlinks to {node_id}:\n"
        for n in backlinks:
            response += f"• {n.title} (ID: {n.id})\n"
        return response

    if query.startswith("forward links ") or query.startswith("links from "):
        node_id = query.replace("forward links ", "").replace("links from ", "").strip()
        from core.second_brain import get_forward_links
        forward = get_forward_links(node_id)
        if not forward:
            return "No forward links found."
        response = f"Forward links from {node_id}:\n"
        for n in forward:
            response += f"• {n.title} (ID: {n.id})\n"
        return response

    if query in ["graph stats", "knowledge graph stats", "second brain stats"]:
        from core.second_brain import get_graph_stats
        stats = get_graph_stats()
        return f"Knowledge Graph:\nNodes: {stats['nodes']}\nEdges: {stats['edges']}\nDensity: {stats['density']:.3f}\nNode types: {stats['node_types']}\nRelation types: {stats['relation_types']}"

    if query in ["find clusters", "graph clusters", "clusters"]:
        from core.second_brain import find_clusters
        clusters = find_clusters(3)
        if not clusters:
            return "No clusters found (min size 3)."
        response = f"Found {len(clusters)} clusters:\n"
        for i, cluster in enumerate(clusters[:5]):
            response += f"Cluster {i+1}: {len(cluster)} nodes\n"
        return response

    if query in ["due cards", "review cards", "cards due"]:
        from core.second_brain import get_due_cards
        due = get_due_cards(10)
        if not due:
            return "No cards due for review."
        response = f"Due cards ({len(due)}):\n"
        for d in due:
            response += f"• {d['title']} ({d['state']}) - interval: {d['interval']}d\n"
        return response

    if query.startswith("review "):
        # Format: "review <schedule_id> <rating>"
        parts = query.replace("review ", "").split()
        if len(parts) >= 2:
            schedule_id = parts[0]
            try:
                rating = int(parts[1])
                if 0 <= rating <= 3:
                    from core.second_brain import review_card
                    result = review_card(schedule_id, rating)
                    if "error" in result:
                        return result["error"]
                    return f"Reviewed! Next interval: {result['new_interval']}d, Ease: {result['new_ease_factor']:.2f}, State: {result['new_state']}"
            except ValueError:
                pass
        return "Say 'review <schedule_id> <rating>' where rating is 0-3"

    if query in ["review stats", "spaced repetition stats"]:
        from core.second_brain import get_review_stats
        stats = get_review_stats()
        return f"Review Stats:\nTotal: {stats['total_reviews']}\nSuccess rate: {stats['success_rate']:.0%}\nAvg ease: {stats['avg_ease']:.2f}"

    if query.startswith("daily note ") or query.startswith("today's note"):
        if query == "today's note" or query == "daily note":
            from core.second_brain import get_daily_note
            today = datetime.now().strftime("%Y-%m-%d")
            note = get_daily_note(today)
            if note:
                return f"Today's note:\n{note['content'][:500]}"
            return "No note for today. Say 'create daily note <content>'"
        content = query.replace("daily note ", "").strip()
        from core.second_brain import create_daily_note
        note_id = create_daily_note(content=content)
        return f"Created daily note: {note_id}"

    if query in ["recent notes", "recent daily notes"]:
        from core.second_brain import get_recent_daily_notes
        notes = get_recent_daily_notes(5)
        if not notes:
            return "No recent daily notes."
        response = "Recent daily notes:\n"
        for n in notes:
            response += f"• {n['date']}: {n['content'][:100]}\n"
        return response

    if query.startswith("create view ") or query.startswith("save view "):
        name = query.replace("create view ", "").replace("save view ", "").strip()
        from core.second_brain import create_graph_view
        view_id = create_graph_view(name)
        return f"Created graph view: {name} (ID: {view_id})"

    if query in ["list views", "graph views", "saved views"]:
        from core.second_brain import list_graph_views
        views = list_graph_views()
        if not views:
            return "No saved views."
        response = "Graph views:\n"
        for v in views:
            response += f"• {v['name']} ({v['layout']}) - {v['id']}\n"
        return response

    if query.startswith("neighbors ") or query.startswith("connected to "):
        node_id = query.replace("neighbors ", "").replace("connected to ", "").strip()
        depth = 1
        if " depth " in node_id:
            parts = node_id.split(" depth ")
            node_id = parts[0].strip()
            try:
                depth = int(parts[1].strip())
            except:
                pass
        from core.second_brain import get_node_neighbors
        neighbors = get_node_neighbors(node_id, depth)
        if not neighbors:
            return f"No neighbors found for {node_id}."
        return f"Neighbors of {node_id} (depth {depth}): {', '.join(list(neighbors)[:20])}"

    if query.startswith("path from ") and " to " in query:
        parts = query.replace("path from ", "").split(" to ")
        if len(parts) == 2:
            source_id, target_id = parts[0].strip(), parts[1].strip()
            from core.second_brain import get_shortest_path
            path = get_shortest_path(source_id, target_id)
            if path:
                return f"Path: {' -> '.join(path)}"
            return "No path found."

    if query.startswith("unlinked mentions "):
        node_id = query.replace("unlinked mentions ", "").strip()
        from core.second_brain import get_unlinked_mentions
        mentions = get_unlinked_mentions(node_id)
        if not mentions:
            return "No unlinked mentions found."
        response = f"Unlinked mentions of {node_id}:\n"
        for n in mentions[:10]:
            response += f"• {n.title} (ID: {n.id})\n"
        return response

    if query.startswith("centrality "):
        node_id = query.replace("centrality ", "").strip()
        from core.second_brain import get_centrality
        cent = get_centrality(node_id)
        return f"Centrality for {node_id}:\nOut-degree: {cent['out_degree']}\nIn-degree: {cent['in_degree']}\nTotal: {cent['total_degree']}"

    # ============================
    # AI TUTOR (Phase 21)
    # ============================

    if query.startswith("explain ") or query.startswith("teach me "):
        text = query.replace("explain ", "").replace("teach me ", "").strip()
        # Format: "topic | type | difficulty"
        parts = text.split("|")
        topic = parts[0].strip()
        exp_type = parts[1].strip() if len(parts) > 1 else "concept"
        difficulty = parts[2].strip() if len(parts) > 2 else "intermediate"
        from core.ai_tutor import explain
        return explain(topic, exp_type, difficulty)

    if query.startswith("quiz ") or query.startswith("test me on "):
        topic = query.replace("quiz ", "").replace("test me on ", "").strip()
        num_q = 5
        difficulty = "medium"
        if " questions" in topic:
            try:
                num_q = int(topic.split(" questions")[0].split()[-1])
            except:
                pass
        if " easy" in topic:
            difficulty = "easy"
            topic = topic.replace(" easy", "")
        elif " hard" in topic:
            difficulty = "hard"
            topic = topic.replace(" hard", "")
        from core.ai_tutor import quiz
        questions = quiz(topic, num_q, difficulty)
        if not questions:
            return f"No quiz available for {topic}."
        response = f"Quiz on {topic} ({len(questions)} questions):\n"
        for i, q in enumerate(questions, 1):
            response += f"\n{i}. {q['question']}"
            if q['type'] == 'multiple_choice' and q.get('options'):
                for opt in q['options']:
                    response += f"\n  - {opt}"
        return response

    if query.startswith("ask tutor ") or query.startswith("ask teacher "):
        question = query.replace("ask tutor ", "").replace("ask teacher ", "").strip()
        topic = None
        if " about " in question:
            parts = question.split(" about ", 1)
            question, topic = parts[0].strip(), parts[1].strip()
        from core.ai_tutor import ask_tutor
        return ask_tutor(question, topic)

    if query in ["what should i learn next", "next topic", "suggest topic"]:
        from core.ai_tutor import suggest_next
        suggestions = suggest_next()
        if not suggestions:
            return "All topics completed! Great job."
        response = "Suggested next topics:\n"
        for s in suggestions:
            response += f"• {s['name']} ({s['difficulty']}) - {s['description'][:80]}\n"
        return response

    if query in ["my progress", "learning progress", "study progress", "dashboard"]:
        from core.ai_tutor import get_dashboard
        dash = get_dashboard()
        stats = dash['stats']
        response = f"Learning Dashboard:\n"
        response += f"Topics: {stats['total_topics']} total\n"
        response += f"Mastered: {stats['mastered']} | Completed: {stats['completed']} | In progress: {stats['in_progress']}\n"
        response += f"Avg mastery: {stats['avg_mastery']:.0%} | Study time: {stats['total_time_hours']:.1f}h\n"
        if dash['suggested_topics']:
            response += "\nNext up:\n"
            for s in dash['suggested_topics'][:3]:
                response += f"• {s['name']} ({s['difficulty']})\n"
        return response

    if query.startswith("study plan for ") or query.startswith("plan for "):
        goal = query.replace("study plan for ", "").replace("plan for ", "").strip()
        hours = 5
        if " hours" in goal:
            try:
                hours = int(goal.split(" hours")[0].split()[-1])
            except:
                pass
        from core.ai_tutor import create_study_plan
        plan = create_study_plan(goal, hours)
        response = f"Study Plan: {goal}\n"
        response += f"Total: {plan['total_hours']:.1f}h over {plan['estimated_weeks']} weeks ({plan['hours_per_week']}h/week)\n"
        response += "Topics:\n"
        for t in plan['topics']:
            response += f"• {t['name']} ({t['hours']:.1f}h, {t['difficulty']})\n"
        response += "\nMilestones:\n"
        for m in plan['milestones']:
            response += f"Week {m['target_week']}: {m['topic']}\n"
        return response

    if query.startswith("start topic ") or query.startswith("begin topic "):
        topic = query.replace("start topic ", "").replace("begin topic ", "").strip()
        from core.ai_tutor import start_topic
        if start_topic(topic):
            return f"Started learning: {topic}"
        return f"Topic '{topic}' not found."

    if query.startswith("complete topic ") or query.startswith("finish topic "):
        topic = query.replace("complete topic ", "").replace("finish topic ", "").strip()
        from core.ai_tutor import complete_topic
        if complete_topic(topic):
            return f"Completed: {topic}"
        return f"Topic '{topic}' not found."

    if query.startswith("progress on ") or query.startswith("status of "):
        topic = query.replace("progress on ", "").replace("status of ", "").strip()
        from core.ai_tutor import get_topic_progress
        progress = get_topic_progress(topic)
        if not progress:
            return f"Topic '{topic}' not found."
        return f"Progress on {topic}: {progress['status']} - Mastery: {progress['mastery_level']:.0%}"

    # ============================
    # PASSIVE MENTOR (Phase 22)
    # ============================

    if query in ["mentor status", "passive mentor status", "mentor debug"]:
        from core.passive_mentor import mentor_debug
        return mentor_debug()

    if query in ["show suggestions", "mentor suggestions", "proactive suggestions"]:
        from core.passive_mentor import mentor_suggestions
        return mentor_suggestions()

    if query in ["show insights", "mentor insights", "learning insights"]:
        from core.passive_mentor import mentor_insights
        return mentor_insights()

    if query in ["show anomalies", "mentor anomalies", "anomalies"]:
        from core.passive_mentor import mentor_anomalies
        return mentor_anomalies()

    if query.startswith("resolve anomaly "):
        anomaly_id = query.replace("resolve anomaly ", "").strip()
        from core.passive_mentor import passive_mentor
        passive_mentor.resolve_anomaly(anomaly_id)
        return f"Anomaly {anomaly_id} resolved."

    if query.startswith("dismiss anomaly "):
        anomaly_id = query.replace("dismiss anomaly ", "").strip()
        from core.passive_mentor import passive_mentor
        passive_mentor.resolve_anomaly(anomaly_id, is_false_positive=True)
        return f"Anomaly {anomaly_id} dismissed as false positive."

    if query in ["start mentor", "start passive mentor"]:
        from core.passive_mentor import passive_mentor
        passive_mentor.start()
        return "Passive mentor started."

    if query in ["stop mentor", "stop passive mentor"]:
        from core.passive_mentor import passive_mentor
        passive_mentor.stop()
        return "Passive mentor stopped."

    # ============================
    # SYSTEM AGENT (Phase 23)
    # ============================

    if query in ["system status", "system snapshot", "sys status", "sys snapshot"]:
        from core.system_agent import system_snapshot
        return system_snapshot()

    if query in ["system debug", "system agent debug", "sys debug"]:
        from core.system_agent import system_agent_debug
        return system_agent_debug()

    if query in ["system alerts", "show alerts", "alerts"]:
        from core.system_agent import system_alerts
        return system_alerts()

    if query.startswith("create alert ") or query.startswith("alert on "):
        # Format: "create alert cpu > 80 critical" or "alert on memory > 85 warning"
        parts = query.replace("create alert ", "").replace("alert on ", "").split()
        if len(parts) >= 3:
            metric = parts[0]
            condition = parts[1]
            threshold = float(parts[2])
            severity = parts[3] if len(parts) > 3 else "warning"
            from core.system_agent import create_alert
            return create_alert(metric, condition, threshold, severity)
        return "Format: 'create alert <metric> <condition> <threshold> [severity]'"

    if query in ["list alerts", "show alerts", "alerts list"]:
        from core.system_agent import list_alerts
        return list_alerts()

    if query.startswith("acknowledge alert ") or query.startswith("ack alert "):
        alert_id = query.replace("acknowledge alert ", "").replace("ack alert ", "").strip()
        from core.system_agent import acknowledge_alert
        return acknowledge_alert(alert_id)

    if query in ["system processes", "top processes", "top cpu", "top processes"]:
        from core.system_agent import system_processes
        return system_processes()

    if query.startswith("kill process ") or query.startswith("kill pid "):
        pid_str = query.replace("kill process ", "").replace("kill pid ", "").strip()
        try:
            pid = int(pid_str)
            from core.system_agent import kill_process
            return kill_process(pid)
        except ValueError:
            return "Invalid PID."

    if query.startswith("restart service "):
        service = query.replace("restart service ", "").strip()
        from core.system_agent import restart_service
        return restart_service(service)

    if query.startswith("service status "):
        service = query.replace("service status ", "").strip()
        from core.system_agent import service_status
        return service_status(service)

    if query in ["list services", "show services", "services"]:
        from core.system_agent import list_services
        return list_services()

    if query.startswith("create automation ") or query.startswith("automation "):
        # Simplified - real implementation would need more parsing
        from core.system_agent import create_automation
        return create_automation("", "", "")

    if query in ["list automations", "automations list", "automations"]:
        from core.system_agent import list_automations
        return list_automations()

    # ============================
    # CYBERSECURITY AGENT (Phase 24)
    # ============================

    if query in ["cybersecurity status", "security status", "sec status"]:
        from core.cybersecurity_agent import cybersecurity_debug
        return cybersecurity_debug()

    if query.startswith("security events") or query.startswith("sec events"):
        event_type = query.replace("security events", "").replace("sec events", "").strip()
        limit = 10
        if " " in event_type:
            parts = event_type.rsplit(" ", 1)
            if parts[1].isdigit():
                event_type = parts[0]
                limit = int(parts[1])
        from core.cybersecurity_agent import cybersecurity_events
        return cybersecurity_events(event_type if event_type else None, limit)

    if query in ["security incidents", "sec incidents", "incidents"]:
        from core.cybersecurity_agent import cybersecurity_incidents
        return cybersecurity_incidents()

    if query.startswith("create incident ") or query.startswith("new incident "):
        parts = query.replace("create incident ", "").replace("new incident ", "").split("|")
        if len(parts) >= 3:
            title = parts[0].strip()
            description = parts[1].strip()
            severity = parts[2].strip()
            from core.cybersecurity_agent import cybersecurity_incident_create
            return cybersecurity_incident_create(title, description, severity)
        return "Format: 'create incident <title> | <description> | <severity>'"

    if query.startswith("update incident "):
        incident_id = query.replace("update incident ", "").strip()
        # Format: "update incident <id> status=resolved" or "update incident <id> severity=high"
        updates = {}
        for part in incident_id.split():
            if "=" in part:
                k, v = part.split("=", 1)
                updates[k] = v
            else:
                incident_id = part
        if "incident_id" in locals():
            from core.cybersecurity_agent import cybersecurity_incident_update
            return cybersecurity_incident_update(incident_id, **updates)
        return "Format: 'update incident <id> status=resolved' or 'update incident <id> severity=high'"

    if query in ["network connections", "network scan", "scan network"]:
        from core.cybersecurity_agent import cybersecurity_network
        return cybersecurity_network()

    if query in ["file integrity", "integrity check", "check integrity"]:
        from core.cybersecurity_agent import cybersecurity_integrity_check
        return cybersecurity_integrity_check()

    if query.startswith("monitor path ") or query.startswith("watch path "):
        path = query.replace("monitor path ", "").replace("watch path ", "").strip()
        recursive = "false" not in query
        from core.cybersecurity_agent import cybersecurity_add_path_cmd
        return cybersecurity_add_path_cmd(path, "true" if recursive else "false")

    if query in ["scan network", "network scan"]:
        from core.cybersecurity_agent import cybersecurity_scan_network
        return cybersecurity_scan_network()

    if query in ["suspicious processes", "sus processes", "process scan"]:
        from core.cybersecurity_agent import cybersecurity_processes
        return cybersecurity_processes()

    if query in ["security incidents", "sec incidents", "incidents list"]:
        from core.cybersecurity_agent import cybersecurity_incidents
        return cybersecurity_incidents()

    if query.startswith("create security incident ") or query.startswith("new security incident "):
        parts = query.replace("create security incident ", "").replace("new security incident ", "").split("|")
        if len(parts) >= 3:
            title = parts[0].strip()
            description = parts[1].strip()
            severity = parts[2].strip()
            from core.cybersecurity_agent import cybersecurity_incident_create
            return cybersecurity_incident_create(title, description, severity)
        return "Format: 'create security incident <title> | <description> | <severity>'"

    if query.startswith("update security incident "):
        incident_id = query.replace("update security incident ", "").strip()
        updates = {}
        for part in incident_id.split():
            if "=" in part:
                k, v = part.split("=", 1)
                updates[k] = v
            else:
                incident_id = part
        if "incident_id" in locals():
            from core.cybersecurity_agent import cybersecurity_incident_update
            return cybersecurity_incident_update(incident_id, **updates)
        return "Format: 'update security incident <id> status=resolved'"

    if query in ["security events", "sec events", "events"]:
        from core.cybersecurity_agent import cybersecurity_events
        return cybersecurity_events()

    if query in ["network connections", "net connections", "connections"]:
        from core.cybersecurity_agent import cybersecurity_network
        return cybersecurity_network()

    if query in ["file integrity", "integrity check"]:
        from core.cybersecurity_agent import cybersecurity_integrity_check
        return cybersecurity_integrity_check()

    if query.startswith("monitor "):
        path = query.replace("monitor ", "").strip()
        recursive = "recursive" in query
        from core.cybersecurity_agent import cybersecurity_add_path
        return cybersecurity_add_path(path, "true" if recursive else "false")

    if query in ["scan network", "network scan"]:
        from core.cybersecurity_agent import cybersecurity_scan_network
        return cybersecurity_scan_network()

    if query in ["suspicious processes", "sus processes", "process scan"]:
        from core.cybersecurity_agent import cybersecurity_processes
        return cybersecurity_processes()

    if query in ["security incidents", "sec incidents"]:
        from core.cybersecurity_agent import cybersecurity_incidents
        return cybersecurity_incidents()

    if query.startswith("create security incident "):
        parts = query.replace("create security incident ", "").split("|")
        if len(parts) >= 3:
            title = parts[0].strip()
            description = parts[1].strip()
            severity = parts[2].strip()
            from core.cybersecurity_agent import cybersecurity_incident_create
            return cybersecurity_incident_create(title, description, severity)
        return "Format: 'create security incident <title> | <description> | <severity>'"

    if query.startswith("update security incident "):
        incident_id = query.replace("update security incident ", "").strip()
        updates = {}
        for part in incident_id.split():
            if "=" in part:
                k, v = part.split("=", 1)
                updates[k] = v
            else:
                incident_id = part
        if "incident_id" in locals():
            from core.cybersecurity_agent import cybersecurity_incident_update
            return cybersecurity_incident_update(incident_id, **updates)
        return "Format: 'update security incident <id> status=resolved'"

    if query in ["threat intel", "threat intelligence", "threat int"]:
        from core.cybersecurity_agent import cybersecurity_threat_intel
        return cybersecurity_threat_intel()

    if query.startswith("add threat "):
        parts = query.replace("add threat ", "").split("|")
        if len(parts) >= 2:
            ind_type = parts[0].strip()
            value = parts[1].strip()
            threat_type = parts[2].strip() if len(parts) > 2 else None
            severity = parts[3].strip() if len(parts) > 3 else "medium"
            desc = parts[4].strip() if len(parts) > 4 else ""
            from core.cybersecurity_agent import cybersecurity_add_intel
            return cybersecurity_add_intel(ind_type, value, threat_type, severity, desc)
        return "Format: 'add threat <type> | <value> | <threat_type> | <severity> | <description>'"

    if query.startswith("check threat "):
        parts = query.replace("check threat ", "").split()
        if len(parts) >= 2:
            ind_type = parts[0]
            value = parts[1]
            from core.cybersecurity_agent import cybersecurity_check_intel
            return cybersecurity_check_intel(ind_type, value)
        return "Format: 'check threat <type> <value>'"

    if query in ["scan vulnerabilities", "vuln scan", "vulnerabilities"]:
        from core.cybersecurity_agent import cybersecurity_scan_vulns
        return cybersecurity_scan_vulns()

    if query.startswith("create hunt "):
        parts = query.replace("create hunt ", "").split("|")
        if len(parts) >= 3:
            name = parts[0].strip()
            description = parts[1].strip()
            query = parts[2].strip()
            from core.cybersecurity_agent import cybersecurity_add_hunt
            return cybersecurity_add_hunt(name, description, query)
        return "Format: 'create hunt <name> | <description> | <query>'"

    if query.startswith("run hunt "):
        hunt_id = query.replace("run hunt ", "").strip()
        from core.cybersecurity_agent import cybersecurity_run_hunt
        return cybersecurity_run_hunt(hunt_id)

    if query.startswith("monitor "):
        path = query.replace("monitor ", "").strip()
        recursive = "recursive" in query
        from core.cybersecurity_agent import cybersecurity_add_path
        return cybersecurity_add_path(path, "true" if recursive else "false")

    if query in ["integrity check", "file integrity", "check integrity"]:
        from core.cybersecurity_agent import cybersecurity_integrity_check
        return cybersecurity_integrity_check()

    if query in ["scan network", "network scan"]:
        from core.cybersecurity_agent import cybersecurity_scan_network
        return cybersecurity_scan_network()

    if query in ["suspicious processes", "sus processes", "process scan"]:
        from core.cybersecurity_agent import cybersecurity_processes
        return cybersecurity_processes()

    if query in ["security incidents", "sec incidents"]:
        from core.cybersecurity_agent import cybersecurity_incidents
        return cybersecurity_incidents()

    if query.startswith("create security incident "):
        parts = query.replace("create security incident ", "").split("|")
        if len(parts) >= 3:
            title = parts[0].strip()
            description = parts[1].strip()
            severity = parts[2].strip()
            from core.cybersecurity_agent import cybersecurity_incident_create
            return cybersecurity_incident_create(title, description, severity)
        return "Format: 'create security incident <title> | <description> | <severity>'"

    if query.startswith("update security incident "):
        incident_id = query.replace("update security incident ", "").strip()
        updates = {}
        for part in incident_id.split():
            if "=" in part:
                k, v = part.split("=", 1)
                updates[k] = v
            else:
                incident_id = part
        if "incident_id" in locals():
            from core.cybersecurity_agent import cybersecurity_incident_update
            return cybersecurity_incident_update(incident_id, **updates)
        return "Format: 'update security incident <id> status=resolved'"

    # ============================
    # ACCOUNTING AGENT (Phase 26)
    # ============================

    if query in ["accounting status", "accounting dashboard", "accounting debug"]:
        from core.accounting_agent import accounting_debug
        return accounting_debug()

    if query in ["trial balance", "trial balance report", "tb report"]:
        from core.accounting_agent import get_trial_balance
        tb = get_trial_balance()
        if tb["is_balanced"]:
            return f"Trial Balance: BALANCED\nTotal Debits: ${tb['total_debits']:,.2f}\nTotal Credits: ${tb['total_credits']:,.2f}"
        else:
            return f"Trial Balance: OUT OF BALANCE\nDebits: ${tb['total_debits']:,.2f} | Credits: ${tb['total_credits']:,.2f} | Diff: ${tb['total_debits'] - tb['total_credits']:,.2f}"

    if query.startswith("create journal entry ") or query.startswith("new journal entry "):
        parts = query.replace("create journal entry ", "").replace("new journal entry ", "").split("|")
        if len(parts) >= 3:
            date_str = parts[0].strip()
            description = parts[1].strip()
            lines_str = parts[2].strip()
            try:
                date_ts = datetime.strptime(date_str, "%Y-%m-%d").timestamp()
            except:
                return "Invalid date format. Use YYYY-MM-DD."
            from core.accounting_agent import create_journal_entry
            lines = []
            for line in lines_str.split(";"):
                parts = line.split("|")
                if len(parts) >= 4:
                    account_code, debit, credit, desc = parts[0].strip(), float(parts[1] or 0), float(parts[2] or 0), parts[3].strip()
                    from core.accounting_agent import accounting_agent
                    acc = accounting_agent.chart_of_accounts.get_account_by_code(account_code)
                    if acc:
                        lines.append({"account_id": acc["id"], "description": desc, "debit": debit, "credit": credit})
            from core.accounting_agent import create_journal_entry
            entry_id = create_journal_entry(date_ts, description, lines)
            return f"Created journal entry: {entry_id}"
        return "Format: 'create journal entry <date> | <description> | <lines>'"

    if query.startswith("post journal entry "):
        entry_id = query.replace("post journal entry ", "").strip()
        from core.accounting_agent import post_journal_entry
        if post_journal_entry(entry_id):
            return f"Journal entry {entry_id} posted."
        return f"Failed to post journal entry {entry_id}."

    if query.startswith("reverse journal entry "):
        entry_id = query.replace("reverse journal entry ", "").strip()
        reason = ""
        if " reason " in entry_id:
            entry_id, reason = entry_id.split(" reason ", 1)
        from core.accounting_agent import reverse_journal_entry
        return reverse_journal_entry(entry_id.strip(), reason.strip())

    if query in ["trial balance", "trial balance report", "tb report"]:
        from core.accounting_agent import get_trial_balance
        tb = get_trial_balance()
        if tb["is_balanced"]:
            return f"Trial Balance: BALANCED\nTotal Debits: ${tb['total_debits']:,.2f}\nTotal Credits: ${tb['total_credits']:,.2f}"
        else:
            return f"Trial Balance: OUT OF BALANCE\nDebits: ${tb['total_debits']:,.2f} | Credits: ${tb['total_credits']:,.2f} | Diff: ${tb['total_debits'] - tb['total_credits']:,.2f}"

    if query.startswith("balance sheet") or query.startswith("balance sheet as of"):
        as_of = time.time()
        if "as of " in query:
            try:
                as_of = datetime.strptime(query.split("as of ")[1].strip(), "%Y-%m-%d").timestamp()
            except:
                pass
        from core.accounting_agent import generate_balance_sheet
        bs = generate_balance_sheet(as_of)
        if not bs.get("balanced"):
            return "Balance sheet not balanced!"
        output = f"Balance Sheet as of {datetime.fromtimestamp(bs['as_of']).strftime('%Y-%m-%d')}:\n"
        output += f"ASSETS:\n"
        for cat, data in bs["assets"].items():
            output += f"  {cat}: ${data['total']:,.2f}\n"
        output += f"  Total Assets: ${bs['total_assets']:,.2f}\n\n"
        output += f"LIABILITIES:\n"
        for cat, data in bs["liabilities"].items():
            output += f"  {cat}: ${data['total']:,.2f}\n"
        output += f"  Total Liabilities: ${bs['total_liabilities']:,.2f}\n\n"
        output += f"EQUITY:\n"
        for cat, data in bs["equity"].items():
            output += f"  {cat}: ${data['total']:,.2f}\n"
        output += f"  Total Equity: ${bs['total_equity']:,.2f}\n"
        output += f"\nBalanced: {'Yes' if bs['balanced'] else 'No'}"
        return output

    if query.startswith("income statement") or query.startswith("income statement for"):
        parts = query.replace("income statement", "").replace("for", "").strip().split(" to ")
        if len(parts) >= 2:
            try:
                start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").timestamp()
                end = datetime.strptime(parts[1].strip(), "%Y-%m-%d").timestamp()
            except:
                return "Format: 'income statement <start_date> to <end_date>' (YYYY-MM-DD)"
            from core.accounting_agent import generate_income_statement
            is_stmt = generate_income_statement(start, end)
            output = f"Income Statement ({datetime.fromtimestamp(start).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(end).strftime('%Y-%m-%d')}):\n"
            output += f"Revenue: ${is_stmt['revenue']['total']:,.2f}\n"
            for cat, data in is_stmt['revenue']['by_category'].items():
                output += f"  {cat}: ${data:,.2f}\n"
            output += f"\nExpenses: ${is_stmt['expenses']['total']:,.2f}\n"
            for cat, data in is_stmt['expenses']['by_category'].items():
                output += f"  {cat}: ${data:,.2f}\n"
            output += f"\nNet Income: ${is_stmt['net_income']:,.2f}"
            return output
        return "Format: 'income statement <start_date> to <end_date>' (YYYY-MM-DD)"

    if query.startswith("cash flow") or query.startswith("cash flow statement"):
        parts = query.replace("cash flow", "").replace("for", "").strip().split(" to ")
        if len(parts) >= 2:
            try:
                start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").timestamp()
                end = datetime.strptime(parts[1].strip(), "%Y-%m-%d").timestamp()
            except:
                return "Format: 'cash flow <start_date> to <end_date>' (YYYY-MM-DD)"
            from core.accounting_agent import generate_cash_flow
            cf = generate_cash_flow(start, end)
            output = f"Cash Flow Statement ({datetime.fromtimestamp(start).strftime('%Y-%m-%d')} to {datetime.fromtimestamp(end).strftime('%Y-%m-%d')}):\n"
            output += f"Operating: ${cf['operating']:,.2f}\n"
            output += f"Investing: ${cf['investing']:,.2f}\n"
            output += f"Financing: ${cf['financing']:,.2f}\n"
            output += f"Net Change: ${cf['net_change']:,.2f}"
            return output
        return "Format: 'cash flow <start_date> to <end_date>' (YYYY-MM-DD)"

    if query.startswith("create journal entry ") or query.startswith("new journal entry "):
        parts = query.replace("create journal entry ", "").replace("new journal entry ", "").split("|")
        if len(parts) >= 3:
            date_str = parts[0].strip()
            description = parts[1].strip()
            lines_str = parts[2].strip()
            try:
                date_ts = datetime.strptime(date_str, "%Y-%m-%d").timestamp()
            except:
                return "Invalid date format. Use YYYY-MM-DD."
            from core.accounting_agent import create_journal_entry
            lines = []
            for line in lines_str.split(";"):
                parts = line.split("|")
                if len(parts) >= 4:
                    lines.append({"account_code": parts[0].strip(), "debit": float(parts[1] or 0), "credit": float(parts[2] or 0), "description": parts[3].strip()})
            from core.accounting_agent import create_journal_entry
            entry_id = create_journal_entry(date_ts, description, lines)
            return f"Created journal entry: {entry_id}"
        return "Format: 'create journal entry <date> | <description> | <lines>'"

    if query.startswith("post journal entry "):
        entry_id = query.replace("post journal entry ", "").strip()
        from core.accounting_agent import post_journal_entry
        if post_journal_entry(entry_id):
            return f"Journal entry {entry_id} posted."
        return f"Failed to post journal entry {entry_id}."

    if query.startswith("reverse journal entry "):
        entry_id = query.replace("reverse journal entry ", "").strip()
        reason = ""
        if " reason " in entry_id:
            entry_id, reason = entry_id.split(" reason ", 1)
        from core.accounting_agent import reverse_journal_entry
        return reverse_journal_entry(entry_id.strip(), reason.strip())

    if query in ["trial balance", "trial balance report", "tb report"]:
        from core.accounting_agent import get_trial_balance
        tb = get_trial_balance()
        if tb["is_balanced"]:
            return f"Trial Balance: BALANCED\nTotal Debits: ${tb['total_debits']:,.2f}\nTotal Credits: ${tb['total_credits']:,.2f}"
        else:
            return f"Trial Balance: OUT OF BALANCE\nDebits: ${tb['total_debits']:,.2f} | Credits: ${tb['total_credits']:,.2f} | Diff: ${tb['total_debits'] - tb['total_credits']:,.2f}"

    if query.startswith("create account ") or query.startswith("new account "):
        parts = query.replace("create account ", "").replace("new account ", "").split("|")
        if len(parts) >= 5:
            code = parts[0].strip()
            name = parts[1].strip()
            acc_type = parts[2].strip()
            parent = parts[3].strip() if len(parts) > 3 else None
            desc = parts[4].strip() if len(parts) > 4 else ""
            normal = parts[5].strip() if len(parts) > 5 else "debit"
            from core.accounting_agent import accounting_agent
            acct_id = accounting_agent.chart_of_accounts.create_account(code, name, acc_type, parent, desc, normal)
            return f"Created account: {acct_id}"
        return "Format: 'create account <code> | <name> | <type> | <parent_code> | <description> | <normal_balance>'"

    if query.startswith("account ") or query.startswith("account info "):
        code = query.replace("account ", "").replace("account info ", "").strip()
        from core.accounting_agent import accounting_agent
        acc = accounting_agent.chart_of_accounts.get_account_by_code(code)
        if acc:
            return f"Account: {acc['name']} ({acc['code']})\nType: {acc['account_type']}\nBalance: ${acc.get('balance', 0):,.2f}"
        return f"Account '{code}' not found."

    if query in ["chart of accounts", "accounts list", "list accounts"]:
        from core.accounting_agent import accounting_agent
        accounts = accounting_agent.chart_of_accounts.list_accounts()
        if not accounts:
            return "No accounts found."
        output = "Chart of Accounts:\n"
        for a in accounts:
            output += f"  {a['code']} - {a['name']} ({a['account_type']}) [{a['normal_balance']}]\n"
        return output

    if query in ["trial balance", "trial balance report", "tb report"]:
        from core.accounting_agent import get_trial_balance
        tb = get_trial_balance()
        if tb["is_balanced"]:
            return f"Trial Balance: BALANCED\nTotal Debits: ${tb['total_debits']:,.2f}\nTotal Credits: ${tb['total_credits']:,.2f}"
        else:
            return f"Trial Balance: OUT OF BALANCE\nDebits: ${tb['total_debits']:,.2f} | Credits: ${tb['total_credits']:,.2f} | Diff: ${tb['total_debits'] - tb['total_credits']:,.2f}"

    if query.startswith("create alert ") or query.startswith("alert on "):
        parts = query.replace("create alert ", "").replace("alert on ", "").split()
        if len(parts) >= 3:
            metric = parts[0]
            condition = parts[1]
            threshold = float(parts[2])
            severity = parts[3] if len(parts) > 3 else "warning"
            from core.accounting_agent import create_alert_rule
            rule_id = create_alert_rule(f"Alert for {metric}", metric, condition, threshold, severity)
            return f"Created alert rule: {rule_id}"
        return "Format: 'create alert <metric> <condition> <threshold> [severity]'"

    if query in ["list alerts", "show alerts", "alerts list"]:
        from core.accounting_agent import list_alerts
        alerts = list_alerts()
        if not alerts:
            return "No alerts."
        output = "Alerts:\n"
        for a in alerts:
            output += f"  • {a['name']}: {a['metric']} {a['condition']} {a['threshold']} [{a['severity']}]\n"
        return output

    if query.startswith("acknowledge alert ") or query.startswith("ack alert "):
        alert_id = query.replace("acknowledge alert ", "").replace("ack alert ", "").strip()
        from core.accounting_agent import acknowledge_alert
        ack_alert(alert_id)
        return f"Acknowledged alert {alert_id}."

    # ============================
    # AUDIT AGENT (Phase 27)
    # ============================

    if query in ["audit status", "audit dashboard", "audit debug"]:
        from core.audit_agent import audit_debug
        return audit_debug()

    if query in ["list audits", "list engagements", "audit list"]:
        from core.audit_agent import list_engagements
        audits = list_engagements()
        if not audits:
            return "No audit engagements found."
        output = f"Audit Engagements ({len(audits)}):\n"
        for a in audits:
            output += f"  • {a['engagement_number']} - {a['client_name']} ({a['status']})\n"
        return output

    if query.startswith("create audit ") or query.startswith("new audit "):
        parts = query.replace("create audit ", "").replace("new audit ", "").split("|")
        if len(parts) >= 8:
            client_name = parts[0].strip()
            client_id = parts[1].strip()
            audit_type = parts[2].strip()
            scope = parts[3].strip()
            try:
                planned_start = datetime.strptime(parts[4].strip(), "%Y-%m-%d").timestamp()
                planned_end = datetime.strptime(parts[5].strip(), "%Y-%m-%d").timestamp()
            except:
                return "Invalid date format. Use YYYY-MM-DD."
            lead_auditor = parts[6].strip()
            team = [m.strip() for m in parts[7].split(",")] if len(parts) > 7 else []
            materiality = float(parts[8].strip()) if len(parts) > 8 else 0
            planning = parts[9].strip() if len(parts) > 9 else ""
            from core.audit_agent import create_audit_engagement
            eng = create_audit_engagement(client_name, client_id, audit_type, scope,
                                         planned_start, planned_end, lead_auditor, team, materiality, planning)
            return f"Created audit engagement: {eng.engagement_number} ({eng.id})"
        return "Format: 'create audit <client> | <client_id> | <type> | <scope> | <start> | <end> | <lead> | <team> | <materiality> | <notes>'"

    if query.startswith("start audit "):
        eng_id = query.replace("start audit ", "").strip()
        from core.audit_agent import start_audit
        if start_audit(eng_id):
            return f"Audit {eng_id} started."
        return f"Failed to start audit {eng_id}."

    if query.startswith("complete audit ") or query.startswith("finish audit "):
        eng_id = query.replace("complete audit ", "").replace("finish audit ", "").strip()
        from core.audit_agent import complete_audit
        if complete_audit(eng_id):
            return f"Audit {eng_id} completed."
        return f"Failed to complete audit {eng_id}."

    if query.startswith("audit program "):
        parts = query.replace("audit program ", "").split("|")
        if len(parts) >= 5:
            eng_id = parts[0].strip()
            area = parts[1].strip()
            objective = parts[2].strip()
            procedures = [p.strip() for p in parts[3].split(",")]
            risk = parts[4].strip()
            assigned = parts[5].strip() if len(parts) > 5 else "audit team"
            from core.audit_agent import create_audit_program
            prog_id = create_audit_program(eng_id, area, objective, procedures, risk, assigned)
            return f"Created audit program: {prog_id}"
        return "Format: 'audit program <eng_id> | <area> | <objective> | <proc1,proc2> | <risk> | <assigned>'"

    if query.startswith("create workpaper "):
        parts = query.replace("create workpaper ", "").split("|")
        if len(parts) >= 4:
            eng_id = parts[0].strip()
            ref = parts[1].strip()
            title = parts[2].strip()
            desc = parts[3].strip() if len(parts) > 3 else ""
            prog_id = parts[4].strip() if len(parts) > 4 else None
            prep = parts[5].strip() if len(parts) > 5 else "system"
            from core.audit_agent import create_workpaper
            wp_id = create_workpaper(eng_id, ref, title, desc, prog_id, prep)
            return f"Created workpaper: {wp_id}"
        return "Format: 'create workpaper <eng_id> | <ref> | <title> | <desc> | <prog_id> | <preparer>'"

    if query.startswith("update workpaper "):
        parts = query.replace("update workpaper ", "").split("|")
        if len(parts) >= 3:
            wp_id = parts[0].strip()
            content = parts[1].strip()
            status = parts[2].strip() if len(parts) > 2 else "draft"
            from core.audit_agent import update_workpaper
            if update_workpaper(wp_id, content, status):
                return f"Updated workpaper {wp_id}."
            return f"Failed to update workpaper {wp_id}."
        return "Format: 'update workpaper <wp_id> | <content> | <status>'"

    if query.startswith("create finding "):
        parts = query.replace("create finding ", "").split("|")
        if len(parts) >= 6:
            eng_id = parts[0].strip()
            title = parts[1].strip()
            desc = parts[2].strip()
            severity = parts[3].strip()
            category = parts[4].strip()
            wp_id = parts[5].strip() if len(parts) > 5 else None
            root = parts[6].strip() if len(parts) > 6 else ""
            impact = parts[7].strip() if len(parts) > 7 else ""
            rec = parts[8].strip() if len(parts) > 8 else ""
            assigned = parts[9].strip() if len(parts) > 9 else ""
            target = parts[10].strip() if len(parts) > 10 else None
            mitre = [m.strip() for m in parts[11].split(",")] if len(parts) > 11 else None
            from core.audit_agent import create_finding
            fid = create_finding(eng_id, title, desc, severity, category, wp_id, root, impact, rec, assigned, target, mitre)
            return f"Created finding: {fid}"
        return "Format: 'create finding <eng_id> | <title> | <desc> | <severity> | <category> | <wp_id> | <root_cause> | <impact> | <recommendation> | <assigned> | <target_date> | <mitre_techniques>'"

    if query.startswith("add evidence "):
        parts = query.replace("add evidence ", "").split("|")
        if len(parts) >= 7:
            eng_id = parts[0].strip()
            ev_type = parts[1].strip()
            desc = parts[2].strip()
            source = parts[3].strip()
            file_path = parts[4].strip() if len(parts) > 4 else None
            collector = parts[5].strip() if len(parts) > 5 else "system"
            wp_id = parts[6].strip() if len(parts) > 6 else None
            finding_id = parts[7].strip() if len(parts) > 7 else None
            rel = parts[8].strip() if len(parts) > 8 else "supports"
            relia = parts[9].strip() if len(parts) > 9 else "high"
            from core.audit_agent import add_evidence
            ev_id = add_evidence(eng_id, ev_type, desc, source, file_path, collector, wp_id, finding_id, rel, relia)
            return f"Added evidence: {ev_id}"
        return "Format: 'add evidence <eng_id> | <type> | <desc> | <source> | <file> | <collector> | <wp_id> | <finding_id> | <relevance> | <reliability>'"

    if query.startswith("assess risk "):
        parts = query.replace("assess risk ", "").split("|")
        if len(parts) >= 4:
            eng_id = parts[0].strip()
            area = parts[1].strip()
            risk = parts[2].strip()
            likelihood = parts[3].strip()
            impact = parts[4].strip()
            from core.audit_agent import assess_risk
            return assess_risk(eng_id, area, risk, likelihood, impact)
        return "Format: 'assess risk <eng_id> | <area> | <risk_desc> | <likelihood> | <impact>'"

    if query.startswith("create sample "):
        parts = query.replace("create sample ", "").split("|")
        if len(parts) >= 4:
            eng_id = parts[0].strip()
            area = parts[1].strip()
            pop = int(parts[2].strip())
            conf = float(parts[3].strip()) if len(parts) > 3 else 0.95
            tol = float(parts[4].strip()) if len(parts) > 4 else 0.05
            exp = float(parts[5].strip()) if len(parts) > 5 else 0.01
            from core.audit_agent import create_audit_sample
            result = create_audit_sample(eng_id, area, pop, conf, tol, exp)
            return f"Created sample: {result}"
        return "Format: 'create sample <eng_id> | <area> | <population> | <confidence> | <tolerable_error> | <expected_error>'"

    if query.startswith("register framework "):
        parts = query.replace("register framework ", "").split("|")
        if len(parts) >= 5:
            name = parts[0].strip()
            version = parts[1].strip()
            desc = parts[2].strip()
            category = parts[3].strip()
            jurisdiction = parts[4].strip()
            reqs = json.loads(parts[5].strip()) if len(parts) > 5 else []
            from core.audit_agent import register_framework
            fid = register_framework(name, version, desc, category, jurisdiction, reqs)
            return f"Registered framework: {fid}"
        return "Format: 'register framework <name> | <version> | <desc> | <category> | <jurisdiction> | <requirements_json>'"

    if query.startswith("assess compliance "):
        parts = query.replace("assess compliance ", "").split()
        if len(parts) >= 2:
            eng_id = parts[0]
            fw_id = parts[1]
            from core.audit_agent import assess_compliance
            return assess_compliance(eng_id, fw_id)
        return "Format: 'assess compliance <eng_id> <framework_id>'"

    if query.startswith("generate report "):
        parts = query.replace("generate report ", "").split()
        eng_id = parts[0]
        rtype = parts[1] if len(parts) > 1 else "audit_opinion"
        from core.audit_agent import generate_audit_report
        return generate_audit_report(eng_id, rtype)

    if query.startswith("review "):
        parts = query.replace("review ", "").split("|")
        if len(parts) >= 3:
            eng_id = parts[0].strip()
            wp_id = parts[1].strip()
            reviewer = parts[2].strip()
            rtype = parts[3].strip() if len(parts) > 3 else "workpaper"
            from core.audit_agent import create_quality_review
            rid = create_quality_review(eng_id, wp_id, reviewer, rtype)
            return f"Created quality review: {rid}"
        return "Format: 'review <eng_id> | <wp_id> | <reviewer> | <type>'"

    if query.startswith("log time "):
        parts = query.replace("log time ", "").split("|")
        if len(parts) >= 4:
            eng_id = parts[0].strip()
            staff = parts[1].strip()
            hours = float(parts[2])
            activity = parts[3].strip()
            desc = parts[4].strip() if len(parts) > 4 else ""
            billable = parts[5].lower() == "true" if len(parts) > 5 else True
            rate = float(parts[5]) if len(parts) > 5 else 0
            from core.audit_agent import log_audit_time
            tid = log_audit_time(eng_id, staff, hours, activity, desc, billable, rate)
            return f"Logged time entry: {tid}"
        return "Format: 'log time <eng_id> | <staff> | <hours> | <activity> | <desc> | <billable> | <rate>'"

    if query.startswith("budget ") and " for " in query:
        parts = query.replace("budget ", "").split(" for ")
        if len(parts) >= 2:
            eng_id = parts[1].strip()
            budget_parts = parts[0].split("|")
            if len(budget_parts) >= 4:
                name = budget_parts[0].strip()
                period = budget_parts[1].strip()
                start = datetime.strptime(budget_parts[2].strip(), "%Y-%m-%d").timestamp()
                total = float(budget_parts[3])
                from core.audit_agent import create_engagement_budget
                bid = create_engagement_budget(eng_id, total, period)
                return f"Created budget: {bid}"
        return "Format: 'budget <name> | <period> | <start_date> | <total> for <eng_id>'"

    if query.startswith("get budget "):
        bid = query.replace("get budget ", "").strip()
        from core.audit_agent import get_engagement_budget
        b = get_engagement_budget(bid)
        if b:
            return f"Budget {b['id']}: {b['total_hours']}h / ${b['total_fee']:,.2f} (Spent: {b['spent_hours']:.1f}h / ${b['spent_fee']:,.2f})"
        return "Budget not found."

    if query.startswith("create automation ") or query.startswith("automation "):
        parts = query.replace("create automation ", "").replace("automation ", "").split("|")
        if len(parts) >= 6:
            name = parts[0].strip()
            trigger_type = parts[1].strip()
            trigger_cfg = json.loads(parts[2]) if parts[2] else {}
            action_type = parts[3].strip()
            action_cfg = json.loads(parts[4]) if parts[4] else {}
            cooldown = int(parts[5]) if len(parts) > 5 else 60
            from core.audit_agent import create_automation_rule
            aid = create_automation_rule(name, trigger_type, trigger_cfg, action_type, action_cfg, cooldown)
            return f"Created automation rule: {aid}"
        return "Format: 'create automation <name> | <trigger_type> | <trigger_json> | <action_type> | <action_json> | <cooldown>'"

    if query in ["list automations", "automations list", "automations"]:
        from core.audit_agent import audit_agent
        rules = audit_agent.automation_engine.list_rules()
        if not rules:
            return "No automation rules."
        output = f"Automation Rules ({len(rules)}):\n"
        for r in rules:
            output += f"  • {r['name']} ({r['trigger_type']} -> {r['action_type']}) {'✓' if r['enabled'] else '✗'}\n"
        return output

    if query.startswith("enable automation "):
        from core.audit_agent import audit_agent
        rid = query.replace("enable automation ", "").strip()
        return f"Automation {rid} enabled (stub)."

    if query.startswith("disable automation "):
        from core.audit_agent import audit_agent
        rid = query.replace("disable automation ", "").strip()
        return f"Automation {rid} disabled (stub)."

    if query.startswith("delete automation "):
        from core.audit_agent import audit_agent
        rid = query.replace("delete automation ", "").strip()
        if audit_agent.automation_engine.remove_rule(rid):
            return f"Deleted automation {rid}."
        return f"Failed to delete automation {rid}."

    # ============================
    # MULTI-AGENT SYSTEM (Phase 36)
    # ============================

    if query in ["agent status", "multi agent status", "show agents"]:
        from core.multi_agent import registry, ma_debug
        return ma_debug()

    if query.startswith("agent task ") or query.startswith("submit task "):
        task_desc = query.replace("agent task ", "").replace("submit task ", "").strip()
        from core.multi_agent import create_task
        task_id = create_task("execute", {"description": task_desc})
        return f"Submitted task: {task_id}"

    if query.startswith("agent plan "):
        goal = query.replace("agent plan ", "").strip()
        from core.multi_agent import create_task
        task_id = create_task("plan", {"type": "decompose", "goal": goal})
        return f"Planning task submitted: {task_id}"

    if query.startswith("agent research "):
        topic = query.replace("agent research ", "").strip()
        from core.multi_agent import create_task
        task_id = create_task("research", {"type": "web_search", "query": topic})
        return f"Research task submitted: {task_id}"

    if query.startswith("agent review "):
        import pyperclip
        try:
            code = pyperclip.paste()
            if not code or len(code) < 10:
                return "No code in clipboard. Copy code first."
        except:
            return "Could not access clipboard."
        from core.multi_agent import create_task
        task_id = create_task("review", {"type": "code_review", "code": code})
        return f"Code review task submitted: {task_id}"

    if query in ["agent dashboard", "multi agent dashboard"]:
        from core.multi_agent import get_dashboard
        dash = get_dashboard()
        return (f"Multi-Agent Dashboard:\n"
                f"  Overdue: {dash['overdue_tasks']}\n"
                f"  Today: {dash['today_tasks']}\n"
                f"  Events: {dash['today_events']}\n"
                f"  Meetings: {dash['upcoming_meetings']}\n"
                f"  Inbox: {dash['inbox_count']}\n"
                f"  Habits due: {dash['habits_due']}\n"
                f"  Energy: {dash['energy_trend']} ({dash['avg_energy']:.0f}/10)")

    if query in ["agent briefing", "morning briefing", "daily briefing"]:
        from core.multi_agent import morning_briefing
        return morning_briefing()

    if query in ["agent schedule", "daily schedule", "plan my day"]:
        from core.multi_agent import suggest_schedule
        sched = suggest_schedule()
        if not sched["scheduled_tasks"]:
            return "No tasks scheduled for today."
        output = f"Schedule for {sched['date']} ({sched['available_hours']}h available):\n"
        for t in sched["scheduled_tasks"]:
            output += f"  • {t['title']} ({t['duration_min']}min, priority {t['priority']})\n"
        output += f"Buffer: {sched['buffer_minutes']}min"
        return output

    if query.startswith("agent workflow ") or query.startswith("create workflow "):
        parts = query.replace("agent workflow ", "").replace("create workflow ", "").split("|")
        if len(parts) >= 3:
            name = parts[0].strip()
            desc = parts[1].strip()
            steps_json = parts[2].strip()
            try:
                steps = json.loads(steps_json)
                from core.multi_agent import workflow_engine
                wf_id = workflow_engine.create_workflow(name, desc, steps)
                return f"Created workflow: {wf_id}"
            except json.JSONDecodeError:
                return "Invalid steps JSON format."
        return "Format: 'create workflow <name> | <description> | <steps_json>'"

    if query.startswith("run workflow "):
        wf_id = query.replace("run workflow ", "").strip()
        from core.multi_agent import workflow_engine
        exec_id = workflow_engine.execute_workflow(wf_id)
        return f"Started workflow execution: {exec_id}"

    if query in ["list workflows", "workflows list"]:
        from core.multi_agent import get_ma_connection
        conn = get_ma_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description FROM workflows WHERE is_active = 1")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return "No workflows defined."
        output = "Workflows:\n"
        for r in rows:
            output += f"  • {r[0]}: {r[1]} - {r[2]}\n"
        return output

    return None