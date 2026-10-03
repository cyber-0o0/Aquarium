"""
Modular gear for the soldier base body (UNIT-GEAR-ASSETS.md, starter set, section 8).

Every item is a separate low-poly mesh rigidly parented to ONE bone (Parent -> Bone, no weights),
pivot at the head of that bone, mesh axes = character axes (Blender: Z up, face -Y, left +X;
exported glTF: Y up, face +Z, left +X). Materials use only the spec slots (01-09, Weapon | ...).

Run (after build_soldier.py produced soldier_base.blend):
    python3 build_gear.py             # items, atlas bake, pose/clipping test, renders, soldier_gear.blend
    python3 build_gear.py --preview   # quick low-sample renders, no bake
"""
import math
import os
import sys

import bpy  # noqa: E402  (bpy must be imported before bmesh/mathutils)
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
PREVIEW = "--preview" in ARGS
OUT = os.path.dirname(os.path.abspath(__file__))
REN = os.path.join(OUT, "renders_gear")
os.makedirs(REN, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "soldier_base.blend"))
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
arm = bpy.data.objects["Armature"]
BODY = {n: bpy.data.objects[n] for n in ("Soldier_Body", "Soldier_Hair", "Soldier_Gloves",
                                          "Soldier_Boots")}

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
FRONT = Vector((0, -1, 0))
ARM_Z = 1.415
HIP = Vector((0.095, 0.0, 0.95))
ANKLE = Vector((0.160, 0.0, 0.10))
LEG_AXIS = (ANKLE - HIP).normalized()
TEAM_PREVIEW = "#2f6fd6"


def leg_h(z):
    f = (HIP.z - z) / (HIP.z - ANKLE.z)
    return (HIP.lerp(ANKLE, f) - HIP).length


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# materials: spec slots, matte hand-painted look (same recipe as the body)
# ---------------------------------------------------------------------------
def srgb(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out + [1.0]


def scale_col(c, f):
    return [min(1.0, c[0] * f), min(1.0, c[1] * f), min(1.0, c[2] * f), 1.0]


def make_mat(name, hexcol, rough=0.85, var=0.10, scale=9.0, edge=0.2, metal=0.0, grain=0.05,
             emit=0.0):
    base = srgb(hexcol)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = base
    nt = m.node_tree
    n, lk = nt.nodes, nt.links
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    tc = n.new("ShaderNodeTexCoord")
    n1 = n.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = scale
    n1.inputs["Detail"].default_value = 3.0
    lk.new(tc.outputs["Object"], n1.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.name = "PaintRamp"
    ramp.color_ramp.elements[0].position = 0.32
    ramp.color_ramp.elements[1].position = 0.68
    ramp.color_ramp.elements[0].color = scale_col(base, 1.0 - var)
    ramp.color_ramp.elements[1].color = scale_col(base, 1.0 + var)
    lk.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    n2 = n.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 160.0
    n2.inputs["Detail"].default_value = 1.0
    lk.new(tc.outputs["Object"], n2.inputs["Vector"])
    gm = n.new("ShaderNodeMixRGB")
    gm.blend_type = "OVERLAY"
    gm.inputs["Fac"].default_value = grain
    lk.new(ramp.outputs["Color"], gm.inputs["Color1"])
    lk.new(n2.outputs["Color"], gm.inputs["Color2"])
    geo = n.new("ShaderNodeNewGeometry")
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.52
    mr.inputs["From Max"].default_value = 0.62
    lk.new(geo.outputs["Pointiness"], mr.inputs["Value"])
    fac = n.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    fac.inputs[1].default_value = edge
    lk.new(mr.outputs["Result"], fac.inputs[0])
    em = n.new("ShaderNodeMixRGB")
    em.name = "EdgeMix"
    em.inputs["Color2"].default_value = scale_col(base, 1.45)
    lk.new(fac.outputs["Value"], em.inputs["Fac"])
    lk.new(gm.outputs["Color"], em.inputs["Color1"])
    lk.new(em.outputs["Color"], bsdf.inputs["Base Color"])
    if emit:
        bsdf.inputs["Emission Color"].default_value = base
        bsdf.inputs["Emission Strength"].default_value = emit
    return m


def recolor(m, hexcol, var=0.06):
    base = srgb(hexcol)
    ramp = m.node_tree.nodes["PaintRamp"]
    ramp.color_ramp.elements[0].color = scale_col(base, 1.0 - var)
    ramp.color_ramp.elements[1].color = scale_col(base, 1.0 + var)
    m.node_tree.nodes["EdgeMix"].inputs["Color2"].default_value = scale_col(base, 1.3)
    m.diffuse_color = base


SLOTS = {
    "01": make_mat("01_Fabric", "#6c6a4b", var=0.10, scale=8, edge=0.25, grain=0.08),
    "02": make_mat("02_Armor", "#4a503f", rough=0.75, var=0.10, scale=6, edge=0.45, grain=0.04),
    "03": make_mat("03_Webbing", "#7b6b4d", var=0.10, scale=9, edge=0.3, grain=0.10),
    "04": make_mat("04_RubberLeather", "#2c2a26", rough=0.8, var=0.08, edge=0.3, grain=0.05),
    "06": make_mat("06_Metal", "#6e6d64", rough=0.55, var=0.08, edge=0.5, metal=0.5, grain=0.0),
    "07": make_mat("07_TeamColor", TEAM_PREVIEW, rough=0.8, var=0.06, scale=8, edge=0.3,
                   grain=0.03),
    "08": make_mat("08_GlassLens", "#1f4752", rough=0.15, var=0.0, edge=0.0, grain=0.0),
    "09": make_mat("09_SquadEmblem", "#c8a23c", rough=0.8, var=0.05, edge=0.2, grain=0.0),
    "Wsteel": make_mat("Weapon | Graphite steel", "#3a3c3f", rough=0.5, var=0.08, edge=0.5,
                       metal=0.4, grain=0.0),
    "Wpoly": make_mat("Weapon | Olive polymer", "#4f5539", rough=0.7, var=0.08, edge=0.35,
                      grain=0.02),
    "Wgrip": make_mat("Weapon | Rubber grip", "#242322", rough=0.9, var=0.05, edge=0.2,
                      grain=0.1),
    "Wedge": make_mat("Weapon | Machined edges", "#8e8d87", rough=0.4, var=0.05, edge=0.4,
                      metal=0.8, grain=0.0),
    "Wcyan": make_mat("Weapon | Optic cyan", "#38d6e6", rough=0.2, var=0.0, edge=0.0,
                      grain=0.0, emit=1.5),
}


# ---------------------------------------------------------------------------
# low-poly mesh building
# ---------------------------------------------------------------------------
class MB:
    """Accumulates parts (each with one material) into one mesh."""

    def __init__(self):
        self.v, self.f, self.m = [], [], []

    def add(self, verts, faces, mat, inside=None):
        """mat: slot key or a list of slot keys per face. Normals are made consistent per part;
        `inside` (a point) orients open parts so they face away from it."""
        bm = bmesh.new()
        bv = [bm.verts.new(p) for p in verts]
        mats = mat if isinstance(mat, list) else [mat] * len(faces)
        keep = []
        for f, mk in zip(faces, mats):
            try:
                bf = bm.faces.new([bv[i] for i in f])
                bf.material_index = len(keep)
                keep.append(mk)
            except ValueError:
                pass
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        closed = all(e.is_manifold for e in bm.edges)
        if closed and inside is None:
            vol = sum(f.calc_center_median().dot(f.normal) * f.calc_area() for f in bm.faces)
            if vol < 0:  # inside-out (recalc can be fooled by thick, folded shells)
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
        if inside is not None:
            s = sum((f.normal.dot(f.calc_center_median() - inside)) * f.calc_area()
                    for f in bm.faces)
            if s < 0:
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.verts.index_update()
        off = len(self.v)
        self.v += [v.co.copy() for v in bm.verts]
        for bf in bm.faces:
            self.f.append([v.index + off for v in bf.verts])
            self.m.append(keep[bf.material_index])
        bm.free()
        return self

    def merge(self, other):
        off = len(self.v)
        self.v += [p.copy() for p in other.v]
        self.f += [[i + off for i in f] for f in other.f]
        self.m += list(other.m)
        return self

    def mirrored(self):
        o = MB()
        o.v = [Vector((-p.x, p.y, p.z)) for p in self.v]
        o.f = [list(reversed(f)) for f in self.f]
        o.m = list(self.m)
        return o

    def tris(self):
        return sum(len(f) - 2 for f in self.f)

    def bvh(self):
        return BVHTree.FromPolygons(self.v, self.f)

    def build(self, name, smooth_angle=40.0):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(p) for p in self.v], [], self.f)
        keys = []
        for k in self.m:
            if k not in keys:
                keys.append(k)
        for k in keys:
            me.materials.append(SLOTS[k])
        for p, k in zip(me.polygons, self.m):
            p.material_index = keys.index(k)
        me.validate()
        me.shade_smooth()
        try:
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
        except Exception:
            pass
        return bpy.data.objects.new(name, me)


