"""
Kubereshwar Dham - 3D miniature diorama (Blender script)
=========================================================

Ek floating miniature diorama banata hai: Shiv mandir (Nagara shikhara),
mandapa, bada Shivling, saffron flags, gende ki maala, ped, chhote
shraddhalu, road aur gate. Golden-hour lighting aur tilt-shift camera ke saath.

Kaise chalayein
---------------
1) Blender GUI mein:
   Blender kholein -> "Scripting" tab -> Open -> yeh file -> "Run Script".
   Scene ban jayega. Render karne ke liye F12 dabayein.

2) Command line (seedha image ban jayegi):
   blender -b -P kubereshwar_dham_diorama.py -- --out dham.png
   blender -b -P kubereshwar_dham_diorama.py -- --aspect 16:9 --samples 256 --out thumb.png

Options (sab optional):
   --out PATH        output image (default: kubereshwar_dham.png)
   --aspect 9:16     9:16 (reel), 16:9 (YouTube), 1:1 (post)
   --res 1080        chhoti side ka pixel size (1080 -> 1080x1920)
   --samples 128     zyada = saaf image, lekin dheema
   --seed 7          logon/pedon ki random placement badalne ke liye
   --save PATH.blend scene ko .blend file mein save karein
   --gpu             GPU se render (agar available ho)

Tested on Blender 5.2. Blender 4.x par bhi chalna chahiye.
"""

import bpy
import math
import random
import sys
from mathutils import Vector

# ---------------------------------------------------------------- options


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {
        "out": "kubereshwar_dham.png",
        "aspect": "9:16",
        "res": 1080,
        "samples": 128,
        "seed": 7,
        "save": None,
        "gpu": False,
    }
    i = 0
    while i < len(argv):
        key = argv[i].lstrip("-")
        if key == "gpu":
            opts["gpu"] = True
        elif key in opts and i + 1 < len(argv):
            val = argv[i + 1]
            opts[key] = int(val) if isinstance(opts[key], int) and not isinstance(opts[key], bool) else val
            i += 1
        i += 1
    return opts


OPTS = parse_args()
random.seed(OPTS["seed"])

# ---------------------------------------------------------------- helpers


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


_MATS = {}


def mat(name, color, rough=0.55, metal=0.0, emit=0.0, brick=None):
    """Principled material (clay-jaisa look). brick=(color2, scale) se tiles pattern."""
    if name in _MATS:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit > 0:
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit
    if brick:
        color2, scale = brick
        tex = nt.nodes.new("ShaderNodeTexBrick")
        tex.inputs["Color1"].default_value = (*color, 1.0)
        tex.inputs["Color2"].default_value = (*color2, 1.0)
        tex.inputs["Mortar"].default_value = (color[0] * 0.75, color[1] * 0.75, color[2] * 0.75, 1.0)
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Mortar Size"].default_value = 0.015
        tex.offset = 0.5
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    _MATS[name] = m
    return m


def finish(obj, material, bevel=0.0, smooth=False):
    obj.data.materials.append(material)
    if bevel > 0:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = "ANGLE"
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def box(loc, size, material, bevel=0.03, name="Box"):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return finish(o, material, bevel)


def cyl(loc, r, h, material, verts=24, bevel=0.0, name="Cyl", smooth=True):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc)
    o = bpy.context.active_object
    o.name = name
    return finish(o, material, bevel, smooth)


