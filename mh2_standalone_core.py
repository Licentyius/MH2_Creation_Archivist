"""
MakeHuman 2 Standalone Core Engine (Does the same as downloads.py & core.importfiles)
Contributed to the MH2 Community by Elvaerwyn_MH2 2026 
"""
import os
import sys
import json
import shutil
import zipfile
import tempfile
import types
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

