from queue import Queue

# Global queue used by Nova background services
event_queue = Queue()


def add_event(event_type, path, destination=None):
    """
    Add a filesystem event to the queue.
    """

    event_queue.put(
        {
            "type": event_type,
            "path": path,
            "destination": destination
        }
    )


def get_event():
    """
    Wait until an event is available.
    """

    return event_queue.get()


def task_done():
    """
    Mark current event as processed.
    """

    event_queue.task_done()


def queue_size():
    return event_queue.qsize()