"""
MakeHuman 2 Standalone Core Engine v1.2 (Does the same as downloads.py & core.importfiles)
Contributed to the MH2 Community by Elvaerwyn_MH2 2026 
"""
import os
import sys
import json
import shutil
import zipfile
import tempfile
import types
import webbrowser
from PySide6.QtGui import QImage


class StandaloneAssetPack:
    """Drop-in standalone replacement for MakeHuman 2's core.importfiles.AssetPack."""
    def __init__(self):
        self._temp_dirs = []

    def unZip(self, zip_path):
        if not os.path.exists(zip_path):
            return None, f"ZIP file not found: {zip_path}"
        try:
            temp_dir = tempfile.mkdtemp(prefix="mh2_unpack_")
            self._temp_dirs.append(temp_dir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)
            return temp_dir, None
        except Exception as e:
            return None, f"Failed to extract {os.path.basename(zip_path)}: {e}"

    def cleanupUnzip(self):
        while self._temp_dirs:
            d = self._temp_dirs.pop()
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)

    @staticmethod
    def titleToFileName(title):
        keep = [c if (c.isalnum() or c in ("_", "-")) else "_" for c in str(title)]
        return "".join(keep).strip("_").lower() or "asset"


class StandaloneThumb:
    """Drop-in standalone replacement for opengl.texture.MH_Thumb."""
    def rescale(self, image_path, size=128):
        if not os.path.exists(image_path):
            return
        img = QImage(image_path)
        if not img.isNull():
            scaled = img.scaled(size, size)
            scaled.save(image_path, "PNG")


def inject_standalone_mh2_shims():
    """
    Registers lightweight core.importfiles and opengl.texture modules in sys.modules
    so mh2_archive.py and mh2_creator.py run natively outside MakeHuman 2 on Windows.
    """
    if "core" not in sys.modules:
        core_mod = types.ModuleType("core")
        sys.modules["core"] = core_mod
    if "core.importfiles" not in sys.modules:
        imp_mod = types.ModuleType("core.importfiles")
        imp_mod.AssetPack = StandaloneAssetPack
        sys.modules["core.importfiles"] = imp_mod
        sys.modules["core"].importfiles = imp_mod

    if "opengl" not in sys.modules:
        gl_mod = types.ModuleType("opengl")
        sys.modules["opengl"] = gl_mod
    if "opengl.texture" not in sys.modules:
        tex_mod = types.ModuleType("opengl.texture")
        tex_mod.MH_Thumb = StandaloneThumb
        sys.modules["opengl.texture"] = tex_mod
        sys.modules["opengl"].texture = tex_mod


