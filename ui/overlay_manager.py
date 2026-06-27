from collections import deque

from ui.overlays.selection_overlay import SelectionOverlay


class OverlayManager:

    def __init__(self):

        self.selection_overlay = None

        self.queue = deque()

        self.overlay_visible = False

    # ======================================================

    def get_overlay(self):

        if self.selection_overlay is None:

            self.selection_overlay = SelectionOverlay()

            self.selection_overlay.closed.connect(
                self.overlay_closed
            )

        return self.selection_overlay

    # ======================================================

    def show_files(
        self,
        items,
        callback=None,
        title="Files"
    ):

        self.queue.append(

            (
                items,
                callback,
                title
            )

        )

        self.process_queue()

    # ======================================================

    def process_queue(self):

        if self.overlay_visible:

            return

        if not self.queue:

            return

        items, callback, title = self.queue.popleft()

        overlay = self.get_overlay()

        self.overlay_visible = True

        print("Opening SelecttionOverlay...")

        overlay.show_results(

            items,

            callback=callback,

            title=title

        )

        print("SelectionOverlay opened")

    # ======================================================

    def overlay_closed(self):

        self.overlay_visible = False

        self.process_queue()

    # ======================================================

    def hide(self):

        if self.selection_overlay:

            self.selection_overlay.hide_overlay()


overlay_manager = OverlayManager()