def frame(t, ref):
    t = Vector(t).normalized()
    ref = Vector(ref)
    if abs(ref.normalized().dot(t)) > 0.97:
        ref = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 0, 1))
    v = (ref - t * ref.dot(t)).normalized()
    u = v.cross(t).normalized()
    return u, v, t


def rings_mesh(rings, segs, cap0=True, cap1=True, rot=0.0):
    """rings: (center, tangent|None, ref, ra, rb, n) -> superellipse tube with n-gon caps."""
    cs = [Vector(r[0]) for r in rings]
    verts, faces, idx = [], [], []
    for i, (c, t, ref, ra, rb, n) in enumerate(rings):
        if t is None:
            t = cs[min(i + 1, len(cs) - 1)] - cs[max(i - 1, 0)]
        u, v, _ = frame(t, ref)
        r = []
        for k in range(segs):
            a = 2 * math.pi * k / segs + rot
            ca, sa = math.cos(a), math.sin(a)
            x = math.copysign(abs(ca) ** (2.0 / n), ca) * ra
            y = math.copysign(abs(sa) ** (2.0 / n), sa) * rb
            r.append(len(verts))
            verts.append(Vector(c) + u * x + v * y)
        idx.append(r)
    for i in range(len(idx) - 1):
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append([idx[i][k], idx[i][k2], idx[i + 1][k2], idx[i + 1][k]])
    if cap0:
        faces.append(list(reversed(idx[0])))
    if cap1:
        faces.append(list(idx[-1]))
    return verts, faces


def cyl(p0, p1, r, segs=6, r1=None, ref=Z, rot=0.0):
    p0, p1 = Vector(p0), Vector(p1)
    t = p1 - p0
    return rings_mesh([(p0, t, ref, r, r, 2.0), (p1, t, ref, r1 or r, r1 or r, 2.0)], segs,
                      rot=rot)


def box(center, size, rot=None, chamfer=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if chamfer > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=chamfer, segments=1, profile=0.5,
                        affect="EDGES")
    m = Matrix.Translation(Vector(center))
    if rot is not None:
        m = m @ (rot.to_4x4() if len(rot) == 3 else rot)
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    bm.verts.index_update()
    verts = [v.co.copy() for v in bm.verts]
    faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    return verts, faces


def basis(nrm, up=Z):
    """rotation whose local Z = nrm (outward), local Y ~ up"""
    n = Vector(nrm).normalized()
    x = Vector(up).cross(n)
    if x.length < 1e-4:
        x = Vector((1, 0, 0))
    x.normalize()
    y = n.cross(x)
    return Matrix((x, y, n)).transposed()


def strap(points, ups, w, h):
    """flat rectangular strap through points; ups = surface normals (strap lies flat on them)"""
    pts = [Vector(p) for p in points]
    verts, faces, idx = [], [], []
    for i, p in enumerate(pts):
        t = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        u, v, _ = frame(t, ups[i])
        r = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            r.append(len(verts))
            verts.append(p + u * (sx * w / 2) + v * (sy * h / 2))
        idx.append(r)
    for i in range(len(idx) - 1):
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append([idx[i][k], idx[i][k2], idx[i + 1][k2], idx[i + 1][k]])
    faces.append(list(reversed(idx[0])))
    faces.append(list(idx[-1]))
    return verts, faces


def torus(center, axis, R, r, segs=8, sides=4):
    u, v, t = frame(axis, Z if abs(Vector(axis).z) < 0.9 else X)
    verts, faces = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        c = Vector(center) + (u * math.cos(a) + v * math.sin(a)) * R
        radial = (u * math.cos(a) + v * math.sin(a))
        for j in range(sides):
            b = 2 * math.pi * j / sides + math.pi / sides
            verts.append(c + radial * (r * math.cos(b)) + t * (r * math.sin(b)))
    for i in range(segs):
        for j in range(sides):
            i2, j2 = (i + 1) % segs, (j + 1) % sides
            faces.append([i * sides + j, i2 * sides + j, i2 * sides + j2, i * sides + j2])
    return verts, faces


