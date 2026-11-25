"""
Elvaerwyns MH2 Official Theme Engine V1.1 (INI-Configurable QSS)
Saves theme.ini inside <active_data_folder>/themes/theme.ini
Contributed by Elvaerwyn_MH2 2026
"""
import os
import re
import configparser
from PySide6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget
from mh2_standalone_core import get_windows_mh2_userdata


PRESETS = {
    "mh2_steel_orange": {
        "accent": "#f69038",
        "accent_bright": "#fdb863",
        "accent_deep": "#f58220",
        "accent_dark": "#6a3304",
        "accent_disabled": "#8e4e1a",
        "selection_bg": "#d7801a",
        "bg_center": "#3c3c3c",
        "bg_mid": "#2b2b2b",
        "bg_edge": "#000000",
        "panel_center": "#989898",
        "panel_dark": "#323232",
        "text_color": "#FFFFFF",
        "btn_text": "#000000",
        "font_size": "14",
        "font_family": "Helvetica, Arial, sans-serif",
        "font_size": "14",
        "border_width": "3",
        "border_radius": "8",
    },
    "mh2_fantasy_purple": {
        "accent": "#a855f7",
        "accent_bright": "#d8b4fe",
        "accent_deep": "#9333ea",
        "accent_dark": "#3b0764",
        "accent_disabled": "#581c87",
        "selection_bg": "#7e22ce",
        "bg_center": "#322b3d",
        "bg_mid": "#221d2b",
        "bg_edge": "#09070d",
        "panel_center": "#8b809e",
        "panel_dark": "#292333",
        "text_color": "#FFFFFF",
        "btn_text": "#000000",
        "font_size": "14",
        "font_family": "Helvetica, Arial, sans-serif",
        "font_size": "14",
        "border_width": "3",
        "border_radius": "8",
    },
    "mh2_cyber_cyan": {
        "accent": "#06b6d4",
        "accent_bright": "#67e8f9",
        "accent_deep": "#0891b2",
        "accent_dark": "#164e63",
        "accent_disabled": "#155e75",
        "selection_bg": "#0e7490",
        "bg_center": "#29383d",
        "bg_mid": "#1c272b",
        "bg_edge": "#060a0c",
        "panel_center": "#7d969e",
        "panel_dark": "#202c30",
        "text_color": "#FFFFFF",
        "btn_text": "#000000",
        "font_size": "14",
        "font_family": "Helvetica, Arial, sans-serif",
        "font_size": "14",
        "border_width": "3",
        "border_radius": "8",
    },
    "classic_flat_dark": {
        "accent": "#606060",
        "accent_bright": "#888888",
        "accent_deep": "#505050",
        "accent_dark": "#2a2a2a",
        "accent_disabled": "#3a3a3a",
        "selection_bg": "#4a4a4a",
        "bg_center": "#252526",
        "bg_mid": "#252526",
        "bg_edge": "#1e1e1e",
        "panel_center": "#333337",
        "panel_dark": "#2d2d30",
        "text_color": "#E0E0E0",
        "btn_text": "#000000",
        "font_size": "14",
        "font_family": "Helvetica, Arial, sans-serif",
        "font_size": "14",
        "border_width": "1",
        "border_radius": "4",
    },
}


