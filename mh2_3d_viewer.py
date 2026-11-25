"""
MakeHuman 2 3D & Multi-View Mesh Inspector V1.1 (Software 3D + Texture + Body Mannequin Engine in one)
Contributed to MH2 Community from Elvaerwyn_MH2 2026
"""
import os
import io
import math
import zipfile
from PySide6.QtCore import Qt, QPointF, QThread, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF, QImage, QTransform
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QApplication, QSlider, QDialog
)


def parse_obj_raw(raw_bytes):
    """Parses raw OBJ vertices (un-normalized world coords), UVs, and faces."""
    verts = []
    uvs = []
    faces = []
    text = raw_bytes.decode("utf-8", errors="ignore") if isinstance(raw_bytes, (bytes, bytearray)) else str(raw_bytes)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        tag = next(iter(parts), "")
        if tag == "v" and len(parts) >= 4:
            _, sx, sy, sz, *_ = parts
            try:
                verts.append((float(sx), float(sy), float(sz)))
            except ValueError:
                pass
        elif tag == "vt" and len(parts) >= 3:
            _, su, sv, *_ = parts
            try:
                uvs.append((float(su), float(sv)))
            except ValueError:
                pass
        elif tag == "f" and len(parts) >= 4:
            v_idx = []
            t_idx = []
            for p in parts[1:]:
                v_str, _, rest = p.partition("/")
                t_str, _, _ = rest.partition("/")
                try:
                    vi = int(v_str)
                    v_idx.append(vi - 1 if vi > 0 else len(verts) + vi)
                except ValueError:
                    pass
                if t_str:
                    try:
                        ti = int(t_str)
                        t_idx.append(ti - 1 if ti > 0 else len(uvs) + ti)
                    except ValueError:
                        t_idx.append(-1)
                else:
                    t_idx.append(-1)

            if len(v_idx) >= 3:
                v_first, *v_rest = v_idx
                t_first, *t_rest = t_idx
                for idx_r in range(len(v_rest) - 1):
                    va, vb = v_rest[idx_r], v_rest[idx_r + 1]
                    ta, tb = t_rest[idx_r], t_rest[idx_r + 1]
                    faces.append(((v_first, va, vb), (t_first, ta, tb)))
    return verts, uvs, faces


def normalize_verts(verts, ref_verts=None):
    """Centers and scales verts to [-1, 1], optionally sharing bounding box with a base mannequin."""
    if not verts:
        return []
    box_src = (verts + ref_verts) if ref_verts else verts
    xs = [x for (x, _, _) in box_src]
    ys = [y for (_, y, _) in box_src]
    zs = [z for (_, _, z) in box_src]
    cx = (min(xs) + max(xs)) * 0.5
    cy = (min(ys) + max(ys)) * 0.5
    cz = (min(zs) + max(zs)) * 0.5
    scale = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1e-5) * 0.5
    return [((x - cx) / scale, (y - cy) / scale, (z - cz) / scale) for (x, y, z) in verts]


def parse_obj_bytes(raw_bytes, max_faces=25000):
    verts, uvs, faces = parse_obj_raw(raw_bytes)
    if not verts:
        return [], [], []
    if len(faces) > max_faces:
        faces = faces[:max_faces]
    return normalize_verts(verts), uvs, faces