# ---------------------------------------------------------------------------
# surface fitting: rays from outside find the OUTERMOST surface; an envelope (max over
# neighbouring rays) makes hard pieces rest on pockets/buttons instead of following them
# ---------------------------------------------------------------------------
def bvh_of(*things):
    verts, polys = [], []
    for t in things:
        off = len(verts)
        if isinstance(t, MB):
            verts += [p.copy() for p in t.v]
            polys += [[i + off for i in f] for f in t.f]
        else:
            mw = t.matrix_world
            verts += [mw @ v.co for v in t.data.vertices]
            polys += [[i + off for i in p.vertices] for p in t.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def hit(bvh, origin, direction):
    d = Vector(direction).normalized()
    loc, nrm, _, dist = bvh.ray_cast(Vector(origin), d)
    return loc, nrm, dist


def cast_grid(bvh, ray_fn, nu, nv, env=0.0, closed_u=False):
    cols = nu if closed_u else nu + 1
    P, D = [], []
    for j in range(nv + 1):
        rp, rd, dists = [], [], []
        for i in range(cols):
            u, v = i / nu, j / nv
            o, d = ray_fn(u, v)
            best = None
            offs = [(0.0, 0.0)]
            if env > 0:
                offs = [(a * env / nu, b * env / nv) for a in (-1, 0, 1) for b in (-1, 0, 1)]
            for du, dv in offs:
                uu = u + du if closed_u else min(1.0, max(0.0, u + du))
                vv = min(1.0, max(0.0, v + dv))
                o2, d2 = ray_fn(uu, vv)
                _, _, dist = hit(bvh, o2, d2)
                if dist is not None and (best is None or dist < best):
                    best = dist
            dists.append(best)
            rp.append(o)
            rd.append(Vector(d).normalized())
        known = [x for x in dists if x is not None]
        fill = sum(known) / len(known) if known else 0.0
        P.append([o + d * (x if x is not None else fill) for o, d, x in zip(rp, rd, dists)])
        D.append(rd)
    return P, D


def shell(P, D, thick, lift=0.002, closed_u=False, single=False, mat="03", mat_fn=None):
    """Thicken a fitted grid outward (against the ray direction). thick(u, v) -> metres.
    single=True: outer skin + side skirt only (no hidden inner face)."""
    nv = len(P) - 1
    cols = len(P[0])
    nu = cols if closed_u else cols - 1
    verts, faces, mats = [], [], []
    oi = [[0] * cols for _ in range(nv + 1)]
    ii = [[0] * cols for _ in range(nv + 1)]
    for j in range(nv + 1):
        for i in range(cols):
            out = -D[j][i]
            oi[j][i] = len(verts)
            verts.append(P[j][i] + out * (lift + thick(i / nu, j / nv)))
            ii[j][i] = len(verts)
            verts.append(P[j][i] + out * lift)

    def tag(kind, i, j):
        return mat_fn(kind, i, j) if mat_fn else mat
    ulim = cols if closed_u else cols - 1
    for j in range(nv):
        for i in range(ulim):
            i2 = (i + 1) % cols
            faces.append([oi[j][i], oi[j][i2], oi[j + 1][i2], oi[j + 1][i]])
            mats.append(tag("outer", i, j))
            if not single:
                faces.append([ii[j][i], ii[j + 1][i], ii[j + 1][i2], ii[j][i2]])
                mats.append(tag("inner", i, j))
    for i in range(ulim):
        i2 = (i + 1) % cols
        faces.append([oi[0][i], ii[0][i], ii[0][i2], oi[0][i2]])
        mats.append(tag("bottom", i, 0))
        faces.append([oi[nv][i], oi[nv][i2], ii[nv][i2], ii[nv][i]])
        mats.append(tag("top", i, nv))
    if not closed_u:
        for j in range(nv):
            faces.append([oi[j][0], oi[j + 1][0], ii[j + 1][0], ii[j][0]])
            mats.append(tag("left", 0, j))
            faces.append([oi[j][cols - 1], ii[j][cols - 1], ii[j + 1][cols - 1],
                          oi[j + 1][cols - 1]])
            mats.append(tag("right", cols - 1, j))
    return verts, faces, mats


def pillow(t_edge, t_mid, width=0.25, closed_u=False):
    def f(u, v):
        e = min(v, 1 - v) if closed_u else min(u, 1 - u, v, 1 - v)
        return t_edge + (t_mid - t_edge) * smoothstep(0.0, width, e)
    return f


def planar_rays(x0, x1, z0, z1, side, xscale=None, far=1.0):
    """rays travelling along +-Y (side=-1: from the front, +1: from the back)"""
    d = Vector((0, -side, 0))

    def fn(u, v):
        z = lerp(z0, z1, v)
        s = xscale(v) if xscale else 1.0
        xc = (x0 + x1) / 2
        x = xc + (lerp(x0, x1, u) - xc) * s
        return Vector((x, side * far, z)), d
    return fn


def top_rays(x0, x1, y0, y1, ztop=2.5):
    def fn(u, v):
        return Vector((lerp(x0, x1, u), lerp(y0, y1, v), ztop)), -Z
    return fn


def wrap_rays(origin, axis, ref, a0, a1, h0, h1, R=0.45):
    axis = Vector(axis).normalized()
    ref = Vector(ref)
    ref = (ref - axis * ref.dot(axis)).normalized()
    side = axis.cross(ref)
    origin = Vector(origin)

    def fn(u, v):
        a = lerp(a0, a1, u)
        h = lerp(h0, h1, v)
        out = ref * math.cos(a) + side * math.sin(a)
        return origin + axis * h + out * R, -out
    return fn


def on_surface(bvh, origin, direction, off=0.0):
    loc, nrm, _ = hit(bvh, origin, direction)
    if loc is None:
        raise RuntimeError("ray missed: %s %s" % (tuple(origin), tuple(direction)))
    return loc + nrm * off, nrm


def strap_over(bvh, rays, w, h, gap=0.002):
    pts, ups = [], []
    for o, d in rays:
        p, n = on_surface(bvh, o, d, gap + h / 2)
        pts.append(p)
        ups.append(n)
    return strap(pts, ups, w, h)


# ---------------------------------------------------------------------------
# scene organisation
# ---------------------------------------------------------------------------
GEAR = bpy.data.collections.new("Gear")
scene.collection.children.link(GEAR)
COLS = {}
for key, title in (("head", "Gear_01_Head"), ("torso", "Gear_02_Torso"),
                   ("arms", "Gear_03_Arms"), ("back", "Gear_04_Back"),
                   ("belt", "Gear_05_Belt_Legs"), ("weapon", "Gear_06_Weapons"),
                   ("accent", "Gear_07_Accents")):
    c = bpy.data.collections.new(title)
    GEAR.children.link(c)
    COLS[key] = c

ITEMS = {}  # name -> dict(obj, id, bone, budget)


def attach(ob, bone_name):
    """pivot = bone head, mesh in character axes, Parent -> Bone without weights"""
    b = arm.data.bones[bone_name]
    head = arm.matrix_world @ b.head_local
    ob.data.transform(Matrix.Translation(-head))
    ob.parent = arm
    ob.parent_type = "BONE"
    ob.parent_bone = bone_name
    pm = arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = pm.inverted() @ Matrix.Translation(head)


def add_item(item_id, name, mb, bone, slot, budget, mirror_to=None):
    out = []
    for nm, m, bn in ((name, mb, bone),) + ((
            (mirror_to[0], mb.mirrored(), mirror_to[1]),) if mirror_to else ()):
        ob = m.build(nm)
        COLS[slot].objects.link(ob)
        attach(ob, bn)
        ITEMS[nm] = dict(obj=ob, id=item_id, bone=bn, budget=budget, tris=m.tris(), mb=m)
        out.append(ob)
        print("%-4s %-28s %-12s %4d tris (budget %d-%d)" % (item_id, nm, bn, m.tris(), *budget))
    return out


BODY_BVH = bvh_of(*BODY.values())
HEAD_BVH = bvh_of(BODY["Soldier_Body"], BODY["Soldier_Hair"])
REST_PTS = [ob.matrix_world @ v.co for ob in BODY.values() for v in ob.data.vertices]
REST_KD = KDTree(len(REST_PTS))
for _i, _p in enumerate(REST_PTS):
    REST_KD.insert(_p, _i)
REST_KD.balance()


def bbox(pts, pad=0.0):
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo - Vector((pad,) * 3), hi + Vector((pad,) * 3)


def inside_box(p, lo, hi):
    return lo.x <= p.x <= hi.x and lo.y <= p.y <= hi.y and lo.z <= p.z <= hi.z


WORST_AT = [None]


RAY_DIRS = (Vector((0.267, 0.534, 0.802)).normalized(), Vector((-0.577, 0.211, -0.789)).normalized())


def is_inside(bvh, p):
    """point-in-closed-mesh by ray parity (two directions must agree)"""
    for d in RAY_DIRS:
        o, c = p, 0
        for _ in range(32):
            loc, _, _, _ = bvh.ray_cast(o, d)
            if loc is None:
                break
            c += 1
            o = loc + d * 1e-5
        if c % 2 == 0:
            return False
    return True


def depth_inside(points, bvh, lo, hi, idx=False):
    """deepest of `points` lying inside the closed surfaces in `bvh` (metres, up to 6 cm)"""
    worst, hits = 0.0, []
    for i, p in enumerate(points):
        if not inside_box(p, lo, hi):
            continue
        loc, _, _, dist = bvh.find_nearest(p, 0.06)
        if loc is None or dist < 1e-4 or not is_inside(bvh, p):
            continue
        if dist > worst:
            worst = dist
            if idx:
                WORST_AT[0] = p.copy()
        if idx and dist > 0.002:
            hits.append(i)
    return (worst, hits) if idx else worst


def penetration(part, extra=()):
    """how deep the rest-pose body (and `extra` gear) pokes into `part`"""
    lo, hi = bbox(part.v, 0.004)
    c, r = (lo + hi) / 2, (hi - lo).length / 2
    pts = [REST_PTS[i] for _, i, _ in REST_KD.find_range(c, r)]
    for e in extra:
        pts += e.v
    worst = depth_inside(pts, part.bvh(), lo, hi)
    for e in extra:  # and the piece poking into the gear it rests on
        worst = max(worst, depth_inside(part.v, e.bvh(), *bbox(e.v, 0.004)))
    return worst


def fitted(make, lift, mat=None, extra=(), tol=0.0006, tries=7):
    """build a fitted piece, raising it off the surface until nothing pokes through
    (straight edges between ray samples otherwise cut into curved surfaces)"""
    part = None
    for _ in range(tries):
        out = make(lift)
        part = MB().add(out[0], out[1], out[2] if mat is None else mat)
        pen = penetration(part, extra)
        if pen < tol:
            break
        lift += pen + 0.0015
    else:
        print("fitted: residual %.1f mm (lift %.1f mm)" % (pen * 1000, lift * 1000))
    return part


def sphere_rays(center, t0, t1, w0, w1, R=0.5):
    """rays toward `center`: t = angle over the top (front +), w = sideways angle"""
    center = Vector(center)

    def fn(u, v):
        t, w = lerp(t0, t1, v), lerp(w0, w1, u)
        d = Vector((math.sin(w), -math.sin(t) * math.cos(w), math.cos(t) * math.cos(w)))
        return center + d * R, -d
    return fn


# ===========================================================================
# H1  mod_head_helmet_basic  (head)
# ===========================================================================
def build_helmet():
    mb = MB()
    # one closed thick dome: inner surface (top->rim) then outer surface (rim->top)
    R = [  # z, rx, ry, cy
        (1.832, 0.084, 0.100, 0.010),
        (1.790, 0.113, 0.135, 0.008),
        (1.735, 0.118, 0.140, 0.006),
        (1.712, 0.121, 0.143, 0.006),
        (1.698, 0.130, 0.152, 0.006),
        (1.735, 0.133, 0.155, 0.006),
        (1.786, 0.127, 0.149, 0.008),
        (1.829, 0.106, 0.126, 0.010),
        (1.858, 0.066, 0.080, 0.010),
    ]
    v, f = rings_mesh([((0, cy, z), Z, FRONT, rx, ry, 2.0) for z, rx, ry, cy in R], 16)
    for p in v:  # rim higher at the brow, lower at the nape
        w = max(0.0, min(1.0, (1.76 - p.z) / 0.06))
        p.z += -0.10 * p.y * w
    shell_mb = MB().add(v, f, "01")
    mb.merge(shell_mb)
    # team-colour band over the crown, brow to nape: the RTS camera sees the top of the head
    P, D = cast_grid(shell_mb.bvh(), sphere_rays((0, 0.008, 1.70), -1.0, 1.05, -0.21, 0.21), 2, 6)
    mb.add(*shell(P, D, lambda u, v: 0.004, lift=0.0008)[:2], "07")
    # chin strap hugging the face
    pts = [(0.121, 0.012, 1.712), (0.112, -0.006, 1.660), (0.096, -0.030, 1.605),
           (0.066, -0.052, 1.560), (0.030, -0.066, 1.538), (0.0, -0.070, 1.533)]
    full = pts + [(-x, y, z) for x, y, z in reversed(pts[:-1])]
    P2, U2 = [], []
    for p in full:
        p = Vector(p)
        loc, nrm, _, _ = HEAD_BVH.find_nearest(p)
        if (p - loc).dot(nrm) < 0.007:
            p = loc + nrm * 0.007
        P2.append(p)
        U2.append(nrm)
    mb.add(*strap(P2, U2, 0.014, 0.004), "04")
    return mb


add_item("H1", "mod_head_helmet_basic", build_helmet(), "head", "head", (300, 450))

# ===========================================================================
# T2  mod_torso_plate_carrier  (chest)
# Bottom edge kept at 1.15 m: when the spine bends to aim down it must not reach the belt.
# ===========================================================================
T_BOTTOM = 1.15


def plate_shape(v):
    return 1.0 - 0.32 * smoothstep(0.55, 1.0, v)   # cut top corners like a SAPI plate


def plate(side, z1):
    rays = planar_rays(-0.125, 0.125, T_BOTTOM, z1, side, plate_shape)
    return fitted(lambda lift: shell(*cast_grid(BODY_BVH, rays, 4, 4, env=0.7),
                                     pillow(0.013, 0.030, 0.2), lift=lift), 0.006, "02")


def build_plate_carrier():
    mb = MB()
    front, back = plate(-1, 1.40), plate(1, 1.42)
    mb.merge(front).merge(back)
    # cummerbund between the plates
    for s in (1, -1):
        a0, a1 = (0.98, math.pi - 0.98) if s > 0 else (-math.pi + 0.98, -0.98)
        rays = wrap_rays((0, 0, 0), Z, FRONT, a0, a1, T_BOTTOM + 0.01, 1.28)
        mb.merge(fitted(lambda lift: shell(*cast_grid(BODY_BVH, rays, 3, 1, env=0.5),
                                           lambda u, v: 0.010, lift=lift), 0.004, "03"))
    # shoulder straps
    fit = bvh_of(BODY["Soldier_Body"], front, back)
    for s in (1, -1):
        x = 0.118 * s
        rays = [((x, -1, 1.375), Y), ((x, -1, 1.43), Y)]
        rays += [((x, y, 2.5), -Z) for y in (-0.075, -0.035, 0.005, 0.045, 0.08)]
        rays += [((x, 1, 1.44), -Y), ((x, 1, 1.395), -Y)]
        mb.merge(fitted(lambda g: strap_over(fit, rays, 0.034, 0.008, gap=g), 0.005, "03",
                        extra=(front, back)))
    pb = front.bvh()
    # three rifle magazine pouches
    for x in (-0.074, 0.0, 0.074):
        p, n = on_surface(pb, (x, -1, 1.205), Y)
        c = p + Vector((0, -0.024, 0))
        mb.add(*box(c, (0.064, 0.044, 0.090), chamfer=0.008), "03")
        mb.add(*box(c + Vector((0, -0.002, 0.047)), (0.068, 0.050, 0.026)), "03")
    # radio pouch + antenna stub (upper left chest)
    p, n = on_surface(pb, (0.068, -1, 1.335), Y)
    c = p + Vector((0, -0.021, 0))
    mb.add(*box(c, (0.052, 0.040, 0.090), chamfer=0.007), "03")
    mb.add(*box(c + Vector((0, -0.001, 0.049)), (0.042, 0.032, 0.014)), "06")
    mb.add(*cyl(c + Vector((0.012, 0.004, 0.055)), c + Vector((0.016, 0.004, 0.145)), 0.0055,
                segs=4, r1=0.004), "04")
    # squad emblem tab (upper right chest)
    p, n = on_surface(pb, (-0.062, -1, 1.36), Y)
    mb.add(*box(p + Vector((0, -0.003, 0)), (0.064, 0.005, 0.032)), "09")
    return mb


add_item("T2", "mod_torso_plate_carrier", build_plate_carrier(), "chest", "torso", (450, 700))

# ===========================================================================
# T1  mod_torso_chest_rig  (chest)
# ===========================================================================
def build_chest_rig():
    mb = MB()
    rays = planar_rays(-0.135, 0.135, T_BOTTOM, 1.30, -1)
    panel = fitted(lambda lift: shell(*cast_grid(BODY_BVH, rays, 4, 2, env=0.7),
                                      pillow(0.006, 0.011, 0.2), lift=lift), 0.005, "03")
    mb.merge(panel)
    rays_b = wrap_rays((0, 0, 0), Z, FRONT, 0.98, 2 * math.pi - 0.98, T_BOTTOM + 0.008,
                       T_BOTTOM + 0.043)
    band = fitted(lambda lift: shell(*cast_grid(BODY_BVH, rays_b, 8, 1, env=0.5),
                                     lambda u, v: 0.007, lift=lift), 0.004, "03")
    mb.merge(band)
    fit = bvh_of(BODY["Soldier_Body"], panel, band)
    for s in (1, -1):
        x = 0.118 * s
        rays = [((x, -1, 1.285), Y), ((x, -1, 1.36), Y)]
        rays += [((x, y, 2.5), -Z) for y in (-0.06, -0.02, 0.02, 0.06)]
        rays += [((x * 0.95, 1, 1.40), -Y), ((x * 0.85, 1, 1.30), -Y), ((x * 0.8, 1, 1.22), -Y),
                 ((x * 0.8, 1, T_BOTTOM + 0.025), -Y)]
        mb.merge(fitted(lambda g: strap_over(fit, rays, 0.032, 0.006, gap=g), 0.005, "03",
                        extra=(panel, band)))
    pb = panel.bvh()
    for x in (-0.066, 0.0, 0.066):
        p, n = on_surface(pb, (x, -1, 1.235), Y)
        c = p + Vector((0, -0.022, 0.0))
        mb.add(*box(c, (0.058, 0.042, 0.100), chamfer=0.008), "03")
        mb.add(*box(c + Vector((0, -0.002, 0.052)), (0.062, 0.048, 0.024)), "03")
    return mb


add_item("T1", "mod_torso_chest_rig", build_chest_rig(), "chest", "torso", (300, 500))

# ===========================================================================
# A1  mod_arm_patch.L/.R  (upper_arm) - team colour on the outer upper arm (faces up)
# ===========================================================================
def build_arm_patch():
    rays = wrap_rays((0, 0, ARM_Z), X, Z, -0.38, 0.88, 0.272, 0.364)
    return fitted(lambda lift: shell(*cast_grid(BODY_BVH, rays, 2, 2, env=0.5),
                                     pillow(0.004, 0.007, 0.3), lift=lift), 0.002, "07")


add_item("A1", "mod_arm_patch.L", build_arm_patch(), "upper_arm.L", "arms", (20, 40),
         mirror_to=("mod_arm_patch.R", "upper_arm.R"))

# ===========================================================================
# P1  mod_belt_pouches  (pelvis)
# Belt real estate, angle from the front (left side; mirrored on the right):
#   0-0.33 buckle | 0.33-0.9 free: the vest/rig front swings down here when aiming down
#   1.08 grenade, 1.36 smoke (P3) | 1.74, 2.20 pouches (P1) | back centre free: pack swing zone
# ===========================================================================
BELT_Z0, BELT_Z1 = 1.026, 1.082
P1_POUCH_ANGLES = (1.74, 2.20)


def build_belt_pouches():
    mb = MB()
    rays = wrap_rays((0, 0, 0), Z, FRONT, 0.33, 2 * math.pi - 0.33, BELT_Z0, BELT_Z1)
    belt = fitted(lambda lift: shell(*cast_grid(BODY_BVH, rays, 12, 1, env=0.4),
                                     lambda u, v: 0.013, lift=lift), 0.005, "03")
    mb.merge(belt)
    bb = belt.bvh()
    p, n = on_surface(BODY_BVH, (0, -1, 1.054), Y)   # front buckle closing the gap
    mb.add(*box(p + Vector((0, -0.012, 0)), (0.066, 0.016, 0.050)), "06")
    for s in (1, -1):
        for a in P1_POUCH_ANGLES:
            a *= s
            out = Vector((math.sin(a), -math.cos(a), 0))
            p, n = on_surface(bb, out * 0.5 + Vector((0, 0, 1.06)), -out)
            rot = basis(out)
            c = p + out * 0.026 + Vector((0, 0, -0.012))
            mb.add(*box(c, (0.064, 0.088, 0.048), rot=rot, chamfer=0.008), "03")
            mb.add(*box(c + Vector((0, 0, 0.042)) + out * 0.003, (0.068, 0.024, 0.054),
                        rot=rot), "03")
    return mb, belt


p1, P1_BELT = build_belt_pouches()
add_item("P1", "mod_belt_pouches", p1, "pelvis", "belt", (200, 350))

# ===========================================================================
# P3  mod_belt_grenades  (pelvis)
# Short sleeves wrap the trouser belt AND enclose P1's belt, so P3 works with or without P1
# (P1's belt passes hidden inside the sleeves).
# ===========================================================================
def build_grenades():
    mb = MB()
    p1b = P1_BELT.bvh()
    for s in (1, -1):
        for a, kind in ((1.08, "frag"), (1.36, "smoke")):
            a *= s
            out = Vector((math.sin(a), -math.cos(a), 0))
            rays = wrap_rays((0, 0, 0), Z, FRONT, a - 0.12, a + 0.12, BELT_Z0 - 0.007,
                             BELT_Z1 + 0.007)
            P, D = cast_grid(BODY_BVH, rays, 2, 1)
            base_r = min(Vector((p.x, p.y, 0)).length for row in P for p in row)
            # outer radius of P1's belt here (the sleeve must close over it)
            r_p1 = max(Vector((q.x, q.y, 0)).length for q in
                       (on_surface(p1b, out * 0.5 + Vector((0, 0, z)) +
                                   Vector((out.y, -out.x, 0)) * w, -out)[0]
                        for z in (1.03, 1.054, 1.078) for w in (-0.02, 0.0, 0.02)))

            def make(lift, P=P, D=D, base_r=base_r, r_p1=r_p1):
                return shell(P, D, lambda u, v: max(0.006, r_p1 + 0.004 - base_r - lift),
                             lift=lift)
            sleeve = fitted(make, 0.006, "03")
            mb.merge(sleeve)
            p, n = on_surface(sleeve.bvh(), out * 0.5 + Vector((0, 0, 1.055)), -out)
            if kind == "frag":
                c = p + out * 0.030 + Vector((0, 0, 0.0))
                mb.add(*cyl(c - Z * 0.032, c + Z * 0.030, 0.029, segs=6, ref=out), "06")
                mb.add(*cyl(c + Z * 0.030, c + Z * 0.050, 0.012, segs=4, ref=out), "06")
                mb.add(*box(c + Z * 0.010 + out * 0.031, (0.012, 0.006, 0.05),
                            rot=basis(out)), "06")
            else:
                c = p + out * 0.028 + Vector((0, 0, 0.006))
                mb.add(*cyl(c - Z * 0.042, c + Z * 0.040, 0.026, segs=6, ref=out), "06")
                mb.add(*cyl(c + Z * 0.040, c + Z * 0.066, 0.028, segs=6, ref=out), "07")
    return mb


add_item("P3", "mod_belt_grenades", build_grenades(), "pelvis", "belt", (120, 250))

# ===========================================================================
# L1  mod_knee.L/.R  (shin)
# ===========================================================================
def build_knee():
    mb = MB()
    r1 = wrap_rays(HIP, LEG_AXIS, FRONT, -1.0, 1.0, leg_h(0.595), leg_h(0.448), R=0.13)
    mb.merge(fitted(lambda lift: shell(*cast_grid(BODY_BVH, r1, 3, 3, env=0.6),
                                       pillow(0.010, 0.024, 0.3), lift=lift), 0.003, "02"))
    r2 = wrap_rays(HIP, LEG_AXIS, FRONT, 0.95, 2 * math.pi - 0.95, leg_h(0.488), leg_h(0.466),
                   R=0.13)
    mb.merge(fitted(lambda lift: shell(*cast_grid(BODY_BVH, r2, 4, 1, env=0.4),
                                       lambda u, v: 0.005, lift=lift), 0.002, "04"))
    return mb


add_item("L1", "mod_knee.L", build_knee(), "shin.L", "belt", (60, 120),
         mirror_to=("mod_knee.R", "shin.R"))

# ===========================================================================
# B1 / B3 packs (chest). Bottom at 1.16 m: leaning back to aim up swings the pack bottom down
# toward the belt, so it needs room above the P1 rear pouches.
# ===========================================================================
PACK_BOTTOM = 1.16


def pack_mat(kind, i, j, nv):
    return "07" if kind == "top" or (kind == "outer" and j == nv - 1) else "01"


def build_pack(under, x_half, z1, depth, nu=4, nv=5):
    fit = bvh_of(BODY["Soldier_Body"], *under)
    rays = planar_rays(-x_half, x_half, PACK_BOTTOM, z1, 1,
                       xscale=lambda v: 1.0 - 0.22 * smoothstep(0.55, 1.0, v))
    grid = cast_grid(fit, rays, nu, nv, env=0.7)
    pack = fitted(lambda lift: shell(*grid, pillow(depth * 0.5, depth, 0.3), lift=lift,
                                     mat_fn=lambda k, i, j: pack_mat(k, i, j, nv)), 0.008,
                  extra=under)
    return pack, fit


def pack_straps(mb, fit, under, x, front_z):
    for s in (1, -1):
        rays = [((x * s, 1, 1.452), -Y)]
        rays += [((x * s, y, 2.5), -Z) for y in (0.06, 0.02, -0.02, -0.06)]
        rays += [((x * s, -1, z), Y) for z in front_z]
        mb.merge(fitted(lambda g: strap_over(fit, rays, 0.028, 0.006, gap=g), 0.004, "03",
                        extra=under))


def build_pack_small():
    t2 = ITEMS["mod_torso_plate_carrier"]["mb"]
    mb, fit = build_pack([t2], 0.140, 1.44, 0.16)
    pk = mb.bvh()
    p, n = on_surface(pk, (0, 1, 1.25), -Y)
    mb.add(*box(p + Vector((0, 0.016, 0)), (0.20, 0.034, 0.10), chamfer=0.01), "03")
    p, n = on_surface(pk, (0, 0.2, 2.5), -Z)
    mb.add(*box(p + Vector((0, 0, 0.008)), (0.07, 0.016, 0.014)), "03")  # grab handle
    pack_straps(mb, fit, [t2], 0.118, (1.39, 1.33))
    return mb


add_item("B1", "mod_back_pack_small", build_pack_small(), "chest", "back", (250, 400))


def build_pack_engineer():
    t1 = ITEMS["mod_torso_chest_rig"]["mb"]
    mb, fit = build_pack([t1], 0.165, 1.455, 0.20)
    pk = mb.bvh()
    # shovel on the left side of the pack, kept toward the back (clear of the swinging arm)
    p, n = on_surface(pk, (1, 0.27, 1.23), -X)
    sx = p.x + 0.010
    mb.add(*box((sx, 0.27, 1.225), (0.012, 0.120, 0.14), chamfer=0.004), "06")
    mb.add(*cyl((sx + 0.002, 0.27, 1.295), (sx + 0.002, 0.27, 1.445), 0.0135, segs=6, ref=X),
           "04")
    mb.add(*box((sx + 0.002, 0.27, 1.452), (0.026, 0.07, 0.022)), "04")
    # cable coil, upper right of the back face
    p, n = on_surface(pk, (-0.075, 1, 1.36), -Y)
    mb.add(*torus(p + Vector((0, 0.020, 0)), Y, 0.056, 0.017, segs=8, sides=4), "04")
    # tool box, lower back face
    p, n = on_surface(pk, (0.0, 1, 1.225), -Y)
    c = p + Vector((0, 0.040, 0))
    mb.add(*box(c, (0.17, 0.08, 0.090), chamfer=0.008), "06")
    mb.add(*box(c + Vector((0, 0, 0.053)), (0.07, 0.014, 0.016)), "04")
    pack_straps(mb, fit, [t1], 0.118, (1.40, 1.33))
    return mb


add_item("B3", "mod_back_engineer", build_pack_engineer(), "chest", "back", (400, 600))

# ===========================================================================
# W1 mod_wpn_rifle (weapon) + W1m mod_mag_rifle (magazine)
# Built in weapon space: pivot = pistol grip (where the right hand holds it), barrel -Y
# (= +Z after glTF export), up +Z. ~15-20 % thicker than a real AK.
# ===========================================================================
def build_rifle():
    mb = MB()
    W = 0.050  # receiver width (real ~0.04)
    mb.add(*box((0, -0.075, 0.085), (W, 0.30, 0.070), chamfer=0.008), "Wsteel")       # receiver
    mb.add(*rings_mesh([((0, 0.062, 0.115), -Y, Z, W * 0.48, 0.018, 2.0),
                        ((0, -0.200, 0.115), -Y, Z, W * 0.48, 0.018, 2.0)], 6), "Wsteel")  # cover
    mb.add(*box((0, 0.012, -0.002), (0.036, 0.042, 0.115),
                rot=Matrix.Rotation(-0.30, 3, "X"), chamfer=0.006), "Wgrip")             # grip
    mb.add(*box((0, -0.045, 0.030), (0.012, 0.075, 0.012)), "Wsteel")                 # guard
    mb.add(*box((0, -0.265, 0.088), (0.058, 0.165, 0.058), chamfer=0.010), "Wpoly")   # handguard
    mb.add(*cyl((0, -0.200, 0.128), (0, -0.370, 0.128), 0.015, segs=6, ref=Z), "Wpoly")  # gas tube
    mb.add(*cyl((0, -0.345, 0.092), (0, -0.560, 0.092), 0.012, segs=6, ref=Z), "Wsteel")  # barrel
    mb.add(*box((0, -0.520, 0.110), (0.022, 0.030, 0.050)), "Wsteel")                 # front sight
    mb.add(*cyl((0, -0.560, 0.092), (0, -0.610, 0.092), 0.018, segs=6, ref=Z), "Wedge")  # brake
    mb.add(*rings_mesh([((0, 0.075, 0.098), -Y, Z, 0.022, 0.026, 3.0),
                        ((0, 0.170, 0.080), -Y, Z, 0.022, 0.040, 3.0),
                        ((0, 0.255, 0.062), -Y, Z, 0.024, 0.060, 3.0)], 6, rot=math.pi / 6),
           "Wpoly")                                                                   # stock
    mb.add(*box((0, 0.265, 0.062), (0.050, 0.020, 0.124)), "Wgrip")                   # butt pad
    mb.add(*box((0.027, -0.010, 0.100), (0.006, 0.090, 0.012)), "Wedge")              # selector
    mb.add(*box((-0.030, -0.140, 0.112), (0.020, 0.012, 0.010)), "Wedge")             # charger
    # red-dot sight
    mb.add(*box((0, -0.090, 0.138), (0.036, 0.070, 0.012)), "Wsteel")
    mb.add(*cyl((0, -0.055, 0.170), (0, -0.125, 0.170), 0.024, segs=8, ref=Z), "Wsteel")
    for y in (-0.0545, -0.1255):
        mb.add(*cyl((0, y, 0.170), (0, y + (0.001 if y > -0.1 else -0.001), 0.170), 0.019,
                    segs=8, ref=Z), "Wcyan")
    return mb


def build_mag():
    path = [(0, -0.130, 0.058), (0, -0.134, 0.005), (0, -0.150, -0.045), (0, -0.178, -0.092),
            (0, -0.214, -0.132)]
    rings = [(p, None, Y, 0.024, 0.052 if i < 4 else 0.050, 2.0) for i, p in enumerate(path)]
    v, f = rings_mesh(rings, 4, rot=math.pi / 4)
    mb = MB().add(v, f, "Wsteel")
    mb.add(*box((0, -0.220, -0.140), (0.038, 0.060, 0.014),
                rot=Matrix.Rotation(-0.70, 3, "X")), "Wedge")                         # base plate
    return mb


WPN_HEAD = arm.matrix_world @ arm.data.bones["weapon"].head_local
rifle = build_rifle()
rifle.v = [p + WPN_HEAD for p in rifle.v]
add_item("W1", "mod_wpn_rifle", rifle, "weapon", "weapon", (400, 700))
mag = build_mag()
mag.v = [p + WPN_HEAD for p in mag.v]  # sits in the rifle's mag well; pivot = `magazine` bone
add_item("W1m", "mod_mag_rifle", mag, "magazine", "weapon", (40, 80))


# ---------------------------------------------------------------------------
# UVs: one shared atlas for all gear
# ---------------------------------------------------------------------------
gear_objs = [it["obj"] for it in ITEMS.values()]
bpy.ops.object.select_all(action="DESELECT")
for ob in gear_objs:
    ob.select_set(True)
bpy.context.view_layer.objects.active = gear_objs[0]
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.006)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")