QSS_TEMPLATE = """
QMainWindow, QDialog {{
    color: {text_color};
    font-family: {font_family};
    font-weight: bold;
    font-size: {font_size}px;
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 1.0, fx: 0.5, fy: 0.5,
                stop: 0 {bg_center},
                stop: 0.6 {bg_mid},
                stop: 1 {bg_edge});
}}


QWidget {{
    color: {text_color};
    font-family: {font_family};
    font-weight: bold;
    font-size: {font_size}px;
}}


QScrollArea, QWidget#qt_scrollarea_viewport {{
    background: transparent;
    border: none;
}}

QGroupBox, QListWidget, QTreeView, QTableView, QMenu {{
    border-radius: {border_radius}px;
    border: {border_width}px solid {accent};
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 1.1,
                fx: 0.5, fy: 0.5,
                stop: 0 {panel_center},
                stop: 0.8 {panel_dark},
                stop: 1.0 {accent});
}}

QGroupBox {{
    margin-top: 12px;
    padding-top: 14px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 2px 14px;
    color: {btn_text};
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                stop:0 {accent_bright}, stop:1 {accent});
    border: 1px solid #1a1a1a;
    border-radius: 4px;
}}

QListWidget {{
    color: {text_color};
    selection-background-color: {selection_bg};
}}

QListWidget::item:selected, QTreeView::item:selected, QTableView::item:selected {{
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.8,
                fx: 0.5, fy: 0.5,
                stop: 0 {accent}, stop: 1 #1e1e1e);
    color: {text_color};
}}

QListWidget::item:hover, QTreeView::item:hover {{
    background: rgba(246, 144, 56, 0.25);
}}

QPushButton {{
    color: {btn_text};
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                 stop:0 #ffffff, stop:0.5 #e0e0e0, stop:1 #ffffff);
    font: bold {font_size}px;
    border: 3px solid {panel_center};
    border-radius: 6px;
    padding: 4px 8px;
}}

QPushButton:hover {{
    background: #f0f0f0;
    border: 2px solid {accent};
}}

QPushButton:checked, QPushButton:pressed {{
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                 stop:0 {panel_center}, stop:0.5 {accent}, stop:1 {panel_center});
    color: {text_color};
    border: 3px solid {text_color};
}}

QPushButton:disabled {{
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                 stop:0 {panel_dark}, stop:0.5 #888888, stop:1 {panel_dark});
    color: #bbbbbb;
    border: 3px solid {accent_disabled};
    border-radius: 6px;
}}

QTabWidget::pane {{
    border: {border_width}px solid {accent};
    border-radius: {border_radius}px;
    top: -3px;
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 1.0, fx: 0.5, fy: 0.5,
                stop: 0 {bg_center},
                stop: 0.7 {bg_mid},
                stop: 1 {bg_edge});
}}

QTabBar::tab {{
    border: 1px solid #555555;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 5px 11px;
    color: {text_color};
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 1.1,
                fx: 0.5, fy: 0.5,
                stop: 0 {accent_dark},
                stop: 0.6 {selection_bg},
                stop: 1.0 {panel_dark});
}}

QTabBar::tab:selected {{
    border: {border_width}px solid {accent};
    border-bottom: none;
    color: {text_color};
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 1.1,
                fx: 0.5, fy: 0.5,
                stop: 0 {panel_center},
                stop: 0.7 {panel_dark},
                stop: 1.0 {accent});
}}

QTabBar::tab:hover {{
    color: {accent_bright};
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 1.1,
                fx: 0.5, fy: 0.5,
                stop: 0 {selection_bg},
                stop: 1.0 #1e1e1e);
}}

QLabel {{
    background-color: transparent;
}}

QToolTip {{
    border: 1px solid black;
    background-color: {accent};
    padding: 2px;
    color: #000000;
}}

QLineEdit, QSpinBox, QTextEdit {{
    background-color: #1e1e1e;
    border: 2px solid {accent};
    border-radius: 4px;
    padding: 3px;
    color: {text_color};
}}

QComboBox {{
    background: {panel_dark};
    border: 2px solid {panel_center};
    border-radius: 4px;
    padding: 2px 8px;
    color: {text_color};
}}

QComboBox:hover {{
    border: 2px solid {accent};
}}

QComboBox QAbstractItemView {{
    background-color: {panel_dark};
    color: {text_color};
    selection-background-color: {accent};
    border: 2px solid {accent};
}}

QProgressBar {{
    background-color: #000000;
    color: {text_color};
    border: 2px solid {panel_center};
    text-align: center;
    border-radius: 6px;
}}

QProgressBar::chunk {{
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                stop:0 {panel_dark}, stop:0.2 {panel_center}, stop:0.5 {accent}, stop:1 {panel_dark});
    border-radius: 5px;
}}

QSlider::groove:horizontal {{
    border: 2px solid {panel_center};
    height: 10px;
    background: #141414;
    border-radius: 5px;
}}

QSlider::sub-page:horizontal {{
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                stop:0 {accent_dark}, stop:1 {accent});
    border: 1px solid {accent};
    height: 10px;
    border-radius: 5px;
}}

QSlider::handle:horizontal {{
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                stop:0 #ffffff, stop:0.5 #e0e0e0, stop:1 #ffffff);
    border: 2px solid {accent};
    width: 16px;
    height: 18px;
    margin: -6px 0;
    border-radius: 5px;
}}

QSlider::handle:horizontal:hover {{
    background: {accent_bright};
    border: 2px solid #ffffff;
}}

QScrollBar:vertical {{
    border: 1px solid #1e1e1e;
    background: #000000;
    width: 14px;
    margin: 18px 0 18px 0;
}}

QScrollBar:horizontal {{
    border: 1px solid #1e1e1e;
    background: #000000;
    height: 14px;
    margin: 0 18px 0 18px;
}}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                stop:0 #ffffff, stop:0.5 #e0e0e0, stop:1 #ffffff);
    border: 2px solid {panel_center};
    border-radius: 4px;
    min-height: 20px;
    min-width: 20px;
}}

QScrollBar::handle:hover {{
    border-color: {accent};
}}

QScrollBar::handle:pressed {{
    background: {accent};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    border: 3px solid {panel_center};
    background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
                stop:0 #000000, stop:0.5 {accent_dark}, stop:1 #000000);
    border-radius: 4px;
    subcontrol-origin: margin;
}}

QScrollBar::sub-line:vertical {{ height: 16px; subcontrol-position: top; }}
QScrollBar::add-line:vertical {{ height: 16px; subcontrol-position: bottom; }}
QScrollBar::sub-line:horizontal {{ width: 16px; subcontrol-position: left; }}
QScrollBar::add-line:horizontal {{ width: 16px; subcontrol-position: right; }}
"""