def build_procedural_mannequin(gender="unisex"):
    """
    Generates an anatomical MakeHuman hm08-aligned mannequin (Y: -8.5 to +8.5, A-pose)
    so clothes, boots, hair, and hats snap into their exact anatomical position.
    """
    verts = []
    faces = []

    def add_tube(rings, closed_cap=True):
        base_idx = len(verts)
        segs = 14
        for (cy, cx_off, cz_off, rx, rz) in rings:
            for s in range(segs):
                ang = (2.0 * math.pi * s) / segs
                verts.append((cx_off + math.cos(ang) * rx, cy, cz_off + math.sin(ang) * rz))
        for r in range(len(rings) - 1):
            r0 = base_idx + r * segs
            r1 = base_idx + (r + 1) * segs
            for s in range(segs):
                sn = (s + 1) % segs
                faces.append(((r0 + s, r1 + s, r1 + sn), (-1, -1, -1)))
                faces.append(((r0 + s, r1 + sn, r0 + sn), (-1, -1, -1)))
        if closed_cap and len(rings) >= 2:
            top_c = len(verts)
            _, cx_t, cz_t, _, _ = rings[-1]
            yt = rings[-1][0]
            verts.append((cx_t, yt, cz_t))
            rt = base_idx + (len(rings) - 1) * segs
            for s in range(segs):
                sn = (s + 1) % segs
                faces.append(((rt + s, top_c, rt + sn), (-1, -1, -1)))

    if gender == "female":
        hip_w, waist_w, chest_w, sh_w = 1.65, 1.12, 1.52, 1.68
    elif gender == "male":
        hip_w, waist_w, chest_w, sh_w = 1.48, 1.32, 1.78, 2.05
    else:
        hip_w, waist_w, chest_w, sh_w = 1.56, 1.22, 1.64, 1.85

    # Torso + Neck + Head (MakeHuman hm08 vertical proportions: feet ~ -8.4, crown ~ +8.4)
    torso_rings = [
        (-0.3, 0.0, 0.0, hip_w * 0.85, 0.95),
        (0.4,  0.0, 0.0, hip_w, 1.05),
        (1.6,  0.0, 0.0, waist_w, 0.88),
        (3.0,  0.0, 0.05, chest_w, 1.05),
        (4.3,  0.0, 0.0, sh_w, 0.92),
        (4.9,  0.0, 0.0, 0.62, 0.62),
        (5.7,  0.0, 0.05, 0.56, 0.58),
        (6.3,  0.0, 0.12, 0.78, 0.88),
        (7.3,  0.0, 0.10, 0.86, 0.96),
        (8.1,  0.0, 0.05, 0.68, 0.78),
        (8.45, 0.0, 0.0, 0.25, 0.28),
    ]
    add_tube(torso_rings)

    # Left & Right Legs + Feet
    for side in (-1.0, 1.0):
        x_hip = side * (hip_w * 0.52)
        leg_rings = [
            (-8.4, x_hip * 0.95, 0.35, 0.44, 0.85),
            (-7.9, x_hip * 0.95, 0.10, 0.42, 0.52),
            (-6.2, x_hip * 0.95, -0.05, 0.54, 0.56),
            (-4.4, x_hip * 0.96, 0.05, 0.52, 0.54),
            (-2.2, x_hip * 0.98, 0.0, 0.74, 0.78),
            (-0.1, x_hip,        0.0, 0.82, 0.86),
        ]
        add_tube(leg_rings)

        # Arms (A-pose ~35 deg)
        arm_rings = [
            (4.2, side * (sh_w * 0.88), 0.0, 0.52, 0.52),
            (2.5, side * (sh_w + 1.15), -0.05, 0.44, 0.44),
            (0.8, side * (sh_w + 2.25), 0.05, 0.36, 0.36),
            (-0.4, side * (sh_w + 3.05), 0.12, 0.28, 0.42),
        ]
        add_tube(arm_rings)

    return verts, faces


def parse_mhmat_info(mat_bytes):
    tex_name = None
    diff_rgb = None
    text = mat_bytes.decode("utf-8", errors="ignore")
    for line in text.splitlines():
        s = line.strip()
        low = s.lower()
        if low.startswith("diffusetexture") or low.startswith("map_kd"):
            _, _, val = s.partition(" ")
            val = val.lstrip("= ").strip().strip('"').strip("'")
            if val:
                tex_name = os.path.basename(val.replace("\\", "/"))
        elif low.startswith("diffusecolor "):
            parts = s.split()
            if len(parts) >= 4:
                try:
                    _, sr, sg, sb, *_ = parts
                    diff_rgb = (
                        min(255, max(0, int(float(sr) * 255))),
                        min(255, max(0, int(float(sg) * 255))),
                        min(255, max(0, int(float(sb) * 255))),
                    )
                except ValueError:
                    pass
    return tex_name, diff_rgb


