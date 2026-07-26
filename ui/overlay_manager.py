from collections import deque

from ui.overlays.selection_overlay import SelectionOverlay
from ui.overlays.vision_overlay import VisionOverlay

class OverlayManager:

    def __init__(self):

        self.selection_overlay = None

        self.queue = deque()

        self.overlay_visible = False

        self.vision_overlay = None

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

    # =======================================================

    def get_vision_overlay(self):

        if self.vision_overlay is None:

            self.vision_overlay = VisionOverlay()

            self.vision_overlay.closed.connect(
                self.overlay_closed
            )

        return self.vision_overlay
    
    # =========================================================

    def show_vision(
            self,
            text,
            title="Vision"
    ):
        
        if self.overlay_visible:
            return
        
        overlay = self.get_vision_overlay()

        self.overlay_visible = True

        overlay.show_message(
            text,
            title
        )


overlay_manager = OverlayManager()