def get_app_folder():
    """Returns the folder where the standalone script or compiled .exe lives."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(os.path.abspath(__file__))


def get_windows_mh2_userdata(mode=None, custom_path=None):
    """
    Resolves the active storage root:
      - mode == 'portable': <app_folder>/mh2_studio_data
      - mode == 'mh2':      auto-detected MakeHuman 2 data folder
      - mode == 'custom':   user-selected folder
    """
    app_dir = get_app_folder()
    cfg_file = os.path.join(app_dir, "mh2_studio_config.json")
    portable_dir = os.path.join(app_dir, "mh2_studio_data")

    cfg = {}
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

    if mode:
        cfg["mode"] = mode
        if custom_path:
            cfg["custom_path"] = os.path.normpath(custom_path)
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)

    active_mode = cfg.get("mode", "portable")

    if active_mode == "portable":
        base = portable_dir
    elif active_mode == "custom" and cfg.get("custom_path"):
        base = cfg["custom_path"]
    else:
        # 1. Check saved mh2_path from previous selection if available
        if cfg.get("mh2_path") and os.path.isdir(cfg["mh2_path"]):
            base = cfg["mh2_path"]
        else:
            # 2. Search portable sibling folders, all drive roots for mh2/makehuman2/data, and Documents
            app_parent = os.path.dirname(app_dir)
            candidates = [
                os.path.join(app_dir, "data"),
                os.path.join(app_dir, "makehuman2", "data"),
                os.path.join(app_parent, "makehuman2", "data"),
                os.path.join(app_parent, "mh2", "makehuman2", "data"),
                os.path.join(app_parent, "data"),
                os.path.join(os.path.expanduser("~"), "Documents", "makehuman2", "data"),
            ]
            # Also scan other local drives (D:\ through Z:\) for common MH2 install paths
            for drive in "DEFGHIJKLMNOPQRSTUVWXYZ":
                d_root = f"{drive}:\\"
                if os.path.exists(d_root):
                    candidates.extend([
                        os.path.join(d_root, "mh2_suite", "mh2", "makehuman2", "data"),
                        os.path.join(d_root, "makehuman2", "data"),
                        os.path.join(d_root, "MakeHuman2", "data"),
                    ])
            base = next((c for c in candidates if os.path.isdir(c)), candidates[-1])
            cfg["mh2_path"] = base
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)

    subfolders = [
        "clothes", "hair", "eyes", "eyebrows", "eyelashes", "teeth", "tongue",
        "skins", "target", "proxy", "poses", "expressions", "animations",
        "rigs", "props", "models", "themes", "shaders", "downloads", "creator"
    ]
    for sub in subfolders:
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    return base

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QScrollArea, QLabel


class PanZoomImageViewer(QScrollArea):
    """Interactive 2D preview canvas: Mouse Wheel = Zoom, Left-Drag = Pan, Double-Click = Reset Fit."""
    def __init__(self, placeholder_text="No preview available", min_height=150):
        super().__init__()
        self._orig_pixmap = None
        self._zoom = 1.0
        self._drag_pos = None

        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(min_height)
        self.setStyleSheet("background-color: #151515; border: 1px solid #3A3A3A; border-radius: 4px;")

        self.img_label = QLabel(placeholder_text)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setWordWrap(True)
        self.img_label.setStyleSheet("color: #888888; background: transparent; border: none; padding: 8px;")
        self.setWidget(self.img_label)

    def setPixmap(self, pixmap):
        if pixmap and not pixmap.isNull():
            self._orig_pixmap = pixmap
            self._zoom = 1.0
            self.setCursor(Qt.OpenHandCursor)
            self._apply_zoom(fit_window=True)
        else:
            self.clear()

    def clear(self):
        self._orig_pixmap = None
        self._zoom = 1.0
        self.setCursor(Qt.ArrowCursor)
        self.img_label.clear()
        self.img_label.resize(max(self.viewport().width(), 160), max(self.viewport().height(), 120))

    def setText(self, text):
        self._orig_pixmap = None
        self.setCursor(Qt.ArrowCursor)
        self.img_label.setText(text)
        self.img_label.resize(max(self.viewport().width() - 8, 160), max(self.viewport().height() - 8, 120))

    def _apply_zoom(self, fit_window=False):
        if not self._orig_pixmap or self._orig_pixmap.isNull():
            return
        vw = max(self.viewport().width() - 10, 120)
        vh = max(self.viewport().height() - 10, 120)
        if fit_window:
            base_pix = self._orig_pixmap.scaled(vw, vh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._zoom = base_pix.width() / max(float(self._orig_pixmap.width()), 1.0)
        else:
            target_w = max(24, int(self._orig_pixmap.width() * self._zoom))
            target_h = max(24, int(self._orig_pixmap.height() * self._zoom))
            base_pix = self._orig_pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_label.setPixmap(base_pix)
        self.img_label.resize(base_pix.size())

    def wheelEvent(self, event):
        if self._orig_pixmap and not self._orig_pixmap.isNull():
            factor = 1.18 if event.angleDelta().y() > 0 else 0.84
            self._zoom = max(0.15, min(8.0, self._zoom * factor))
            self._apply_zoom(fit_window=False)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._orig_pixmap:
            self._drag_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            delta = event.position() - self._drag_pos
            self._drag_pos = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._drag_pos = None
            self.setCursor(Qt.OpenHandCursor if self._orig_pixmap else Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._orig_pixmap:
            self._apply_zoom(fit_window=True)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

import subprocess
import webbrowser


def open_external_link(url, new_window=True):
    """Opens a URL in a separate browser window on Windows, falling back to webbrowser."""
    clean = str(url).strip()
    if not clean:
        return
    if os.name == "nt" and new_window:
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
            ) as k:
                prog_id, _ = winreg.QueryValueEx(k, "ProgId")
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                rf"{prog_id}\shell\open\command"
            ) as cmd_k:
                raw_cmd, _ = winreg.QueryValueEx(cmd_k, "")
            exe = raw_cmd.split('"')[1] if raw_cmd.startswith('"') else raw_cmd.split()[0]
            if os.path.exists(exe):
                flag = "-new-window" if "firefox" in exe.lower() else "--new-window"
                subprocess.Popen([exe, flag, clean])
                return
        except Exception:
            pass
    webbrowser.open(clean, new=1 if new_window else 2)
