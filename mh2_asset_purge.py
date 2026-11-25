##############
#  Asset Inventory & Asset Purger V1.2 
#  Official Core Tool Module by Elvaerwyn_MH2 for MakeHuman 2 
#  changes for linux and baseclass dedicated behaviour  by punkduck
#  Changes to help windows return to previous behaviour
##############

import os
import gc
from send2trash import send2trash
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QListWidget, QMessageBox, QCheckBox, QDockWidget
)

class MH2AssetPurgerPanel():
    def __init__(self, mh_app, mh_glob, pluginname):
        self.mh_app = mh_app
        self.mh_glob = mh_glob
        self.pluginname = pluginname
        self.mainwindow = self.mh_glob.MainWindow
        self.repo = self.mh_glob.pluginRepo
        self.dock = None
        self.panel = None

        self.installed_assets_cache = {}
        self.categories = []

    class Panel(QWidget):
        def __init__(self, parent):
            super().__init__()

            self.setObjectName("MH2AssetPurgerPanel")
            layout = QVBoxLayout(self)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(6)
        
            title = QLabel("Asset Purger & Recycle Bin Unloader")
            title.setStyleSheet("font-weight: bold;")
            layout.addWidget(title)
        
            desc = QLabel("Select items below to safely move asset layers to your system Recycle Bin:")
            desc.setWordWrap(True)
            layout.addWidget(desc)
        
            self.cart_list_widget = QListWidget()
            self.cart_list_widget.setSelectionMode(QListWidget.MultiSelection)
            layout.addWidget(self.cart_list_widget)
        
            self.chk_force_detach = QCheckBox("Force drop items from active 3D view before wipe")
            self.chk_force_detach.setChecked(True)
            layout.addWidget(self.chk_force_detach)
        
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(6)
        
            self.btn_sync = QPushButton("🔄 Sync Inventory")
            self.btn_sync.clicked.connect(parent.sync_installed_to_cart)
            btn_layout.addWidget(self.btn_sync)
        
            self.btn_purge = QPushButton("🗑️ Move to Trash")
            self.btn_purge.clicked.connect(parent.execute_mass_purge_cart)
            btn_layout.addWidget(self.btn_purge)
        
            layout.addLayout(btn_layout)

    def sync_installed_to_cart(self):
        self.panel.cart_list_widget.clear()
        self.installed_assets_cache = {}

        env = self.mh_glob.env
        basename = env.basename
        
        # FIXED: Converts global basefolders to a local list instance to secure runtime execution
        self.categories = list(env.basefolders)
        self.categories.extend(["target", 'geometries', "skins", "poses", "props", "models"])

        user_data_dir = env.path_userdata

        for cat in self.categories:
            cat_path = os.path.normpath(os.path.join(user_data_dir, cat, basename)).replace("\\", "/")
            if not os.path.exists(cat_path):
                continue
                
            for root, _, files in os.walk(cat_path):
                for file in files:
                    if "manifest" in file.lower() or file.endswith((".json", ".log", ".pysync")):
                        continue

                    if file.lower().endswith(('.mhclo', '.mhbin', '.mhh', '.target', '.mhm', '.bvh', '.mhpose', '.mhskel')):
                        asset_name, ext = os.path.splitext(file)
                        full_path = os.path.normpath(os.path.join(root, file)).replace("\\", "/")

                        label = f"[{cat.upper()}]  {asset_name}"
                        if label not in self.installed_assets_cache:
                            self.installed_assets_cache[label] = {
                                'name': asset_name,
                                'category': cat,
                                'primary_file': full_path,
                                'parent_folder': os.path.normpath(root).replace("\\", "/")
                            }
                            self.panel.cart_list_widget.addItem(label)

        if self.panel.cart_list_widget.count() == 0:
            self.panel.cart_list_widget.addItem("No assets found in workspace directory.")
        else:
            self.panel.cart_list_widget.sortItems()

    def execute_mass_purge_cart(self):
        selected_rows = self.panel.cart_list_widget.selectedIndexes()
        
        if not selected_rows or (len(selected_rows) == 1 and self.panel.cart_list_widget.item(0).text().startswith("No assets")):
            QMessageBox.information(self.panel, "Selection Empty", "Please select items within the data listing matrix first.")
            return

        msg = QMessageBox(self.panel)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Send to Recycle Bin?")
        msg.setText(f"Move these {len(selected_rows)} asset package(s) to the Trash?")
        msg.setInformativeText("This will safely relocate the precise asset layers and empty custom subfolders. You can restore them from your Recycle Bin if needed.")
        
        yes_btn = msg.addButton(QMessageBox.Yes)
        no_btn = msg.addButton(QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.exec()
        
        if msg.clickedButton() == no_btn:
            return

        env = self.mh_glob.env
        purged_count = 0
        base_cls = self.mh_glob.baseClass

        for index in selected_rows:
            label = index.data()
            if label not in self.installed_assets_cache:
                continue

            asset_data = self.installed_assets_cache[label]
            primary_file = os.path.normpath(asset_data['primary_file']).replace("\\", "/")

            if self.panel.chk_force_detach.isChecked() and base_cls:
                base_cls.detachAssetByName(primary_file)

            parent_folder = os.path.normpath(asset_data['parent_folder']).replace("\\", "/")
            cat_root = os.path.normpath(os.path.join(env.path_userdata, asset_data['category'], env.basename)).replace("\\", "/")

            if primary_file.lower().endswith(('.mhclo', '.mhbin')) and parent_folder != cat_root:
                env.logLine(1, f"[mh2_asset_purge] Removing custom subfolder structure: {parent_folder}")
                send2trash(os.path.normpath(parent_folder))
                purged_count += 1
            else:

                target_name = asset_data['name'].lower() if env.osindex == 0 else asset_data['name']

                if os.path.exists(parent_folder):
                    for file in os.listdir(parent_folder):
                        file_path = os.path.normpath(os.path.join(parent_folder, file)).replace("\\", "/")
                        
                        if os.path.isdir(file_path):
                            continue 
                            
                        if "manifest" in file.lower() or file.endswith((".json", ".log")):
                            continue
                        
                        file_name_no_ext, _ = os.path.splitext(file)
                        if env.osindex == 0:
                            file_name_no_ext = file_name_no_ext.lower()

                        if file_name_no_ext == target_name:
                            env.logLine(1, f"[mh2_asset_purge] Moving asset layer to Recycle Bin: {file_path}")
                            send2trash(file_path)
                            purged_count += 1

        gc.collect()
        self.mh_glob.MainWindow.syncRepositories(True)
                    
        if self.mh_glob.openGLWindow:
            self.mh_glob.openGLWindow.update()

        self.sync_installed_to_cart()
        QMessageBox.information(self.panel, "Purge Complete", f"Successfully moved {purged_count} item files to your Recycle Bin/Trash.")

    def shutdown(self):
        if self.panel:
            self.panel.close()
            self.panel.deleteLater()
        if self.dock:
            self.mainwindow.removeDockWidget(self.dock)
            self.dock.close()
            self.dock.deleteLater()
        self.dock = None

    def initialize(self):
        if self.pluginname in self.repo:
            self.shutdown()

        self.dock = QDockWidget("Asset Inventory Purger", self.mainwindow)
        self.dock.setObjectName("mh2_asset_purger_dock_widget")
        self.dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.panel = self.Panel(self)
        self.dock.setWidget(self.panel)
        self.sync_installed_to_cart()

        if hasattr(self.mainwindow, "addDockWidget"):
            self.mainwindow.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        else:
            self.dock.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        self.dock.show()
        self.repo[self.pluginname] = self
        return True


def load_extension(app, glob):
    pluginname = os.path.abspath(__file__)
    plugin = MH2AssetPurgerPanel(app, glob, pluginname)
    return plugin.initialize()

def unload_extension(glob):
    pluginname = os.path.abspath(__file__)
    if pluginname in glob.pluginRepo:
        glob.pluginRepo[pluginname].shutdown()
        glob.pluginRepo.pop(pluginname)