# ---------------------------------------------------------------------------
# loadouts, poses, clipping test
# ---------------------------------------------------------------------------
LOADOUTS = {
    "motor_rifle": ["mod_head_helmet_basic", "mod_torso_plate_carrier", "mod_arm_patch.L",
                    "mod_arm_patch.R", "mod_back_pack_small", "mod_belt_pouches", "mod_knee.L",
                    "mod_knee.R", "mod_wpn_rifle", "mod_mag_rifle"],
    "engineer": ["mod_head_helmet_basic", "mod_torso_chest_rig", "mod_arm_patch.L",
                 "mod_arm_patch.R", "mod_back_engineer", "mod_belt_pouches",
                 "mod_belt_grenades"],
}


def show(names, body=True):
    for nm, it in ITEMS.items():
        vis = nm in names
        it["obj"].hide_render = not vis
        it["obj"].hide_viewport = not vis
    for ob in BODY.values():
        ob.hide_render = not body
        ob.hide_viewport = not body


def upd():
    bpy.context.view_layer.update()


def reset_pose():
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    upd()


def rot_world(name, axis, deg):
    upd()
    pb = arm.pose.bones[name]
    m = pb.matrix.copy()
    h = m.translation.copy()
    pb.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, axis) @ \
        Matrix.Translation(-h) @ m
    upd()


