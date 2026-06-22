import os
import webbrowser
import urllib.parse
import pyautogui


def run_command(query):

    query = query.lower().strip()

    # ==========================
    # GOOGLE SEARCH
    # ==========================

    if query.startswith("search "):

        search_term = query.replace("search ", "").strip()

        url = (
            "https://www.google.com/search?q="
            + urllib.parse.quote(search_term)
        )

        webbrowser.open(url)

        return f"Searching for {search_term}"

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

    # ==========================
    # APPLICATIONS
    # ==========================

    apps = {
        "edge": "start msedge",
        "microsoft edge": "start msedge",
        "brave": "start brave",
        "chrome": "start chrome",
        "firefox": "start firefox",
        "notepad": "start notepad",
        "calculator": "start calc",
        "paint": "start mspaint",
        "cmd": "start cmd",
        "powershell": "start powershell",
        "spotify": "start spotify",
        "discord": "start discord",
        "steam": "start steam",
        "vscode": "start code",
        "visual studio code": "start code",
        "explorer": "start explorer"
    }

    # ==========================
    # OPEN COMMAND
    # ==========================

    if query.startswith("open "):

        item = query.replace("open ", "").strip()

        # Open websites

        if item in websites:

            webbrowser.open(websites[item])

            return f"Opening {item}"

        # Open apps

        if item in apps:

            os.system(apps[item])

            return f"Opening {item}"

        return f"I don't know how to open {item} yet."

    # ==========================
    # POWERPOINT CONTROL
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
    # VOLUME CONTROL
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