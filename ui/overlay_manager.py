from collections import deque

from ui.overlays.selection_overlay import SelectionOverlay
from ui.overlays.vision_overlay import VisionOverlay
from ui.widgets.widget_framework import (
    get_widget, show_file_results, show_system_info, show_notification,
    show_progress, show_text, WidgetType
)


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

        # Use new widget framework for file results
        show_file_results(items, callback, title)

    # ======================================================

    def show_system_info(self):
        """Show system information widget."""
        show_system_info()

    # ======================================================

    def show_notification(self, message: str, icon: str = "ℹ", color: str = "#2E7DFF", timeout: int = 5):
        """Show a toast notification."""
        show_notification(message, icon, color, timeout)

    # ======================================================

    def show_progress(self, title: str = "Processing..."):
        """Show progress widget and return it for updates."""
        return show_progress(title)

    # ======================================================

    def show_text(self, text: str, title: str = "Content"):
        """Show text display widget."""
        show_text(text, title)

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