class MH2MeshViewport(QWidget):
    def __init__(self, label="3D View", yaw=0.45, pitch=0.25):
        super().__init__()
        self.view_label = label
        self.yaw = yaw
        self.pitch = pitch
        self.zoom = 1.0
        self.wireframe = False
        self.textured = True
        self.smooth = True
        self.light_gain = 1.25
        self.verts = []
        self.uvs = []
        self.faces = []
        self.body_verts = []
        self.body_faces = []
        self.tex_image = None
        self._last_pos = None
        self.setMinimumSize(180, 180)
        self.setStyleSheet("background-color: #141414; border: 1px solid #3A3A3A; border-radius: 4px;")

    def set_mesh(self, verts, uvs, faces, tex_image=None, body_verts=None, body_faces=None):
        self.verts = verts
        self.uvs = uvs
        self.faces = faces
        self.body_verts = body_verts or []
        self.body_faces = body_faces or []
        self.tex_image = tex_image if (tex_image and not tex_image.isNull()) else None
        self.update()

    def set_angles(self, yaw, pitch, zoom=1.0):
        self.yaw = yaw
        self.pitch = pitch
        self.zoom = zoom
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._last_pos = event.position()

    def mouseMoveEvent(self, event):
        if self._last_pos is not None:
            delta = event.position() - self._last_pos
            self.yaw += delta.x() * 0.012
            self.pitch = max(-1.5, min(1.5, self.pitch + delta.y() * 0.012))
            self._last_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        self._last_pos = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self.zoom = max(0.3, min(4.0, self.zoom * (1.1 if delta > 0 else 0.9)))
        self.update()

    def _make_uv_brush(self, p0, p1, p2, t0, t1, t2):
        u_len = len(self.uvs)
        if not self.tex_image or not self.textured or t0 < 0 or t1 < 0 or t2 < 0 or t0 >= u_len or t1 >= u_len or t2 >= u_len:
            return None

        tw = float(self.tex_image.width())
        th = float(self.tex_image.height())
        u0, v0 = self.uvs[t0]
        u1, v1 = self.uvs[t1]
        u2, v2 = self.uvs[t2]

        tx0, ty0 = u0 * tw, (1.0 - v0) * th
        tx1, ty1 = u1 * tw, (1.0 - v1) * th
        tx2, ty2 = u2 * tw, (1.0 - v2) * th

        du1, dv1 = tx1 - tx0, ty1 - ty0
        du2, dv2 = tx2 - tx0, ty2 - ty0
        det = du1 * dv2 - du2 * dv1
        if abs(det) < 1e-6:
            return None

        sx0, sy0 = p0.x(), p0.y()
        dx1, dy1 = p1.x() - sx0, p1.y() - sy0
        dx2, dy2 = p2.x() - sx0, p2.y() - sy0

        inv = 1.0 / det
        m11 = (dx1 * dv2 - dx2 * dv1) * inv
        m12 = (dy1 * dv2 - dy2 * dv1) * inv
        m21 = (dx2 * du1 - dx1 * du2) * inv
        m22 = (dy2 * du1 - dy1 * du2) * inv
        dx = sx0 - (m11 * tx0 + m21 * ty0)
        dy = sy0 - (m12 * tx0 + m22 * ty0)

        brush = QBrush(self.tex_image)
        brush.setTransform(QTransform(m11, m12, m21, m22, dx, dy))
        return brush

    def _project_points(self, pt_list, cy, sy, cp, sp, scale, cx, center_y):
        proj = []
        rot_z = []
        for (x, y, z) in pt_list:
            rx = x * cy - z * sy
            rz = x * sy + z * cy
            ry = y * cp - rz * sp
            rz2 = y * sp + rz * cp
            persp = 3.2 / max(0.5, 3.2 - rz2)
            proj.append(QPointF(cx + rx * scale * persp, center_y - ry * scale * persp))
            rot_z.append((rx, ry, rz2))
        return proj, rot_z

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#181818"))

        badge = f"{self.view_label} [TEX]" if (self.tex_image and self.textured) else self.view_label
        painter.setPen(QColor("#CCCCCC"))
        painter.drawText(8, 16, badge)

        if (not self.verts or not self.faces) and (not self.body_verts or not self.body_faces):
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No .obj Mesh Loaded\n(Drag to Orbit • Scroll to Zoom)")
            return

        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        scale = min(w, h) * 0.38 * self.zoom
        cx, center_y = w * 0.5, h * 0.52

        b_proj, b_rot = self._project_points(self.body_verts, cy, sy, cp, sp, scale, cx, center_y)
        m_proj, m_rot = self._project_points(self.verts, cy, sy, cp, sp, scale, cx, center_y)

        render_tris = []

        def _collect(proj_pts, rot_pts, face_list, is_body):
            v_len = len(proj_pts)
            for ((i0, i1, i2), (t0, t1, t2)) in face_list:
                if i0 >= v_len or i1 >= v_len or i2 >= v_len:
                    continue
                x0, y0, z0 = rot_pts[i0]
                x1, y1, z1 = rot_pts[i1]
                x2, y2, z2 = rot_pts[i2]
                ux, uy, uz = x1 - x0, y1 - y0, z1 - z0
                vx, vy, vz = x2 - x0, y2 - y0, z2 - z0
                nx = uy * vz - uz * vy
                ny = uz * vx - ux * vz
                nz = ux * vy - uy * vx
                n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
                if n_len < 1e-8:
                    continue
                if nz < 0:
                    nx, ny, nz = -nx, -ny, -nz
                nx /= n_len
                ny /= n_len
                nz /= n_len

                key = max(0.0, nx * 0.35 + ny * 0.55 + nz * 0.76)
                fill = max(0.0, -nx * 0.65 + ny * 0.20 + nz * 0.45) * 0.45
                rim = max(0.0, ny * 0.60 - nz * 0.30) * 0.25
                light = min(1.35, (0.32 + key * 0.78 + fill + rim) * self.light_gain)
                avg_z = (z0 + z1 + z2) / 3.0
                render_tris.append((avg_z, is_body, i0, i1, i2, t0, t1, t2, light))

        _collect(b_proj, b_rot, self.body_faces, True)
        _collect(m_proj, m_rot, self.faces, False)
        render_tris.sort(key=lambda t: next(iter(t)))

        use_tex = bool(self.tex_image and self.textured)
        for (_, is_body, i0, i1, i2, t0, t1, t2, light) in render_tris:
            pts = b_proj if is_body else m_proj
            p0, p1, p2 = pts[i0], pts[i1], pts[i2]
            poly = QPolygonF([p0, p1, p2])

            if self.wireframe:
                painter.setPen(QPen(QColor("#555555" if is_body else "#2ECC71"), 0.7))
                painter.setBrush(Qt.NoBrush)
                painter.drawPolygon(poly)
                continue

            if is_body:
                shade = min(230, int(55 + light * 120))
                painter.setPen(QPen(QColor(45, 45, 50, 60), 0.3))
                painter.setBrush(QBrush(QColor(shade, int(shade * 0.94), int(shade * 0.90))))
                painter.drawPolygon(poly)
            else:
                uv_brush = self._make_uv_brush(p0, p1, p2, t0, t1, t2) if use_tex else None
                if uv_brush is not None:
                    painter.setPen(QPen(uv_brush, 0.75) if self.smooth else Qt.NoPen)
                    painter.setBrush(uv_brush)
                    painter.drawPolygon(poly)
                    if light < 0.95:
                        shadow_alpha = min(160, int((0.95 - light) * 140))
                        painter.setBrush(QBrush(QColor(0, 0, 0, shadow_alpha)))
                        painter.drawPolygon(poly)
                    elif light > 1.02:
                        glow_alpha = min(90, int((light - 1.0) * 160))
                        painter.setBrush(QBrush(QColor(255, 255, 255, glow_alpha)))
                        painter.drawPolygon(poly)
                else:
                    shade = min(255, int(45 + light * 165))
                    col = QColor(shade, min(255, shade + 6), min(255, shade + 14))
                    if self.smooth:
                        painter.setPen(QPen(col, 0.8))
                    else:
                        painter.setPen(QPen(QColor(25, 25, 25, 110), 0.45))
                    painter.setBrush(QBrush(col))
                    painter.drawPolygon(poly)

