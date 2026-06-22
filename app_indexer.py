import os
import json

APP_LOCATIONS = [
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%USERPROFILE%\Desktop"),
]


def build_app_index():

    apps = {}

    for location in APP_LOCATIONS:

        if not os.path.exists(location):
            continue

        for root, dirs, files in os.walk(location):

            for file in files:

                if file.endswith(".lnk"):

                    app_name = os.path.splitext(file)[0].lower()

                    apps[app_name] = os.path.join(root, file)

    with open("apps.json", "w", encoding="utf-8") as f:

        json.dump(apps, f, indent=4)

    return len(apps)


if __name__ == "__main__":

    count = build_app_index()

    print(f"Indexed {count} applications")