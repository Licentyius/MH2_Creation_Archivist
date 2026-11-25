"""
MakeHuman 2 Vault Downloader V1.1
Contributed to the MH2 Community by Elvaerwyn_MH2 2026
"""

import os
import json
import shutil
import zipfile
import tempfile
import subprocess
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QIcon


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel,
    QListWidget, QListWidgetItem, QComboBox, QGroupBox, QMessageBox,
    QFileDialog, QSplitter, QTextEdit, QProgressBar, QTabBar, QTabWidget
)
from mh2_3d_viewer import MH2Mesh3DInspector
from mh2_standalone_core import StandaloneThumb, get_windows_mh2_userdata
from mh2_standalone_core import StandaloneThumb, get_windows_mh2_userdata, PanZoomImageViewer


def _fetch_bytes(url, timeout=25):
    clean_url = str(url).strip()
    cmd = [
        "curl", "-sSL", "--fail",
        "--connect-timeout", "6",
        "--max-time", str(timeout),
        "-H", "User-Agent: Mozilla/5.0 MH2_Studio/1.0",
        clean_url
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run(cmd, capture_output=True, creationflags=flags)
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout
    err = proc.stderr.decode("utf-8", errors="ignore").strip()
    raise RuntimeError(f"Fetch failed: {err or clean_url}")

class VaultListSyncWorker(QThread):
    progress = Signal(int, str)
    done = Signal(bool, str)

    def __init__(self, asset_dest, pack_dest):
        super().__init__()
        self.asset_dest = asset_dest
        self.pack_dest = pack_dest

    def run(self):
        host_api = "https://api." + "github.com"
        host_raw = "https://raw." + "githubusercontent.com"
        repo = "Makehuman-2/MH2_Legacy_Vault"
        api_url = f"{host_api}/repos/{repo}/contents"
        raw_base = f"{host_raw}/{repo}/main/"

        try:
            self.progress.emit(15, "Querying MH2_Legacy_Vault...")
            listing = json.loads(_fetch_bytes(api_url, timeout=20).decode("utf-8"))
            json_files = [
                item["name"] for item in listing
                if isinstance(item, dict) and item.get("name", "").lower().endswith(".json")
            ]
            if not json_files:
                self.done.emit(False, "No .json manifests found in MH2_Legacy_Vault.")
                return

            pack_file = next((f for f in json_files if "pack" in f.lower()), None)
            asset_file = next((f for f in json_files if "pack" not in f.lower()), json_files[0])

            downloaded = []
            if asset_file:
                self.progress.emit(45, f"Downloading {asset_file}...")
                os.makedirs(os.path.dirname(self.asset_dest), exist_ok=True)
                with open(self.asset_dest, "wb") as f:
                    f.write(_fetch_bytes(raw_base + asset_file, timeout=25))
                downloaded.append(asset_file)

            if pack_file:
                self.progress.emit(80, f"Downloading {pack_file}...")
                os.makedirs(os.path.dirname(self.pack_dest), exist_ok=True)
                with open(self.pack_dest, "wb") as f:
                    f.write(_fetch_bytes(raw_base + pack_file, timeout=25))
                downloaded.append(pack_file)

            self.progress.emit(100, "Done!")
            self.done.emit(True, f"Synced: {', '.join(downloaded)}")
        except Exception as e:
            self.done.emit(False, f"Manifest sync error: {e}")


class VaultBatchCartWorker(QThread):
    progress = Signal(int, str)
    done = Signal(bool, str)

    def __init__(self, cart_items, user_data_dir, mesh_base):
        super().__init__()
        self.cart_items = cart_items
        self.user_data_dir = user_data_dir
        self.mesh_base = mesh_base

    def run(self):
        from auto_mhmat_fixer2 import convert_mhmat_to_pbr

        host_raw = "https://raw." + "githubusercontent.com"
        raw_base = f"{host_raw}/Makehuman-2/MH2_Legacy_Vault/main/"
        total = max(len(self.cart_items), 1)
        scaler = StandaloneThumb()
        type_folders = {
            "clothing": "clothes", "clothes": "clothes",
            "skin": "skins", "skins": "skins",
            "expression": "expressions", "expressions": "expressions",
            "pose": "poses", "poses": "poses",
            "rig": "rigs", "rigs": "rigs",
            "model": "models", "models": "models",
        }
        installed = 0
        for idx, item in enumerate(self.cart_items):
            title = item.get("title", "asset")
            mtype = str(item.get("type", "clothes")).lower()
            folder_cat = type_folders.get(mtype, mtype)
            safe_name = "".join(c if (c.isalnum() or c in "_-") else "_" for c in title).strip("_").lower() or "asset"
            dest_dir = os.path.join(self.user_data_dir, folder_cat, self.mesh_base, safe_name)
            os.makedirs(dest_dir, exist_ok=True)

            files_map = item.get("files", {})
            urls = list(files_map.values()) if isinstance(files_map, dict) else list(files_map)
            self.progress.emit(int((idx / total) * 100), f"Downloading [{idx + 1}/{total}]: {title}")

            for f_url in urls:
                if not isinstance(f_url, str) or not f_url.strip():
                    continue
                full_url = f_url.strip()
                if not full_url.startswith("http"):
                    full_url = raw_base + full_url.lstrip("/")

                clean_f, _, _ = full_url.partition("?")
                fname = os.path.basename(clean_f)
                if not fname:
                    continue

                out_path = os.path.join(dest_dir, fname)
                try:
                    raw = _fetch_bytes(full_url, timeout=25)
                    with open(out_path, "wb") as f:
                        f.write(raw)
                    if out_path.lower().endswith(".thumb"):
                        scaler.rescale(out_path)
                    elif out_path.lower().endswith(".mhmat"):
                        convert_mhmat_to_pbr(out_path)
                except Exception:
                    pass
            installed += 1

        self.progress.emit(100, "Cart complete!")
        self.done.emit(True, f"Installed {installed} asset(s) into {self.mesh_base}!")

class DirectZipInstallWorker(QThread):
    progress = Signal(int, str)
    done = Signal(bool, str)

    def __init__(self, source_url_or_path, user_data_dir, mesh_base):
        super().__init__()
        self.src = source_url_or_path.strip()
        self.user_data_dir = user_data_dir
        self.mesh_base = mesh_base

    def run(self):
        temp_dir = tempfile.mkdtemp(prefix="mh2_zip_install_")
        zip_path = self.src
        try:
            if self.src.lower().startswith(("http://", "https://")):
                self.progress.emit(15, f"Downloading {os.path.basename(self.src)}...")
                zip_path = os.path.join(temp_dir, "downloaded_pack.zip")
                with open(zip_path, "wb") as f:
                    f.write(_fetch_bytes(self.src, timeout=45))

            if not os.path.exists(zip_path):
                self.done.emit(False, f"ZIP not found: {zip_path}")
                return

            self.progress.emit(60, "Extracting & sorting files...")
            extract_dir = os.path.join(temp_dir, "unpacked")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            known_roots = {
                "clothes", "hair", "eyes", "eyebrows", "eyelashes", "teeth",
                "tongue", "skins", "target", "proxy", "poses", "expressions",
                "animations", "rigs", "props", "models", "themes", "shaders"
            }
            copied = 0
            for root, _, files in os.walk(extract_dir):
                if not files:
                    continue
                rel = os.path.relpath(root, extract_dir).replace("\\", "/")
                parts = [p for p in rel.split("/") if p and p != "."]
                cat = next((p.lower() for p in parts if p.lower() in known_roots), "clothes")
                sub_name = parts[-1] if parts and parts[-1].lower() not in known_roots else "imported_pack"
                if cat in ("models", "themes"):
                    target_dir = os.path.join(self.user_data_dir, cat)
                else:
                    target_dir = os.path.join(self.user_data_dir, cat, self.mesh_base, sub_name)
                os.makedirs(target_dir, exist_ok=True)
                for fn in files:
                    shutil.copy2(os.path.join(root, fn), os.path.join(target_dir, fn))
                    copied += 1

            shutil.rmtree(temp_dir, ignore_errors=True)
            self.progress.emit(100, "Extraction complete!")
            self.done.emit(True, f"Extracted {copied} files into {self.mesh_base}!")
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.done.emit(False, f"ZIP install failed: {e}")


class _SingleThumbWorker(QThread):
    loaded = Signal(str, str)

    def __init__(self, key, url, dest):
        super().__init__()
        self.key = key
        self.url = url
        self.dest = dest

    def run(self):
        try:
            raw = _fetch_bytes(self.url, timeout=15)
            os.makedirs(os.path.dirname(self.dest), exist_ok=True)
            with open(self.dest, "wb") as f:
                f.write(raw)
            self.loaded.emit(self.key, self.dest)
        except Exception:
            pass
class MH2VaultDownloaderTab(QWidget):
    """3-Column Vault Downloader matching MHSelectAssetWindow."""
    CATEGORY_TABS = [
        ("All", set()),
        ("Clothes", {"clothes", "clothing"}),
        ("Hair", {"hair"}),
        ("Eyes", {"eye", "eyes"}),
        ("Eyebrows", {"eyebrow", "eyebrows"}),
        ("Eyelashes", {"eyelash", "eyelashes"}),
        ("Teeth", {"teeth"}),
        ("Tongue", {"tongue"}),
        ("Skins", {"skin", "skins"}),
        ("Target", {"target", "targets"}),
        ("Proxy", {"proxy", "proxymeshes"}),
        ("Poses", {"pose", "poses"}),
        ("Expressions", {"expression", "expressions"}),
        ("Rigs", {"rig", "rigs"}),
        ("Props", {"prop", "props"}),
        ("Models", {"model", "models"}),
        ("Materials", {"material", "materials"}),
    ]

    def __init__(self, mh_glob):
        super().__init__()
        self.mh_glob = mh_glob
        self.assets_dict = {}
        self.cart_items = []
        self.favorites = {}
        self._active_key = None
        self._active_rec = None
        self._thumb_workers = []
        self._load_favorites()
        self._init_ui()
        self._load_cached_lists()

    def _list_paths(self):
        base = os.path.join(self.mh_glob.env.path_userdata, "downloads", self.mh_glob.env.basename)
        return os.path.join(base, "assets.json"), os.path.join(base, "assetpacks.json")

    def _fav_path(self):
        return os.path.join(self.mh_glob.env.path_userdata, "downloads", "mh2_vault_favorites.json")

    def _render_dir(self):
        d = os.path.join(self.mh_glob.env.path_userdata, "downloads", self.mh_glob.env.basename, "render")
        os.makedirs(d, exist_ok=True)
        return d

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        top_bar = QHBoxLayout()
        self.btn_sync = QPushButton("Sync Legacy Vault Lists")
        self.btn_sync.setStyleSheet("font-weight: bold; padding: 4px 10px;")
        self.btn_sync.clicked.connect(self._sync_lists)
        top_bar.addWidget(self.btn_sync)

        self.btn_set_data = QPushButton("Set MH2 Data Folder...")
        self.btn_set_data.clicked.connect(self._pick_data_folder)
        top_bar.addWidget(self.btn_set_data)

        self.lbl_data_path = QLabel(f"Data: {self.mh_glob.env.path_userdata}")
        self.lbl_data_path.setStyleSheet("color: #999999; font-size: 11px;")
        top_bar.addWidget(self.lbl_data_path, 1)
        root.addLayout(top_bar)

        self.cat_tabs = QTabBar()
        self.cat_tabs.setExpanding(False)
        self.cat_tabs.setUsesScrollButtons(True)
        for label, _ in self.CATEGORY_TABS:
            self.cat_tabs.addTab(label)
        self.cat_tabs.currentChanged.connect(lambda _: self._refresh_list_view())
        root.addWidget(self.cat_tabs)

        splitter = QSplitter(Qt.Horizontal)

        col1 = QWidget()
        c1_lay = QVBoxLayout(col1)
        c1_lay.setContentsMargins(0, 0, 2, 0)
        self.asset_list = QListWidget()
        self.asset_list.currentItemChanged.connect(self._on_asset_selected)
        c1_lay.addWidget(self.asset_list, 1)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search name, author, or tag...")
        self.search_box.textChanged.connect(self._refresh_list_view)
        filter_row.addWidget(self.search_box, 1)
        c1_lay.addLayout(filter_row)
        splitter.addWidget(col1)

        col2 = QGroupBox("Selected Asset")
        c2_lay = QVBoxLayout(col2)

        self.preview_tabs = QTabWidget()
        self.thumb_preview = PanZoomImageViewer("Select an asset from the list\n(Wheel = Zoom • Drag = Pan • Double-Click = Reset)", min_height=180)
        self.preview_tabs.addTab(self.thumb_preview, "2D Thumbnail")

        self.thumb_preview.setMinimumHeight(180)
        self.thumb_preview.setAlignment(Qt.AlignCenter)
        self.thumb_preview.setStyleSheet("background-color: #161616; color: #888888; border: 1px solid #3A3A3A;")
        self.preview_tabs.addTab(self.thumb_preview, "2D Thumbnail")

        self.vault_3d = MH2Mesh3DInspector()
        self.preview_tabs.addTab(self.vault_3d, "3D & Multi-View")
        c2_lay.addWidget(self.preview_tabs, 2)

        self.detail_box = QTextEdit()
        self.detail_box.setReadOnly(True)
        self.detail_box.setMaximumHeight(150)
        c2_lay.addWidget(self.detail_box, 1)

        c2_btns = QHBoxLayout()
        self.btn_single_dl = QPushButton("Single Download")
        self.btn_single_dl.setStyleSheet("font-weight: bold; padding: 5px;")
        self.btn_single_dl.setEnabled(False)
        self.btn_single_dl.clicked.connect(self._single_download_selected)
        c2_btns.addWidget(self.btn_single_dl, 1)

        self.btn_bookmark = QPushButton("★ Bookmark")
        self.btn_bookmark.setEnabled(False)
        self.btn_bookmark.clicked.connect(self._toggle_bookmark)
        c2_btns.addWidget(self.btn_bookmark)
        c2_lay.addLayout(c2_btns)
        splitter.addWidget(col2)

        col3 = QWidget()
        c3_lay = QVBoxLayout(col3)
        c3_lay.setContentsMargins(2, 0, 0, 0)

        fav_grp = QGroupBox("Favorites / Bookmarks")
        f_lay = QVBoxLayout(fav_grp)
        self.fav_list = QListWidget()
        self.fav_list.currentItemChanged.connect(self._on_fav_selected)
        self.fav_list.setIconSize(QSize(54, 54))

        f_lay.addWidget(self.fav_list, 1)

        fav_btns = QHBoxLayout()
        btn_fav_to_cart = QPushButton("+ Add to Cart")
        btn_fav_to_cart.clicked.connect(self._fav_to_cart)
        btn_fav_del = QPushButton("Remove")
        btn_fav_del.clicked.connect(self._remove_fav)
        fav_btns.addWidget(btn_fav_to_cart)
        fav_btns.addWidget(btn_fav_del)
        f_lay.addLayout(fav_btns)
        c3_lay.addWidget(fav_grp, 1)

        cart_grp = QGroupBox("Batch Asset Cart")
        ct_lay = QVBoxLayout(cart_grp)
        btn_add_cart = QPushButton("+ Add Selected Asset to Cart")
        btn_add_cart.clicked.connect(self._add_selected_to_cart)
        ct_lay.addWidget(btn_add_cart)

        self.cart_list = QListWidget()
        self.cart_list.setIconSize(QSize(54, 54))
        ct_lay.addWidget(self.cart_list, 1)

        cart_btns = QHBoxLayout()
        btn_rm = QPushButton("Remove")
        btn_rm.clicked.connect(self._remove_cart_item)
        btn_clr = QPushButton("Clear")
        btn_clr.clicked.connect(self._clear_cart)
        cart_btns.addWidget(btn_rm)
        cart_btns.addWidget(btn_clr)
        ct_lay.addLayout(cart_btns)

        self.btn_checkout = QPushButton("Download All in Cart (0)")
        self.btn_checkout.setStyleSheet("font-weight: bold; padding: 5px;")
        self.btn_checkout.setEnabled(False)
        self.btn_checkout.clicked.connect(self._checkout_cart)
        ct_lay.addWidget(self.btn_checkout)
        c3_lay.addWidget(cart_grp, 1)

        splitter.addWidget(col3)
        splitter.setSizes([310, 460, 310])
        root.addWidget(splitter, 1)

        pack_grp = QGroupBox("Asset Pack URL / Local ZIP Extractor")
        p_lay = QHBoxLayout(pack_grp)
        self.pack_combo = QComboBox()
        self.pack_combo.currentIndexChanged.connect(self._on_pack_chosen)
        p_lay.addWidget(self.pack_combo, 1)

        self.zip_input = QLineEdit()
        self.zip_input.setPlaceholderText("GitHub/Patreon .zip URL or local .zip...")
        p_lay.addWidget(self.zip_input, 1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_local_zip)
        p_lay.addWidget(btn_browse)

        self.btn_install_zip = QPushButton("Download & Extract ZIP")
        self.btn_install_zip.setStyleSheet("font-weight: bold;")
        self.btn_install_zip.clicked.connect(self._install_zip)
        p_lay.addWidget(self.btn_install_zip)
        root.addWidget(pack_grp)

        self.prog_bar = QProgressBar()
        self.prog_bar.setVisible(False)
        root.addWidget(self.prog_bar)
    def _pick_data_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select MakeHuman 2 Data Folder", self.mh_glob.env.path_userdata
        )
        if not folder:
            return
        new_path = get_windows_mh2_userdata(folder)
        self.mh_glob.env.path_userdata = new_path
        self.lbl_data_path.setText(f"Data: {new_path}")
        self._load_cached_lists()

    def _load_favorites(self):
        fpath = self._fav_path()
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    self.favorites = json.load(f)
            except Exception:
                self.favorites = {}

    def _save_favorites(self):
        try:
            fpath = self._fav_path()
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(self.favorites, f, indent=4)
        except Exception:
            pass

    def _get_record_icon(self, key, rec, auto_fetch=True):
        from PySide6.QtGui import QIcon
        if not isinstance(rec, dict):
         return QIcon()
        title = str(rec.get("title", key))
        files = rec.get("files") if isinstance(rec.get("files"), dict) else {}
        thumb_url = str(files.get("thumb", rec.get("thumb", ""))).strip()
        clean_url, _, _ = thumb_url.partition("?")
        clean_name = os.path.basename(clean_url) if clean_url else ""

        rdir = self._render_dir()
        safe_title = "".join(c if (c.isalnum() or c in "_-.") else "_" for c in title)
        candidates = [
         os.path.join(rdir, f"{safe_title}.thumb"),
         os.path.join(rdir, f"{key}.thumb"),
         os.path.join(rdir, f"{key}.png"),
        ]
        if clean_name:
         candidates.insert(0, os.path.join(rdir, clean_name))

        for path in candidates:
         if os.path.exists(path) and os.path.getsize(path) > 0:
             pix = QPixmap(path)
             if not pix.isNull():
                 return QIcon(pix.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        if auto_fetch and thumb_url and thumb_url.startswith("http") and clean_name:
         dest = os.path.join(rdir, clean_name)
         worker = _SingleThumbWorker(key, thumb_url, dest)
         worker.loaded.connect(lambda _k, _p: self._refresh_fav_list())
         self._thumb_workers.append(worker)
         worker.finished.connect(lambda w=worker: self._thumb_workers.remove(w) if w in self._thumb_workers else None)
         worker.start()
        return QIcon()

    def _refresh_fav_list(self):
     self.fav_list.clear()
     for k, rec in self.favorites.items():
         title = rec.get("title", k) if isinstance(rec, dict) else str(k)
         icon = self._get_record_icon(k, rec, auto_fetch=True)
         item = QListWidgetItem(icon, "")
         item.setSizeHint(QSize(0, 42))
         item.setData(Qt.UserRole, (k, rec))
         self.fav_list.addItem(item)

         row_lbl = QLabel(
             f"<span style='color:#f69038; font-size:17px;'>&#9733;</span> "
             f"<span style='color:#FFFFFF; font-weight:bold;'>{title}</span>"
         )
         row_lbl.setStyleSheet("background: transparent; padding-left: 2px;")
         row_lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
         self.fav_list.setItemWidget(item, row_lbl)


    def _load_cached_lists(self):
        a_path, p_path = self._list_paths()
        self.assets_dict = {}
        if os.path.exists(a_path):
            try:
                with open(a_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    for idx, item in enumerate(raw):
                        if isinstance(item, dict):
                            k = str(item.get("id", item.get("title", idx)))
                            self.assets_dict[k] = item
                elif isinstance(raw, dict):
                    self.assets_dict = raw
            except Exception:
                pass

        self.pack_combo.blockSignals(True)
        self.pack_combo.clear()
        self.pack_combo.addItem("-- Select Legacy Vault Asset Pack --", "")
        if os.path.exists(p_path):
            try:
                with open(p_path, "r", encoding="utf-8") as f:
                    raw_p = json.load(f)
                packs = raw_p.get("packs", raw_p) if isinstance(raw_p, dict) else {}
                for key, info in packs.items():
                    if isinstance(info, dict) and info.get("url"):
                        label = f"{info.get('descr', key)} ({info.get('license', 'CC0')})"
                        self.pack_combo.addItem(label, info["url"])
            except Exception:
                pass
        self.pack_combo.blockSignals(False)
        self._refresh_fav_list()
        self._refresh_list_view()

    def _refresh_list_view(self):
        q = self.search_box.text().strip().lower()
        tab_idx = max(0, self.cat_tabs.currentIndex())
        tab_label, allowed_slugs = self.CATEGORY_TABS[tab_idx]
        active_mesh = str(self.mh_glob.env.basename).lower()

        self.asset_list.clear()
        for key, rec in self.assets_dict.items():
            if not isinstance(rec, dict):
                continue

            rec_base = str(rec.get("base", rec.get("basemesh", ""))).lower().strip()
            if rec_base and rec_base not in ("*", "common", active_mesh):
                if not (active_mesh == "fantasy" and rec_base == "hm08"):
                    continue

            title = str(rec.get("title", rec.get("name", key)))
            atype = str(rec.get("type", "")).lower().strip()
            subtype = str(rec.get("subtype", rec.get("category", ""))).lower().strip()
            folder_hint = str(rec.get("folder", "")).lower().strip()
            author = str(rec.get("author", rec.get("username", ""))).lower()

            # Combine type + subtype + folder tokens so Hair/Eyes/Eyebrows/Eyelashes/Teeth/Tongue match
            tokens = {t for t in (atype, subtype) if t}
            for part in folder_hint.replace("\\", "/").split("/"):
                if part:
                    tokens.add(part)

            if allowed_slugs:
                if not (tokens & allowed_slugs):
                    continue
                # Prevent Hair/Eyes/Eyebrows/Eyelashes/Teeth/Tongue from flooding the Clothes tab when type=="clothes"
                if tab_label == "Clothes" and (tokens & {"hair", "eye", "eyes", "eyebrow", "eyebrows", "eyelash", "eyelashes", "teeth", "tongue"}):
                    continue

            if q and (q not in title.lower() and q not in author and not any(q in t for t in tokens)):
                continue

            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, (key, rec))
            self.asset_list.addItem(item)

    def _on_asset_selected(self, current, _prev):
        if not current:
            self.btn_single_dl.setEnabled(False)
            self.btn_bookmark.setEnabled(False)
            self._active_key = None
            self._active_rec = None
            return
        key, rec = current.data(Qt.UserRole)
        self._inspect_record(key, rec)

    def _on_fav_selected(self, current, _prev):
        if not current:
            return
        key, rec = current.data(Qt.UserRole)
        if isinstance(rec, dict):
            self._inspect_record(key, rec)

    def _inspect_record(self, key, rec):
        self._active_key = key
        self._active_rec = rec
        self.btn_single_dl.setEnabled(True)
        self.btn_bookmark.setEnabled(True)
        self.btn_bookmark.setText("★ Bookmarked" if key in self.favorites else "☆ Bookmark")

        lines = [
            f"Title:    {rec.get('title', key)}",
            f"Type:     {rec.get('type', 'N/A')}",
            f"Author:   {rec.get('author', 'Unknown')}",
            f"License:  {rec.get('license', 'CC0 / CC-BY')}",
            f"Created:  {rec.get('created', 'N/A')}",
            f"\n{rec.get('description', rec.get('descr', 'No description.'))}"
        ]
        self.detail_box.setPlainText("\n".join(lines))
        self._show_or_fetch_thumb(key, rec)
        self._load_3d_for_record(rec)

    def _load_3d_for_record(self, rec):
        files = rec.get("files") if isinstance(rec.get("files"), dict) else {}
        file_urls = [v.strip() for v in files.values() if isinstance(v, str) and v.strip()]

        host = ".".join(["raw", "githubusercontent", "com"])
        repo_base = "/".join(["https:/", host, "Makehuman-2", "MH2_Legacy_Vault", "main", ""])

        def _abs_url(u):
            return u if u.startswith("http") else (repo_base + u.lstrip("/"))

        obj_url = None
        for u in file_urls:
            clean_u, _, _ = u.partition("?")
            if clean_u.lower().endswith(".obj"):
                obj_url = _abs_url(u)
                break

        if not obj_url:
            for u in file_urls:
                clean_u, _, q_part = u.partition("?")
                if clean_u.lower().endswith((".mhclo", ".proxy")):
                    root_path, _ = os.path.splitext(clean_u)
                    obj_url = _abs_url(root_path + ".obj" + (f"?{q_part}" if q_part else ""))
                    break

        # Find .mhmat URL in rec["files"] (or derive from .mhclo/.obj URL)
        mat_url = None
        for u in file_urls:
            clean_u, _, _ = u.partition("?")
            if clean_u.lower().endswith(".mhmat"):
                mat_url = _abs_url(u)
                break
        if not mat_url and obj_url:
            clean_o, _, q_part = obj_url.partition("?")
            root_o, _ = os.path.splitext(clean_o)
            mat_url = root_o + ".mhmat" + (f"?{q_part}" if q_part else "")

        all_abs_urls = [_abs_url(u) for u in file_urls]
        if obj_url:
            self.vault_3d.load_from_url(obj_url, mat_url=mat_url, extra_urls=all_abs_urls)
        else:
            self.vault_3d._clear_meshes("No .obj or .mhclo mesh listed for this asset.")


    def _show_or_fetch_thumb(self, key, rec):
        title = str(rec.get("title", key))
        files = rec.get("files") if isinstance(rec.get("files"), dict) else {}
        thumb_url = str(files.get("thumb", rec.get("thumb", ""))).strip()
        clean_url, _, _ = thumb_url.partition("?")
        clean_name = os.path.basename(clean_url) if clean_url else ""

        rdir = self._render_dir()
        safe_title = "".join(c if (c.isalnum() or c in "_-.") else "_" for c in title)
        candidates = [
            os.path.join(rdir, f"{safe_title}.thumb"),
            os.path.join(rdir, f"{key}.thumb"),
            os.path.join(rdir, f"{key}.png"),
        ]
        if clean_name:
            candidates.insert(0, os.path.join(rdir, clean_name))

        for path in candidates:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                pix = QPixmap(path)
                if not pix.isNull():
                    self.thumb_preview.setPixmap(pix.scaled(220, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    return

        if thumb_url and thumb_url.startswith("http") and clean_name:
            self.thumb_preview.clear()
            self.thumb_preview.setText("Loading thumbnail...")
            dest = os.path.join(rdir, clean_name)
            worker = _SingleThumbWorker(key, thumb_url, dest)
            worker.loaded.connect(self._on_thumb_ready)
            self._thumb_workers.append(worker)
            worker.finished.connect(lambda: self._thumb_workers.remove(worker) if worker in self._thumb_workers else None)
            worker.start()
        else:
            self.thumb_preview.clear()
            self.thumb_preview.setText("No thumbnail preview available")


    def _on_thumb_ready(self, key, path):
        if key == self._active_key and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self.thumb_preview.setPixmap(pix.scaled(220, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _toggle_bookmark(self):
        if not self._active_key or not self._active_rec:
            return
        if self._active_key in self.favorites:
            self.favorites.pop(self._active_key, None)
            self.btn_bookmark.setText("☆ Bookmark")
        else:
            self.favorites[self._active_key] = self._active_rec
            self.btn_bookmark.setText("★ Bookmarked")
        self._save_favorites()
        self._refresh_fav_list()

    def _fav_to_cart(self):
        cur = self.fav_list.currentItem()
        if not cur:
            return
        k, rec = cur.data(Qt.UserRole)
        if rec and rec not in self.cart_items:
            self.cart_items.append(rec)
            self.cart_list.addItem(QListWidgetItem(self._get_record_icon(k, rec), rec.get("title", "Asset")))
            self._sync_cart_btn()

    def _remove_fav(self):
        cur = self.fav_list.currentItem()
        if not cur:
            return
        k, _ = cur.data(Qt.UserRole)
        self.favorites.pop(k, None)
        self._save_favorites()
        self._refresh_fav_list()

    def _single_download_selected(self):
        if not self._active_rec:
            return
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.btn_single_dl.setEnabled(False)
        self.cart_worker = VaultBatchCartWorker(
            [self._active_rec], self.mh_glob.env.path_userdata, self.mh_glob.env.basename
        )
        self.cart_worker.progress.connect(lambda v, _: self.prog_bar.setValue(v))
        self.cart_worker.done.connect(self._on_single_done)
        self.cart_worker.start()

    def _on_single_done(self, ok, msg):
        self.prog_bar.setVisible(False)
        self.btn_single_dl.setEnabled(True)
        QMessageBox.information(self, "Single Download Complete", msg)


    def _add_selected_to_cart(self):
        if self._active_rec and self._active_rec not in self.cart_items:
            self.cart_items.append(self._active_rec)
            icon = self._get_record_icon(self._active_key, self._active_rec)
            self.cart_list.addItem(QListWidgetItem(icon, self._active_rec.get("title", "Asset")))
            self._sync_cart_btn()

    def _remove_cart_item(self):
        row = self.cart_list.currentRow()
        if 0 <= row < len(self.cart_items):
            self.cart_items.pop(row)
            self.cart_list.takeItem(row)
            self._sync_cart_btn()

    def _clear_cart(self):
        self.cart_items.clear()
        self.cart_list.clear()
        self._sync_cart_btn()

    def _sync_cart_btn(self):
        n = len(self.cart_items)
        self.btn_checkout.setText(f"Download All in Cart ({n})")
        self.btn_checkout.setEnabled(n > 0)

    def _sync_lists(self):
        a_path, p_path = self._list_paths()
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.sync_worker = VaultListSyncWorker(a_path, p_path)
        self.sync_worker.progress.connect(lambda v, _: self.prog_bar.setValue(v))
        self.sync_worker.done.connect(self._on_sync_done)
        self.sync_worker.start()

    def _on_sync_done(self, ok, msg):
        self.prog_bar.setVisible(False)
        if ok:
            self._load_cached_lists()
            QMessageBox.information(self, "Vault Synced", msg)
        else:
            QMessageBox.warning(self, "Sync Failed", msg)

    def _checkout_cart(self):
        if not self.cart_items:
            return
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.btn_checkout.setEnabled(False)
        self.cart_worker = VaultBatchCartWorker(
            list(self.cart_items), self.mh_glob.env.path_userdata, self.mh_glob.env.basename
        )
        self.cart_worker.progress.connect(lambda v, _: self.prog_bar.setValue(v))
        self.cart_worker.done.connect(self._on_cart_done)
        self.cart_worker.start()

    def _on_cart_done(self, ok, msg):
        self.prog_bar.setVisible(False)
        self._clear_cart()
        QMessageBox.information(self, "Batch Download Complete", msg)

    def _on_pack_chosen(self, idx):
        url = self.pack_combo.itemData(idx)
        if url:
            if not url.startswith("http"):
                host_raw = ".".join(["raw", "githubusercontent", "com"])
                url = f"https://{host_raw}/Makehuman-2/MH2_Legacy_Vault/main/" + url.lstrip("/")

            self.zip_input.setText(url)

    def _browse_local_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Asset Pack ZIP", "", "ZIP Archives (*.zip)")
        if path:
            self.zip_input.setText(path)

    def _install_zip(self):
        src = self.zip_input.text().strip()
        if not src:
            return
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.btn_install_zip.setEnabled(False)
        self.zip_worker = DirectZipInstallWorker(src, self.mh_glob.env.path_userdata, self.mh_glob.env.basename)
        self.zip_worker.progress.connect(lambda v, _: self.prog_bar.setValue(v))
        self.zip_worker.done.connect(self._on_zip_done)
        self.zip_worker.start()

    def _on_zip_done(self, ok, msg):
        self.prog_bar.setVisible(False)
        self.btn_install_zip.setEnabled(True)
        if ok:
            QMessageBox.information(self, "Install Complete", msg)
        else:
            QMessageBox.warning(self, "Install Error", msg)
