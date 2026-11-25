"""
MakeHuman 2 Standalone Community Studio Suite (Archive + Creator + 3D Multi-View + Downloader Tools)
Hybrid of all of Elvs Creations built into one Suite. 
Contributed by Elvaerwyn_MH2 2026
"""

import os
import sys
import zipfile
import urllib.request
from PySide6.QtCore import Qt, QUrl, QThread, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QMessageBox, QProgressDialog, QFileDialog, QCheckBox
)


from mh2_standalone_core import (
    inject_standalone_mh2_shims,
    get_windows_mh2_userdata,
    get_app_folder,
    StandaloneThumb
)


# Inject standalone shims BEFORE importing mh2_archive / mh2_creator
inject_standalone_mh2_shims()

from mh2_studio_suite import MH2UnifiedStudioWidget
from mh2_vault_downloader import _fetch_bytes
from theme import MH2ThemeManager, ThemeSelectorBar


class _StandaloneEnv:
    def __init__(self):
        self.path_userdata = get_windows_mh2_userdata()
        self.basename = "hm08"
        self.auto_pbr = True

    def logLine(self, level, msg):
        print(f"[MH2 Studio] {msg}")


class _StandaloneMainWindow(QMainWindow):
    def syncRepositories(self):
        pass


class _StandaloneBaseClass:
    def __init__(self, mesh_name="hm08"):
        self.baseInfo = {
            "name": mesh_name,
            "parentmesh": "hm08" if mesh_name == "fantasy" else None
        }


class _StandaloneGlob:
    def __init__(self, main_win):
        self.env = _StandaloneEnv()
        self.baseClass = _StandaloneBaseClass(self.env.basename)
        self.MainWindow = main_win
        self.pluginRepo = {}
        self.openGLBlock = False
        self.lastdownload = ""

class BulkThumbSyncWorker(QThread):
    progress = Signal(int, str)
    finished_ok = Signal(bool, str)

    def __init__(self, render_dir):
        super().__init__()
        self.render_dir = render_dir

    def run(self):
        host = "https://" + "github.com"
        url = f"{host}/Makehuman-2/MH2_Legacy_Vault/releases/latest/download/library_thumbs.zip"
        os.makedirs(self.render_dir, exist_ok=True)
        zip_tmp = os.path.join(self.render_dir, "_thumbs_tmp.zip")
        try:
            self.progress.emit(10, "Downloading library_thumbs.zip from MH2_Legacy_Vault...")
            raw_zip = _fetch_bytes(url, timeout=60)
            with open(zip_tmp, "wb") as out:
                out.write(raw_zip)

            thumb_scaler = StandaloneThumb()
            with zipfile.ZipFile(zip_tmp, "r") as zf:
                members = [m for m in zf.namelist() if not m.endswith("/")]
                total = max(len(members), 1)
                for idx, member in enumerate(members):
                    fname = os.path.basename(member)
                    if not fname:
                        continue
                    if fname.lower().endswith(".png"):
                        fname = fname[:-4] + ".thumb"
                    elif not fname.lower().endswith(".thumb"):
                        fname = fname + ".thumb"
                    dest = os.path.join(self.render_dir, fname)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        dst.write(src.read())
                    thumb_scaler.rescale(dest)
                    if idx % 50 == 0:
                        self.progress.emit(15 + int((idx / total) * 85), f"Extracting ({idx}/{total})...")

            if os.path.exists(zip_tmp):
                os.remove(zip_tmp)
            self.finished_ok.emit(True, "Thumbnail cache synchronized from MH2_Legacy_Vault!")
        except Exception as e:
            if os.path.exists(zip_tmp):
                os.remove(zip_tmp)
            self.finished_ok.emit(False, f"Thumbnail sync failed: {e}")