def aim(name, target):
    upd()
    pb = arm.pose.bones[name]
    cur = (pb.tail - pb.head)
    want = Vector(target) - pb.head
    q = cur.rotation_difference(want).to_matrix().to_4x4()
    h = pb.head.copy()
    pb.matrix = Matrix.Translation(h) @ q @ Matrix.Translation(-h) @ pb.matrix
    upd()


def two_bone(upper, lower, wrist, pole):
    """analytic 2-bone IK: aim upper/lower so the wrist reaches `wrist`, elbow toward `pole`"""
    upd()
    a = arm.pose.bones[upper].length
    b = arm.pose.bones[lower].length
    s = arm.pose.bones[upper].head.copy()
    w = Vector(wrist)
    d = w - s
    L = min(d.length, (a + b) * 0.999)
    dn = d.normalized()
    x = (a * a - b * b + L * L) / (2 * L)
    hgt = math.sqrt(max(a * a - x * x, 0.0))
    pv = Vector(pole) - s
    pv = (pv - dn * pv.dot(dn)).normalized()
    elbow = s + dn * x + pv * hgt
    aim(upper, elbow)
    aim(lower, s + dn * L)


def move_weapon(grip):
    """put the weapon bone's head at `grip`, keeping the rifle level and pointing forward"""
    upd()
    pb = arm.pose.bones["weapon"]
    pb.matrix = Matrix.Translation(Vector(grip)) @ pb.bone.matrix_local.to_3x3().to_4x4()
    upd()


