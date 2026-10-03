"""
Procedural base body: stylized modern infantry soldier for a top-down RTS.

T-pose, palms down, plain olive field uniform (jacket tucked in, cargo trousers),
combat boots, gloves. No helmet / vest / backpack / weapons / pouches.
Height 1.8 m, Z-up, character faces -Y (Blender "Front" view).

Run:
    python3 build_soldier.py            # full build: .blend, turnaround, bake, GLB/FBX
    python3 build_soldier.py --preview  # fast low-sample turnaround only
Requires the `bpy` module (pip install bpy==4.2.0) or Blender 4.2:
    blender -b -P build_soldier.py -- [--preview]
"""
import math
import os
import sys

import bpy  # noqa: E402  (bpy must be imported before bmesh/mathutils)
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_point_line

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
PREVIEW = "--preview" in ARGS
OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# scene reset
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
bpy.context.preferences.filepaths.save_version = 0
COL = bpy.data.collections.new("SoldierBase")
scene.collection.children.link(COL)

LEFT = []  # objects built for the left side (+X) that get mirrored to the right


# ---------------------------------------------------------------------------
# materials (hand-painted look: low-frequency colour variation + soft edge light)
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


MATS = {}


def make_mat(name, hexcol, rough=0.85, var=0.12, scale=9.0, edge=0.25, metal=0.0, grain=0.05):
    base = srgb(hexcol)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = base
    nt = m.node_tree
    n, l = nt.nodes, nt.links
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    tc = n.new("ShaderNodeTexCoord")
    # broad, painterly blotches
    n1 = n.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = scale
    n1.inputs["Detail"].default_value = 3.0
    n1.inputs["Roughness"].default_value = 0.45
    l.new(tc.outputs["Object"], n1.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.32
    ramp.color_ramp.elements[1].position = 0.68
    ramp.color_ramp.elements[0].color = scale_col(base, 1.0 - var)
    ramp.color_ramp.elements[1].color = scale_col(base, 1.0 + var)
    l.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    # fine fabric / leather grain
    n2 = n.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 180.0
    n2.inputs["Detail"].default_value = 1.0
    l.new(tc.outputs["Object"], n2.inputs["Vector"])
    grain_mix = n.new("ShaderNodeMixRGB")
    grain_mix.blend_type = "OVERLAY"
    grain_mix.inputs["Fac"].default_value = grain
    l.new(ramp.outputs["Color"], grain_mix.inputs["Color1"])
    l.new(n2.outputs["Color"], grain_mix.inputs["Color2"])
    # painted edge highlight on convex forms (curvature, not lighting)
    geo = n.new("ShaderNodeNewGeometry")
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.52
    mr.inputs["From Max"].default_value = 0.60
    l.new(geo.outputs["Pointiness"], mr.inputs["Value"])
    fac = n.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    fac.inputs[1].default_value = edge
    l.new(mr.outputs["Result"], fac.inputs[0])
    edge_mix = n.new("ShaderNodeMixRGB")
    edge_mix.blend_type = "MIX"
    edge_mix.inputs["Color2"].default_value = scale_col(base, 1.45)
    l.new(fac.outputs["Value"], edge_mix.inputs["Fac"])
    l.new(grain_mix.outputs["Color"], edge_mix.inputs["Color1"])
    l.new(edge_mix.outputs["Color"], bsdf.inputs["Base Color"])
    MATS[name] = m
    return m


make_mat("M_Uniform", "#5d6443", var=0.10, scale=7.0, edge=0.30, grain=0.07)
make_mat("M_UniformPatch", "#535a3b", var=0.10, scale=7.0, edge=0.35, grain=0.07)
make_mat("M_Skin", "#c99a76", rough=0.7, var=0.06, scale=14.0, edge=0.15, grain=0.0)
make_mat("M_Hair", "#3a2a1f", rough=0.9, var=0.10, scale=30.0, edge=0.0, grain=0.08)
make_mat("M_Eye", "#2b2421", rough=0.5, var=0.0, edge=0.0, grain=0.0)
make_mat("M_Lip", "#a5705c", rough=0.7, var=0.03, edge=0.0, grain=0.0)
make_mat("M_Belt", "#2f2e28", rough=0.9, var=0.08, scale=20.0, edge=0.3, grain=0.12)
make_mat("M_Metal", "#6e6b5f", rough=0.6, var=0.05, edge=0.4, metal=0.6, grain=0.0)
make_mat("M_Button", "#3a3c2b", rough=0.7, var=0.0, edge=0.3, grain=0.0)
make_mat("M_BootLeather", "#43352a", rough=0.75, var=0.12, scale=10.0, edge=0.35, grain=0.08)
make_mat("M_BootToe", "#2e251e", rough=0.7, var=0.08, scale=10.0, edge=0.4, grain=0.05)
make_mat("M_BootSole", "#1e1c1a", rough=0.9, var=0.05, edge=0.2, grain=0.05)
make_mat("M_Lace", "#29231e", rough=0.9, var=0.0, edge=0.2, grain=0.0)
make_mat("M_Glove", "#36342e", rough=0.85, var=0.08, scale=14.0, edge=0.3, grain=0.1)
make_mat("M_GloveLeather", "#4d4337", rough=0.75, var=0.08, scale=14.0, edge=0.35, grain=0.06)

GROUP_OF_MAT = {
    "M_Hair": "Hair",
    "M_BootLeather": "Boots", "M_BootSole": "Boots", "M_BootToe": "Boots", "M_Lace": "Boots",
    "M_Glove": "Gloves", "M_GloveLeather": "Gloves",
}


# ---------------------------------------------------------------------------
# mesh helpers
# ---------------------------------------------------------------------------
def mk_obj(name, verts, faces, mat, bones, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    me.materials.append(MATS[mat])
    ob = bpy.data.objects.new(name, me)
    COL.objects.link(ob)
    ob["bones"] = ",".join(bones)
    ob["group"] = GROUP_OF_MAT.get(mat, "Body")
    return ob


def apply_subsurf(ob, levels=2):
    mod = ob.modifiers.new("SubD", "SUBSURF")
    mod.levels = levels
    mod.render_levels = levels
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    old = ob.data
    ob.data = me
    me.name = old.name
    bpy.data.meshes.remove(old)
    return ob


def apply_mod(ob, kind, **props):
    mod = ob.modifiers.new("tmp", kind)
    for k, v in props.items():
        setattr(mod, k, v)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def ring(c, t, ref, ra, rb, n=2.0):
    return (Vector(c), None if t is None else Vector(t), Vector(ref), ra, rb, n)


def loft(name, rings, mat, bones, segs=16, cap0=True, cap1=True, bulge0=0.3, bulge1=0.3,
         subd=1, left=False):
    """Skin a list of cross-section rings into a quad tube with domed caps."""
    centers = [r[0] for r in rings]
    verts, faces, ring_idx = [], [], []
    for i, (c, t, ref, ra, rb, n) in enumerate(rings):
        if t is None:
            a = centers[max(i - 1, 0)]
            b = centers[min(i + 1, len(centers) - 1)]
            t = b - a
        t = t.normalized()
        v = (ref - t * ref.dot(t)).normalized()
        u = v.cross(t).normalized()
        idx = []
        for k in range(segs):
            ang = 2.0 * math.pi * k / segs
            ca, sa = math.cos(ang), math.sin(ang)
            x = math.copysign(abs(ca) ** (2.0 / n), ca) * ra
            y = math.copysign(abs(sa) ** (2.0 / n), sa) * rb
            idx.append(len(verts))
            verts.append(c + u * x + v * y)
        ring_idx.append((idx, t))
    for i in range(len(ring_idx) - 1):
        a, b = ring_idx[i][0], ring_idx[i + 1][0]
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append([a[k], a[k2], b[k2], b[k]])

    def cap(ri, sign, bulge):
        idx, t = ring_idx[ri]
        c = centers[ri]
        # inner ring keeps the cap flatter after subdivision
        span = sum(((verts[j] - c).length for j in idx)) / segs
        inner = []
        for j in idx:
            inner.append(len(verts))
            verts.append(c + (verts[j] - c) * 0.55 + t * sign * span * bulge * 0.6)
        ci = len(verts)
        verts.append(c + t * sign * span * bulge)
        for k in range(segs):
            k2 = (k + 1) % segs
            faces.append([idx[k], idx[k2], inner[k2], inner[k]])
            faces.append([inner[k], inner[k2], ci])

    if cap0:
        cap(0, -1.0, bulge0)
    if cap1:
        cap(len(rings) - 1, 1.0, bulge1)
    ob = mk_obj(name, verts, faces, mat, bones)
    if subd:
        apply_subsurf(ob, subd)
    if left:
        LEFT.append(ob)
    return ob


def ellipsoid(name, center, size, mat, bones, rot=None, segs=12, rings_=8, left=False):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings_, radius=1.0)
    mtx = Matrix.Translation(Vector(center))
    if rot is not None:
        mtx = mtx @ rot
    mtx = mtx @ Matrix.Diagonal(Vector(size)).to_4x4()
    bmesh.ops.transform(bm, matrix=mtx, verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(MATS[mat])
    ob = bpy.data.objects.new(name, me)
    COL.objects.link(ob)
    ob["bones"] = ",".join(bones)
    ob["group"] = GROUP_OF_MAT.get(mat, "Body")
    if left:
        LEFT.append(ob)
    return ob


def rounded_box(name, center, size, mat, bones, rot=None, bevel=0.3, left=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS[mat])
    ob = bpy.data.objects.new(name, me)
    COL.objects.link(ob)
    apply_subsurf(ob, 2)
    # squash the subdivided cube toward a box with rounded corners
    for v in ob.data.vertices:
        p = v.co * 2.0
        q = Vector([math.copysign(min(1.0, abs(c) ** (1.0 - bevel) * 1.08), c) for c in p])
        v.co = q * 0.5
    mtx = Matrix.Translation(Vector(center))
    if rot is not None:
        mtx = mtx @ rot
    mtx = mtx @ Matrix.Diagonal(Vector(size)).to_4x4()
    ob.data.transform(mtx)
    for p in ob.data.polygons:
        p.use_smooth = True
    ob["bones"] = ",".join(bones)
    ob["group"] = GROUP_OF_MAT.get(mat, "Body")
    if left:
        LEFT.append(ob)
    return ob


def bvh_of(*objs):
    verts, polys = [], []
    for ob in objs:
        off = len(verts)
        verts.extend([v.co.copy() for v in ob.data.vertices])
        polys.extend([[i + off for i in p.vertices] for p in ob.data.polygons])
    return BVHTree.FromPolygons(verts, polys)


def surf_hit(bvh, origin, direction):
    loc, nrm, _, _ = bvh.ray_cast(Vector(origin), Vector(direction).normalized())
    return loc, nrm


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def patch(name, bvh, origin, axis, ref, a0, a1, h0, h1, mat, bones, thick=0.005, nu=10,
          nv=10, wrap=False, edge=0.35, left=False):
    """Fabric panel that hugs a surface: rays are cast from an axis outwards (cylindrical
    parametrisation: angle a0..a1 around `axis`, distance h0..h1 along it) and the hits are
    thickened into a closed shell with softly bevelled borders."""
    axis = Vector(axis).normalized()
    ref = Vector(ref)
    ref = (ref - axis * ref.dot(axis)).normalized()
    side = axis.cross(ref)
    origin = Vector(origin)
    cols = nu if wrap else nu + 1
    outer, inner = [], []
    for j in range(nv + 1):
        h = h0 + (h1 - h0) * j / nv
        ro, ri = [], []
        for i in range(cols):
            a = a0 + (a1 - a0) * i / nu
            d = ref * math.cos(a) + side * math.sin(a)
            loc, nrm = surf_hit(bvh, origin + axis * h, d)
            if loc is None:
                loc, nrm = origin + axis * h + d * 0.05, d
            ev = min(j / nv, 1 - j / nv)
            eu = 1.0 if wrap else min(i / nu, 1 - i / nu)
            prof = edge + (1 - edge) * smoothstep(0.0, 0.12, min(eu, ev))
            ro.append(loc + nrm * (0.0012 + thick * prof))
            ri.append(loc - nrm * 0.0015)
        outer.append(ro)
        inner.append(ri)
    verts, faces = [], []
    oi = [[0] * cols for _ in range(nv + 1)]
    ii = [[0] * cols for _ in range(nv + 1)]
    for j in range(nv + 1):
        for i in range(cols):
            oi[j][i] = len(verts)
            verts.append(outer[j][i])
            ii[j][i] = len(verts)
            verts.append(inner[j][i])
    ulim = cols if wrap else cols - 1
    for j in range(nv):
        for i in range(ulim):
            i2 = (i + 1) % cols
            faces.append([oi[j][i], oi[j][i2], oi[j + 1][i2], oi[j + 1][i]])
            faces.append([ii[j][i], ii[j + 1][i], ii[j + 1][i2], ii[j][i2]])
    # border walls
    border = []
    for i in range(ulim):
        border.append(((0, i), (0, (i + 1) % cols)))
        border.append(((nv, i), (nv, (i + 1) % cols)))
    if not wrap:
        for j in range(nv):
            border.append(((j, 0), (j + 1, 0)))
            border.append(((j, cols - 1), (j + 1, cols - 1)))
    for (ja, ia), (jb, ib) in border:
        faces.append([oi[ja][ia], oi[jb][ib], ii[jb][ib], ii[ja][ia]])
    ob = mk_obj(name, verts, faces, mat, bones)
    if left:
        LEFT.append(ob)
    return ob


def mirror_x(ob):
    me = ob.data.copy()
    for v in me.vertices:
        v.co.x = -v.co.x
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    name = ob.name.replace(".L", ".R") if ob.name.endswith(".L") else ob.name + ".R"
    me.name = name
    ob2 = bpy.data.objects.new(name, me)
    COL.objects.link(ob2)
    ob2["bones"] = ",".join(b.replace(".L", ".R") for b in ob["bones"].split(","))
    ob2["group"] = ob["group"]
    return ob2


Z, Y, X = (0, 0, 1), (0, 1, 0), (1, 0, 0)
FRONT = (0, -1, 0)

# ---------------------------------------------------------------------------
# key proportions (metres)
# ---------------------------------------------------------------------------
ARM_Z = 1.415
HIP = Vector((0.095, 0.0, 0.95))
ANKLE = Vector((0.160, 0.0, 0.10))
LEG_AXIS = (ANKLE - HIP).normalized()


def leg_point(z, dy=0.0):
    f = (HIP.z - z) / (HIP.z - ANKLE.z)
    p = HIP.lerp(ANKLE, f)
    return Vector((p.x, p.y + dy, z))


def leg_h(z):
    """distance along the leg axis from the hip for a given height"""
    return (leg_point(z) - HIP).length * (1 if z <= HIP.z else -1)


# ---------------------------------------------------------------------------
# HEAD
# ---------------------------------------------------------------------------
head = loft("Head", [
    ring((0, -0.045, 1.548), Z, FRONT, 0.030, 0.028),
    ring((0, -0.034, 1.566), Z, FRONT, 0.056, 0.053),
    ring((0, -0.010, 1.596), Z, FRONT, 0.068, 0.082),
    ring((0, 0.000, 1.636), Z, FRONT, 0.076, 0.096),
    ring((0, 0.004, 1.681), Z, FRONT, 0.080, 0.102),
    ring((0, 0.006, 1.726), Z, FRONT, 0.079, 0.100),
    ring((0, 0.008, 1.761), Z, FRONT, 0.070, 0.088),
    ring((0, 0.008, 1.784), Z, FRONT, 0.046, 0.058),
], "M_Skin", ["Head"], segs=16, bulge0=0.2, bulge1=0.25, subd=2)

HS = 1.07
HTOP = Vector((0, 0.008, 1.79))
for v in head.data.vertices:
    v.co = HTOP + (v.co - HTOP) * HS


def hz(z):
    return HTOP.z + (z - HTOP.z) * HS


neck = loft("Neck", [
    ring((0, 0.006, 1.44), Z, FRONT, 0.062, 0.062),
    ring((0, 0.008, 1.52), Z, FRONT, 0.055, 0.058),
    ring((0, 0.020, 1.60), Z, FRONT, 0.050, 0.052),
    ring((0, 0.022, 1.625), Z, FRONT, 0.044, 0.044),
], "M_Skin", ["Chest", "Neck", "Head"], segs=12)

hb = bvh_of(head)

# hair: shell over the scalp above a sloped hairline
hb_scalp = bvh_of(head)
hair = bpy.data.objects.new("Hair", head.data.copy())
COL.objects.link(hair)
hair["bones"] = "Head"
hair["group"] = "Hair"
bm = bmesh.new()
bm.from_mesh(hair.data)


def hairline(p0):
    p = HTOP + (p0 - HTOP) / HS
    zh = 1.690 - 0.50 * p.y               # high at the forehead, low at the nape
    ear_w = smoothstep(0.045, 0.066, abs(p.x)) * (1 - smoothstep(0.025, 0.06, abs(p.y - 0.006)))
    zh += max(0.0, 1.705 - zh) * ear_w    # clear the ears
    if p.y < -0.02:
        zh += 0.012 * min(1.0, abs(p.x) / 0.07) ** 2  # rounded front corners
    return hz(zh)


kill = [f for f in bm.faces if f.calc_center_median().z < hairline(f.calc_center_median())]
bmesh.ops.delete(bm, geom=kill, context="FACES")
bm.verts.ensure_lookup_table()
edge_verts = [v for v in bm.verts if v.is_boundary]
for _ in range(3):  # relax the stair-stepped border into a clean curve
    for v in edge_verts:
        nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
        avg = sum((n.co for n in nb), Vector()) / max(len(nb), 1)
        v.co = v.co.lerp(avg, 0.5)
        v.co.z = v.co.z * 0.5 + hairline(v.co) * 0.5
        loc, nrm, _, _ = hb_scalp.find_nearest(v.co)
        v.co = loc
bm.to_mesh(hair.data)
bm.free()
hair.data.materials.clear()
hair.data.materials.append(MATS["M_Hair"])
hair.data.update()
for v in hair.data.vertices:  # buzz cut: thickness fades out toward the hairline
    t = 0.0008 + 0.0062 * smoothstep(0.0, 0.018, v.co.z - hairline(v.co))
    v.co = v.co + v.normal * t
apply_mod(hair, "SMOOTH", factor=0.6, iterations=6)
for p in hair.data.polygons:
    p.use_smooth = True

# face: minimal, calm
for sx in (1, -1):
    sfx = ".L" if sx > 0 else ".R"
    loc, nrm = surf_hit(hb, (0.033 * sx, -1, hz(1.688)), Y)
    ellipsoid("Eye" + sfx, loc - nrm * 0.002, (0.0095, 0.006, 0.0115), "M_Eye", ["Head"])
    loc, nrm = surf_hit(hb, (0.036 * sx, -1, hz(1.712)), Y)
    ellipsoid("Brow" + sfx, loc + nrm * 0.001, (0.019, 0.006, 0.0048), "M_Hair", ["Head"],
              rot=Matrix.Rotation(-0.10 * sx, 4, "Y"))
    loc, nrm = surf_hit(hb, (1.0 * sx, 0.012, hz(1.664)), (-sx, 0, 0))
    ellipsoid("Ear" + sfx, loc + nrm * 0.002, (0.011, 0.020, 0.030), "M_Skin", ["Head"],
              rot=Matrix.Rotation(0.18 * sx, 4, "Z"))
loc, nrm = surf_hit(hb, (0, -1, hz(1.655)), Y)
ellipsoid("Nose", loc + Vector((0, 0.005, 0.0)), (0.0115, 0.014, 0.021), "M_Skin", ["Head"],
          rot=Matrix.Rotation(-0.25, 4, "X"))
loc, nrm = surf_hit(hb, (0, -1, hz(1.607)), Y)
ellipsoid("Mouth", loc - nrm * 0.0024, (0.017, 0.0035, 0.0032), "M_Lip", ["Head"])

# ---------------------------------------------------------------------------
# JACKET (torso, collar, sleeves)
# ---------------------------------------------------------------------------
TB = ["Hips", "Spine", "Chest", "Neck", "Shoulder.L", "Shoulder.R", "UpperArm.L", "UpperArm.R"]
torso = loft("Jacket", [
    ring((0, 0.000, 0.99), Z, FRONT, 0.150, 0.104, 2.2),
    ring((0, 0.000, 1.04), Z, FRONT, 0.152, 0.105, 2.2),
    ring((0, -0.002, 1.10), Z, FRONT, 0.155, 0.108, 2.3),
    ring((0, -0.004, 1.18), Z, FRONT, 0.166, 0.116, 2.3),
    ring((0, -0.006, 1.26), Z, FRONT, 0.181, 0.126, 2.4),
    ring((0, -0.005, 1.34), Z, FRONT, 0.192, 0.125, 2.5),
    ring((0, -0.002, 1.40), Z, FRONT, 0.199, 0.114, 2.6),
    ring((0, 0.002, 1.445), Z, FRONT, 0.188, 0.100, 2.6),
    ring((0, 0.004, 1.476), Z, FRONT, 0.135, 0.085, 2.3),
    ring((0, 0.006, 1.500), Z, FRONT, 0.074, 0.066),
], "M_Uniform", TB, segs=20, bulge0=0.1, bulge1=0.15)
tb = bvh_of(torso)

collar = loft("Collar", [
    ring((0, 0.004, 1.468), Z, FRONT, 0.092, 0.084),
    ring((0, 0.006, 1.500), Z, FRONT, 0.075, 0.071),
    ring((0, 0.008, 1.532), Z, FRONT, 0.069, 0.067),
], "M_Uniform", ["Chest", "Neck"], segs=16, cap0=False, cap1=False, subd=0)
apply_mod(collar, "SOLIDIFY", thickness=0.007, offset=1.0)
apply_subsurf(collar, 1)

# front placket + buttons
patch("Placket", tb, (0, 0, 0), Z, FRONT, -0.13, 0.13, 1.075, 1.462, "M_UniformPatch",
      ["Spine", "Chest", "Hips"], thick=0.0035, nu=4, nv=18)
for i, z in enumerate((1.14, 1.22, 1.30, 1.38)):
    loc, nrm = surf_hit(tb, (0, 0, z), FRONT)
    ellipsoid("Button%d" % i, loc + nrm * 0.0045, (0.0065, 0.003, 0.0065), "M_Button", ["Chest"],
              segs=10, rings_=6)

# chest pockets with flaps
patch("ChestPocket.L", tb, (0, 0, 0), Z, FRONT, 0.30, 0.86, 1.235, 1.345, "M_Uniform",
      ["Chest"], thick=0.006, left=True)
patch("ChestFlap.L", tb, (0, 0, 0), Z, FRONT, 0.27, 0.89, 1.335, 1.378, "M_UniformPatch",
      ["Chest"], thick=0.010, nv=6, left=True)
loc, nrm = surf_hit(tb, (0, 0, 1.343), (math.sin(0.58), -math.cos(0.58), 0))
ellipsoid("ChestBtn.L", loc + nrm * 0.0115, (0.006, 0.003, 0.006), "M_Button", ["Chest"],
          segs=10, rings_=6, left=True)
# back yoke panel
patch("Yoke", tb, (0, 0, 0), Z, FRONT, math.pi - 1.05, math.pi + 1.05, 1.36, 1.43,
      "M_UniformPatch", ["Chest"], thick=0.0025, nu=14, nv=5)

sleeve = loft("Sleeve.L", [
    ring((0.12, 0, 1.405), X, Z, 0.074, 0.074),
    ring((0.17, 0, 1.410), X, Z, 0.076, 0.080),
    ring((0.22, 0, 1.413), X, Z, 0.072, 0.074),
    ring((0.29, 0, ARM_Z), X, Z, 0.063, 0.063),
    ring((0.37, 0, ARM_Z), X, Z, 0.059, 0.058),
    ring((0.46, 0, ARM_Z), X, Z, 0.051, 0.050),
    ring((0.53, 0, ARM_Z), X, Z, 0.055, 0.052),
    ring((0.62, 0, ARM_Z), X, Z, 0.051, 0.047),
    ring((0.70, 0, ARM_Z), X, Z, 0.048, 0.045),
    ring((0.725, 0, ARM_Z), X, Z, 0.044, 0.042),
], "M_Uniform", ["Chest", "Shoulder.L", "UpperArm.L", "LowerArm.L"], segs=16, left=True)
sb = bvh_of(sleeve)
# shoulder pocket on the lateral upper arm (faces up in a palms-down T-pose)
patch("SleevePocket.L", sb, (0, 0, ARM_Z), X, Z, -0.55, 1.05, 0.255, 0.375, "M_Uniform",
      ["UpperArm.L"], thick=0.006, left=True)
patch("SleeveFlap.L", sb, (0, 0, ARM_Z), X, Z, -0.62, 1.12, 0.238, 0.268, "M_UniformPatch",
      ["UpperArm.L"], thick=0.009, nv=5, left=True)
# forearm cuff tab
patch("CuffTab.L", sb, (0, 0, ARM_Z), X, Z, math.pi - 0.5, math.pi + 0.5, 0.655, 0.695,
      "M_UniformPatch", ["LowerArm.L"], thick=0.004, nv=5, left=True)

# ---------------------------------------------------------------------------
# GLOVES (slightly oversized hands), palms down, thumbs forward (-Y)
# ---------------------------------------------------------------------------
loft("GloveCuff.L", [
    ring((0.692, 0, ARM_Z), X, Z, 0.050, 0.048),
    ring((0.703, 0, ARM_Z), X, Z, 0.057, 0.054),
    ring((0.748, 0, ARM_Z - 0.001), X, Z, 0.055, 0.050),
    ring((0.768, 0, ARM_Z - 0.002), X, Z, 0.046, 0.040),
], "M_Glove", ["LowerArm.L", "Hand.L"], segs=16, left=True)
palm = loft("Palm.L", [
    ring((0.735, 0, ARM_Z), X, Z, 0.042, 0.027, 2.4),
    ring((0.770, 0, ARM_Z), X, Z, 0.054, 0.030, 2.6),
    ring((0.815, 0, ARM_Z), X, Z, 0.060, 0.029, 2.7),
    ring((0.852, 0, ARM_Z), X, Z, 0.058, 0.024, 2.6),
    ring((0.868, 0, ARM_Z), X, Z, 0.048, 0.017, 2.4),
], "M_Glove", ["LowerArm.L", "Hand.L"], segs=16, left=True)
pb = bvh_of(palm)
patch("Knuckle.L", pb, (0, 0, ARM_Z), X, Z, -0.95, 0.95, 0.818, 0.862, "M_GloveLeather",
      ["Hand.L"], thick=0.006, nu=10, nv=5, left=True)
patch("PalmPad.L", pb, (0, 0, ARM_Z), X, (0, 0, -1), -0.9, 0.9, 0.772, 0.855, "M_GloveLeather",
      ["Hand.L"], thick=0.003, nu=10, nv=6, left=True)

FINGERS = [  # name, y, length, radius
    ("Index", -0.036, 0.074, 0.0165),
    ("Middle", -0.012, 0.082, 0.0170),
    ("Ring", 0.012, 0.077, 0.0165),
    ("Pinky", 0.035, 0.063, 0.0150),
]
for fname, fy, flen, fr in FINGERS:
    x0 = 0.848
    pts = [
        (x0, fy, ARM_Z + 0.001, fr * 1.05),
        (x0 + flen * 0.35, fy * 1.06, ARM_Z, fr),
        (x0 + flen * 0.62, fy * 1.10, ARM_Z - 0.004, fr * 0.97),
        (x0 + flen * 0.88, fy * 1.12, ARM_Z - 0.010, fr * 0.93),
        (x0 + flen, fy * 1.13, ARM_Z - 0.014, fr * 0.75),
    ]
    loft(fname + ".L", [ring(p[:3], None, Z, p[3] * 0.9, p[3] * 0.85) for p in pts], "M_Glove",
         ["Hand.L", fname + "1.L", fname + "2.L"], segs=8, bulge1=0.6, left=True)
loft("Thumb.L", [
    ring((0.772, -0.034, ARM_Z - 0.004), None, Z, 0.021, 0.019),
    ring((0.800, -0.062, ARM_Z - 0.008), None, Z, 0.019, 0.018),
    ring((0.826, -0.080, ARM_Z - 0.011), None, Z, 0.018, 0.017),
    ring((0.843, -0.090, ARM_Z - 0.013), None, Z, 0.016, 0.015),
    ring((0.852, -0.094, ARM_Z - 0.015), None, Z, 0.011, 0.011),
], "M_Glove", ["Hand.L", "Thumb1.L", "Thumb2.L"], segs=8, bulge1=0.6, left=True)

# ---------------------------------------------------------------------------
# TROUSERS
# ---------------------------------------------------------------------------
PB = ["Hips", "Spine", "UpperLeg.L", "UpperLeg.R"]
pelvis = loft("Pelvis", [
    ring((0, 0.010, 0.83), Z, FRONT, 0.085, 0.070),
    ring((0, 0.012, 0.87), Z, FRONT, 0.152, 0.112, 2.2),
    ring((0, 0.010, 0.93), Z, FRONT, 0.172, 0.121, 2.3),
    ring((0, 0.004, 1.00), Z, FRONT, 0.167, 0.117, 2.3),
    ring((0, 0.002, 1.06), Z, FRONT, 0.161, 0.114, 2.3),
    ring((0, 0.002, 1.085), Z, FRONT, 0.160, 0.113, 2.3),
    ring((0, 0.002, 1.090), Z, FRONT, 0.152, 0.106, 2.3),
], "M_Uniform", PB, segs=20, bulge0=0.2, bulge1=0.05)
plb = bvh_of(pelvis)

# belt + buckle
patch("Belt", plb, (0, 0, 0), Z, FRONT, 0.0, 2 * math.pi, 1.036, 1.072, "M_Belt",
      ["Hips", "Spine"], thick=0.006, nu=48, nv=3, wrap=True, edge=0.6)
loc, nrm = surf_hit(plb, (0, 0, 1.054), FRONT)
rounded_box("Buckle", loc + nrm * 0.009, (0.052, 0.012, 0.042), "M_Metal", ["Hips"], bevel=0.35)
# back pockets
patch("BackPocket.L", plb, (0, 0, 0), Z, FRONT, math.pi - 0.78, math.pi - 0.18, 0.905, 1.012,
      "M_Uniform", ["Hips"], thick=0.004, left=True)
patch("BackFlap.L", plb, (0, 0, 0), Z, FRONT, math.pi - 0.80, math.pi - 0.16, 1.0, 1.03,
      "M_UniformPatch", ["Hips"], thick=0.007, nv=4, left=True)


def lr(z, w, d, n=2.0, dy=0.0):
    return ring(leg_point(z, dy), LEG_AXIS, FRONT, w * 1.07, d * 1.07, n)


leg = loft("Leg.L", [
    lr(0.975, 0.094, 0.104),
    lr(0.880, 0.093, 0.099, dy=0.004),
    lr(0.760, 0.084, 0.090, dy=0.002),
    lr(0.630, 0.072, 0.078),
    lr(0.525, 0.064, 0.070, dy=-0.004),
    lr(0.430, 0.066, 0.071, dy=0.004),
    lr(0.330, 0.059, 0.064, dy=0.003),
    lr(0.250, 0.062, 0.067),
    lr(0.205, 0.068, 0.072),
    lr(0.178, 0.068, 0.072),
    lr(0.163, 0.052, 0.055),
], "M_Uniform", ["Hips", "UpperLeg.L", "LowerLeg.L"], segs=16, bulge0=0.1, bulge1=0.1,
    left=True)
lb = bvh_of(leg)
# outward = +X: with ref=FRONT the side vector is roughly -X, so outward is angle -pi/2
OUTA = -math.pi / 2
patch("CargoPocket.L", lb, HIP, LEG_AXIS, FRONT, OUTA - 0.70, OUTA + 1.05, leg_h(0.765),
      leg_h(0.585), "M_Uniform", ["UpperLeg.L"], thick=0.008, nu=12, nv=12, left=True)
patch("CargoFlap.L", lb, HIP, LEG_AXIS, FRONT, OUTA - 0.76, OUTA + 1.11, leg_h(0.792),
      leg_h(0.745), "M_UniformPatch", ["UpperLeg.L"], thick=0.012, nu=12, nv=5, left=True)
patch("KneePatch.L", lb, HIP, LEG_AXIS, FRONT, -0.95, 0.95, leg_h(0.585), leg_h(0.455),
      "M_UniformPatch", ["UpperLeg.L", "LowerLeg.L"], thick=0.005, nu=12, nv=10, left=True)
loc, nrm = surf_hit(lb, leg_point(0.770), (math.cos(0.75), -math.sin(0.75), 0))
ellipsoid("CargoBtn.L", loc + nrm * 0.0135, (0.0065, 0.0032, 0.0065), "M_Button",
          ["UpperLeg.L"], segs=10, rings_=6, left=True)

# ---------------------------------------------------------------------------
# BOOTS (chunky, slightly oversized)
# ---------------------------------------------------------------------------
BX = 0.163
BOOT_B = ["LowerLeg.L", "Foot.L", "Toes.L"]
loft("BootShaft.L", [
    ring((ANKLE.x, 0.008, 0.215), Z, FRONT, 0.058, 0.062),
    ring((ANKLE.x, 0.008, 0.185), Z, FRONT, 0.062, 0.067),
    ring((ANKLE.x + 0.001, 0.010, 0.140), Z, FRONT, 0.064, 0.072),
    ring((ANKLE.x + 0.002, 0.012, 0.080), Z, FRONT, 0.066, 0.080),
], "M_BootLeather", ["LowerLeg.L", "Foot.L"], segs=16, bulge0=0.1, bulge1=0.1, left=True)
foot = loft("BootFoot.L", [
    ring((BX, 0.088, 0.075), FRONT, Z, 0.042, 0.048, 2.4),
    ring((BX, 0.072, 0.090), FRONT, Z, 0.058, 0.066, 2.6),
    ring((BX, 0.030, 0.098), FRONT, Z, 0.065, 0.076, 2.6),
    ring((BX, -0.030, 0.085), FRONT, Z, 0.067, 0.066, 2.6),
    ring((BX, -0.090, 0.066), FRONT, Z, 0.069, 0.050, 2.7),
    ring((BX, -0.150, 0.056), FRONT, Z, 0.068, 0.040, 2.7),
    ring((BX, -0.200, 0.053), FRONT, Z, 0.060, 0.034, 2.5),
    ring((BX, -0.228, 0.050), FRONT, Z, 0.044, 0.026, 2.3),
], "M_BootLeather", BOOT_B, segs=16, bulge0=0.25, bulge1=0.35, left=True)
loft("BootSole.L", [
    ring((BX, 0.100, 0.021), FRONT, Z, 0.050, 0.020, 4.0),
    ring((BX, 0.088, 0.021), FRONT, Z, 0.066, 0.021, 5.0),
    ring((BX, 0.020, 0.021), FRONT, Z, 0.071, 0.021, 5.0),
    ring((BX, -0.040, 0.021), FRONT, Z, 0.071, 0.018, 5.0),
    ring((BX, -0.120, 0.019), FRONT, Z, 0.075, 0.018, 5.0),
    ring((BX, -0.200, 0.021), FRONT, Z, 0.068, 0.019, 4.5),
    ring((BX, -0.236, 0.026), FRONT, Z, 0.050, 0.017, 3.5),
], "M_BootSole", ["Foot.L", "Toes.L"], segs=16, bulge0=0.15, bulge1=0.3, left=True)
for ob in [o for o in COL.objects if o.name.startswith(("BootShaft", "BootFoot", "BootSole"))]:
    for v in ob.data.vertices:
        v.co = Vector((BX + (v.co.x - BX) * 1.10, -0.07 + (v.co.y + 0.07) * 1.04, v.co.z * 1.06))
fb = bvh_of(foot)
patch("ToeCap.L", fb, (BX, 0, 0.05), FRONT, Z, -1.25, 1.25, 0.150, 0.236, "M_BootToe",
      ["Toes.L"], thick=0.004, nu=12, nv=6, left=True)
patch("HeelCap.L", fb, (BX, 0, 0.07), FRONT, (0, 0, -1), math.pi - 1.6, math.pi + 1.6, -0.09,
      0.02, "M_BootLeather", ["Foot.L"], thick=0.004, nu=12, nv=6, edge=0.5, left=True)
# lace panel + laces across the instep and up the shaft front
patch("Tongue.L", fb, (BX, 0, 0.05), FRONT, Z, -0.42, 0.42, 0.005, 0.125, "M_BootLeather",
      ["Foot.L"], thick=0.005, nu=6, nv=10, left=True)
for i, y in enumerate((-0.020, -0.045, -0.070, -0.095, -0.118)):
    loc, nrm = surf_hit(fb, (BX, y, 0.0), Z)
    rounded_box("Lace%d.L" % i, loc + nrm * 0.008, (0.05, 0.007, 0.006), "M_Lace", ["Foot.L"],
                rot=Matrix.Rotation(math.atan2(-nrm.y, nrm.z), 4, "X"), bevel=0.5, left=True)
shaft = [o for o in COL.objects if o.name == "BootShaft.L"][0]
shb = bvh_of(shaft)
for i, z in enumerate((0.112, 0.140)):
    loc, nrm = surf_hit(shb, (ANKLE.x, 0.01, z), FRONT)
    rounded_box("ShaftLace%d.L" % i, loc + nrm * 0.004, (0.048, 0.007, 0.006), "M_Lace",
                ["LowerLeg.L"], bevel=0.5, left=True)
# ---------------------------------------------------------------------------
# mirror left -> right
# ---------------------------------------------------------------------------
for ob in list(LEFT):
    mirror_x(ob)

# ---------------------------------------------------------------------------
# ARMATURE
# ---------------------------------------------------------------------------
KNEE = leg_point(0.52, -0.008)
BONES = [  # name, head, tail, parent, connected, deform
    ("Root", (0, 0, 0), (0, 0.25, 0), None, False, False),
    ("Hips", (0, 0.005, 0.95), (0, 0.005, 1.06), "Root", False, True),
    ("Spine", (0, 0.005, 1.06), (0, 0.004, 1.20), "Hips", True, True),
    ("Chest", (0, 0.004, 1.20), (0, 0.004, 1.40), "Spine", True, True),
    ("Neck", (0, 0.008, 1.47), (0, 0.012, 1.585), "Chest", False, True),
    ("Head", (0, 0.012, 1.585), (0, 0.012, 1.80), "Neck", True, True),
]
for s, sx in (("L", 1), ("R", -1)):
    def m(p, sx=sx):
        return (p[0] * sx, p[1], p[2])
    BONES += [
        ("Shoulder." + s, m((0.03, 0, 1.42)), m((0.165, 0, ARM_Z)), "Chest", False, True),
        ("UpperArm." + s, m((0.165, 0, ARM_Z)), m((0.465, 0.004, ARM_Z)), "Shoulder." + s, True, True),
        ("LowerArm." + s, m((0.465, 0.004, ARM_Z)), m((0.750, 0, ARM_Z)), "UpperArm." + s, True, True),
        ("Hand." + s, m((0.750, 0, ARM_Z)), m((0.848, 0, ARM_Z)), "LowerArm." + s, True, True),
        ("Thumb1." + s, m((0.772, -0.034, ARM_Z - 0.004)), m((0.810, -0.070, ARM_Z - 0.009)), "Hand." + s, False, True),
        ("Thumb2." + s, m((0.810, -0.070, ARM_Z - 0.009)), m((0.852, -0.094, ARM_Z - 0.015)), "Thumb1." + s, True, True),
        ("UpperLeg." + s, m(HIP), m(KNEE), "Hips", False, True),
        ("LowerLeg." + s, m(KNEE), m(ANKLE), "UpperLeg." + s, True, True),
        ("Foot." + s, m(ANKLE), m((BX, -0.13, 0.04)), "LowerLeg." + s, True, True),
        ("Toes." + s, m((BX, -0.13, 0.04)), m((BX, -0.225, 0.04)), "Foot." + s, True, True),
    ]
    for fname, fy, flen, fr in FINGERS:
        x0 = 0.848
        mid = (x0 + flen * 0.55, fy * 1.08, ARM_Z - 0.002)
        tip = (x0 + flen, fy * 1.13, ARM_Z - 0.014)
        BONES += [
            (fname + "1." + s, m((x0, fy, ARM_Z + 0.001)), m(mid), "Hand." + s, False, True),
            (fname + "2." + s, m(mid), m(tip), fname + "1." + s, True, True),
        ]

arm_data = bpy.data.armatures.new("SoldierRig")
arm_data.display_type = "STICK"
arm = bpy.data.objects.new("Armature", arm_data)
COL.objects.link(arm)
arm.show_in_front = True
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones
for name, h, t, parent, conn, deform in BONES:
    b = eb.new(name)
    b.head, b.tail = Vector(h), Vector(t)
    b.use_deform = deform
for name, h, t, parent, conn, deform in BONES:
    if parent:
        eb[name].parent = eb[parent]
        eb[name].use_connect = conn
for b in eb:  # consistent bone roll: Z axis up for spine/arms, forward for legs
    if b.name.startswith(("UpperLeg", "LowerLeg", "Foot", "Toes")):
        b.align_roll(Vector((0, -1, 0)) if not b.name.startswith(("Foot", "Toes")) else Vector((0, 0, 1)))
    elif b.name in ("Root",):
        b.align_roll(Vector((0, 0, 1)))
    elif b.name in ("Hips", "Spine", "Chest", "Neck", "Head"):
        b.align_roll(Vector((0, -1, 0)))
    else:
        b.align_roll(Vector((0, 0, 1)))
bpy.ops.object.mode_set(mode="OBJECT")
arm.select_set(False)
BONE_SEG = {name: (Vector(h), Vector(t)) for name, h, t, _, _, d in BONES if d}


# ---------------------------------------------------------------------------
# skin weights: smooth inverse-distance to allowed bone segments
# ---------------------------------------------------------------------------
def seg_dist(p, a, b):
    q, f = intersect_point_line(p, a, b)
    f = max(0.0, min(1.0, f))
    return (p - a.lerp(b, f)).length


def weight(ob, power=5.0):
    names = [n for n in ob["bones"].split(",") if n]
    groups = {n: ob.vertex_groups.new(name=n) for n in names}
    for v in ob.data.vertices:
        ws = []
        for n in names:
            a, b = BONE_SEG[n]
            d = max(seg_dist(v.co, a, b), 0.004)
            ws.append((1.0 / d ** power, n))
        ws.sort(reverse=True)
        ws = ws[:3]
        tot = sum(w for w, _ in ws)
        for w, n in ws:
            w /= tot
            if w > 0.01:
                groups[n].add([v.index], w, "REPLACE")


meshes = [o for o in COL.objects if o.type == "MESH"]
for ob in meshes:
    weight(ob)


# ---------------------------------------------------------------------------
# join into modular pieces and bind to the armature
# ---------------------------------------------------------------------------
def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    ob.select_set(False)
    return ob


PIECES = {}
BY_GROUP = {}
for o in meshes:
    BY_GROUP.setdefault(o["group"], []).append(o)
for g, nice in (("Body", "Soldier_Body"), ("Hair", "Soldier_Hair"), ("Gloves", "Soldier_Gloves"),
                ("Boots", "Soldier_Boots")):
    objs = BY_GROUP[g]
    objs.sort(key=lambda o: o.name not in ("Jacket", "Head", "Hair", "Palm.L", "BootFoot.L"))
    PIECES[g] = join(objs, nice)

for ob in PIECES.values():
    for k in ("bones", "group"):
        if k in ob:
            del ob[k]
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.to_mesh(ob.data)
    bm.free()
    ob.parent = arm
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    # game mesh stays low; one extra subdivision only at render time
    sub = ob.modifiers.new("RenderSmooth", "SUBSURF")
    sub.levels = 0
    sub.render_levels = 1

# UVs
for ob in PIECES.values():
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.select_set(False)

# ---------------------------------------------------------------------------
# render setup: flat, even, shadowless-looking ambient light, light grey backdrop
# ---------------------------------------------------------------------------
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24 if PREVIEW else 160
scene.cycles.use_denoising = True
try:
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception:
    pass
scene.cycles.max_bounces = 4
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.film_transparent = False

world = bpy.data.worlds.new("FlatGrey")
scene.world = world
world.use_nodes = True
wn, wl = world.node_tree.nodes, world.node_tree.links
bg_light = wn["Background"]
bg_light.inputs["Color"].default_value = (1, 1, 1, 1)
bg_light.inputs["Strength"].default_value = 1.15
bg_cam = wn.new("ShaderNodeBackground")
bg_cam.inputs["Color"].default_value = srgb("#c9cacc")
bg_cam.inputs["Strength"].default_value = 1.0
lp = wn.new("ShaderNodeLightPath")
mix = wn.new("ShaderNodeMixShader")
wl.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
wl.new(bg_light.outputs["Background"], mix.inputs[1])
wl.new(bg_cam.outputs["Background"], mix.inputs[2])
wl.new(mix.outputs["Shader"], wn["World Output"].inputs["Surface"])

cam_data = bpy.data.cameras.new("TurnCam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 2.08
cam = bpy.data.objects.new("TurnCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
RES = 640 if PREVIEW else 1400
scene.render.resolution_x = RES
scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

VIEWS = [
    ("front", (0, -10, 0.91), (math.pi / 2, 0, 0)),
    ("side", (-10, 0, 0.91), (math.pi / 2, 0, -math.pi / 2)),
    ("back", (0, 10, 0.91), (math.pi / 2, 0, math.pi)),
]
renders = []
os.makedirs(os.path.join(OUT, "renders"), exist_ok=True)
for vname, loc, rot in VIEWS:
    cam.location = loc
    cam.rotation_euler = rot
    path = os.path.join(OUT, "renders", "view_%s.png" % vname)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    renders.append((vname, path))
    print("rendered", path)

# 3/4 perspective beauty shot
if not PREVIEW:
    cam_data.type = "PERSP"
    cam_data.lens = 115
    cam.location = (3.6, -5.6, 2.3)
    d = Vector((0, 0, 0.92)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1400
    scene.render.filepath = os.path.join(OUT, "renders", "view_three_quarter.png")
    bpy.ops.render.render(write_still=True)
    # top-down RTS camera
    cam.location = (0, -4.2, 6.0)
    d = Vector((0, 0, 0.8)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, "renders", "view_rts_topdown.png")
    bpy.ops.render.render(write_still=True)
    cam_data.type = "ORTHO"
    cam.location, cam.rotation_euler = VIEWS[0][1], VIEWS[0][2]

if PREVIEW or "--closeups" in ARGS:
    for cname, loc, rot, scale in (
        ("head_front", (0, -10, 1.67), (math.pi / 2, 0, 0), 0.38),
        ("head_side", (-10, 0, 1.67), (math.pi / 2, 0, -math.pi / 2), 0.38),
        ("hand_top", (0.78, 0, 10), (0, 0, 0), 0.36),
        ("hand_front", (0.78, -10, 1.41), (math.pi / 2, 0, 0), 0.36),
        ("boot_side", (-10, -0.05, 0.16), (math.pi / 2, 0, -math.pi / 2), 0.5),
        ("top_down", (0, 0, 10), (0, 0, 0), 2.08),
    ):
        cam.location, cam.rotation_euler, cam_data.ortho_scale = loc, rot, scale
        scene.render.filepath = os.path.join(OUT, "renders", "close_%s.png" % cname)
        bpy.ops.render.render(write_still=True)
    cam_data.ortho_scale = 2.08

# stitch the turnaround sheet
try:
    from PIL import Image, ImageDraw, ImageFont
    ims = [Image.open(p).convert("RGB") for _, p in renders]
    w, h = ims[0].size
    pad = int(h * 0.07)
    sheet = Image.new("RGB", (w * 3, h + pad), ims[0].getpixel((5, 5)))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=int(pad * 0.45))
    except TypeError:
        font = ImageFont.load_default()
    for i, ((vname, _), im) in enumerate(zip(renders, ims)):
        sheet.paste(im, (i * w, pad))
        label = vname.upper()
        tw = draw.textlength(label, font=font)
        draw.text((i * w + (w - tw) / 2, pad * 0.3), label, fill=(70, 72, 74), font=font)
    sheet.save(os.path.join(OUT, "soldier_base_turnaround.png"))
    print("sheet saved")
except Exception as exc:  # pragma: no cover
    print("could not stitch sheet:", exc)

if PREVIEW:
    sys.exit(0)

# ---------------------------------------------------------------------------
# save the editable .blend (procedural materials)
# ---------------------------------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "soldier_base.blend"), compress=True)

# ---------------------------------------------------------------------------
# bake albedo (colour only: no light, no shadow) -> game materials -> export
# ---------------------------------------------------------------------------
scene.cycles.samples = 16
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
SIZES = {"Body": 2048, "Hair": 512, "Gloves": 1024, "Boots": 1024}
for g, ob in PIECES.items():
    img = bpy.data.images.new("T_Soldier_%s_BaseColor" % g, SIZES[g], SIZES[g])
    for slot in ob.material_slots:
        nt = slot.material.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.nodes.active = node
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=8, use_clear=True)
    img.filepath_raw = os.path.join(tex_dir, img.name + ".png")
    img.file_format = "PNG"
    img.save()
    ob.select_set(False)
    for slot in ob.material_slots:
        nt = slot.material.node_tree
        for nd in [n for n in nt.nodes if n.type == "TEX_IMAGE"]:
            nt.nodes.remove(nd)
    # single game material per piece
    gm = bpy.data.materials.new("M_Soldier_%s" % g)
    gm.use_nodes = True
    bsdf = gm.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    tn = gm.node_tree.nodes.new("ShaderNodeTexImage")
    tn.image = bpy.data.images.load(img.filepath_raw)
    gm.node_tree.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
    ob.data.materials.clear()
    ob.data.materials.append(gm)
    print("baked", g)

bpy.ops.object.select_all(action="DESELECT")
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "soldier_base.glb"), export_format="GLB",
                          export_apply=False, export_skins=True, export_animations=False)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "soldier_base.fbx"), add_leaf_bones=False,
                         path_mode="COPY", embed_textures=True, bake_anim=False,
                         object_types={"ARMATURE", "MESH"}, apply_scale_options="FBX_SCALE_ALL",
                         armature_nodetype="NULL")
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "soldier_base_game.blend"), compress=True)

# low-poly LOD for in-game use
for ob in PIECES.values():
    mod = ob.modifiers.new("LOD", "DECIMATE")
    mod.ratio = 0.3
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "soldier_base_lod1.glb"), export_format="GLB",
                          export_apply=True, export_skins=True, export_animations=False)
for ob in PIECES.values():
    ob.modifiers.remove(ob.modifiers["LOD"])

tris = {g: sum(len(p.vertices) - 2 for p in ob.data.polygons) for g, ob in PIECES.items()}
print("triangles:", tris, "total", sum(tris.values()))
print("DONE")
