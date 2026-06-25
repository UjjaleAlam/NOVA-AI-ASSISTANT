import threading

from event_queue import (
    get_event,
    task_done
)

from database import (
    insert_file,
    update_file,
    delete_file
)


def worker():

    while True:

        event = get_event()

        try:

            if event["type"] == "created":

                insert_file(event["path"])

            elif event["type"] == "modified":

                update_file(event["path"])

            elif event["type"] == "deleted":

                delete_file(event["path"])

            elif event["type"] == "moved":

                delete_file(event["path"])

                insert_file(event["destination"])

        except Exception as e:

            print(e)

        finally:

            task_done()


def start_worker():

    thread = threading.Thread(
        target=worker,
        daemon=True
    )

    thread.start()