# ---------------------------------------------------------------------------
# AIM OFFSET (engine mechanic: the soldier leans toward where he shoots).
# The aim angle is split over the spine chain; `weapon` is a child of `chest`, so the rifle, both
# arms and all chest-mounted gear turn together while pelvis-mounted gear stays put.
# ---------------------------------------------------------------------------
# Fractions of the aim angle per bone, applied in this order on top of the animation.
#   weapon chain: spine + chest + aim = 1.0  -> the rifle points exactly at the target
#   head chain:   spine + chest + neck + head = 1.0 -> the head looks exactly at the target
# Up: mostly `aim` (arms + rifle swing about the shoulder line), the torso leans back a little -
#     leaning all the way would drive the pack bottom into the belt.
# Down: more torso lean (the vest turns with the rifle), less `aim` - otherwise the butt dips
#     into the magazine pouches. Yaw is torso-only (big turns: rotate the whole unit / root).
AIM_BONES = ("spine", "chest", "aim", "neck", "head")
AIM_PITCH_UP = {"spine": 0.12, "chest": 0.23, "aim": 0.65, "neck": 0.30, "head": 0.35}
AIM_PITCH_DOWN = {"spine": 0.20, "chest": 0.35, "aim": 0.45, "neck": 0.20, "head": 0.25}
AIM_YAW = {"spine": 0.35, "chest": 0.65, "aim": 0.0, "neck": 0.0, "head": 0.0}
AIM_RANGE = {"up": 45, "down": 35, "left": 45, "right": 45}


def apply_aim(pitch=0.0, yaw=0.0):
    """pitch > 0 aims up, yaw > 0 aims to the soldier's left; added on top of the current pose.
    Pitch turns about the soldier's side axis, yaw about the vertical (world axes here)."""
    for b in AIM_BONES:
        if yaw and AIM_YAW[b]:
            rot_world(b, Z, yaw * AIM_YAW[b])
        split = AIM_PITCH_UP if pitch > 0 else AIM_PITCH_DOWN
        if pitch and split[b]:
            rot_world(b, X, -pitch * split[b])


