"""
MakeHuman 2 Studio_Suite.py (logic routing)
Contributed to the MH2 Community by Elvaerwyn_MH2 2026
"""

import os
import sys
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTabWidget, QGroupBox, QMessageBox, QScrollArea
)

from mh2_3d_viewer import MH2Mesh3DInspector
from mh2_archive import MH2AssetBrowserPanel, MH2AssetCard
from mh2_creator import MH2CreatorPortalPanel
from mh2_vault_downloader import MH2VaultDownloaderTab
from mh2_material_maker import MH2MaterialMakerTab
from mh2_asset_purge import MH2AssetPurgerPanel



class MH2UnifiedStudioWidget(QWidget):
    """
    Unifies MH2_Archive, MH2_Creator, and MH2Mesh3DInspector into one tabbed suite.
    Works inside gui/downloads.py AND inside mh2_studio_standalone.py.
    """
    def __init__(self, parent_widget, mh_glob, standalone=False):
        super().__init__(parent_widget)
        self.mh_glob = mh_glob
        self.standalone = standalone

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        # Quick-Access Official Links Bar (Strictly Makehuman-2 GitHub & Patreon)
        link_bar = QHBoxLayout()
        lbl = QLabel("Official MH2 Hubs:")
        lbl.setStyleSheet("font-weight: bold; color: #CCCCCC;")
        link_bar.addWidget(lbl)

        gh_org = "https://github.com/orgs/Makehuman-2/repositories"
        pt_page = "https://www.patreon.com/Makehuman2/posts/legacy-community-176209129"

        btn_gh = QPushButton("GitHub Repositories")
        btn_gh.setStyleSheet("padding: 3px 8px;")
        btn_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(gh_org)))
        link_bar.addWidget(btn_gh)

        btn_pt = QPushButton("Patreon Free Legacy Full Zips")
        btn_pt.setStyleSheet("padding: 3px 8px;")
        btn_pt.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(pt_page)))
        link_bar.addWidget(btn_pt)
        link_bar.addStretch()
        root.addLayout(link_bar)

        # Master 3-Tab Suite
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # ---------------------------------------------------------
        # TAB 1: Community Archive Browser + Integrated 3D Tab
        # ---------------------------------------------------------
        self.archive_panel = MH2AssetBrowserPanel(self, self.mh_glob)
        self.archive_3d = MH2Mesh3DInspector()
        self.archive_panel.inspect_tabs.insertTab(1, self.archive_3d, "3D & Multi-View")

        # Hook card inspection to also feed the 3D Multi-View Inspector
        orig_highlight = self.archive_panel.highlight_asset

        def _highlight_with_3d(card):
            orig_highlight(card)
            zname = card.key if card.key.endswith(".zip") else f"{card.key}.zip"
            zpath = os.path.join(self.archive_panel.local_install_destination, zname)
            if os.path.exists(zpath):
                self.archive_3d.load_from_zip(zpath)
                return

            # Stream the remote GitHub .zip directly into memory for instant 3D preview
            repo_path = self.archive_panel.get_current_repo_path()
            zip_url = card.data.get("url") or f"https://raw.githubusercontent.com/{repo_path}/main/{zname}"
            self.archive_3d.load_from_url(zip_url, label=zname)

        self.archive_panel.highlight_asset = _highlight_with_3d
        self.tabs.addTab(self.archive_panel, "Community Archive")


        # ---------------------------------------------------------
        # TAB 2: Creator Portal Studio + Integrated 3D Preview
        # ---------------------------------------------------------
        self.creator_ctrl = MH2CreatorPortalPanel(None, self.mh_glob, "mh2_creator_embedded")
        self.creator_panel = self.creator_ctrl.Panel(self.creator_ctrl)
        self.creator_ctrl.panel = self.creator_panel

        # Save and auto-load Creator identity inside the standalone program's own folder
        app_folder = os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, "frozen", False) else __file__))
        self.creator_ctrl.credentials_path = os.path.join(app_folder, "vault_pref.json").replace("\\", "/")

        if os.path.exists(self.creator_ctrl.credentials_path):
            try:
                import json
                with open(self.creator_ctrl.credentials_path, "r", encoding="utf-8") as f:
                    pref_data = json.load(f)
                saved_user = pref_data.get("remember_user", "")
                saved_tok = pref_data.get("saved_token", "")
                if saved_user:
                    self.creator_panel.user_input.setText(saved_user)
                if saved_tok:
                    self.creator_panel.pass_input.setText(saved_tok)
                    self.creator_panel.remember_checkbox.setChecked(True)
            except Exception:
                pass

        creator_container = QWidget()

        # TAB 2b: Legacy Vault Single-Asset & Batch Cart Downloader (downloads.py features)
        self.vault_downloader = MH2VaultDownloaderTab(self.mh_glob)
        self.tabs.addTab(self.vault_downloader, "Vault & Cart Downloader")

        self.material_maker = MH2MaterialMakerTab(self.mh_glob)
        self.tabs.addTab(self.material_maker, "Material Maker")
        # ---------------------------------------------------------
        # TAB 2c: Asset Inventory & Recycle Bin Purger
        # ---------------------------------------------------------
        self.purger_ctrl = MH2AssetPurgerPanel(None, self.mh_glob, "mh2_asset_purger_embedded")
        self.purger_panel = self.purger_ctrl.Panel(self.purger_ctrl)
        self.purger_ctrl.panel = self.purger_panel
        self.purger_ctrl.sync_installed_to_cart()
        self.tabs.addTab(self.purger_panel, "Asset Purger")


        creator_container = QWidget()
        c_layout = QVBoxLayout(creator_container)
        c_layout.setContentsMargins(2, 2, 2, 2)
        c_layout.addWidget(self.creator_panel, 2)

        self.creator_3d = MH2Mesh3DInspector()
        c_box = QGroupBox("3D & Multi-View Mesh Pre-Flight Check")
        cb_layout = QVBoxLayout(c_box)
        cb_layout.addWidget(self.creator_3d)
        c_layout.addWidget(c_box, 1)

        # Hook Creator folder sync to automatically load .obj into 3D Multi-View
        orig_refresh = self.creator_ctrl.refresh_local_file_index

        def _refresh_with_3d(path, manual_refresh=True, auto_detect=False):
            orig_refresh(path, manual_refresh=manual_refresh, auto_detect=auto_detect)
            if manual_refresh:
                self.creator_3d.load_from_folder(path)

        self.creator_ctrl.refresh_local_file_index = _refresh_with_3d

        creator_scroll = QScrollArea()
        creator_scroll.setWidgetResizable(True)
        creator_scroll.setWidget(creator_container)
        self.tabs.addTab(creator_scroll, "Creator Upload Studio")

        # ---------------------------------------------------------
        # TAB 3: Dedicated Full-Screen 3D & Multi-View Inspector
        # ---------------------------------------------------------
        self.standalone_3d = MH2Mesh3DInspector()
        t3_wrap = QWidget()
        t3_lay = QVBoxLayout(t3_wrap)
        t3_bar = QHBoxLayout()
        btn_load_folder = QPushButton("Open Local Folder (.obj)")
        btn_load_folder.clicked.connect(self._pick_3d_folder)
        btn_load_zip = QPushButton("Open Staged ZIP (.obj)")
        btn_load_zip.clicked.connect(self._pick_3d_zip)
        t3_bar.addWidget(btn_load_folder)
        t3_bar.addWidget(btn_load_zip)
        t3_bar.addStretch()
        t3_lay.addLayout(t3_bar)
        t3_lay.addWidget(self.standalone_3d, 1)
        self.tabs.addTab(t3_wrap, "3D Multi-View Inspector")

    def _pick_3d_folder(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "Select Folder Containing .obj Mesh")
        if d:
            self.standalone_3d.load_from_folder(d)

    def _pick_3d_zip(self):
        from PySide6.QtWidgets import QFileDialog
        f, _ = QFileDialog.getOpenFileName(
            self, "Select ZIP Archive", self.archive_panel.local_install_destination, "ZIP Archives (*.zip)"
        )
        if f:
            self.standalone_3d.load_from_zip(f)
