"""
Nova Widget Framework - Phase 6
Universal UI widgets for different information types.
Widget philosophy:
- Small info = Voice only
- Medium info = Voice + Widget  
- Large info = Widget + short voice summary
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListView,
    QPushButton, QProgressBar, QTextEdit, QFrame, QGridLayout
)
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QPixmap, QIcon
from enum import Enum
from typing import Optional, Callable, Any, List, Dict
from dataclasses import dataclass
import time

from ui.overlay import NovaOverlay
from ui.animations.fade import FadeAnimation
from ui.delegates.selection_delegate import SelectionDelegate
from ui.models.selection_model import SelectionModel
from core.file_icons import get_file_icon


class WidgetType(Enum):
    FILE_RESULTS = "file_results"
    FOLDER_RESULTS = "folder_results"
    SYSTEM_INFO = "system_info"
    NOTIFICATION = "notification"
    PROGRESS = "progress"
    CONFIRMATION = "confirmation"
    TEXT_DISPLAY = "text_display"
    IMAGE_PREVIEW = "image_preview"
    CODE_PREVIEW = "code_preview"


@dataclass
class WidgetConfig:
    type: WidgetType
    title: str = "NOVA"
    width: int = 650
    height: int = 450
    timeout: int = 0  # 0 = no auto-close
    position: str = "center"  # center, top_right, bottom_right
    voice_summary: bool = True
    actions: List[Dict] = None


class BaseWidget(QWidget):
    """Base class for all Nova widgets."""
    
    def __init__(self, config: WidgetConfig):
        super().__init__()
        self.config = config
        self.callback: Optional[Callable] = None
        self._auto_close_timer: Optional[QTimer] = None
        self._setup_base()
        
    def _setup_base(self):
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(self.config.width, self.config.height)
        self.hide()
        
        # Shadow effect
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)
        
        # Fade animation
        self.fade = FadeAnimation(self)
        
    def center(self):
        screen = self.screen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        
        if self.config.position == "center":
            x = geometry.center().x() - self.width() // 2
            y = geometry.center().y() - self.height() // 2
        elif self.config.position == "top_right":
            x = geometry.right() - self.width() - 20
            y = geometry.top() + 20
        elif self.config.position == "bottom_right":
            x = geometry.right() - self.width() - 20
            y = geometry.bottom() - self.height() - 20
        else:
            x = geometry.center().x() - self.width() // 2
            y = geometry.center().y() - self.height() // 2
            
        self.move(x, y)
        
    def show_widget(self):
        self.center()
        self.raise_()
        self.activateWindow()
        self.fade.fade_in()
        
        if self.config.timeout > 0:
            self._auto_close_timer = QTimer.singleShot(
                self.config.timeout * 1000,
                self.hide_widget
            )
            
    def hide_widget(self):
        if self._auto_close_timer:
            self._auto_close_timer.stop()
        self.fade.fade_out()
        
    def set_callback(self, callback: Callable):
        self.callback = callback


class FileResultsWidget(BaseWidget):
    """Widget for displaying file search results with open actions."""
    
    def __init__(self, config: WidgetConfig = None):
        if config is None:
            config = WidgetConfig(
                type=WidgetType.FILE_RESULTS,
                title="File Search Results",
                width=700,
                height=500
            )
        super().__init__(config)
        self._build_ui()
        
    def _build_ui(self):
        self.container = QWidget(self)
        self.container.resize(self.width(), self.height())
        self.container.setStyleSheet("""
            QWidget {
                background: #1E1E1E;
                border-radius: 18px;
                border: 1px solid #444;
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet("background: #252525; border-top-left-radius: 18px; border-top-right-radius: 18px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        self.title_label = QLabel(self.config.title)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        self.count_label = QLabel("0 results")
        self.count_label.setStyleSheet("font-size: 12px; color: #AAAAAA;")
        header_layout.addWidget(self.count_label)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #AAAAAA;
                font-size: 20px;
                font-weight: bold;
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background: #333333;
                color: #FFFFFF;
            }
        """)
        close_btn.clicked.connect(self.hide_widget)
        header_layout.addWidget(close_btn)
        
        layout.addWidget(header)
        
        # Results list
        self.model = SelectionModel()
        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(SelectionDelegate())
        self.view.doubleClicked.connect(self._on_item_selected)
        self.view.setSelectionMode(QListView.SingleSelection)
        self.view.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setStyleSheet("""
            QListView {
                background: transparent;
                border: none;
                outline: none;
            }
        """)
        layout.addWidget(self.view)
        
        # Footer
        footer = QWidget()
        footer.setFixedHeight(50)
        footer.setStyleSheet("background: #252525; border-bottom-left-radius: 18px; border-bottom-right-radius: 18px;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        
        self.status_label = QLabel("Use ↑↓ to navigate, Enter to open, Esc to close")
        self.status_label.setStyleSheet("font-size: 11px; color: #888888;")
        footer_layout.addWidget(self.status_label)
        
        footer_layout.addStretch()
        
        open_btn = QPushButton("Open")
        open_btn.setFixedSize(80, 32)
        open_btn.setStyleSheet("""
            QPushButton {
                background: #2E7DFF;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1E6DDF; }
            QPushButton:pressed { background: #0E5DCF; }
        """)
        open_btn.clicked.connect(lambda: self._on_item_selected(self.view.currentIndex()))
        footer_layout.addWidget(open_btn)
        
        layout.addWidget(footer)
        
    def show_results(self, items: List[Dict], callback: Callable = None, title: str = None):
        self.callback = callback
        if title:
            self.title_label.setText(title)
            
        # Add index numbers to items
        for i, item in enumerate(items):
            item["_index"] = i + 1
            
        self.model.set_items(items)
        self.count_label.setText(f"{len(items)} result{'s' if len(items) != 1 else ''}")
        
        if self.model.rowCount() > 0:
            self.view.setCurrentIndex(self.model.index(0))
            
        self.show_widget()
        
    def _on_item_selected(self, index):
        if not index.isValid():
            return
        item = self.model.get_item(index.row())
        if item and self.callback:
            self.callback(item)
        self.hide_widget()
        
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.hide_widget()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            idx = self.view.currentIndex()
            if idx.isValid():
                self._on_item_selected(idx)
        super().keyPressEvent(event)


class SystemInfoWidget(BaseWidget):
    """Widget for displaying system information (CPU, RAM, disk, battery)."""
    
    def __init__(self, config: WidgetConfig = None):
        if config is None:
            config = WidgetConfig(
                type=WidgetType.SYSTEM_INFO,
                title="System Information",
                width=400,
                height=350,
                position="top_right",
                timeout=10
            )
        super().__init__(config)
        self._build_ui()
        
    def _build_ui(self):
        self.container = QWidget(self)
        self.container.resize(self.width(), self.height())
        self.container.setStyleSheet("""
            QWidget {
                background: #1E1E1E;
                border-radius: 18px;
                border: 1px solid #444;
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Title
        self.title_label = QLabel(self.config.title)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # System stats grid
        grid = QGridLayout()
        grid.setSpacing(12)
        
        self.cpu_bar = self._create_stat_bar("CPU", 0)
        self.ram_bar = self._create_stat_bar("RAM", 1)
        self.disk_bar = self._create_stat_bar("Disk", 2)
        self.battery_bar = self._create_stat_bar("Battery", 3)
        
        grid.addWidget(self.cpu_bar["label"], 0, 0)
        grid.addWidget(self.cpu_bar["bar"], 0, 1)
        grid.addWidget(self.cpu_bar["value"], 0, 2)
        
        grid.addWidget(self.ram_bar["label"], 1, 0)
        grid.addWidget(self.ram_bar["bar"], 1, 1)
        grid.addWidget(self.ram_bar["value"], 1, 2)
        
        grid.addWidget(self.disk_bar["label"], 2, 0)
        grid.addWidget(self.disk_bar["bar"], 2, 1)
        grid.addWidget(self.disk_bar["value"], 2, 2)
        
        grid.addWidget(self.battery_bar["label"], 3, 0)
        grid.addWidget(self.battery_bar["bar"], 3, 1)
        grid.addWidget(self.battery_bar["value"], 3, 2)
        
        layout.addLayout(grid)
        
        # Network status
        self.network_label = QLabel("Internet: Checking...")
        self.network_label.setStyleSheet("font-size: 12px; color: #AAAAAA;")
        self.network_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.network_label)
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(2000)
        
    def _create_stat_bar(self, name: str, row: int):
        label = QLabel(name)
        label.setStyleSheet("font-size: 13px; font-weight: bold; min-width: 60px;")
        
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setFixedHeight(12)
        bar.setStyleSheet("""
            QProgressBar {
                background: #2A2A2A;
                border-radius: 6px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #2E7DFF, stop:1 #00D4FF);
                border-radius: 6px;
            }
        """)
        
        value = QLabel("0%")
        value.setStyleSheet("font-size: 12px; color: #AAAAAA; min-width: 40px;")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        return {"label": label, "bar": bar, "value": value}
        
    def _update_stats(self):
        import psutil
        import socket
        
        cpu = psutil.cpu_percent()
        self.cpu_bar["bar"].setValue(int(cpu))
        self.cpu_bar["value"].setText(f"{cpu:.0f}%")
        self.cpu_bar["value"].setStyleSheet(
            f"font-size: 12px; color: {'#FF6B6B' if cpu > 80 else '#AAAAAA'};"
        )
        
        ram = psutil.virtual_memory()
        self.ram_bar["bar"].setValue(int(ram.percent))
        self.ram_bar["value"].setText(f"{ram.percent:.0f}%")
        self.ram_bar["value"].setStyleSheet(
            f"font-size: 12px; color: {'#FF6B6B' if ram.percent > 80 else '#AAAAAA'};"
        )
        
        disk = psutil.disk_usage('/')
        disk_pct = disk.percent
        self.disk_bar["bar"].setValue(int(disk_pct))
        self.disk_bar["value"].setText(f"{disk_pct:.0f}%")
        self.disk_bar["value"].setStyleSheet(
            f"font-size: 12px; color: {'#FF6B6B' if disk_pct > 90 else '#AAAAAA'};"
        )
        
        try:
            battery = psutil.sensors_battery()
            if battery:
                bat_pct = battery.percent
                self.battery_bar["bar"].setValue(int(bat_pct))
                self.battery_bar["value"].setText(f"{bat_pct:.0f}%{' ⚡' if battery.power_plugged else ''}")
                self.battery_bar["value"].setStyleSheet(
                    f"font-size: 12px; color: {'#FF6B6B' if bat_pct < 20 and not battery.power_plugged else '#AAAAAA'};"
                )
            else:
                self.battery_bar["bar"].setValue(0)
                self.battery_bar["value"].setText("N/A")
        except:
            self.battery_bar["value"].setText("N/A")
            
        try:
            socket.create_connection(("google.com", 80), timeout=2)
            self.network_label.setText("Internet: Connected")
            self.network_label.setStyleSheet("font-size: 12px; color: #4ECC4E;")
        except:
            self.network_label.setText("Internet: Disconnected")
            self.network_label.setStyleSheet("font-size: 12px; color: #FF6B6B;")


class NotificationWidget(BaseWidget):
    """Toast-style notification widget."""
    
    def __init__(self, config: WidgetConfig = None):
        if config is None:
            config = WidgetConfig(
                type=WidgetType.NOTIFICATION,
                title="",
                width=350,
                height=100,
                position="bottom_right",
                timeout=5
            )
        super().__init__(config)
        self._build_ui()
        
    def _build_ui(self):
        self.container = QWidget(self)
        self.container.resize(self.width(), self.height())
        self.container.setStyleSheet("""
            QWidget {
                background: #1E1E1E;
                border-radius: 12px;
                border: 1px solid #444;
                color: white;
            }
        """)
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        self.icon_label = QLabel("ℹ")
        self.icon_label.setFixedSize(28, 28)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.icon_label)
        
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.message_label, 1)
        
    def show_notification(self, message: str, icon: str = "ℹ", color: str = "#2E7DFF"):
        self.icon_label.setText(icon)
        self.icon_label.setStyleSheet(f"font-size: 16px; color: {color};")
        self.message_label.setText(message)
        self.show_widget()


class ProgressWidget(BaseWidget):
    """Progress bar widget for long-running operations."""
    
    def __init__(self, config: WidgetConfig = None):
        if config is None:
            config = WidgetConfig(
                type=WidgetType.PROGRESS,
                title="Processing...",
                width=400,
                height=150,
                position="center"
            )
        super().__init__(config)
        self._build_ui()
        
    def _build_ui(self):
        self.container = QWidget(self)
        self.container.resize(self.width(), self.height())
        self.container.setStyleSheet("""
            QWidget {
                background: #1E1E1E;
                border-radius: 18px;
                border: 1px solid #444;
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        self.title_label = QLabel(self.config.title)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("font-size: 12px; color: #AAAAAA;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #2A2A2A;
                border-radius: 5px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #2E7DFF, stop:1 #00D4FF);
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("font-size: 11px; color: #888888;")
        self.detail_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.detail_label)
        
    def update_progress(self, value: int, status: str = "", detail: str = ""):
        self.progress_bar.setValue(value)
        if status:
            self.status_label.setText(status)
        if detail:
            self.detail_label.setText(detail)
            
    def complete(self, message: str = "Complete"):
        self.status_label.setText(message)
        self.progress_bar.setValue(100)
        QTimer.singleShot(1500, self.hide_widget)


class TextDisplayWidget(BaseWidget):
    """Widget for displaying longer text content (code, logs, documents)."""
    
    def __init__(self, config: WidgetConfig = None):
        if config is None:
            config = WidgetConfig(
                type=WidgetType.TEXT_DISPLAY,
                title="Content",
                width=700,
                height=500
            )
        super().__init__(config)
        self._build_ui()
        
    def _build_ui(self):
        self.container = QWidget(self)
        self.container.resize(self.width(), self.height())
        self.container.setStyleSheet("""
            QWidget {
                background: #1E1E1E;
                border-radius: 18px;
                border: 1px solid #444;
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet("background: #252525; border-top-left-radius: 18px; border-top-right-radius: 18px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        self.title_label = QLabel(self.config.title)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #AAAAAA;
                font-size: 18px;
                border: none;
                border-radius: 14px;
            }
            QPushButton:hover { background: #333333; color: white; }
        """)
        close_btn.clicked.connect(self.hide_widget)
        header_layout.addWidget(close_btn)
        
        layout.addWidget(header)
        
        # Text area
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("""
            QTextEdit {
                background: #1A1A1A;
                border: none;
                border-bottom-left-radius: 18px;
                border-bottom-right-radius: 18px;
                color: #E0E0E0;
                font-family: 'Consolas', 'Monospace';
                font-size: 12px;
                padding: 16px;
            }
        """)
        layout.addWidget(self.text_area)
        
    def show_text(self, text: str, title: str = None):
        if title:
            self.title_label.setText(title)
        self.text_area.setPlainText(text)
        self.show_widget()


# Widget registry
_widget_instances: Dict[WidgetType, BaseWidget] = {}


def get_widget(widget_type: WidgetType, config: WidgetConfig = None) -> BaseWidget:
    """Get or create a widget instance."""
    if widget_type not in _widget_instances:
        if widget_type == WidgetType.FILE_RESULTS:
            _widget_instances[widget_type] = FileResultsWidget(config)
        elif widget_type == WidgetType.FOLDER_RESULTS:
            _widget_instances[widget_type] = FileResultsWidget(config)
        elif widget_type == WidgetType.SYSTEM_INFO:
            _widget_instances[widget_type] = SystemInfoWidget(config)
        elif widget_type == WidgetType.NOTIFICATION:
            _widget_instances[widget_type] = NotificationWidget(config)
        elif widget_type == WidgetType.PROGRESS:
            _widget_instances[widget_type] = ProgressWidget(config)
        elif widget_type == WidgetType.TEXT_DISPLAY:
            _widget_instances[widget_type] = TextDisplayWidget(config)
        else:
            _widget_instances[widget_type] = FileResultsWidget(config)
    return _widget_instances[widget_type]


def show_file_results(items: List[Dict], callback: Callable = None, title: str = "File Results"):
    widget = get_widget(WidgetType.FILE_RESULTS)
    widget.show_results(items, callback, title)


def show_system_info():
    widget = get_widget(WidgetType.SYSTEM_INFO)
    widget.show_widget()


def show_notification(message: str, icon: str = "ℹ", color: str = "#2E7DFF", timeout: int = 5):
    config = WidgetConfig(type=WidgetType.NOTIFICATION, timeout=timeout)
    widget = get_widget(WidgetType.NOTIFICATION, config)
    widget.show_notification(message, icon, color)


def show_progress(title: str = "Processing..."):
    config = WidgetConfig(type=WidgetType.PROGRESS, title=title)
    widget = get_widget(WidgetType.PROGRESS, config)
    widget.show_widget()
    return widget


def show_text(text: str, title: str = "Content"):
    widget = get_widget(WidgetType.TEXT_DISPLAY)
    widget.show_text(text, title)