class _RepoScanWorker(QThread):
    scan_done = Signal(str, dict, str)

    def __init__(self, repo):
        super().__init__()
        self.repo = repo


    def run(self):
        import json
        from mh2_vault_downloader import _fetch_bytes

        api_host = ".".join(["api", "github", "com"])
        raw_host = ".".join(["raw", "githubusercontent", "com"])
        rel_url = f"https://{api_host}/repos/{self.repo}/releases"
        tree_url = f"https://{api_host}/repos/{self.repo}/git/trees/HEAD?recursive=1"
        raw_base = f"https://{raw_host}/{self.repo}/HEAD/"

        sources = {}
        rel_count = 0
        obj_count = 0
        zip_count = 0

        try:
            releases = json.loads(_fetch_bytes(rel_url, timeout=8).decode("utf-8"))
            if isinstance(releases, list):
                for rel in releases:
                    if not isinstance(rel, dict):
                        continue
                    tag = rel.get("tag_name", "release")
                    for asset in rel.get("assets", []):
                        if not isinstance(asset, dict):
                            continue
                        aname = asset.get("name", "")
                        dl_url = asset.get("browser_download_url", "")
                        if aname.lower().endswith(".zip") and "thumb" not in aname.lower() and dl_url:
                            sources[f"[Release:{tag}] {aname}"] = (dl_url, None)
                            rel_count += 1
        except Exception:
            pass

        try:
            data = json.loads(_fetch_bytes(tree_url, timeout=8).decode("utf-8"))
            tree = data.get("tree", [])
            blobs = [item["path"] for item in tree if isinstance(item, dict) and item.get("type") == "blob" and item.get("path")]

            for p in blobs:
                low = p.lower()
                if low.endswith(".obj"):
                    folder_p = os.path.dirname(p)
                    nearby = [
                        b for b in blobs
                        if (folder_p and b.startswith(folder_p + "/")) or (not folder_p and "/" not in b)
                    ]
                    mat_rel = next((n for n in nearby if n.lower().endswith((".mhmat", ".mtl"))), None)
                    mat_url = (raw_base + mat_rel) if mat_rel else None
                    sources[f"[OBJ] {p}"] = (raw_base + p, (mat_url, []))
                    obj_count += 1
                elif low.endswith(".zip") and "thumb" not in low:
                    sources[f"[ZIP] {p}"] = (raw_base + p, None)
                    zip_count += 1
        except Exception:
            pass

        if sources:
            msg = f"Found {rel_count} Release ZIPs, {obj_count} .OBJs & {zip_count} repo ZIPs — pick a pack!"
        else:
            msg = f"No .obj or release .zip meshes found in {self.repo}."
        self.scan_done.emit(self.repo, sources, msg)


class _MeshStreamWorker(QThread):
    finished_stream = Signal(str, object, str)

    def __init__(self, name, source, mat_or_tex):
        super().__init__()
        self.name = name
        self.source = source
        self.mat_or_tex = mat_or_tex

    def run(self):
        from mh2_vault_downloader import _fetch_bytes
        try:
            clean_src, _, _ = self.source.partition("?")
            is_zip = clean_src.lower().endswith(".zip")
            raw_bytes = _fetch_bytes(self.source, timeout=90 if is_zip else 12)
            extracted = {}

            if is_zip:
                with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as zf:
                    names = zf.namelist()
                    obj_members = [m for m in names if m.lower().endswith(".obj")]
                    if not obj_members:
                        self.finished_stream.emit(self.name, {}, f"No .obj inside {os.path.basename(self.name)}")
                        return

                    mat_by_dir = {}
                    any_mat = None
                    for m in names:
                        if m.lower().endswith((".mhmat", ".mtl")):
                            mb = zf.read(m)
                            mat_by_dir[os.path.dirname(m)] = mb
                            if any_mat is None:
                                any_mat = mb

                    for obj_m in sorted(obj_members):
                        obj_dir = os.path.dirname(obj_m)
                        mat_bytes = mat_by_dir.get(obj_dir, any_mat)
                        tex_bytes = None
                        if mat_bytes:
                            tex_ref, _ = parse_mhmat_info(mat_bytes)
                            if tex_ref:
                                hit = next((n for n in names if os.path.basename(n).lower() == tex_ref.lower()), None)
                                if hit:
                                    tex_bytes = zf.read(hit)
                        extracted[obj_m] = (zf.read(obj_m), tex_bytes)
            else:
                tex_bytes = None
                if isinstance(self.mat_or_tex, tuple):
                    mat_url, extra_urls = self.mat_or_tex
                    tex_ref = None
                    if isinstance(mat_url, str) and mat_url.startswith("http"):
                        try:
                            mat_bytes = _fetch_bytes(mat_url, timeout=8)
                            tex_ref, _ = parse_mhmat_info(mat_bytes)
                        except Exception:
                            tex_ref = None

                    if tex_ref:
                        ref_low = tex_ref.lower()
                        candidates = []
                        for eu in extra_urls:
                            clean_eu, _, _ = eu.partition("?")
                            if clean_eu.lower().endswith(ref_low):
                                candidates.append(eu)
                        if isinstance(mat_url, str) and mat_url.startswith("http"):
                            clean_mat, _, _ = mat_url.partition("?")
                            mat_dir, _, _ = clean_mat.rpartition("/")
                            candidates.extend([f"{mat_dir}/{tex_ref}", f"{mat_dir}/textures/{tex_ref}"])

                        for c_url in candidates:
                            try:
                                tex_bytes = _fetch_bytes(c_url, timeout=8)
                                if tex_bytes:
                                    break
                            except Exception:
                                pass
                extracted[os.path.basename(self.name)] = (raw_bytes, tex_bytes)

            self.finished_stream.emit(self.name, extracted, "")
        except Exception as e:
            self.finished_stream.emit(self.name, {}, f"Server timeout/error: {e}")

