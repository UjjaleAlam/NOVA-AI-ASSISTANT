from datetime import datetime
import psutil
import socket


def get_greeting():

    hour = datetime.now().hour

    if hour < 12:
        return "Good morning"

    elif hour < 18:
        return "Good afternoon"

    return "Good evening"


def get_battery():

    try:
        battery = psutil.sensors_battery()

        if battery:
            return f"Battery is {battery.percent} percent"

        return "Battery information unavailable"

    except:
        return "Battery information unavailable"


def get_internet():

    try:
        socket.create_connection(("google.com", 80), timeout=3)
        return "Internet is connected"

    except:
        return "Internet is disconnected"


def startup_message():

    today = datetime.now().strftime("%A, %B %d")

    message = (
        f"{get_greeting()} Sir. "
        f"Today is {today}. "
        f"{get_internet()}. "
        f"{get_battery()}. "
        f"How can I help you?"
    )

    return message