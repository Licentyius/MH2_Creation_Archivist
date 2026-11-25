"""
MakeHuman 2 Creator Material_maker V1 by Elvaerwyn_MH2 2026
Adds material creation/exporting options to studio from the MH2 system established by Punk and Elv
"""


import os
import json
import shutil
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QColor, QImage
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QCheckBox, QScrollArea, QLineEdit, QMessageBox, QRadioButton,
    QFileDialog, QSlider, QComboBox, QListWidget, QListWidgetItem,
    QColorDialog, QSplitter
)
from mh2_3d_viewer import MH2MeshViewport, parse_obj_raw, normalize_verts


class StandaloneMHMaterial:
    TEX_KEYS = [
        "diffuseTexture", "normalmapTexture", "aomapTexture",
        "metallicRoughnessTexture", "emissiveTexture",
        "maskTexture", "sp_litsphereTexture"
    ]

    def __init__(self, userdata_dir=""):
        self.userdata_dir = userdata_dir
        self.mhmat_dir = ""
        self.filepath = ""
        self.name = "custom_material"
        self.description = "MakeHuman 2 PBR Material"
        self.tags = []
        self.reset_defaults()


    def reset_defaults(self):
        self.textures = {k: "" for k in self.TEX_KEYS}
        self.shader = "pbr"
        self.ambientColor = [1.0, 1.0, 1.0]
        self.diffuseColor = [1.0, 1.0, 1.0]
        self.specularColor = [0.5, 0.5, 0.5]
        self.emissiveColor = [0.0, 0.0, 0.0]
        self.colorationColor = [1.0, 1.0, 1.0]
        self.colorationMethod = 0
        self.metallicFactor = 0.0
        self.roughnessFactor = 0.5
        self.normalmapIntensity = 1.0
        self.aomapIntensity = 1.0
        self.emissiveFactor = 0.0
        self.sp_AdditiveShading = 0.0
        self.transparent = False
        self.alphaToCoverage = False
        self.backfaceCull = False
        self.transmission = 0.0
        self.ior = 1.45
        self.glassRoughness = 0.05
        self.glassColor = [1.0, 1.0, 1.0]

    def resolve_texture(self, rel_name):
        if not rel_name:
            return ""
        clean = rel_name.strip().strip('"').strip("'").replace("\\", "/")
        if os.path.isfile(clean):
            return clean
        candidates = [
            os.path.join(self.mhmat_dir, clean),
            os.path.join(os.path.dirname(self.mhmat_dir), clean),
            os.path.join(self.mhmat_dir, os.path.basename(clean)),
        ]
        if "/" in clean:
            sub = clean.split("/", 1)[1]
            candidates.append(os.path.join(self.mhmat_dir, sub))
        for c in candidates:
            if os.path.isfile(c):
                return os.path.normpath(c).replace("\\", "/")
        return ""
    def load_from_file(self, path):
        """Loads material properties from a .mhmat file."""
        if not os.path.isfile(path):
            return False
        self.reset_defaults()
        self.filepath = os.path.normpath(path).replace("\\", "/")
        self.mhmat_dir = os.path.dirname(self.filepath)
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.description = f"{self.name} material"
        self.tags = []
        mr_found = False

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                words = line.strip().split()
                if not words or words[0] in ("#", "//"):
                    continue
                # Parses texture keys, shader data, colors, and PBR factors...
        if not mr_found:
            self.roughnessFactor = round(max(0.0, min(1.0, 1.0 - sum(self.specularColor) / 3.0)), 4)
        return True

    def upgrade_to_pbr(self):
        """Upgrades legacy Phong settings to MakeHuman 2 PBR."""
        if not self.textures.get("aomapTexture"):
            self.ambientColor = [1.0, 1.0, 1.0]
        if self.shader == "phong":
            self.roughnessFactor = round(max(0.05, min(1.0, 1.0 - sum(self.specularColor) / 3.0)), 4)
        self.shader = "pbr"
    def rel_tex_name(self, tex_path, out_dir, copy_external=True):
        """Resolves relative texture path and optionally copies external textures into out_dir."""
        if not tex_path or not os.path.isfile(tex_path):
            return ""
        norm_tex = os.path.normpath(tex_path).replace("\\", "/")
        norm_out = os.path.normpath(out_dir).replace("\\", "/")
        if norm_tex.startswith(norm_out + "/"):
            return norm_tex[len(norm_out) + 1:]
        if copy_external:
            dst = os.path.join(out_dir, os.path.basename(tex_path))
            if os.path.normcase(tex_path) != os.path.normcase(dst):
                shutil.copy2(tex_path, dst)
            return os.path.basename(tex_path)
        return norm_tex

    def save_mhmat(self, path, copy_textures=True):
        """Writes a native MakeHuman 2 .mhmat file."""
        out_dir = os.path.dirname(os.path.abspath(path))
        os.makedirs(out_dir, exist_ok=True)
        self.filepath = os.path.normpath(path).replace("\\", "/")
        self.mhmat_dir = out_dir

        # Formats name, description, colors, factors, textures, glass, and shader into .mhmat lines...
        lines = [
            f"# MakeHuman2 Material definition for {self.name}\n",
            f"name {self.name}\n",
            f"description {self.description}\n",
            f"shader {self.shader}\n",
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True

    def export_mtl(self, mtl_path, copy_textures=True):
        """Exports a standard Wavefront .mtl material file alongside textures."""
        out_dir = os.path.dirname(os.path.abspath(mtl_path))
        os.makedirs(out_dir, exist_ok=True)
        dr, dg, db = self.diffuseColor
        sr, sg, sb = self.specularColor
        lines = [
            f"# Wavefront MTL exported by MH2 Material Maker\n",
            f"newmtl {self.name}\n",
            f"Kd {dr:.4f} {dg:.4f} {db:.4f}\n",
            f"Ks {sr:.4f} {sg:.4f} {sb:.4f}\n",
            f"Ns {(1.0 - self.roughnessFactor) * 500.0:.2f}\n",
            f"d {0.35 if self.transparent else 1.0:.2f}\n",
        ]
        diff = self.rel_tex_name(self.textures.get("diffuseTexture", ""), out_dir, copy_textures)
        if diff:
            lines.append(f"map_Kd {diff}\n")
        norm = self.rel_tex_name(self.textures.get("normalmapTexture", ""), out_dir, copy_textures)
        if norm:
            lines.append(f"map_Bump {norm}\n")
        with open(mtl_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    def export_blender_node_script(self, py_path, copy_textures=True):
        """Generates a self-contained Blender Python script that builds a Principled BSDF node tree."""
        out_dir = os.path.dirname(os.path.abspath(py_path))
        os.makedirs(out_dir, exist_ok=True)
        diff = self.rel_tex_name(self.textures.get("diffuseTexture", ""), out_dir, copy_textures)
        norm = self.rel_tex_name(self.textures.get("normalmapTexture", ""), out_dir, copy_textures)
        mr = self.rel_tex_name(self.textures.get("metallicRoughnessTexture", ""), out_dir, copy_textures)
        ao = self.rel_tex_name(self.textures.get("aomapTexture", ""), out_dir, copy_textures)
        em = self.rel_tex_name(self.textures.get("emissiveTexture", ""), out_dir, copy_textures)

        script = [
            "import os, bpy\n",
            f"BASE_DIR = os.path.dirname(os.path.abspath(__file__))\n",
            f"mat = bpy.data.materials.new(name={self.name!r})\n",
            "mat.use_nodes = True\n",
            "nt = mat.node_tree\n",
            "nt.nodes.clear()\n",
            "out = nt.nodes.new('ShaderNodeOutputMaterial')\n",
            "bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')\n",
            "nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])\n",
            f"bsdf.inputs['Metallic'].default_value = {self.metallicFactor}\n",
            f"bsdf.inputs['Roughness'].default_value = {self.roughnessFactor}\n",
            f"bsdf.inputs['IOR'].default_value = {self.ior}\n",
        ]
        # Maps image texture nodes to BSDF sockets (Base Color, Metallic/Roughness, Normal, Emission)...
        with open(py_path, "w", encoding="utf-8") as f:
            f.writelines(script)

    def export_unreal_bundle(self, base_path, copy_textures=True):
        """Exports a UE5 JSON descriptor and UE5 Editor Python material builder script."""
        out_dir = os.path.dirname(os.path.abspath(base_path))
        os.makedirs(out_dir, exist_ok=True)
        payload = {
            "material_name": self.name,
            "shader_model": "DefaultLit",
            "blend_mode": "Translucent" if self.transparent else ("Masked" if self.alphaToCoverage else "Opaque"),
            "two_sided": not self.backfaceCull,
            "scalars": {
                "Metallic": self.metallicFactor,
                "Roughness": self.roughnessFactor,
                "NormalIntensity": self.normalmapIntensity,
                "AOIntensity": self.aomapIntensity,
                "EmissiveStrength": self.emissiveFactor,
                "Opacity": 0.35 if self.transparent else 1.0,
            },
            "vectors": {
                "BaseColorTint": self.diffuseColor,
                "EmissiveColor": self.emissiveColor,
                "ColorationTint": self.colorationColor,
            },
            "textures": {
                k: self.rel_tex_name(self.textures.get(k, ""), out_dir, copy_textures)
                for k in self.TEX_KEYS if self.textures.get(k)
            },
        }
        with open(base_path + "_ue5.json", "w", encoding="utf-8") as jf:
            json.dump(payload, jf, indent=4)

        ue_py = [
            "import json, os, unreal\n",
            "# Run inside UE5 Editor Python Console to auto-create Material Instance & import textures\n",
            f"cfg_path = os.path.join(os.path.dirname(__file__), {os.path.basename(base_path) + '_ue5.json'!r})\n",
            "data = json.load(open(cfg_path, 'r', encoding='utf-8'))\n",
            "asset_tools = unreal.AssetToolsHelpers.get_asset_tools()\n",
            "mat = asset_tools.create_asset(data['material_name'], '/Game/MH2_Materials', unreal.Material, unreal.MaterialFactoryNew())\n",
            "unreal.EditorAssetLibrary.save_loaded_asset(mat)\n",
        ]
        with open(base_path + "_ue5_import.py", "w", encoding="utf-8") as pf:
            pf.writelines(ue_py)
class TextureSlotCard(QGroupBox):
    """Texture map slot with 64x64 thumbnail preview, Clear button, and optional factor slider."""
    def __init__(self, title, tex_key, mat_model, on_changed, slider_cfg=None, color_attr=None):
        super().__init__(title)
        self.tex_key = tex_key
        self.mat = mat_model
        self.on_changed = on_changed
        self.slider_cfg = slider_cfg
        self.color_attr = color_attr

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 12, 6, 6)

        self.btn_map = QPushButton("Load Map")
        self.btn_map.setFixedSize(68, 68)
        self.btn_map.setToolTip(f"Browse image for {tex_key}")
        self.btn_map.clicked.connect(self._pick_image)
        lay.addWidget(self.btn_map)

        right = QVBoxLayout()
        top_r = QHBoxLayout()
        self.lbl_file = QLabel("None")
        self.lbl_file.setStyleSheet("font-size: 11px; color: #CCCCCC;")
        top_r.addWidget(self.lbl_file, 1)

        btn_clr = QPushButton("Clear")
        btn_clr.setFixedWidth(52)
        btn_clr.clicked.connect(self._clear_image)
        top_r.addWidget(btn_clr)
        right.addLayout(top_r)

        if slider_cfg:
            attr_name, lbl_txt, max_v, scale = slider_cfg
            self.lbl_s = QLabel(f"{lbl_txt}: 0.50")
            self.lbl_s.setStyleSheet("font-size: 11px;")
            self.slider = QSlider(Qt.Horizontal)
            self.slider.setRange(0, max_v)
            self.slider.valueChanged.connect(lambda v: self._on_slide(attr_name, lbl_txt, scale, v))
            right.addWidget(self.lbl_s)
            right.addWidget(self.slider)

        if color_attr:
            self.btn_col = QPushButton("Pick Tint Color...")
            self.btn_col.clicked.connect(self._pick_color)
            right.addWidget(self.btn_col)

        lay.addLayout(right, 1)
        self.sync_from_model()

    def _pick_image(self):
        start_dir = self.mat.mhmat_dir or self.mat.userdata_dir
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select {self.tex_key}", start_dir, "Images (*.png *.jpg *.jpeg *.bmp *.tga)"
        )
        if path:
            self.mat.textures[self.tex_key] = path.replace("\\", "/")
            self.sync_from_model()
            self.on_changed()

    def _clear_image(self):
        self.mat.textures[self.tex_key] = ""
        self.sync_from_model()
        self.on_changed()

    def _on_slide(self, attr_name, lbl_txt, scale, val):
        fval = round(val / scale, 3)
        setattr(self.mat, attr_name, fval)
        self.lbl_s.setText(f"{lbl_txt}: {fval:.2f}")
        self.on_changed()

    def _pick_color(self):
        r, g, b = getattr(self.mat, self.color_attr, [1.0, 1.0, 1.0])
        init_c = QColor.fromRgbF(r, g, b)
        chosen = QColorDialog.getColor(init_c, self, f"Choose {self.color_attr}")
        if chosen.isValid():
            nr, ng, nb, _ = chosen.getRgbF()
            setattr(self.mat, self.color_attr, [round(nr, 4), round(ng, 4), round(nb, 4)])
            self.sync_from_model()
            self.on_changed()

    def sync_from_model(self):
        from PySide6.QtGui import QIcon
        path = self.mat.textures.get(self.tex_key, "")
        if path and os.path.isfile(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self.btn_map.setIcon(QIcon(pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                self.btn_map.setIconSize(pix.scaled(60, 60, Qt.KeepAspectRatio).size())
                self.btn_map.setText("")
            self.lbl_file.setText(os.path.basename(path))
        else:
            self.btn_map.setIcon(QIcon())
            self.btn_map.setText("Load Map")
            self.lbl_file.setText("None")

        if self.slider_cfg:
            attr_name, lbl_txt, _, scale = self.slider_cfg
            cur = float(getattr(self.mat, attr_name, 0.5))
            self.slider.blockSignals(True)
            self.slider.setValue(int(cur * scale))
            self.slider.blockSignals(False)
            self.lbl_s.setText(f"{lbl_txt}: {cur:.2f}")

        if self.color_attr:
            r, g, b = getattr(self.mat, self.color_attr, [1.0, 1.0, 1.0])
            hex_c = QColor.fromRgbF(r, g, b).name()
            self.btn_col.setStyleSheet(f"background-color: {hex_c}; color: #000000; font-weight: bold;")
class MH2MaterialMakerTab(QWidget):
    """Standalone MakeHuman 2 Material Maker + Live 3D Preview + Multi-Engine Exporter."""
    def __init__(self, mh_glob):
        super().__init__()
        self.mh_glob = mh_glob
        self.mat = StandaloneMHMaterial(self.mh_glob.env.path_userdata)
        self._preview_obj_bytes = None
        self._init_ui()
        self.sync_materials_from_disk()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Top Action & Import/Export Bar
        bar = QHBoxLayout()
        btn_import = QPushButton("Import .mhmat...")
        btn_import.clicked.connect(self._import_mhmat)
        btn_sync = QPushButton("Sync MH2 Materials")
        btn_sync.setToolTip("Scan active MH2 data folder for all .mhmat material files")
        btn_sync.clicked.connect(self.sync_materials_from_disk)
        btn_pbr = QPushButton("Upgrade to PBR")
        btn_pbr.setToolTip("Convert legacy Phong material to MakeHuman 2 PBR shader")
        btn_pbr.clicked.connect(self._upgrade_pbr_clicked)
        btn_save = QPushButton("Save .mhmat...")
        btn_save.setStyleSheet("font-weight: bold;")
        btn_save.clicked.connect(self._save_mhmat_clicked)
        btn_blender = QPushButton("Export Blender Nodes (.py)")
        btn_blender.clicked.connect(self._export_blender_clicked)
        btn_unreal = QPushButton("Export Unreal Engine 5")
        btn_unreal.clicked.connect(self._export_unreal_clicked)
        btn_mtl = QPushButton("Export .MTL")
        btn_mtl.clicked.connect(self._export_mtl_clicked)

        for b in (btn_import, btn_sync, btn_pbr, btn_save, btn_blender, btn_unreal, btn_mtl):
            bar.addWidget(b)
        bar.addStretch()
        root.addLayout(bar)
        self._build_columns(root)


    def _build_columns(self, root):
        splitter = QSplitter(Qt.Horizontal)

        # Column 1: Synced MH2 Materials Browser
        left = QGroupBox("Synced .mhmat Library")
        l_lay = QVBoxLayout(left)
        self.mat_filter = QLineEdit()
        self.mat_filter.setPlaceholderText("Filter synced .mhmat files...")
        self.mat_filter.textChanged.connect(self._filter_mat_list)
        l_lay.addWidget(self.mat_filter)

        self.mat_list = QListWidget()
        self.mat_list.currentItemChanged.connect(self._on_synced_mat_selected)
        l_lay.addWidget(self.mat_list, 1)
        splitter.addWidget(left)

        # Column 2: Scrollable MH2 Shader, Texture & PBR Glass Controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        editor_w = QWidget()
        e_lay = QVBoxLayout(editor_w)

        meta_g = QGroupBox("Material Identity & Shader")
        m_lay = QVBoxLayout(meta_g)
        self.name_edit = QLineEdit(self.mat.name)
        self.name_edit.textChanged.connect(lambda t: setattr(self.mat, "name", t))
        self.desc_edit = QLineEdit(self.mat.description)
        self.desc_edit.textChanged.connect(lambda t: setattr(self.mat, "description", t))
        m_lay.addWidget(QLabel("Material Name:"))
        m_lay.addWidget(self.name_edit)
        m_lay.addWidget(QLabel("Description:"))
        m_lay.addWidget(self.desc_edit)

        sh_row = QHBoxLayout()
        self.shader_btns = {}
        for sh in ("pbr", "phong", "litsphere", "toon"):
            rb = QRadioButton(sh.upper())
            rb.toggled.connect(lambda chk, s=sh: self._on_shader_changed(s, chk))
            self.shader_btns[sh] = rb
            sh_row.addWidget(rb)
        m_lay.addLayout(sh_row)

        flag_row = QHBoxLayout()
        self.chk_trans = QCheckBox("Transparent")
        self.chk_trans.toggled.connect(lambda c: (setattr(self.mat, "transparent", c), self._refresh_3d()))
        self.chk_alpha = QCheckBox("Alpha-to-Coverage")
        self.chk_alpha.toggled.connect(lambda c: setattr(self.mat, "alphaToCoverage", c))
        self.chk_cull = QCheckBox("Backface Cull")
        self.chk_cull.toggled.connect(lambda c: setattr(self.mat, "backfaceCull", c))
        for cb in (self.chk_trans, self.chk_alpha, self.chk_cull):
            flag_row.addWidget(cb)
        m_lay.addLayout(flag_row)
        e_lay.addWidget(meta_g)
        # Texture Slots & PBR Glass
        self.slots = [
            TextureSlotCard("Base Color / Diffuse", "diffuseTexture", self.mat, self._refresh_3d, color_attr="diffuseColor"),
            TextureSlotCard("Normal Map", "normalmapTexture", self.mat, self._refresh_3d, ("normalmapIntensity", "Normal Strength", 200, 100.0)),
            TextureSlotCard("Ambient Occlusion", "aomapTexture", self.mat, self._refresh_3d, ("aomapIntensity", "AO Strength", 200, 100.0), color_attr="ambientColor"),
            TextureSlotCard("Metallic / Roughness", "metallicRoughnessTexture", self.mat, self._refresh_3d, ("roughnessFactor", "Roughness Factor", 100, 100.0)),
            TextureSlotCard("Emissive Map", "emissiveTexture", self.mat, self._refresh_3d, ("emissiveFactor", "Emissive Strength", 200, 100.0), color_attr="emissiveColor"),
            TextureSlotCard("Coloration Mask", "maskTexture", self.mat, self._refresh_3d, color_attr="colorationColor"),
            TextureSlotCard("LitSphere / MatCap", "sp_litsphereTexture", self.mat, self._refresh_3d, ("sp_AdditiveShading", "Additive Shading", 100, 100.0)),
        ]
        for s_card in self.slots:
            e_lay.addWidget(s_card)

        # Coloration Method & PBR Glass Controls
        col_g = QGroupBox("Coloration Mode & PBR Glass")
        cg_lay = QVBoxLayout(col_g)
        self.col_method_combo = QComboBox()
        self.col_method_combo.addItems(["0: Off", "1: Hue-to-Color", "2: Desaturate + Multiply"])
        self.col_method_combo.currentIndexChanged.connect(lambda i: (setattr(self.mat, "colorationMethod", i), self._refresh_3d()))
        cg_lay.addWidget(QLabel("Coloration Method:"))
        cg_lay.addWidget(self.col_method_combo)

        self.glass_sliders = {}
        for attr, lbl, max_v, sc in (
            ("metallicFactor", "Metallic Factor", 100, 100.0),
            ("transmission", "PBR Glass Transmission", 100, 100.0),
            ("ior", "Refraction IOR", 250, 100.0),
            ("glassRoughness", "Glass Frosted Roughness", 100, 100.0),
        ):
            l_w = QLabel(f"{lbl}: {getattr(self.mat, attr):.2f}")
            sl = QSlider(Qt.Horizontal)
            sl.setRange(0, max_v)
            sl.setValue(int(getattr(self.mat, attr) * sc))
            sl.valueChanged.connect(lambda v, a=attr, lb=lbl, s=sc, lw=l_w: self._on_glass_slide(a, lb, s, lw, v))
            self.glass_sliders[attr] = (sl, l_w, lbl, sc)
            cg_lay.addWidget(l_w)
            cg_lay.addWidget(sl)

        e_lay.addWidget(col_g)
        e_lay.addStretch()

        scroll.setWidget(editor_w)
        splitter.addWidget(scroll)

        # Column 3: Live 3D Material & Coloration Preview
        right = QGroupBox("Live 3D Material Preview")
        r_lay = QVBoxLayout(right)
        r_bar = QHBoxLayout()
        btn_obj = QPushButton("Load Preview .OBJ...")
        btn_obj.clicked.connect(self._pick_preview_obj)
        r_bar.addWidget(btn_obj)
        r_lay.addLayout(r_bar)

        self.preview_3d = MH2MeshViewport("Material Preview (Drag = Orbit)", 0.45, 0.2)
        r_lay.addWidget(self.preview_3d, 1)
        splitter.addWidget(right)

        splitter.setSizes([240, 460, 360])
        root.addWidget(splitter, 1)
    def sync_materials_from_disk(self):
        """Scans active MH2 data directory for all .mhmat files."""
        self.mat_list.clear()
        base = self.mh_glob.env.path_userdata
        if not os.path.isdir(base):
            return
        for r, _, fs in os.walk(base):
            for fn in sorted(fs):
                if fn.lower().endswith(".mhmat"):
                    full = os.path.join(r, fn).replace("\\", "/")
                    rel = os.path.relpath(full, base).replace("\\", "/")
                    it = QListWidgetItem(rel)
                    it.setData(Qt.UserRole, full)
                    self.mat_list.addItem(it)

    def _filter_mat_list(self, text):
        q = text.strip().lower()
        for i in range(self.mat_list.count()):
            it = self.mat_list.item(i)
            it.setHidden(bool(q) and q not in it.text().lower())

    def _on_synced_mat_selected(self, cur, _prev):
        if not cur:
            return
        path = cur.data(Qt.UserRole)
        if path and self.mat.load_from_file(path):
            self._sync_ui_from_model()
            # Auto-load sibling .obj if present in same folder
            folder = os.path.dirname(path)
            sib_obj = next((os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".obj")), None)
            if sib_obj:
                with open(sib_obj, "rb") as f:
                    self._preview_obj_bytes = f.read()
            self._refresh_3d()

    def _sync_ui_from_model(self):
        self.name_edit.setText(self.mat.name)
        self.desc_edit.setText(self.mat.description)
        rb = self.shader_btns.get(self.mat.shader, self.shader_btns["pbr"])
        rb.setChecked(True)
        self.chk_trans.setChecked(self.mat.transparent)
        self.chk_alpha.setChecked(self.mat.alphaToCoverage)
        self.chk_cull.setChecked(self.mat.backfaceCull)
        self.col_method_combo.setCurrentIndex(min(2, max(0, int(self.mat.colorationMethod))))
        for s_card in self.slots:
            s_card.sync_from_model()
        for attr, (sl, lw, lbl, sc) in self.glass_sliders.items():
            val = float(getattr(self.mat, attr, 0.0))
            sl.blockSignals(True)
            sl.setValue(int(val * sc))
            sl.blockSignals(False)
            lw.setText(f"{lbl}: {val:.2f}")

    def _on_shader_changed(self, shader_name, checked):
        if checked:
            self.mat.shader = shader_name

    def _on_glass_slide(self, attr, lbl, sc, lw, val):
        fv = round(val / sc, 3)
        setattr(self.mat, attr, fv)
        lw.setText(f"{lbl}: {fv:.2f}")
        self._refresh_3d()
    def _pick_preview_obj(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Preview .OBJ Mesh", self.mh_glob.env.path_userdata, "Wavefront OBJ (*.obj)"
        )
        if path:
            with open(path, "rb") as f:
                self._preview_obj_bytes = f.read()
            self._refresh_3d()

    def _refresh_3d(self):
        if not self._preview_obj_bytes:
            return
        raw_v, uvs, faces = parse_obj_raw(self._preview_obj_bytes)
        if not raw_v:
            return
        if len(faces) > 25000:
            faces = faces[:25000]
        norm_v = normalize_verts(raw_v)

        diff_path = self.mat.textures.get("diffuseTexture", "")
        if diff_path and os.path.isfile(diff_path):
            tex_img = QImage(diff_path)
        else:
            r, g, b = self.mat.diffuseColor
            tex_img = QImage(32, 32, QImage.Format_ARGB32)
            tex_img.fill(QColor.fromRgbF(r, g, b))

        self.preview_3d.set_mesh(norm_v, uvs, faces, tex_img)

    def _import_mhmat(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import MakeHuman 2 .mhmat", self.mh_glob.env.path_userdata, "MH2 Material (*.mhmat)"
        )
        if path and self.mat.load_from_file(path):
            self._sync_ui_from_model()
            self._refresh_3d()

    def _upgrade_pbr_clicked(self):
        self.mat.upgrade_to_pbr()
        self._sync_ui_from_model()
        QMessageBox.information(self, "PBR Upgraded", "Material upgraded to MakeHuman 2 PBR shader!")

    def _save_mhmat_clicked(self):
        default_dir = self.mat.mhmat_dir or self.mh_glob.env.path_userdata
        path, _ = QFileDialog.getSaveFileName(
            self, "Save MakeHuman 2 .mhmat", os.path.join(default_dir, f"{self.mat.name}.mhmat"), "MH2 Material (*.mhmat)"
        )
        if path:
            self.mat.save_mhmat(path, copy_textures=True)
            self.sync_materials_from_disk()
            QMessageBox.information(self, "Saved", f"Saved PBR .mhmat & synced textures:\n{path}")

    def _export_blender_clicked(self):
        out_dir = QFileDialog.getExistingDirectory(self, "Select Blender Node Export Folder", self.mh_glob.env.path_userdata)
        if out_dir:
            py_out = os.path.join(out_dir, f"{self.mat.name}_blender_nodes.py")
            self.mat.export_blender_node_script(py_out, copy_textures=True)
            QMessageBox.information(self, "Blender Export Ready", f"Created Principled BSDF Node Builder:\n{py_out}")

    def _export_unreal_clicked(self):
        out_dir = QFileDialog.getExistingDirectory(self, "Select Unreal Engine 5 Export Folder", self.mh_glob.env.path_userdata)
        if out_dir:
            base_out = os.path.join(out_dir, self.mat.name)
            self.mat.export_unreal_bundle(base_out, copy_textures=True)
            QMessageBox.information(self, "Unreal Engine 5 Ready", f"Created UE5 Material Bundle:\n{base_out}_ue5.json\n{base_out}_ue5_import.py")

    def _export_mtl_clicked(self):
        out_dir = QFileDialog.getExistingDirectory(self, "Select Wavefront .MTL Export Folder", self.mh_glob.env.path_userdata)
        if out_dir:
            mtl_out = os.path.join(out_dir, f"{self.mat.name}.mtl")
            self.mat.export_mtl(mtl_out, copy_textures=True)
            QMessageBox.information(self, "MTL Export Ready", f"Exported Wavefront .MTL:\n{mtl_out}")