class MH2Mesh3DInspector(QWidget):
    """Multi-View Mesh + Texture + Male/Female/Unisex Mannequin + Pop-Up Preview Inspector."""
    def __init__(self):
        super().__init__()
        self.pack_sources = {}    # Dropdown 1: pack_label -> url_or_dict
        self.current_items = {}   # Dropdown 2: item_label -> (obj_bytes, tex_bytes)
        self._active_obj_bytes = None
        self._active_tex_bytes = None
        self._active_item_label = ""
        self._stream_workers = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Row 1: Repository Scanner
        repo_bar = QHBoxLayout()
        self.repo_pick = QComboBox()
        self.repo_pick.addItems([
            "Makehuman-2/MH2_Asset_Repository_CC-By",
            "Makehuman-2/MH2_Asset_Repository_CCO",
            "Makehuman-2/MH2_Asset_repository_AGPL",
            "Makehuman-2/MH2_Creator_Portal",
            "Makehuman-2/MH2_Legacy_Vault",
        ])
        self.btn_scan_repo = QPushButton("Scan Repo .OBJs")
        self.btn_scan_repo.setStyleSheet("padding: 3px 6px; font-size: 11px;")
        self.btn_scan_repo.clicked.connect(self._scan_github_repo_objs)
        repo_bar.addWidget(self.repo_pick, 1)
        repo_bar.addWidget(self.btn_scan_repo)
        layout.addLayout(repo_bar)

        # Row 2: Dual Selectors (Release/Local Pack + Item inside ZIP/Folder)
        sel_bar = QHBoxLayout()
        sel_bar.addWidget(QLabel("Pack:"))
        self.pack_selector = QComboBox()
        self.pack_selector.setToolTip("Select Release ZIP, Repo File, or Local Archive")
        self.pack_selector.currentIndexChanged.connect(self._on_pack_selected)
        sel_bar.addWidget(self.pack_selector, 1)

        sel_bar.addWidget(QLabel("Item:"))
        self.item_selector = QComboBox()
        self.item_selector.setToolTip("Select individual .obj item inside the loaded ZIP or folder")
        self.item_selector.currentIndexChanged.connect(self._on_item_selected)
        sel_bar.addWidget(self.item_selector, 1)
        layout.addLayout(sel_bar)

        # Row 3: Camera + Render Mode + Body Mannequin + Quick Pop-Up Preview
        bar = QHBoxLayout()
        self.btn_front = QPushButton("Front")
        self.btn_front.clicked.connect(lambda: self.main_view.set_angles(0.0, 0.0, 1.0))
        self.btn_side = QPushButton("Side")
        self.btn_side.clicked.connect(lambda: self.main_view.set_angles(1.57, 0.0, 1.0))
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(lambda: self.main_view.set_angles(3.14, 0.0, 1.0))
        self.btn_tex = QPushButton("Textured")
        self.btn_tex.setCheckable(True)
        self.btn_tex.setChecked(True)
        self.btn_tex.toggled.connect(self._toggle_textured)
        self.btn_wire = QPushButton("Wireframe")
        self.btn_wire.setCheckable(True)
        self.btn_wire.toggled.connect(self._toggle_wireframe)
        self.btn_quad = QPushButton("4-View")
        self.btn_quad.setCheckable(True)
        self.btn_quad.toggled.connect(self._toggle_quad_view)
        self.btn_smooth = QPushButton("Smooth")
        self.btn_smooth.setCheckable(True)
        self.btn_smooth.setChecked(True)
        self.btn_smooth.toggled.connect(self._toggle_smooth)

        for b in (self.btn_front, self.btn_side, self.btn_back, self.btn_tex, self.btn_smooth, self.btn_wire, self.btn_quad):
            b.setStyleSheet("padding: 3px 6px; font-size: 11px;")
            bar.addWidget(b)

        bar.addWidget(QLabel("Body:"))
        self.body_combo = QComboBox()
        self.body_combo.addItems(["None (Item Only)", "Unisex Base", "Female Base", "Male Base"])
        self.body_combo.setToolTip("Preview clothes, hair, boots, or hats fitted onto a base mannequin")
        self.body_combo.currentIndexChanged.connect(self._re_render_active)
        bar.addWidget(self.body_combo)

        self.btn_popup = QPushButton("Pop-Up Preview")
        self.btn_popup.setStyleSheet("padding: 3px 8px; font-size: 11px; font-weight: bold;")
        self.btn_popup.setToolTip("Open a large quick-preview pop-up window with body mannequin options")
        self.btn_popup.clicked.connect(self._open_popup_preview)
        bar.addWidget(self.btn_popup)
        layout.addLayout(bar)

        # Row 4: Studio Lighting Slider
        light_bar = QHBoxLayout()
        lbl_light = QLabel("☀ Studio Light:")
        lbl_light.setStyleSheet("font-size: 13px; font-weight: bold;")
        light_bar.addWidget(lbl_light)

        self.light_slider = QSlider(Qt.Horizontal)
        self.light_slider.setRange(50, 220)
        self.light_slider.setValue(125)
        self.light_slider.setMinimumHeight(24)
        self.light_slider.valueChanged.connect(self._on_light_changed)
        light_bar.addWidget(self.light_slider, 1)

        self.lbl_light_val = QLabel("125%")
        self.lbl_light_val.setStyleSheet("font-size: 13px; font-weight: bold; min-width: 42px;")
        light_bar.addWidget(self.lbl_light_val)
        layout.addLayout(light_bar)

        # Single Interactive Viewport
        self.main_view = MH2MeshViewport("Interactive 3D (Drag = Orbit | Wheel = Zoom)", 0.45, 0.2)
        layout.addWidget(self.main_view, 1)

        # 4-Way Multi-View Container
        self.quad_container = QWidget()
        quad_layout = QVBoxLayout(self.quad_container)
        quad_layout.setContentsMargins(0, 0, 0, 0)
        quad_layout.setSpacing(4)
        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        self.v_front = MH2MeshViewport("Front View", 0.0, 0.0)
        self.v_side = MH2MeshViewport("Side View", 1.57, 0.0)
        self.v_back = MH2MeshViewport("Back View", 3.14, 0.0)
        self.v_3q = MH2MeshViewport("3/4 Perspective", 0.65, 0.3)
        row1.addWidget(self.v_front)
        row1.addWidget(self.v_side)
        row2.addWidget(self.v_back)
        row2.addWidget(self.v_3q)
        quad_layout.addLayout(row1)
        quad_layout.addLayout(row2)
        self.quad_container.setVisible(False)
        layout.addWidget(self.quad_container, 1)

        self.status_lbl = QLabel("Ready — select a staged ZIP, local folder, or scan a GitHub repository.")
        self.status_lbl.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(self.status_lbl)

    def _get_mannequin_mesh(self):
        idx = self.body_combo.currentIndex()
        if idx == 0:
            return [], []
        mode = {1: "unisex", 2: "female", 3: "male"}.get(idx, "unisex")
        return build_procedural_mannequin(mode)

    def _pick_diffuse_from_names(self, all_names, obj_name, mat_bytes=None):
        if not mat_bytes:
            return None
        tex_ref, _ = parse_mhmat_info(mat_bytes)
        if not tex_ref:
            return None
        return next((n for n in all_names if os.path.basename(n).lower() == tex_ref.lower()), None)

    def _set_items_dropdown(self, items_dict):
        self.current_items = items_dict
        self.item_selector.blockSignals(True)
        self.item_selector.clear()
        for k in items_dict.keys():
            self.item_selector.addItem(k)
        self.item_selector.blockSignals(False)
        if items_dict:
            self._on_item_selected(0)

    def _scan_github_repo_objs(self):
        repo = self.repo_pick.currentText().strip()
        self.btn_scan_repo.setEnabled(False)
        self.status_lbl.setText(f"Scanning Releases & Files in {repo} (background)...")

        worker = _RepoScanWorker(repo)
        worker.scan_done.connect(self._on_repo_scan_done)
        self._stream_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._stream_workers.remove(w) if w in self._stream_workers else None)
        worker.start()

    def _on_repo_scan_done(self, repo, sources, msg):
        self.btn_scan_repo.setEnabled(True)
        self.pack_sources.clear()
        self.pack_selector.blockSignals(True)
        self.pack_selector.clear()
        self.item_selector.clear()

        if sources:
            self.pack_sources.update(sources)
            for label in self.pack_sources.keys():
                self.pack_selector.addItem(label)
            self.pack_selector.blockSignals(False)
            self.status_lbl.setText(msg)
            first_label = next(iter(self.pack_sources))
            if first_label.startswith("[OBJ]"):
                self._on_pack_selected(0)
        else:
            self.pack_selector.blockSignals(False)
            self._clear_meshes(msg)

    def load_from_url(self, mesh_url, label=None, mat_url=None, extra_urls=None):
        clean_u, _, _ = str(mesh_url).partition("?")
        name = label or os.path.basename(clean_u) or "remote_mesh.obj"
        self.pack_sources.clear()
        self.pack_selector.blockSignals(True)
        self.pack_selector.clear()
        self.pack_sources[name] = (mesh_url, (mat_url, extra_urls or []))
        self.pack_selector.addItem(name)
        self.pack_selector.blockSignals(False)
        self._on_pack_selected(0)

    def _on_pack_selected(self, idx):
        pack_name = self.pack_selector.currentText()
        entry = self.pack_sources.get(pack_name)
        if not entry:
            return

        if isinstance(entry, dict):
            self._set_items_dropdown(entry)
            return

        source, mat_or_tex = entry
        if isinstance(source, str) and source.startswith("http"):
            self.status_lbl.setText(f"Streaming {os.path.basename(pack_name)} in background...")
            worker = _MeshStreamWorker(pack_name, source, mat_or_tex)
            worker.finished_stream.connect(self._on_stream_ready)
            self._stream_workers.append(worker)
            worker.finished.connect(lambda w=worker: self._stream_workers.remove(w) if w in self._stream_workers else None)
            worker.start()

    def _on_stream_ready(self, pack_name, extracted, err_msg):
        if err_msg or not extracted:
            self.status_lbl.setText(err_msg or f"Empty response for {os.path.basename(pack_name)}")
            return
        self.pack_sources[pack_name] = extracted
        if self.pack_selector.currentText() == pack_name:
            self._set_items_dropdown(extracted)
            self.status_lbl.setText(
                f"Loaded {len(extracted)} item(s) from {os.path.basename(pack_name)} — use Item dropdown to switch!"
            )

    def _on_item_selected(self, idx):
        item_name = self.item_selector.currentText()
        pair = self.current_items.get(item_name)
        if not pair:
            return
        raw_bytes, tex_bytes = pair
        self._active_item_label = item_name
        self._active_obj_bytes = raw_bytes
        self._active_tex_bytes = tex_bytes
        self._re_render_active()

    def _re_render_active(self):
        if not self._active_obj_bytes:
            return
        raw_verts, uvs, faces = parse_obj_raw(self._active_obj_bytes)
        if not raw_verts:
            self._clear_meshes(f"Empty or invalid .obj data in {os.path.basename(self._active_item_label)}")
            return
        if len(faces) > 25000:
            faces = faces[:25000]

        body_raw_v, body_f = self._get_mannequin_mesh()
        if body_raw_v:
            norm_garment = normalize_verts(raw_verts, ref_verts=body_raw_v)
            norm_body = normalize_verts(body_raw_v, ref_verts=raw_verts)
        else:
            norm_garment = normalize_verts(raw_verts)
            norm_body = []

        tex_img = QImage.fromData(self._active_tex_bytes) if isinstance(self._active_tex_bytes, (bytes, bytearray)) else None
        for vp in (self.main_view, self.v_front, self.v_side, self.v_back, self.v_3q):
            vp.set_mesh(norm_garment, uvs, faces, tex_img, norm_body, body_f)

        tex_note = " + .mhmat Diffuse Texture" if (tex_img and not tex_img.isNull()) else " (Clay Shaded)"
        body_note = f" on {self.body_combo.currentText()}" if body_raw_v else ""
        self.status_lbl.setText(
            f"Loaded {os.path.basename(self._active_item_label)}{body_note} — {len(raw_verts):,} verts | {len(faces):,} tris{tex_note}"
        )

    def load_from_zip(self, zip_path):
        self.pack_sources.clear()
        self.pack_selector.blockSignals(True)
        self.pack_selector.clear()
        extracted = {}
        if os.path.exists(zip_path):
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    names = zf.namelist()
                    objs = sorted([n for n in names if n.lower().endswith(".obj")])
                    mat_name = next((m for m in names if m.lower().endswith((".mhmat", ".mtl"))), None)
                    mat_bytes = zf.read(mat_name) if mat_name else None
                    for obj_n in objs:
                        tex_n = self._pick_diffuse_from_names(names, obj_n, mat_bytes)
                        tex_bytes = zf.read(tex_n) if tex_n else None
                        extracted[obj_n] = (zf.read(obj_n), tex_bytes)
            except Exception as e:
                self.status_lbl.setText(f"ZIP mesh scan error: {e}")

        pack_label = os.path.basename(zip_path)
        self.pack_sources[pack_label] = extracted
        self.pack_selector.addItem(pack_label)
        self.pack_selector.blockSignals(False)
        if extracted:
            self._set_items_dropdown(extracted)
        else:
            self._clear_meshes("No .obj mesh found inside this archive.")

    def load_from_folder(self, folder_path):
        self.pack_sources.clear()
        self.pack_selector.blockSignals(True)
        self.pack_selector.clear()
        extracted = {}
        if folder_path and os.path.isdir(folder_path):
            rel_files = []
            for r, _, fs in os.walk(folder_path):
                for fn in fs:
                    rel_files.append(os.path.relpath(os.path.join(r, fn), folder_path).replace("\\", "/"))

            mat_rel = next((m for m in rel_files if m.lower().endswith((".mhmat", ".mtl"))), None)
            mat_bytes = None
            if mat_rel:
                try:
                    with open(os.path.join(folder_path, mat_rel), "rb") as mf:
                        mat_bytes = mf.read()
                except Exception:
                    pass

            for rel_p in sorted(rel_files):
                if rel_p.lower().endswith(".obj"):
                    fpath = os.path.join(folder_path, rel_p)
                    tex_rel = self._pick_diffuse_from_names(rel_files, rel_p, mat_bytes)
                    tex_bytes = None
                    if tex_rel:
                        try:
                            with open(os.path.join(folder_path, tex_rel), "rb") as tf:
                                tex_bytes = tf.read()
                        except Exception:
                            pass
                    try:
                        with open(fpath, "rb") as f:
                            extracted[rel_p] = (f.read(), tex_bytes)
                    except Exception:
                        pass

        pack_label = os.path.basename(folder_path.rstrip("/\\")) or "Local Folder"
        self.pack_sources[pack_label] = extracted
        self.pack_selector.addItem(pack_label)
        self.pack_selector.blockSignals(False)
        if extracted:
            self._set_items_dropdown(extracted)
        else:
            self._clear_meshes("No .obj mesh in selected folder.")

    def _open_popup_preview(self):
        if not self._active_obj_bytes:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Quick 3D Mannequin Preview — {os.path.basename(self._active_item_label)}")
        dlg.resize(780, 720)
        vlay = QVBoxLayout(dlg)

        top = QHBoxLayout()
        top.addWidget(QLabel("Mannequin Body:"))
        pop_body = QComboBox()
        pop_body.addItems(["None (Item Only)", "Unisex Base", "Female Base", "Male Base"])
        pop_body.setCurrentIndex(self.body_combo.currentIndex() if self.body_combo.currentIndex() > 0 else 1)
        top.addWidget(pop_body)

        btn_f = QPushButton("Front")
        btn_s = QPushButton("Side")
        btn_b = QPushButton("Back")
        btn_w = QPushButton("Wireframe")
        btn_w.setCheckable(True)
        for btn in (btn_f, btn_s, btn_b, btn_w):
            top.addWidget(btn)
        top.addStretch()
        vlay.addLayout(top)

        pop_view = MH2MeshViewport("Quick 3D Preview (Drag to Orbit • Scroll to Zoom)", 0.35, 0.15)
        pop_view.light_gain = self.light_slider.value() / 100.0
        vlay.addWidget(pop_view, 1)

        btn_f.clicked.connect(lambda: pop_view.set_angles(0.0, 0.0, 1.0))
        btn_s.clicked.connect(lambda: pop_view.set_angles(1.57, 0.0, 1.0))
        btn_b.clicked.connect(lambda: pop_view.set_angles(3.14, 0.0, 1.0))
        btn_w.toggled.connect(lambda chk: (setattr(pop_view, "wireframe", chk), pop_view.update()))

        def _sync_popup_body():
            idx = pop_body.currentIndex()
            raw_verts, uvs, faces = parse_obj_raw(self._active_obj_bytes)
            if len(faces) > 25000:
                faces = faces[:25000]
            if idx == 0:
                b_raw, b_f = [], []
                ng = normalize_verts(raw_verts)
                nb = []
            else:
                mode = {1: "unisex", 2: "female", 3: "male"}.get(idx, "unisex")
                b_raw, b_f = build_procedural_mannequin(mode)
                ng = normalize_verts(raw_verts, ref_verts=b_raw)
                nb = normalize_verts(b_raw, ref_verts=raw_verts)
            tex_img = QImage.fromData(self._active_tex_bytes) if isinstance(self._active_tex_bytes, (bytes, bytearray)) else None
            pop_view.set_mesh(ng, uvs, faces, tex_img, nb, b_f)

        pop_body.currentIndexChanged.connect(_sync_popup_body)
        _sync_popup_body()
        dlg.exec()

    def _clear_meshes(self, msg):
        self._active_obj_bytes = None
        self._active_tex_bytes = None
        for vp in (self.main_view, self.v_front, self.v_side, self.v_back, self.v_3q):
            vp.set_mesh([], [], [], None, [], [])
        self.status_lbl.setText(msg)

    def _on_light_changed(self, val):
        if hasattr(self, "lbl_light_val"):
            self.lbl_light_val.setText(f"{val}%")
        gain = val / 100.0
        for vp in (self.main_view, self.v_front, self.v_side, self.v_back, self.v_3q):
            vp.light_gain = gain
            vp.update()

    def _toggle_textured(self, checked):
        for vp in (self.main_view, self.v_front, self.v_side, self.v_back, self.v_3q):
            vp.textured = checked
            vp.update()

    def _toggle_wireframe(self, checked):
        for vp in (self.main_view, self.v_front, self.v_side, self.v_back, self.v_3q):
            vp.wireframe = checked
            vp.update()

    def _toggle_quad_view(self, checked):
        self.main_view.setVisible(not checked)
        self.quad_container.setVisible(checked)

    def _toggle_smooth(self, checked):
        for vp in (self.main_view, self.v_front, self.v_side, self.v_back, self.v_3q):
            vp.smooth = checked
            vp.update()