def hold_rifle(grip, twist=-14.0, reload=False, support=-0.215):
    """bladed stance, rifle shouldered: grip in the right hand, left hand on the handguard"""
    rot_world("spine", Z, twist)
    rot_world("chest", Z, twist)
    rot_world("neck", Z, -twist * 0.9)
    rot_world("head", Z, -twist * 0.9)
    grip = Vector(grip)
    move_weapon(grip)
    two_bone("upper_arm.R", "forearm.R", grip + Vector((0.006, 0.060, 0.030)),
             Vector((-0.8, -0.1, 0.9)))
    aim("hand.R", grip + Vector((0.01, -0.06, -0.06)))
    if reload:
        mag = arm.pose.bones["magazine"].head.copy()
        two_bone("upper_arm.L", "forearm.L", mag + Vector((0.040, 0.035, -0.02)),
                 Vector((0.6, 0.0, 0.8)))
        aim("hand.L", mag + Vector((-0.02, -0.03, -0.03)))
    else:
        guard = grip + Vector((0.0, support, 0.060))
        two_bone("upper_arm.L", "forearm.L", guard + Vector((0.045, 0.045, -0.040)),
                 Vector((0.5, 0.0, 0.7)))
        aim("hand.L", guard + Vector((-0.02, -0.03, 0.0)))


FIRE_GRIP = (-0.155, -0.480, 1.300)   # butt sits just in front of the vest


def pose_run(armed):
    reset_pose()
    rot_world("spine", X, 8)
    rot_world("thigh.L", X, -42)
    rot_world("shin.L", X, 65)
    rot_world("foot.L", X, -15)
    rot_world("thigh.R", X, 28)
    rot_world("shin.R", X, 45)
    if armed:  # low ready while running
        hold_rifle((-0.170, -0.500, 1.170), twist=-12, support=-0.13)
    else:
        rot_world("upper_arm.L", Y, 66)
        rot_world("upper_arm.L", X, 26)
        rot_world("forearm.L", X, -70)
        rot_world("upper_arm.R", Y, -66)
        rot_world("upper_arm.R", X, -30)
        rot_world("forearm.R", X, -75)


def pose_fire(pitch=0.0, yaw=0.0, reload=False):
    reset_pose()
    rot_world("thigh.L", X, -12)
    rot_world("thigh.R", X, 10)
    hold_rifle(FIRE_GRIP, reload=reload)
    apply_aim(pitch, yaw)


def pose_build():
    reset_pose()
    rot_world("spine", X, 16)
    rot_world("chest", X, 14)
    rot_world("head", X, -12)
    rot_world("thigh.L", X, -26)
    rot_world("shin.L", X, 48)
    rot_world("thigh.R", X, -18)
    rot_world("shin.R", X, 40)
    rot_world("upper_arm.L", Y, 55)
    rot_world("upper_arm.L", Z, -55)
    rot_world("forearm.L", Z, -40)
    rot_world("upper_arm.R", Y, -55)
    rot_world("upper_arm.R", Z, 55)
    rot_world("forearm.R", Z, 40)


POSES = {
    "rest": lambda armed: reset_pose(),
    "run": pose_run,
    "fire": lambda armed: pose_fire(),
    "reload": lambda armed: pose_fire(reload=True),
    "aim_up": lambda armed: pose_fire(pitch=AIM_RANGE["up"]),
    "aim_down": lambda armed: pose_fire(pitch=-AIM_RANGE["down"]),
    "aim_left": lambda armed: pose_fire(yaw=AIM_RANGE["left"]),
    "aim_right": lambda armed: pose_fire(yaw=-AIM_RANGE["right"]),
    "build": lambda armed: pose_build(),
}
LOADOUT_POSES = {
    "motor_rifle": ["rest", "run", "fire", "reload", "aim_up", "aim_down", "aim_left",
                    "aim_right"],
    "engineer": ["rest", "run", "aim_up", "aim_down", "aim_left", "aim_right", "build"],
}

# dominant bone of every body vertex (to say WHERE something clips)
DOM = {}
for _k, _ob in BODY.items():
    _names = {g.index: g.name for g in _ob.vertex_groups}
    DOM[_k] = [_names[max(v.groups, key=lambda g: g.weight).group] if len(v.groups) else "?"
               for v in _ob.data.vertices]


