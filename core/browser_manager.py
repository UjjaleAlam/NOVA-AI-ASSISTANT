import urllib.parse
import webbrowser
import pywhatkit


class BrowserManager:

    def __init__(self):

        self.youtube_open = False

        self.current_url = None

    # ==================================================
    # Open URL
    # ==================================================

    def open_url(self, url):

        try:

            webbrowser.open(url)

            self.current_url = url

            return True

        except Exception as e:

            print("Browser:", e)

            return False

    # ==================================================
    # Google Search
    # ==================================================

    def google_search(self, query):

        url = (
            "https://www.google.com/search?q="
            + urllib.parse.quote(query)
        )

        return self.open_url(url)

    # ==================================================
    # YouTube Search
    # ==================================================

    def youtube_search(self, query):

        url = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote(query)
        )

        self.youtube_open = True

        return self.open_url(url)

    # ==================================================
    # Play Music
    # ==================================================

    def play(self, query):

        try:

            pywhatkit.playonyt(query)

            self.youtube_open = True

            return True

        except Exception as e:

            print("Browser:", e)

            return False


browser_manager = BrowserManager()