def cone(loc, r1, r2, h, material, verts=24, name="Cone", smooth=True, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r1, radius2=r2, depth=h, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return finish(o, material, 0, smooth)


def sphere(loc, r, material, scale=(1, 1, 1), name="Sphere", seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    return finish(o, material, 0, True)


def instance(src, loc, scale=1.0):
    """Mesh data share karke copy (bahut saare chhote objects ke liye tez)."""
    o = src.copy()
    o.location = loc
    o.scale = (scale, scale, scale)
    bpy.context.collection.objects.link(o)
    return o


def lathe(name, profile, material, seg=16, star=0.0, loc=(0, 0, 0), smooth=False):
    """Profile [(radius, z), ...] ko z-axis ke chaaron taraf ghuma kar mesh banata hai.
    star > 0 hone par plan taare jaisa (Nagara shikhara ki rekhaayein)."""
    verts, faces = [], []
    for r, z in profile:
        for i in range(seg):
            a = 2 * math.pi * i / seg + math.pi / seg
            rr = r * (1.0 - star if i % 2 else 1.0)
            verts.append((rr * math.cos(a), rr * math.sin(a), z))
    for j in range(len(profile) - 1):
        for i in range(seg):
            a, b = j * seg + i, j * seg + (i + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    if profile[0][0] > 0:
        faces.append(tuple(reversed(range(seg))))
    if profile[-1][0] > 0:
        last = (len(profile) - 1) * seg
        faces.append(tuple(range(last, last + seg)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    o.location = loc
    bpy.context.collection.objects.link(o)
    return finish(o, material, 0, smooth)


def flag(base, height, material, size=0.5, pole_mat=None):
    """Bamboo pole + trikon bhagwa dhwaj."""
    x, y, z = base
    cyl((x, y, z + height / 2), 0.025, height, pole_mat or MAT["wood"], verts=8, name="FlagPole")
    s = size
    verts = [(0, 0, 0), (0, 0, -s * 0.6), (s, 0, -s * 0.32)]
    # thoda lehrata hua: beech ka point aage jhuka
    verts.append((s * 0.5, s * 0.08, -s * 0.28))
    faces = [(0, 3, 2), (0, 1, 3), (1, 2, 3)]
    me = bpy.data.meshes.new("Flag")
    me.from_pydata(verts, [], faces)
    o = bpy.data.objects.new("Flag", me)
    o.location = (x, y, z + height)
    o.rotation_euler = (0, 0, random.uniform(-0.4, 0.4) + math.pi * 0.15)
    bpy.context.collection.objects.link(o)
    sol = o.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.01
    finish(o, material)
    return o


def garland(p1, p2, sag, flower_a, flower_b, count=22):
    """Do points ke beech latakti gende ki maala."""
    p1, p2 = Vector(p1), Vector(p2)
    for i in range(count + 1):
        t = i / count
        p = p1.lerp(p2, t)
        p.z -= sag * 4 * t * (1 - t)
        instance(flower_a if i % 3 else flower_b, p)


# ---------------------------------------------------------------- scene

clear_scene()

MAT = {
    "grass": mat("Grass", (0.30, 0.55, 0.18), 0.8),
    "earth": mat("Earth", (0.42, 0.25, 0.13), 0.9),
    "earth_dark": mat("EarthDark", (0.28, 0.16, 0.08), 0.95),
    "paving": mat("Paving", (0.88, 0.78, 0.62), 0.7, brick=((0.82, 0.71, 0.55), 6.0)),
    "road": mat("Road", (0.72, 0.58, 0.42), 0.95),
    "white": mat("TempleWhite", (0.93, 0.90, 0.84), 0.5),
    "cream": mat("Cream", (0.95, 0.84, 0.62), 0.5),
    "saffron": mat("Saffron", (1.0, 0.40, 0.03), 0.45),
    "red": mat("Maroon", (0.62, 0.08, 0.06), 0.5),
    "gold": mat("Gold", (1.0, 0.72, 0.25), 0.25, metal=1.0),
    "stone_black": mat("ShivlingStone", (0.03, 0.03, 0.035), 0.18),
    "wood": mat("Bamboo", (0.55, 0.38, 0.18), 0.7),
    "trunk": mat("Trunk", (0.33, 0.20, 0.10), 0.85),
    "marigold": mat("Marigold", (1.0, 0.48, 0.0), 0.6),
    "marigold_y": mat("MarigoldYellow", (1.0, 0.78, 0.05), 0.6),
    "skin": mat("Skin", (0.62, 0.40, 0.26), 0.6),
    "rock": mat("Rock", (0.45, 0.42, 0.40), 0.85),
    "diya": mat("DiyaFlame", (1.0, 0.6, 0.15), 0.5, emit=12.0),
}
LEAVES = [mat(f"Leaves{i}", c, 0.75) for i, c in enumerate(
    [(0.16, 0.42, 0.12), (0.22, 0.50, 0.14), (0.12, 0.36, 0.10), (0.30, 0.52, 0.16)])]
CLOTHES = [mat(f"Cloth{i}", c, 0.6) for i, c in enumerate([
    (1.0, 0.40, 0.03), (0.85, 0.08, 0.10), (0.98, 0.80, 0.10), (0.10, 0.45, 0.85),
    (0.95, 0.95, 0.92), (0.75, 0.10, 0.55), (0.10, 0.60, 0.35), (1.0, 0.55, 0.65)])]

# --- floating base: ghaas ki upar wali parat + mitti ki moti parat
HALF = 6.0
box((0, 0, -0.15), (2 * HALF, 2 * HALF, 0.3), MAT["grass"], bevel=0.08, name="GrassTop")
box((0, 0, -1.25), (2 * HALF - 0.1, 2 * HALF - 0.1, 1.9), MAT["earth"], bevel=0.1, name="Earth")
box((0, 0, -2.45), (2 * HALF - 0.6, 2 * HALF - 0.6, 0.6), MAT["earth_dark"], bevel=0.15, name="EarthBottom")
for _ in range(14):  # mitti mein chhote patthar
    side = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
    t = random.uniform(-HALF + 0.6, HALF - 0.6)
    x = side[0] * (HALF - 0.02) if side[0] else t
    y = side[1] * (HALF - 0.02) if side[1] else t
    sphere((x, y, random.uniform(-2.2, -0.6)), random.uniform(0.12, 0.25), MAT["rock"],
           scale=(1, 1, 0.6), name="Rock", seg=10)

# --- aangan (courtyard) aur boundary wall
C = 4.6  # courtyard half-size
box((0, 0, 0.03), (2 * C, 2 * C, 0.06), MAT["paving"], bevel=0.02, name="Courtyard")
WALL_H, WALL_T = 0.32, 0.18
gate_gap = 0.9
box((0, C, WALL_H / 2), (2 * C, WALL_T, WALL_H), MAT["cream"], name="WallBack")
box((-C, 0, WALL_H / 2), (WALL_T, 2 * C, WALL_H), MAT["cream"], name="WallL")
box((C, 0, WALL_H / 2), (WALL_T, 2 * C, WALL_H), MAT["cream"], name="WallR")
seg_len = C - gate_gap
for sx in (-1, 1):
    box((sx * (gate_gap + seg_len / 2), -C, WALL_H / 2), (seg_len, WALL_T, WALL_H), MAT["cream"], name="WallFront")
# deewar par saffron patti
for (lx, ly, sx, sy) in [(0, C, 2 * C, WALL_T), (-C, 0, WALL_T, 2 * C), (C, 0, WALL_T, 2 * C)]:
    box((lx, ly, WALL_H + 0.02), (sx + 0.04, sy + 0.04, 0.05), MAT["saffron"], bevel=0.01, name="WallCap")
for sx in (-1, 1):
    box((sx * (gate_gap + seg_len / 2), -C, WALL_H + 0.02), (seg_len + 0.04, WALL_T + 0.04, 0.05),
        MAT["saffron"], bevel=0.01, name="WallCap")

# --- road aur gate (toran dwar)
box((0, -(C + HALF) / 2 - 0.05, 0.02), (1.7, HALF - C + 0.2, 0.05), MAT["road"], bevel=0.02, name="Road")
for sx in (-1, 1):
    box((sx * gate_gap, -C, 0.9), (0.28, 0.28, 1.8), MAT["red"], name="GatePillar")
    sphere((sx * gate_gap, -C, 1.92), 0.13, MAT["gold"], name="GateKnob")
box((0, -C, 1.75), (2 * gate_gap + 0.5, 0.32, 0.22), MAT["saffron"], name="GateBeam")
box((0, -C, 1.95), (2 * gate_gap - 0.2, 0.22, 0.18), MAT["red"], name="GateTop")

# chhote phool (instance ke liye source)
FLOWER_A = sphere((0, 0, -50), 0.045, MAT["marigold"], name="FlowerA", seg=8)
FLOWER_B = sphere((0, 0, -50), 0.045, MAT["marigold_y"], name="FlowerB", seg=8)
garland((-gate_gap, -C - 0.17, 1.62), (gate_gap, -C - 0.17, 1.62), 0.35, FLOWER_A, FLOWER_B, 26)

# --- mukhya mandir: jagati (stepped plinth)
TY = 2.2  # temple centre (y)
for i, (w, d) in enumerate([(5.2, 6.6), (4.7, 6.1), (4.2, 5.6)]):
    box((0, TY - 0.5, 0.06 + 0.15 * i + 0.075), (w, d, 0.15), MAT["cream" if i % 2 else "white"],
        bevel=0.02, name="Plinth")
PLINTH_TOP = 0.06 + 0.45
# saamne ki seedhiyan
for i in range(3):
    box((0, TY - 0.5 - 3.3 - 0.18 * (2 - i) + 0.05, 0.06 + 0.075 + 0.15 * i),
        (1.3, 0.36 + 0.36 * (2 - i), 0.15), MAT["white"], bevel=0.015, name="Step")

# garbhagriha (gabhara)
GB = 2.6
box((0, TY + 0.6, PLINTH_TOP + 0.9), (GB, GB, 1.8), MAT["white"], bevel=0.04, name="Garbhagriha")
box((0, TY + 0.6, PLINTH_TOP + 1.85), (GB + 0.2, GB + 0.2, 0.12), MAT["saffron"], name="Cornice")
box((0, TY + 0.6 - GB / 2 - 0.01, PLINTH_TOP + 0.6), (0.7, 0.05, 1.1), MAT["red"], name="Doorway")

# shikhara: tiers wala Nagara tower (lathe se)
H, R = 4.4, 1.25
tiers = 9
profile = []
for k in range(tiers):
    z0 = k * H / tiers
    z1 = (k + 1) * H / tiers
    r0 = R * (1 - (z0 / H) ** 1.7) * 0.92 + 0.12
    r1 = R * (1 - (z1 / H) ** 1.7) * 0.92 + 0.12
    profile += [(r0, z0), (r0 * 0.98, z0 + (z1 - z0) * 0.75), (r1 * 0.9, z0 + (z1 - z0) * 0.8)]
profile.append((0.25, H + 0.05))
SHIKHARA_BASE = PLINTH_TOP + 1.91
lathe("Shikhara", profile, MAT["white"], seg=16, star=0.12, loc=(0, TY + 0.6, SHIKHARA_BASE))
# amalaka + kalash
amalaka = lathe("Amalaka", [(0.12, 0), (0.42, 0.06), (0.46, 0.14), (0.42, 0.22), (0.12, 0.28)],
                MAT["cream"], seg=24, star=0.08, loc=(0, TY + 0.6, SHIKHARA_BASE + H + 0.02), smooth=True)
TOP = SHIKHARA_BASE + H + 0.3
lathe("Kalash", [(0.0, 0), (0.15, 0.03), (0.2, 0.15), (0.12, 0.3), (0.06, 0.38), (0.1, 0.42), (0.0, 0.6)],
      MAT["gold"], seg=24, loc=(0, TY + 0.6, TOP), smooth=True)
flag((0.08, TY + 0.6, TOP + 0.4), 1.0, MAT["saffron"], size=0.9)

# chhote urushringa (shikhare ke kono par)
for sx in (-1, 1):
    for sy in (-1, 1):
        p = [(0.42, 0), (0.4, 0.3), (0.34, 0.6), (0.24, 0.9), (0.12, 1.1), (0.05, 1.2)]
        lathe("Urushringa", p, MAT["white"], seg=12, star=0.1,
              loc=(sx * 1.05, TY + 0.6 + sy * 1.05, SHIKHARA_BASE))
        sphere((sx * 1.05, TY + 0.6 + sy * 1.05, SHIKHARA_BASE + 1.25), 0.07, MAT["gold"], name="MiniKalash")

# mandapa (saamne ka hall: khambe + seedhidaar chhat)
MY = TY - 1.9
MW, MD = 3.2, 2.2
box((0, MY, PLINTH_TOP + 0.05), (MW, MD, 0.1), MAT["cream"], name="MandapaFloor")
PIL_H = 1.35
pillar_pos = [(x, y) for x in (-MW / 2 + 0.2, -0.5, 0.5, MW / 2 - 0.2) for y in (MY - MD / 2 + 0.2, MY + MD / 2 - 0.2)]
for (px, py) in pillar_pos:
    cyl((px, py, PLINTH_TOP + 0.1 + PIL_H / 2), 0.11, PIL_H, MAT["white"], verts=8, bevel=0.01, name="Pillar")
    box((px, py, PLINTH_TOP + 0.15), (0.3, 0.3, 0.1), MAT["saffron"], name="PillarBase")
    box((px, py, PLINTH_TOP + 0.1 + PIL_H - 0.05), (0.3, 0.3, 0.1), MAT["saffron"], name="PillarCap")
roof_z = PLINTH_TOP + 0.1 + PIL_H
for i, (w, d) in enumerate([(MW + 0.4, MD + 0.4), (MW - 0.1, MD - 0.1), (MW - 0.6, MD - 0.6),
                            (MW - 1.1, MD - 1.1), (MW - 1.6, MD - 1.4)]):
    box((0, MY, roof_z + 0.12 + 0.24 * i), (w, d, 0.24), MAT["white" if i % 2 == 0 else "saffron"],
        bevel=0.03, name="MandapaRoof")
lathe("MandapaKalash", [(0.0, 0), (0.14, 0.04), (0.17, 0.14), (0.08, 0.28), (0.0, 0.42)],
      MAT["gold"], seg=20, loc=(0, MY, roof_z + 1.2), smooth=True)
front_y = MY - MD / 2 + 0.2 - 0.13
garland((-MW / 2 + 0.2, front_y, roof_z - 0.08), (-0.5, front_y, roof_z - 0.08), 0.22, FLOWER_A, FLOWER_B, 14)
garland((-0.5, front_y, roof_z - 0.08), (0.5, front_y, roof_z - 0.08), 0.25, FLOWER_A, FLOWER_B, 14)
garland((0.5, front_y, roof_z - 0.08), (MW / 2 - 0.2, front_y, roof_z - 0.08), 0.22, FLOWER_A, FLOWER_B, 14)

# --- bada Shivling (aangan ke beech)
SX, SY = 0.0, -2.3
cyl((SX, SY, 0.12), 1.15, 0.14, MAT["white"], verts=48, bevel=0.02, name="ShivPlatform")
cyl((SX, SY, 0.23), 0.95, 0.1, MAT["saffron"], verts=48, bevel=0.02, name="ShivPlatform2")
lathe("Jaladhari", [(0.0, 0.28), (0.78, 0.28), (0.82, 0.36), (0.72, 0.42), (0.6, 0.44), (0.58, 0.5),
                    (0.66, 0.55), (0.62, 0.6), (0.0, 0.6)], MAT["stone_black"], seg=48,
      loc=(SX, SY, 0), smooth=True)
box((SX + 0.95, SY, 0.53), (0.55, 0.22, 0.08), MAT["stone_black"], bevel=0.03, name="JaladhariSpout")
lathe("Lingam", [(0.0, 0.6), (0.36, 0.6)] + [
    (0.36 * math.cos(a), 1.35 + 0.36 * math.sin(a)) for a in [i * math.pi / 2 / 8 for i in range(9)]],
    MAT["stone_black"], seg=48, loc=(SX, SY, 0), smooth=True)
# tripund (teen safed rekhaayein) + bilva/phool
for k in range(3):
    box((SX, SY - 0.35, 1.18 + k * 0.07), (0.42, 0.03, 0.025), MAT["white"], bevel=0.008, name="Tripund")
sphere((SX, SY - 0.36, 1.28), 0.03, MAT["red"], name="Tilak", seg=8)
for k in range(28):
    a = 2 * math.pi * k / 28
    instance(FLOWER_A if k % 2 else FLOWER_B, (SX + 0.68 * math.cos(a), SY + 0.68 * math.sin(a), 0.62))
# chaaron taraf diye
DIYA = sphere((0, 0, -50), 0.035, MAT["diya"], scale=(1, 1, 1.6), name="DiyaSrc", seg=8)
for k in range(12):
    a = 2 * math.pi * k / 12
    instance(DIYA, (SX + 1.05 * math.cos(a), SY + 1.05 * math.sin(a), 0.24))

# --- side shrines (chhote mandir)
for sx in (-1, 1):
    bx, by = sx * 3.4, 1.4
    box((bx, by, 0.2), (1.2, 1.2, 0.3), MAT["cream"], name="ShrinePlinth")
    box((bx, by, 0.75), (0.9, 0.9, 0.8), MAT["white"], name="Shrine")
    box((bx, by - 0.46, 0.65), (0.32, 0.04, 0.5), MAT["red"], name="ShrineDoor")
    p = [(0.55, 0), (0.5, 0.35), (0.4, 0.7), (0.26, 1.0), (0.12, 1.2), (0.08, 1.25)]
    lathe("ShrineShikhara", p, MAT["saffron" if sx < 0 else "white"], seg=12, star=0.1, loc=(bx, by, 1.15))
    sphere((bx, by, 2.45), 0.09, MAT["gold"], name="ShrineKalash")
    flag((bx, by, 2.5), 0.55, MAT["saffron"], size=0.4)

# deewar ke kono par bhagwa dhwaj
for (fx, fy) in [(-C, -C), (C, -C), (-C, C), (C, C), (-C, 0), (C, 0)]:
    flag((fx, fy, WALL_H), 1.3, MAT["saffron"], size=0.5)

# --- ped (aangan ke bahar ghaas par)
def tree(x, y, s):
    cyl((x, y, 0.4 * s), 0.07 * s, 0.8 * s, MAT["trunk"], verts=8, name="Trunk")
    leaf = random.choice(LEAVES)
    for _ in range(3):
        sphere((x + random.uniform(-0.2, 0.2) * s, y + random.uniform(-0.2, 0.2) * s,
                (0.9 + random.uniform(0, 0.45)) * s), random.uniform(0.32, 0.45) * s, leaf,
               name="Leaves", seg=14)


tree_spots = []
for _ in range(400):
    if len(tree_spots) >= 16:
        break
    x, y = random.uniform(-HALF + 0.45, HALF - 0.45), random.uniform(-HALF + 0.45, HALF - 0.45)
    if max(abs(x), abs(y)) < C + 0.5:  # aangan ke andar nahi
        continue
    if abs(x) < 1.3 and y < 0:  # road par nahi
        continue
    if all((x - tx) ** 2 + (y - ty) ** 2 > 0.8 ** 2 for tx, ty in tree_spots):
        tree_spots.append((x, y))
        tree(x, y, random.uniform(0.75, 1.15))

# --- shraddhalu (chhote log)
BODY_SRC = []
for m in CLOTHES:
    o = cone((0, 0, -50), 0.09, 0.05, 0.26, m, verts=12, name="BodySrc")
    BODY_SRC.append(o)
HEAD_SRC = sphere((0, 0, -50), 0.055, MAT["skin"], name="HeadSrc", seg=12)


def person(x, y, z=0.06):
    s = random.uniform(0.9, 1.1)
    instance(random.choice(BODY_SRC), (x, y, z + 0.13 * s), s)
    instance(HEAD_SRC, (x, y, z + 0.31 * s), s)


people = []


def free(x, y):
    if abs(x) < 2.7 and y > -1.0 - 0.6:  # mandir ki jagati
        return False
    if (x - SX) ** 2 + (y - SY) ** 2 < 1.3 ** 2:  # Shivling
        return False
    if max(abs(x - 3.4), abs(y - 1.4)) < 0.8 or max(abs(x + 3.4), abs(y - 1.4)) < 0.8:
        return False
    return all((x - px) ** 2 + (y - py) ** 2 > 0.28 ** 2 for px, py in people)


# Shivling ke charon taraf parikrama karte log
for k in range(16):
    a = 2 * math.pi * k / 16 + random.uniform(-0.1, 0.1)
    x, y = SX + 1.5 * math.cos(a), SY + 1.5 * math.sin(a)
    if free(x, y):
        people.append((x, y))
        person(x, y)
# aangan mein bikhre log
for _ in range(500):
    if len(people) >= 48:
        break
    x, y = random.uniform(-C + 0.35, C - 0.35), random.uniform(-C + 0.35, C - 0.35)
    if free(x, y):
        people.append((x, y))
        person(x, y)
# road par line mein aate log
for k in range(7):
    person(random.uniform(-0.35, 0.35), -C - 0.35 - k * 0.2, 0.04)

# --- lighting: golden hour
bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 4.5
sun.data.color = (1.0, 0.78, 0.55)
sun.data.angle = math.radians(4)
sun.rotation_euler = (math.radians(58), 0, math.radians(-125))

bpy.ops.object.light_add(type="AREA", location=(-12, -14, 14))
fill = bpy.context.active_object
fill.data.energy = 2500
fill.data.size = 12
fill.data.color = (0.75, 0.85, 1.0)
fill.rotation_euler = (Vector((0, 0, 1)) - fill.location).to_track_quat("-Z", "Y").to_euler()

world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
wn, wl = world.node_tree.nodes, world.node_tree.links
bg = wn.get("Background")  # scene ki roshni ke liye
bg.inputs["Color"].default_value = (0.98, 0.84, 0.72, 1.0)
bg.inputs["Strength"].default_value = 0.65
# camera ko dikhne wala background: upar se neeche peach -> cream gradient
cam_bg = wn.new("ShaderNodeBackground")
cam_bg.inputs["Strength"].default_value = 1.0
coord = wn.new("ShaderNodeTexCoord")
sep = wn.new("ShaderNodeSeparateXYZ")
ramp = wn.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[0].color = (1.0, 0.62, 0.38, 1.0)
ramp.color_ramp.elements[1].position = 0.75
ramp.color_ramp.elements[1].color = (1.0, 0.88, 0.70, 1.0)
wl.new(coord.outputs["Window"], sep.inputs["Vector"])
wl.new(sep.outputs["Y"], ramp.inputs["Fac"])
wl.new(ramp.outputs["Color"], cam_bg.inputs["Color"])
lp = wn.new("ShaderNodeLightPath")
mix = wn.new("ShaderNodeMixShader")
wl.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
wl.new(bg.outputs["Background"], mix.inputs[1])
wl.new(cam_bg.outputs["Background"], mix.inputs[2])
wl.new(mix.outputs["Shader"], wn.get("World Output").inputs["Surface"])

# --- camera (isometric angle + tilt-shift DOF)
scene = bpy.context.scene
a, b = (int(v) for v in OPTS["aspect"].split(":"))
short = OPTS["res"]
if a >= b:
    scene.render.resolution_x, scene.render.resolution_y = round(short * a / b), short
else:
    scene.render.resolution_x, scene.render.resolution_y = short, round(short * b / a)
portrait = b > a

target = Vector((0, 0.2, 1.9 if portrait else 2.4))
direction = Vector((0.62, -1.0, 0.72)).normalized()
dist = 28 if portrait else 43
bpy.ops.object.camera_add(location=target + direction * dist)
cam = bpy.context.active_object
cam.data.lens = 60
cam.data.sensor_fit = "HORIZONTAL" if portrait else "AUTO"
cam.data.clip_end = 500
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = (Vector((SX, SY + 1.5, 1.0)) - cam.location).length
cam.data.dof.aperture_fstop = 1.2
scene.camera = cam

# --- render settings
scene.render.engine = "CYCLES"
scene.cycles.samples = OPTS["samples"]
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
if OPTS["gpu"]:
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for backend in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = backend
                prefs.get_devices()
                if any(d.type != "CPU" for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    scene.cycles.device = "GPU"
                    break
            except TypeError:
                continue
    except Exception as e:  # GPU nahi mila to CPU
        print("GPU setup failed, CPU use ho raha hai:", e)
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
except TypeError:
    scene.view_settings.view_transform = "Filmic"
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = bpy.path.abspath(OPTS["out"]) if OPTS["out"].startswith("//") else OPTS["out"]

if OPTS["save"]:
    bpy.ops.wm.save_as_mainfile(filepath=OPTS["save"])

if bpy.app.background:
    bpy.ops.render.render(write_still=True)
    print("Render saved:", scene.render.filepath)
else:
    print("Scene ready! F12 dabakar render karein.")