def posed(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ob.matrix_world
    pts = [mw @ v.co for v in me.vertices]
    polys = [p.vertices[:] for p in me.polygons]
    ev.to_mesh_clear()
    return pts, BVHTree.FromPolygons(pts, polys)


HELD = {"mod_wpn_rifle", "mod_mag_rifle"}
# P3's sleeves deliberately enclose P1's belt (hidden inside); everything else must be clean
ALLOWED_GEAR = {frozenset(("mod_belt_grenades", "mod_belt_pouches")),
                frozenset(("mod_wpn_rifle", "mod_mag_rifle"))}
CLIP_MM = 2.0


def clip_report():
    rows = []
    for lname, names in LOADOUTS.items():
        armed = "mod_wpn_rifle" in names
        for pname in LOADOUT_POSES[lname]:
            POSES[pname](armed)
            body = {k: posed(o) for k, o in BODY.items()}
            gear = {n: posed(ITEMS[n]["obj"]) for n in names}
            for n in names:
                gp, gb = gear[n]
                lo, hi = bbox(gp, 0.003)
                worst, bones, where = 0.0, set(), None
                if n in HELD and pname == "rest":
                    rows.append((lname, pname, n, None, [], {}))
                    continue  # the spec's rest position of `weapon`; animation places the rifle
                for k, (bp, bb) in body.items():
                    if n in HELD and k == "Soldier_Gloves":
                        continue  # the hands are meant to hold the rifle
                    if n in HELD:   # ...and so are the wrists/cuffs
                        bp = [p for p, b in zip(bp, DOM[k]) if not b.startswith(
                            ("hand", "forearm", "thumb", "index", "middle", "ring", "pinky"))]
                    WORST_AT[0] = None
                    d, idx = depth_inside(bp, gb, lo, hi, idx=True)   # body inside gear
                    if d > worst:
                        worst, where = d, WORST_AT[0]
                    bones |= {DOM[k][i] for i in idx}
                others = {}
                for m in names:
                    if m == n or frozenset((n, m)) in ALLOWED_GEAR:
                        continue
                    mp, mbv = gear[m]
                    WORST_AT[0] = None
                    d = max(depth_inside(gp, mbv, *bbox(mp, 0.003), idx=True)[0],
                            depth_inside(mp, gb, lo, hi, idx=True)[0])
                    if "--clip-only" in ARGS and d * 1000 >= CLIP_MM and WORST_AT[0]:
                        print("   worst %-9s %-26s vs %s %.0f mm at (%.3f %.3f %.3f)" % (
                            pname, n, m, d * 1000, *WORST_AT[0]))
                    if d * 1000 >= CLIP_MM:
                        others[m] = d
                if "--clip-only" in ARGS and worst > CLIP_MM / 1000 and where is not None:
                    print("   worst %-9s %-26s %.0f mm at (%.3f %.3f %.3f)" % (
                        pname, n, worst * 1000, *where))
                rows.append((lname, pname, n, worst, sorted(bones), others))
    reset_pose()
    return rows


def make_aim_actions():
    """reference poses for the engine (additive aim offset / blend space): spine chain only"""
    arm.animation_data_create()
    for name, (p, y) in (("AIM_Center", (0, 0)), ("AIM_Up", (AIM_RANGE["up"], 0)),
                         ("AIM_Down", (-AIM_RANGE["down"], 0)),
                         ("AIM_Left", (0, AIM_RANGE["left"])),
                         ("AIM_Right", (0, -AIM_RANGE["right"]))):
        reset_pose()
        apply_aim(p, y)
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        arm.animation_data.action = act
        for b in AIM_BONES:
            arm.pose.bones[b].keyframe_insert("rotation_quaternion", frame=1, group=b)
    arm.animation_data.action = None
    reset_pose()


rows = clip_report()
make_aim_actions()
bad = 0
with open(os.path.join(OUT, "gear_clipping_report.txt"), "w") as fh:
    fh.write("Max penetration per item and pose, millimetres (clean < %.0f mm).\n" % CLIP_MM)
    fh.write("Body = soldier mesh skinned to the rig; bones = where the body pokes in.\n")
    fh.write("Rifle vs gloves is excluded (held). P3 sleeves enclose P1's belt on purpose.\n")
    fh.write("Poses are TEST poses built by build_gear.py (incl. the aim offset at its limits:\n")
    fh.write("up %(up)d, down %(down)d, left %(left)d, right %(right)d deg), "
             "not the game's INF_*/WRK_* clips.\n\n" % AIM_RANGE)
    for lname, pname, n, worst, bones, others in rows:
        if worst is None:
            fh.write("%-12s %-9s %-26s n/a (bind pose: weapon bone at the spec's rest point)\n"
                     % (lname, pname, n))
            continue
        ok = worst * 1000 < CLIP_MM and not others
        bad += not ok
        line = "%-12s %-9s %-26s %s" % (
            lname, pname, n, "ok" if ok else "body %.0f mm %s %s" % (
                worst * 1000, ("[" + ", ".join(bones) + "]") if bones else "",
                " ".join("| %s %.0f mm" % (m, d * 1000) for m, d in others.items())))
        fh.write(line + "\n")
        if not ok:
            print("CLIP", line)
print("clip rows not clean:", bad, "of", len(rows))
if "--clip-only" in ARGS:
    sys.exit(0)

# ---------------------------------------------------------------------------
# renders
# ---------------------------------------------------------------------------
cam = scene.camera
cam_data = cam.data
scene.cycles.samples = 16 if PREVIEW else 96
SZ = 600 if PREVIEW else 1200


def render(path, res=SZ, resy=None):
    scene.render.resolution_x = res
    scene.render.resolution_y = resy or res
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def ortho(loc, rot, scale=2.08, zc=0.91):
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = scale
    cam.location = (loc[0], loc[1], zc)
    cam.rotation_euler = rot


def persp(loc, target, lens=110):
    cam_data.type = "PERSP"
    cam_data.lens = lens
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def sheet(paths, out, labels, cols=None, label_h=0.07):
    from PIL import Image, ImageDraw, ImageFont
    ims = [Image.open(p).convert("RGB") for p in paths]
    w, h = ims[0].size
    cols = cols or len(ims)
    rws = (len(ims) + cols - 1) // cols
    pad = int(h * label_h)
    s = Image.new("RGB", (w * cols, (h + pad) * rws), ims[0].getpixel((3, 3)))
    d = ImageDraw.Draw(s)
    try:
        font = ImageFont.load_default(size=max(12, int(pad * 0.42)))
    except TypeError:
        font = ImageFont.load_default()
    for i, (im, lb) in enumerate(zip(ims, labels)):
        x, y = (i % cols) * w, (i // cols) * (h + pad)
        s.paste(im, (x, y + pad))
        tw = d.textlength(lb, font=font)
        d.text((x + (w - tw) / 2, y + pad * 0.25), lb, fill=(60, 62, 64), font=font)
    s.save(out)


VIEWS = [("FRONT", (0, -10), (math.pi / 2, 0, 0)), ("SIDE", (-10, 0), (math.pi / 2, 0, -math.pi / 2)),
         ("BACK", (0, 10), (math.pi / 2, 0, math.pi))]
for lname, names in LOADOUTS.items():
    show(names)
    reset_pose()
    paths = []
    for vname, loc, rot in VIEWS:
        ortho(loc, rot, scale=2.12)
        p = os.path.join(REN, "%s_%s.png" % (lname, vname.lower()))
        render(p)
        paths.append(p)
    sheet(paths, os.path.join(OUT, "gear_%s_turnaround.png" % lname), [v[0] for v in VIEWS])
    # 3/4 + RTS camera
    persp((3.4, -5.4, 2.3), (0, 0, 0.95), lens=110)
    render(os.path.join(REN, "%s_three_quarter.png" % lname))
    persp((0, -4.2, 6.0), (0, 0, 0.8), lens=120)
    render(os.path.join(REN, "%s_rts.png" % lname), res=SZ // 2)
    # test poses
    plist = [p for p in LOADOUT_POSES[lname] if p != "rest"]
    ppaths = []
    for pname in plist:
        POSES[pname]("mod_wpn_rifle" in names)
        persp((2.6, -4.6, 2.0), (0, -0.1, 0.9), lens=95)
        p = os.path.join(REN, "%s_pose_%s.png" % (lname, pname))
        render(p, res=SZ // 2)
        ppaths.append(p)
    reset_pose()
    sheet(ppaths, os.path.join(OUT, "gear_%s_poses.png" % lname), plist, cols=4)

# aim offset: side view for pitch, top view for yaw (motor rifle loadout)
show(LOADOUTS["motor_rifle"])
apaths, alabels = [], []
for pname, cam_loc, tgt in (("aim_up", (-4.5, -1.2, 1.3), (0, -0.25, 1.15)),
                            ("fire", (-4.5, -1.2, 1.3), (0, -0.25, 1.15)),
                            ("aim_down", (-4.5, -1.2, 1.3), (0, -0.25, 1.15)),
                            ("aim_left", (0.0, -0.4, 6.0), (0, -0.4, 1.0)),
                            ("aim_right", (0.0, -0.4, 6.0), (0, -0.4, 1.0))):
    POSES[pname](True)
    persp(cam_loc, tgt, lens=70)
    p = os.path.join(REN, "aim_%s.png" % pname)
    render(p, res=SZ // 2)
    apaths.append(p)
    alabels.append({"fire": "aim 0"}.get(pname, pname.replace("_", " ")))
reset_pose()
sheet(apaths, os.path.join(OUT, "gear_aim_offset.png"), alabels, cols=5)

# item catalogue
cat_paths, cat_labels = [], []
for nm, it in ITEMS.items():
    if nm.endswith(".R"):
        continue
    show([nm], body=False)
    ob = it["obj"]
    upd()
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    ctr = sum(pts, Vector()) / 8
    ext = max((p - ctr).length for p in pts)
    direction = Vector((0.55, -0.75, 0.42)).normalized()
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ext * 2.3
    cam.location = ctr + direction * 5
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    p = os.path.join(REN, "item_%s.png" % nm.replace(".", "_"))
    render(p, res=SZ // 3)
    cat_paths.append(p)
    cat_labels.append("%s %s  %d tris" % (it["id"], nm, it["tris"]))
sheet(cat_paths, os.path.join(OUT, "gear_items.png"), cat_labels, cols=4, label_h=0.1)
show(list(ITEMS))

# side by side RTS views
try:
    from PIL import Image
    a = Image.open(os.path.join(REN, "motor_rifle_rts.png"))
    b = Image.open(os.path.join(REN, "engineer_rts.png"))
    s = Image.new("RGB", (a.width * 2, a.height))
    s.paste(a, (0, 0))
    s.paste(b, (a.width, 0))
    s.save(os.path.join(OUT, "gear_rts_view.png"))
except Exception as exc:
    print("rts sheet failed", exc)

if PREVIEW:
    sys.exit(0)

# ---------------------------------------------------------------------------
# bake one 1024 atlas (colour only, no light), switch slots to it, save
# ---------------------------------------------------------------------------
recolor(SLOTS["07"], "#d4d4d4")  # team colour is tinted in-engine: bake it neutral
img = bpy.data.images.new("T_Gear_Atlas", 1024, 1024)
for m in SLOTS.values():
    nd = m.node_tree.nodes.new("ShaderNodeTexImage")
    nd.image = img
    m.node_tree.nodes.active = nd
show(list(ITEMS))
bpy.ops.object.select_all(action="DESELECT")
for ob in gear_objs:
    ob.select_set(True)
bpy.context.view_layer.objects.active = gear_objs[0]
scene.cycles.samples = 16
bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=4, use_clear=True)
os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
img.filepath_raw = os.path.join(OUT, "textures", "T_Gear_Atlas.png")
img.file_format = "PNG"
img.save()
atlas = bpy.data.images.load(img.filepath_raw)
for key, m in SLOTS.items():
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    for nd in [n for n in nt.nodes if n not in (bsdf, nt.nodes["Material Output"])]:
        nt.nodes.remove(nd)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = atlas
    if key == "07":  # preview tint only; the engine supplies the real team colour
        tint = nt.nodes.new("ShaderNodeMixRGB")
        tint.blend_type = "MULTIPLY"
        tint.inputs["Fac"].default_value = 1.0
        tint.inputs["Color2"].default_value = srgb(TEAM_PREVIEW)
        nt.links.new(tex.outputs["Color"], tint.inputs["Color1"])
        nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
bpy.ops.object.select_all(action="DESELECT")
reset_pose()
show(list(ITEMS))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "soldier_gear.blend"), compress=True)

with open(os.path.join(OUT, "gear_items.txt"), "w") as fh:
    for nm, it in ITEMS.items():
        lo, hi = it["budget"]
        ok = "ok" if lo <= it["tris"] <= hi else ("LOW" if it["tris"] < lo else "OVER")
        fh.write("%-4s %-26s bone=%-12s tris=%4d budget=%d-%d %s\n" % (
            it["id"], nm, it["bone"], it["tris"], lo, hi, ok))
print("DONE")