class MH2StandaloneWindow(_StandaloneMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MakeHuman 2 — Standalone Asset Studio (Archive + Creator + 3D)")
        self.resize(1120, 840)
        self.mh_glob = _StandaloneGlob(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top Control & Official Links Bar
        top_bar = QHBoxLayout()
        title = QLabel("MakeHuman 2 Standalone Studio")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        top_bar.addWidget(title)

        top_bar.addWidget(QLabel("  Target Mesh:"))
        self.mesh_combo = QComboBox()
        self.mesh_combo.addItems(["hm08", "fantasy"])
        self.mesh_combo.setToolTip("Select target MakeHuman 2 base mesh folder for asset installation")
        self.mesh_combo.currentTextChanged.connect(self._on_mesh_changed)
        top_bar.addWidget(self.mesh_combo)

        top_bar.addWidget(QLabel("  Storage:"))
        self.storage_combo = QComboBox()
        self.storage_combo.addItems([
            "Portable (App Folder)",
            "MakeHuman 2 Data Folder",
            "Custom Folder..."
        ])
        cfg_path = os.path.join(get_app_folder(), "mh2_studio_config.json")
        if os.path.exists(cfg_path):
            try:
                import json
                with open(cfg_path, "r", encoding="utf-8") as f:
                    saved_mode = json.load(f).get("mode", "portable")
                idx_map = {"portable": 0, "mh2": 1, "custom": 2}
                self.storage_combo.setCurrentIndex(idx_map.get(saved_mode, 0))
            except Exception:
                pass
        self.storage_combo.currentIndexChanged.connect(self._on_storage_mode_changed)
        top_bar.addWidget(self.storage_combo)

        btn_sync_thumbs = QPushButton("Sync Legacy Thumbnails")
        btn_sync_thumbs.setToolTip("Download and cache library_thumbs.zip from Makehuman-2/MH2_Legacy_Vault")
        btn_sync_thumbs.clicked.connect(self._sync_thumbnails)
        top_bar.addWidget(btn_sync_thumbs)

        btn_open_data = QPushButton("Open MH2 Data Folder")
        btn_open_data.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.mh_glob.env.path_userdata))
        )
        top_bar.addWidget(btn_open_data)

        self.chk_global_pbr = QCheckBox("Auto-PBR (.mhmat)")
        self.chk_global_pbr.setChecked(True)
        self.chk_global_pbr.setToolTip("Automatically convert .mhmat files to MakeHuman 2 PBR on download/unpack")
        self.chk_global_pbr.toggled.connect(lambda state: setattr(self.mh_glob.env, "auto_pbr", state))
        top_bar.addWidget(self.chk_global_pbr)

        btn_pbr_folder = QPushButton("Convert Folder to PBR...")
        btn_pbr_folder.setToolTip("Batch-convert all .mhmat files inside a chosen folder to PBR")
        btn_pbr_folder.clicked.connect(self._convert_folder_to_pbr)
        top_bar.addWidget(btn_pbr_folder)

        top_bar.addStretch()

        gh_org_home = "https://github.com/Makehuman-2"
        pt_main_page = "https://www.patreon.com/cw/Makehuman2"

        btn_gh = QPushButton("MakeHuman 2 Org")
        btn_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(gh_org_home)))
        top_bar.addWidget(btn_gh)

        btn_pt = QPushButton("MakeHuman 2 Patreon")
        btn_pt.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(pt_main_page)))
        top_bar.addWidget(btn_pt)


        layout.addLayout(top_bar)

        # Unified Archive + Creator + 3D Multi-View Suite
        self.studio = MH2UnifiedStudioWidget(self, self.mh_glob, standalone=True)
        layout.addWidget(self.studio, 1)

        # 1. Initialize Theme Manager (creates <data>/themes/theme.ini) & add top-bar picker
        self.theme_mgr = MH2ThemeManager(self.mh_glob, self)
        self.theme_bar = ThemeSelectorBar(self.theme_mgr)
        top_bar.addWidget(self.theme_bar)
        self.theme_mgr.apply()

    def _on_mesh_changed(self, mesh_name):
        self.mh_glob.env.basename = mesh_name
        self.mh_glob.baseClass = _StandaloneBaseClass(mesh_name)
        self.studio.archive_panel.fetch_remote_manifest()
        if hasattr(self.studio, "vault_downloader"):
            self.studio.vault_downloader._load_cached_lists()

    def _convert_folder_to_pbr(self):
        from auto_mhmat_fixer2 import convert_folder_mhmats_to_pbr
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder to Convert .mhmat Files to PBR", self.mh_glob.env.path_userdata
        )
        if not folder:
            return
        converted, skipped, _ = convert_folder_mhmats_to_pbr(folder)
        QMessageBox.information(
            self,
            "PBR Material Converter",
            f"PBR Conversion Complete!\n\nConverted: {converted} .mhmat file(s)\nAlready PBR / Skipped: {skipped}"
        )

    def _on_storage_mode_changed(self, index):
        if index == 0:
            new_path = get_windows_mh2_userdata(mode="portable")
        elif index == 1:
            new_path = get_windows_mh2_userdata(mode="mh2")
        else:
            folder = QFileDialog.getExistingDirectory(
                self, "Select MakeHuman 2 Data Folder", self.mh_glob.env.path_userdata
            )
            if not folder:
                return
            new_path = get_windows_mh2_userdata(mode="custom", custom_path=folder)

        self.mh_glob.env.path_userdata = new_path

        # Update Archive Panel paths
        arch = self.studio.archive_panel
        arch.local_install_destination = os.path.join(new_path, "downloads", "staging").replace("\\", "/")
        arch.favorites_storage_file = os.path.normpath(os.path.join(new_path, "downloads", "mh2_archive_favorites.json"))
        arch.load_local_favorites_database()
        arch.fetch_remote_manifest()

        # Update Vault Downloader paths
        if hasattr(self.studio, "vault_downloader"):
            vd = self.studio.vault_downloader
            vd.lbl_data_path.setText(f"Data: {new_path}")
            vd._load_cached_lists()

        # Update Creator Staging folder (while keeping vault_pref.json pinned in app folder)
        cr = self.studio.creator_ctrl
        norm_new = new_path.replace("\\", "/")
        cr.creator_root_folder = f"{norm_new}/creator"
        os.makedirs(cr.creator_root_folder, exist_ok=True)
        self.studio.creator_panel.path_input.setText(cr.creator_root_folder)
        cr.refresh_local_file_index(cr.creator_root_folder, manual_refresh=True, auto_detect=True)

        # 2. Sync <new_path>/themes/theme.ini when storage mode changes
        self.theme_mgr._ensure_ini()
        self.theme_bar.combo.blockSignals(True)
        self.theme_bar.combo.clear()
        self.theme_bar.combo.addItems(self.theme_mgr.list_presets())
        self.theme_bar.combo.setCurrentText(self.theme_mgr.get_active_preset())
        self.theme_bar.combo.blockSignals(False)
        self.theme_mgr.apply()

    def _sync_thumbnails(self):
        render_dir = os.path.join(
            self.mh_glob.env.path_userdata, "downloads", self.mh_glob.env.basename, "render"
        )
        self.prog = QProgressDialog("Starting thumbnail sync...", None, 0, 100, self)
        self.prog.setWindowModality(Qt.WindowModal)
        self.prog.show()

        self.thumb_worker = BulkThumbSyncWorker(render_dir)
        self.thumb_worker.progress.connect(lambda val, txt: (self.prog.setValue(val), self.prog.setLabelText(txt)))
        self.thumb_worker.finished_ok.connect(self._on_thumbs_done)
        self.thumb_worker.start()

    def _on_thumbs_done(self, ok, msg):
        self.prog.close()
        if ok:
            QMessageBox.information(self, "Thumbnail Cache Ready", msg)
            self.studio.archive_panel.fetch_remote_manifest()
        else:
            QMessageBox.warning(self, "Sync Notice", msg)


if __name__ == "__main__":
    import traceback
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    try:
        win = MH2StandaloneWindow()
        # 3. Apply Steel Theme onto QApplication right before showing window
        win.theme_mgr.apply(app)
        win.show()
        sys.exit(app.exec())
    except Exception:
        err = traceback.format_exc()
        with open("crash_log.txt", "w", encoding="utf-8") as f:
            f.write(err)
        QMessageBox.critical(None, "Startup Error", err)
        sys.exit(1)