class MH2ThemeManager:
    def __init__(self, mh_glob=None, target_window=None):
        self.mh_glob = mh_glob
        self.target_window = target_window
        self.cfg = configparser.ConfigParser()
        self._ensure_ini()

    @property
    def ini_path(self):
        base = self.mh_glob.env.path_userdata if self.mh_glob else get_windows_mh2_userdata()
        themes_dir = os.path.join(base, "themes")
        os.makedirs(themes_dir, exist_ok=True)
        return os.path.join(themes_dir, "theme.ini")

    def _ensure_ini(self):
        path = self.ini_path
        if not os.path.exists(path):
            self.cfg.clear()
            self.cfg["General"] = {
                "active_preset": "mh2_steel_orange",
                "custom_qss_file": "",
            }
            for preset_name, values in PRESETS.items():
                self.cfg[preset_name] = dict(values)
            self._save_ini()
        else:
            self.cfg.read(path, encoding="utf-8")

    def _save_ini(self):
        with open(self.ini_path, "w", encoding="utf-8") as f:
            self.cfg.write(f)

    def get_active_preset(self):
        return self.cfg.get("General", "active_preset", fallback="mh2_steel_orange")

    def list_presets(self):
        return [s for s in self.cfg.sections() if s != "General"]

    def set_preset(self, preset_name):
        if preset_name in self.cfg:
            self.cfg["General"]["active_preset"] = preset_name
            self._save_ini()
        self.apply()

    def build_qss(self):
        custom_qss = self.cfg.get("General", "custom_qss_file", fallback="").strip()
        if custom_qss:
            themes_dir = os.path.dirname(self.ini_path)
            full_qss = custom_qss if os.path.isabs(custom_qss) else os.path.join(themes_dir, custom_qss)
            if os.path.exists(full_qss):
                with open(full_qss, "r", encoding="utf-8") as f:
                    raw = f.read()
                raw = re.sub(r"image:\s*url\([^)]+\);\s*", "", raw)
                return raw

        preset = self.get_active_preset()
        merged = dict(PRESETS["mh2_steel_orange"])
        if preset in self.cfg:
            merged.update(dict(self.cfg[preset]))
        return QSS_TEMPLATE.format(**merged)

    def apply(self, app=None):
        qss = self.build_qss()
        target = app or QApplication.instance()
        if target is not None:
            target.setStyleSheet(qss)
        if self.target_window is not None:
            self.target_window.setStyleSheet(qss)


class ThemeSelectorBar(QWidget):
    """Compact toolbar widget to switch INI theme presets or reload themes/theme.ini live."""
    def __init__(self, theme_mgr):
        super().__init__()
        self.theme_mgr = theme_mgr
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        lay.addWidget(QLabel("Theme:"))
        self.combo = QComboBox()
        self.combo.addItems(self.theme_mgr.list_presets())
        self.combo.setCurrentText(self.theme_mgr.get_active_preset())
        self.combo.currentTextChanged.connect(self.theme_mgr.set_preset)
        lay.addWidget(self.combo)

        btn_reload = QPushButton("Reload INI")
        btn_reload.setToolTip("Reload themes/theme.ini after editing colors or custom QSS")
        btn_reload.clicked.connect(self._reload)
        lay.addWidget(btn_reload)

    def _reload(self):
        self.theme_mgr._ensure_ini()
        self.theme_mgr.cfg.read(self.theme_mgr.ini_path, encoding="utf-8")
        self.theme_mgr.apply()
