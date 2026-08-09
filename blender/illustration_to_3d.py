#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
イラスト → 3D 化 (Blender / Cycles)

元イラスト:
    ヘッドホンと丸サングラスを着けて笑う女の子が、
    ヴィンテージのラジカセの上にあぐらで座っているポップなイラスト。
    デニムジャケット / グリーンのTシャツ / 薄いブルーのジーンズ /
    オレンジのハイカットスニーカー / レインボーのリストバンド。

このスクリプトはプリミティブとパラメトリックなシェル(格子メッシュ)だけで
上記のキャラクターとラジカセを手続き的に組み立て、
トゥーンシェーダ + Freestyle 輪郭線でイラスト調にレンダリングする。

使い方:
    blender -b -P blender/illustration_to_3d.py -- --out blender/renders --samples 96

オプション:
    --out DIR        出力ディレクトリ (default: blender/renders)
    --samples N      Cycles のサンプル数 (default: 96)
    --res W H        解像度 (default: 900 1350)
    --views a,b,c    front / hero / side / back / face から選択
                     (default: front,hero,side,face)
    --no-render      .blend と .glb だけ書き出してレンダリングしない
"""

import bpy
import os
import sys
from math import radians, sin, cos, pi
from mathutils import Vector, Euler, Matrix

# ---------------------------------------------------------------------------
# パレット (元イラストから抽出した sRGB)
# ---------------------------------------------------------------------------
PALETTE = {
    "skin":        "#F0BC86",
    "skin_shadow": "#E3A473",
    "nail":        "#F7D6BC",
    "blush":       "#EDAE91",
    "mouth":       "#93383C",
    "teeth":       "#FFF6EC",
    "tongue":      "#E06E82",
    "eye":         "#4A2B18",
    "eye_white":   "#FBF6EE",
    "iris":        "#6E4020",
    "pupil":       "#2A1A12",
    "lip":         "#DE907E",
    "teeth_dk":    "#EADCC8",
    "hair":        "#B06B22",
    "hair_light":  "#CE8B3A",
    "hair_dark":   "#96581F",

    "hp_yellow":   "#F5B41C",
    "hp_green":    "#5ABF45",
    "hp_green_dk": "#2C7A2C",

    "frame":       "#F5901E",
    "frame_hi":    "#FFC53D",
    "lens":        "#B478E8",
    "lens_warm":   "#F2705F",

    "denim":       "#4B87C9",
    "denim_dk":    "#2F66A8",
    "denim_hi":    "#9AC6EC",
    "jeans":       "#8FBDE4",
    "jeans_dk":    "#5F97CC",
    "cuff":        "#F2EEDF",

    "hood":        "#F5891F",
    "tee":         "#2FA84F",
    "tee_dk":      "#1E7F3C",
    "print_pink":  "#F27BA0",
    "print_yellow":"#F7D046",
    "print_cream": "#FFF3D6",

    "gold":        "#E0A62B",
    "thread":      "#F2C766",
    "rb_red":      "#E8483C",
    "rb_orange":   "#F5901E",
    "rb_yellow":   "#F7D046",
    "rb_green":    "#4FAE3C",
    "rb_blue":     "#2C74C4",

    "shoe":        "#F87A25",
    "shoe_cream":  "#FFF6E0",
    "shoe_green":  "#3FA845",
    "shoe_blue":   "#2C5FA8",
    "rubber":      "#FBE9C4",
    "outsole":     "#C9A268",
    "shoe_dk":     "#D9541A",
    "eyelet":      "#D8B45C",

    "radio":       "#E4561F",
    "radio_dk":    "#B23B14",
    "radio_panel": "#F3DFA8",
    "radio_grill": "#D9AE55",
    "radio_green": "#4FAE3C",
    "chrome":      "#D5D2C6",
    "deck_glass":  "#6B5A48",
    "dark":        "#3A2418",

    "bg":          "#FAF5E9",
    "bg_shadow":   "#F0E6D2",
}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def col(key, alpha=1.0):
    """パレットのキー（または #RRGGBB）を Blender のリニア RGBA に変換."""
    h = PALETTE.get(key, key).lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(srgb_to_linear(c) for c in rgb) + (alpha,)


# ---------------------------------------------------------------------------
# シーンの基礎
# ---------------------------------------------------------------------------
SUBJECT = "Subject"    # Freestyle の輪郭線を掛けるコレクション
DECAL = "Decal"        # 塗りだけ。輪郭線を掛けない (チークなど)
BACKDROP = "Backdrop"


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll_name in (SUBJECT, DECAL, BACKDROP, "Lights"):
        coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(coll)


def link(obj, coll_name=SUBJECT):
    bpy.data.collections[coll_name].objects.link(obj)
    return obj


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def shade_smooth(obj, angle=52.0):
    me = obj.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    if hasattr(me, "use_auto_smooth"):        # Blender 4.0 以前
        me.use_auto_smooth = True
        me.auto_smooth_angle = radians(angle)
    me.update()


# ---------------------------------------------------------------------------
# マテリアル: Cycles の Toon BSDF でセルルック
# ---------------------------------------------------------------------------
_MATS = {}


def mat(key, size=0.55, smooth=0.10, gloss=0.0, alpha=1.0, name=None,
        bump=0.0, bump_scale=180.0):
    """トゥーン(拡散)+ 少量のトゥーン(光沢)を混ぜたマテリアルを返す(キャッシュ付き).

    bump を指定すると、生地の織り目程度の細かい凹凸をノイズで足す。
    """
    cache_key = (key, round(size, 3), round(smooth, 3), round(gloss, 3),
                 round(alpha, 3), round(bump, 4), round(bump_scale, 1))
    if cache_key in _MATS:
        return _MATS[cache_key]

    m = bpy.data.materials.new(name or key)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)

    diff = nt.nodes.new("ShaderNodeBsdfToon")
    diff.component = "DIFFUSE"
    diff.location = (0, 120)
    diff.inputs["Color"].default_value = col(key)
    diff.inputs["Size"].default_value = size
    diff.inputs["Smooth"].default_value = smooth

    if bump > 0.0:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.location = (-460, -60)
        noise.inputs["Scale"].default_value = bump_scale
        noise.inputs["Detail"].default_value = 4.0
        bump_node = nt.nodes.new("ShaderNodeBump")
        bump_node.location = (-240, -60)
        bump_node.inputs["Strength"].default_value = bump
        bump_node.inputs["Distance"].default_value = 0.004
        nt.links.new(noise.outputs["Fac"], bump_node.inputs["Height"])
        nt.links.new(bump_node.outputs["Normal"], diff.inputs["Normal"])

    shader_out = diff.outputs["BSDF"]

    if gloss > 0.0:
        spec = nt.nodes.new("ShaderNodeBsdfToon")
        spec.component = "GLOSSY"
        spec.location = (0, -140)
        spec.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        spec.inputs["Size"].default_value = 0.12
        spec.inputs["Smooth"].default_value = 0.05

        mixer = nt.nodes.new("ShaderNodeMixShader")
        mixer.location = (300, 0)
        mixer.inputs["Fac"].default_value = gloss
        nt.links.new(shader_out, mixer.inputs[1])
        nt.links.new(spec.outputs["BSDF"], mixer.inputs[2])
        shader_out = mixer.outputs["Shader"]

    if alpha < 1.0:
        trans = nt.nodes.new("ShaderNodeBsdfTransparent")
        trans.location = (300, -260)
        mixer = nt.nodes.new("ShaderNodeMixShader")
        mixer.location = (450, -120)
        mixer.inputs["Fac"].default_value = alpha
        nt.links.new(trans.outputs["BSDF"], mixer.inputs[1])
        nt.links.new(shader_out, mixer.inputs[2])
        shader_out = mixer.outputs["Shader"]
        m.blend_method = "BLEND"

    nt.links.new(shader_out, out.inputs["Surface"])
    _MATS[cache_key] = m
    return m


def glow_mat(key, strength=0.9, alpha=1.0):
    """光の当たり方に左右されないフラットな色 (サングラスのレンズなど)."""
    m = bpy.data.materials.new("glow_" + key)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = col(key)
    em.inputs["Strength"].default_value = strength
    shader = em.outputs["Emission"]
    if alpha < 1.0:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = alpha
        nt.links.new(tr.outputs["BSDF"], mx.inputs[1])
        nt.links.new(shader, mx.inputs[2])
        shader = mx.outputs["Shader"]
        m.blend_method = "BLEND"
    nt.links.new(shader, out.inputs["Surface"])
    return m


def flat_mat(key, strength=1.0):
    """背景用のフラットな拡散マテリアル."""
    m = bpy.data.materials.new("bg_" + key)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    c = col(key)
    d.inputs["Color"].default_value = tuple(v * strength for v in c[:3]) + (1.0,)
    d.inputs["Roughness"].default_value = 0.9
    nt.links.new(d.outputs["BSDF"], out.inputs["Surface"])
    return m


# ---------------------------------------------------------------------------
# ジオメトリ・ヘルパ
# ---------------------------------------------------------------------------
def _finish(obj, material, loc, rot, smooth=True):
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)
    if smooth:
        shade_smooth(obj)
    obj.location = loc
    obj.rotation_euler = Euler(rot)
    return obj


def prim(kind, name, material, scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0),
         coll=SUBJECT, smooth=True, **kw):
    """プリミティブを原点で作り、スケールを適用してから配置する."""
    ops = {
        "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
        "cylinder": bpy.ops.mesh.primitive_cylinder_add,
        "cone": bpy.ops.mesh.primitive_cone_add,
        "torus": bpy.ops.mesh.primitive_torus_add,
        "cube": bpy.ops.mesh.primitive_cube_add,
        "plane": bpy.ops.mesh.primitive_plane_add,
        "circle": bpy.ops.mesh.primitive_circle_add,
    }[kind]
    defaults = {
        "sphere": dict(segments=48, ring_count=24, radius=1.0),
        "cylinder": dict(vertices=40, radius=1.0, depth=1.0),
        "cone": dict(vertices=40, radius1=1.0, radius2=0.6, depth=1.0),
        "torus": dict(major_segments=48, minor_segments=16,
                      major_radius=1.0, minor_radius=0.25),
        "cube": dict(size=1.0),
        "plane": dict(size=1.0),
        "circle": dict(vertices=48, radius=1.0, fill_type="NGON"),
    }[kind]
    defaults.update(kw)
    ops(location=(0, 0, 0), **defaults)

    obj = bpy.context.object
    obj.name = name
    # 生成直後はシーンコレクション直下なので、目的のコレクションへ移す
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    link(obj, coll)

    obj.scale = scale
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish(obj, material, loc, rot, smooth)


def grid_mesh(name, nu, nv, fn, material, thickness=0.0, close_u=False,
              coll=SUBJECT, smooth=True, subsurf=0):
    """fn(u, v) -> Vector で定義される格子サーフェスを作る (u は必要なら周期的)."""
    verts, faces = [], []
    for j in range(nv):
        for i in range(nu):
            u = (i / nu) if close_u else (i / (nu - 1))
            verts.append(fn(u, j / (nv - 1)))

    def idx(i, j):
        return j * nu + (i % nu)

    imax = nu if close_u else nu - 1
    for j in range(nv - 1):
        for i in range(imax):
            faces.append((idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)))

    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate(verbose=False)
    me.update()

    obj = bpy.data.objects.new(name, me)
    link(obj, coll)
    obj.data.materials.append(material)
    if smooth:
        shade_smooth(obj)
    if thickness:
        sol = obj.modifiers.new("solid", "SOLIDIFY")
        sol.thickness = thickness
        sol.offset = 0.0
    if subsurf:
        sub = obj.modifiers.new("sub", "SUBSURF")
        sub.levels = sub.render_levels = subsurf
    return obj


def tube(name, points, radii, material, coll=SUBJECT, res=8, bevres=6, order=3):
    """半径が変化するチューブ(NURBS カーブ + ベベル)をメッシュ化して返す."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for i, (p, r) in enumerate(zip(points, radii)):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
        sp.points[i].radius = r
    sp.order_u = min(order, len(points))
    sp.use_endpoint_u = True
    cu.resolution_u = res
    cu.bevel_depth = 1.0
    cu.bevel_resolution = bevres
    cu.use_fill_caps = True

    obj = bpy.data.objects.new(name, cu)
    link(obj, coll)
    obj.data.materials.append(material)
    activate(obj)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    shade_smooth(obj)
    return obj


def flat_profile(name, width=1.0, thickness=0.30):
    """カーブのベベル断面に使う平たい楕円。毛束をリボン状にするためのもの."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    sp = cu.splines.new("NURBS")
    n = 12
    sp.points.add(n - 1)
    for i in range(n):
        a = 2 * pi * i / n
        sp.points[i].co = (cos(a) * width, sin(a) * thickness, 0.0, 1.0)
    sp.use_cyclic_u = True
    sp.order_u = 3
    cu.resolution_u = 4
    obj = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def strands(name, paths, material, profile=None, coll=SUBJECT, res=8):
    """複数の毛束をまとめて 1 オブジェクトにする。

    paths は [(点のリスト, 半径のリスト), ...]。profile を渡すとリボン状の
    断面になり、丸いチューブより毛束らしく見える。
    """
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    for pts, radii in paths:
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for i, (p, r) in enumerate(zip(pts, radii)):
            sp.points[i].co = (p[0], p[1], p[2], 1.0)
            sp.points[i].radius = r
        sp.order_u = min(4, len(pts))
        sp.use_endpoint_u = True
    cu.resolution_u = res
    if profile is not None:
        cu.bevel_mode = "OBJECT"
        cu.bevel_object = profile
    else:
        cu.bevel_depth = 1.0
        cu.bevel_resolution = 4
    cu.use_fill_caps = True

    obj = bpy.data.objects.new(name, cu)
    link(obj, coll)
    obj.data.materials.append(material)
    activate(obj)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    shade_smooth(obj)
    return obj


def stitching(name, path_fn, material, count=36, dash=0.55, radius=0.0022,
              coll=SUBJECT):
    """縫い目のステッチ。破線を 1 本のカーブオブジェクトにまとめて作る."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    for i in range(count):
        t0 = i / count
        t1 = t0 + dash / count
        sp = cu.splines.new("POLY")
        sp.points.add(1)
        for k, t in enumerate((t0, t1)):
            p = path_fn(t)
            sp.points[k].co = (p[0], p[1], p[2], 1.0)
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    cu.use_fill_caps = True

    obj = bpy.data.objects.new(name, cu)
    link(obj, coll)
    obj.data.materials.append(material)
    activate(obj)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    shade_smooth(obj)
    return obj


def sweep(name, c_fn, r_fn, material, nt=34, na=26, fold=None, thickness=0.0,
          up=Vector((0, 0, 1)), coll=SUBJECT):
    """中心線に沿って断面を掃引した筒を作り、(オブジェクト, 表面座標関数) を返す.

    返り値の surf(t, angle, out) で表面上の任意の点が取れるので、
    縫い目やポケットをぴったり載せられる。
    """
    centers = [Vector(c_fn(i / (nt - 1))) for i in range(nt)]
    tans = []
    for i in range(nt):
        if i == 0:
            d = centers[1] - centers[0]
        elif i == nt - 1:
            d = centers[-1] - centers[-2]
        else:
            d = centers[i + 1] - centers[i - 1]
        tans.append(d.normalized())

    # 平行移動フレーム (ねじれの少ない断面の向き)
    n0 = up - tans[0] * up.dot(tans[0])
    if n0.length < 1e-6:
        alt = Vector((1, 0, 0))
        n0 = alt - tans[0] * alt.dot(tans[0])
    n0.normalize()
    ns, bs = [n0], [tans[0].cross(n0).normalized()]
    for i in range(1, nt):
        n = ns[-1] - tans[i] * ns[-1].dot(tans[i])
        if n.length < 1e-8:
            n = bs[-1].copy()
        n.normalize()
        ns.append(n)
        bs.append(tans[i].cross(n).normalized())

    def surf(t, a, out=0.0):
        t = min(1.0, max(0.0, t))
        x = t * (nt - 1)
        i = int(x)
        if i >= nt - 1:
            i, f = nt - 2, 1.0
        else:
            f = x - i
        c = centers[i].lerp(centers[i + 1], f)
        n = ns[i].lerp(ns[i + 1], f).normalized()
        b = bs[i].lerp(bs[i + 1], f).normalized()
        rr = r_fn(t) + out
        if fold is not None:
            rr += fold(t, a)
        return c + (cos(a) * n + sin(a) * b) * rr

    obj = grid_mesh(name, na, nt, lambda u, v: surf(v, 2 * pi * u),
                    material, thickness=thickness, close_u=True, coll=coll)
    return obj, surf


def dir_angle(surf, t, want, n=48):
    """掃引面の断面で、want の向きに最も張り出す角度を返す.

    平行移動フレームの角度 0 が必ずしも外側とは限らないので、
    縫い目やポケットを「外側」に置きたいときにこれで角度を決める。
    """
    want = Vector(want).normalized()
    return max(((surf(t, 2 * pi * k / n).dot(want), 2 * pi * k / n)
                for k in range(n)))[1]


_WRINKLE_TEX = {}


def wrinkles(obj, scale=0.22, strength=0.006, subdiv=0):
    """布のたるみ・シワ。ディスプレイスで表面をわずかに乱す.

    テクスチャ座標をグローバルにしているので、隣り合うパーツで
    シワの流れがつながって見える。
    """
    key = round(scale, 3)
    tex = _WRINKLE_TEX.get(key)
    if tex is None:
        tex = bpy.data.textures.new(f"wrinkle_{key}", type="CLOUDS")
        tex.noise_scale = scale
        tex.noise_depth = 2
        _WRINKLE_TEX[key] = tex
    if subdiv:
        sub = obj.modifiers.new("presub", "SUBSURF")
        sub.levels = sub.render_levels = subdiv
    m = obj.modifiers.new("wrinkle", "DISPLACE")
    m.texture = tex
    m.strength = strength
    m.mid_level = 0.5
    m.texture_coords = "GLOBAL"
    return obj


def capsule(name, p0, p1, r0, r1, material, coll=SUBJECT):
    """2 点を結ぶテーパー付きシリンダー."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    length = d.length
    obj = prim("cone", name, material, radius1=r0, radius2=r1, depth=length,
               loc=tuple((p0 + p1) / 2.0),
               rot=tuple(d.to_track_quat("Z", "Y").to_euler()), coll=coll)
    return obj


def bevel(obj, width=0.01, segments=3):
    m = obj.modifiers.new("bev", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = radians(35)
    return obj


def subsurf(obj, levels=2):
    m = obj.modifiers.new("sub", "SUBSURF")
    m.levels = m.render_levels = levels
    return obj


def move_group(objs, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """パーツ群をまとめてワールド変換する."""
    M = Matrix.LocRotScale(Vector(loc), Euler(rot), Vector(scale))
    for o in objs:
        o.matrix_world = M @ o.matrix_world
    return objs


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a))) if b != a else 0.0
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# 頭部の座標系  (顔は -Y 方向を向く)
# ---------------------------------------------------------------------------
HEAD_C = Vector((0.0, 0.0, 0.915))
HEAD_R = Vector((0.122, 0.130, 0.140))
HEAD_TILT = radians(-7.0)          # あごを少し上げた角度


def head_point(az, el, out=0.0, radii=None):
    """頭部球面上の点。az: 正面(-Y)からの方位角, el: 仰角."""
    r = Vector(radii) if radii else HEAD_R
    n = Vector((sin(az) * cos(el), -cos(az) * cos(el), sin(el)))
    p = Vector((r.x * n.x, r.y * n.y, r.z * n.z))
    d = Vector((n.x / r.x, n.y / r.y, n.z / r.z)).normalized()   # 楕円体の外向き法線
    return HEAD_C + p + d * out, d


def head_patch(name, az0, el0, ra, rb, material, out=0.0018, thickness=0.0035,
               nu=28, nv=10, squash=1.0):
    """顔の表面に貼り付く楕円パッチ (目・口・チークなど)."""
    def fn(u, v):
        th = 2 * pi * u
        rr = v
        a = az0 + ra * rr * cos(th)
        e = el0 + rb * rr * sin(th) * squash
        return head_point(a, e, out)[0]
    return grid_mesh(name, nu, nv, fn, material, thickness=thickness, close_u=True)


def head_arc(name, az0, el0, half_w, curve, material, width=0.012, out=0.002,
             thickness=0.004, nu=26):
    """顔の表面に沿う細いアーチ (閉じた目・眉)."""
    def fn(u, v):
        t = 2 * u - 1
        a = az0 + half_w * t
        e = el0 + curve * (1 - t * t) + width * (v - 0.5)
        return head_point(a, e, out)[0]
    return grid_mesh(name, nu, 3, fn, material, thickness=thickness)


# ---------------------------------------------------------------------------
# パーツ構築
# ---------------------------------------------------------------------------
def build_head():
    parts = []
    skin = mat("skin", size=0.62, smooth=0.16)

    # 頭蓋 + あご + ほお で顔の輪郭を作る
    parts.append(prim("sphere", "skull", skin, scale=tuple(HEAD_R), loc=tuple(HEAD_C)))
    parts.append(prim("sphere", "jaw", skin, scale=(0.099, 0.110, 0.092),
                      loc=tuple(HEAD_C + Vector((0, -0.007, -0.050)))))
    parts.append(prim("sphere", "chin", skin, scale=(0.062, 0.066, 0.052),
                      loc=tuple(HEAD_C + Vector((0, -0.044, -0.078)))))

    # 首
    parts.append(capsule("neck", (0, 0.008, 0.730), (0, 0.004, 0.836), 0.052, 0.047,
                         mat("skin_shadow", size=0.6)))

    # 耳
    for s in (-1, 1):
        parts.append(prim("sphere", f"ear_{s}", skin, scale=(0.017, 0.029, 0.038),
                          loc=(s * 0.118, 0.012, 0.910), rot=(0, radians(s * 12), 0)))

    # まゆの上の骨格 (眉弓) を少し出して、のっぺりした額を避ける
    for s in (-1, 1):
        bp, _ = head_point(s * 0.46, 0.30, -0.010)
        parts.append(prim("sphere", f"brow_ridge_{s}", skin,
                          scale=(0.040, 0.014, 0.008), loc=tuple(bp),
                          rot=(0, 0, radians(s * -10))))

    parts += build_nose()
    parts += build_mouth()
    for s in (-1, 1):
        parts += build_eye(s)
        parts.append(head_arc(f"brow_{s}", s * 0.50, 0.315, 0.175, 0.06,
                              mat("hair_dark", size=0.7), width=0.013))
    # ほお
    for s in (-1, 1):
        blush = head_patch(f"blush_{s}", s * 0.74, -0.24, 0.155, 0.085,
                           mat("blush", size=0.9), out=0.0010, thickness=0.0015)
        for c in list(blush.users_collection):
            c.objects.unlink(blush)
        link(blush, DECAL)
        parts.append(blush)
    return parts


def build_nose():
    """鼻筋・鼻先・小鼻・鼻孔で構成した鼻."""
    parts = []
    skin = mat("skin", size=0.62, smooth=0.16)
    shadow = mat("skin_shadow", size=0.7)

    bridge_top, _ = head_point(0.0, -0.02, -0.016)
    tip, _ = head_point(0.0, -0.17, 0.004)
    parts.append(capsule("nose_bridge", tuple(bridge_top), tuple(tip),
                         0.007, 0.012, skin))
    parts.append(prim("sphere", "nose_tip", skin, scale=(0.013, 0.013, 0.011),
                      loc=tuple(tip)))
    for s in (-1, 1):
        wing, _ = head_point(s * 0.130, -0.208, -0.008)
        parts.append(prim("sphere", f"nose_wing_{s}", skin,
                          scale=(0.0065, 0.008, 0.0055), loc=tuple(wing)))
        nostril, _ = head_point(s * 0.085, -0.238, -0.010)
        parts.append(prim("sphere", f"nostril_{s}", shadow,
                          scale=(0.0035, 0.005, 0.003), loc=tuple(nostril),
                          rot=(radians(20), 0, 0)))
    return parts


def build_mouth():
    """開いた笑顔: 口腔・上下の唇・歯列."""
    parts = []
    parts.append(head_patch("mouth", 0.0, -0.415, 0.30, 0.165,
                            mat("mouth", size=0.7), out=0.0015, squash=1.0))

    # 上の歯は 1 枚の帯。歯の境目は浅い溝だけ入れて、食いしばりに見せない
    parts.append(head_arc("teeth", 0.0, -0.330, 0.250, -0.018,
                          mat("teeth", size=0.75), width=0.052, out=0.006,
                          thickness=0.004))
    return parts


def build_eye(s):
    """眼球・虹彩・瞳孔・ハイライト・上下まぶた・まつ毛."""
    objs = []
    R = 0.0262
    white = mat("eye_white", size=0.7)
    iris_m = mat("iris", size=0.55, gloss=0.20)
    pupil_m = mat("pupil", size=0.7)
    skin = mat("skin", size=0.62, smooth=0.16)
    lash = mat("eye", size=0.75)

    objs.append(prim("sphere", f"eyeball_{s}", white, scale=(R, R, R),
                     loc=(0, 0, 0), segments=40, ring_count=20))

    def cap(name, radius, ang, material, axis, thickness=0.0, nu=32, nv=8):
        """axis='front' は -Y 方向、'up'/'down' は ±Z を極とする球冠."""
        def fn(u, v):
            th = ang * v
            ph = 2 * pi * u
            a, b, c = sin(th) * cos(ph), sin(th) * sin(ph), cos(th)
            if axis == "front":
                return Vector((a * radius, -c * radius, b * radius))
            if axis == "up":
                return Vector((a * radius, b * radius, c * radius))
            return Vector((a * radius, b * radius, -c * radius))
        return grid_mesh(name, nu, nv, fn, material, thickness=thickness,
                         close_u=True)

    objs.append(cap(f"iris_{s}", R + 0.0006, 0.52, iris_m, "front"))
    objs.append(cap(f"pupil_{s}", R + 0.0012, 0.25, pupil_m, "front"))
    # ハイライト
    objs.append(prim("sphere", f"catchlight_{s}", glow_mat("teeth", 1.5),
                     scale=(0.0042, 0.0042, 0.0042),
                     loc=(-0.009, -R - 0.001, 0.010), segments=16, ring_count=8))

    # まぶた: 上下から球冠でかぶせて、笑った細目にする
    objs.append(cap(f"lid_up_{s}", R + 0.0016, 1.38, skin, "up", thickness=0.0035))
    objs.append(cap(f"lid_lo_{s}", R + 0.0016, 1.18, skin, "down", thickness=0.0035))
    # まつ毛 (まぶたの縁の細い帯)
    def lash_band(name, ang, axis):
        def fn(u, v):
            th = ang - 0.055 * v
            ph = 2 * pi * u
            a, b, c = sin(th) * cos(ph), sin(th) * sin(ph), cos(th)
            rr = R + 0.0026
            if axis == "up":
                return Vector((a * rr, b * rr, c * rr))
            return Vector((a * rr, b * rr, -c * rr))
        return grid_mesh(name, 32, 3, fn, lash, thickness=0.0022, close_u=True)

    objs.append(lash_band(f"lash_up_{s}", 1.385, "up"))

    # 目全体を顔の所定の位置へ (ローカルの -Y が顔の法線を向くように)
    p, n = head_point(s * 0.47, 0.115, -0.023)
    rot = n.to_track_quat("-Y", "Z").to_euler()
    move_group(objs, loc=tuple(p), rot=tuple(rot))
    return objs


def build_hair():
    parts = []
    hair = mat("hair", size=0.5, smooth=0.14, gloss=0.06, bump=0.15, bump_scale=420)
    hair_lt = mat("hair_light", size=0.55, gloss=0.07, bump=0.15, bump_scale=420)
    hair_dk = mat("hair_dark", size=0.55, gloss=0.03)

    r = HEAD_R + Vector((0.016, 0.015, 0.014))
    center = HEAD_C + Vector((0.0, 0.008, 0.006))

    def hairline(az):
        """方位角ごとの生え際の高さ (正面は高く、後ろは低い)."""
        a = abs(((az + pi) % (2 * pi)) - pi)      # 0 = 正面, pi = 後頭部
        front = 0.46
        side = -0.26
        back = -0.95
        if a < 1.30:
            return lerp(front, side, smoothstep(0.70, 1.30, a))
        return lerp(side, back, smoothstep(1.30, 2.10, a))

    def hair_len(az):
        """方位角ごとの毛先までの長さ。正面(顔)はゼロで、横～後ろは肩まで届く."""
        a = abs(((az + pi) % (2 * pi)) - pi)
        if a < 0.90:
            base = 0.010
        elif a < 1.45:
            base = lerp(0.010, 0.235, smoothstep(0.90, 1.45, a))
        else:
            base = lerp(0.235, 0.330, smoothstep(1.45, 2.20, a))
        # 毛先を不揃いにして、まっすぐ切った裾に見えないようにする
        return base * (1.0 + 0.13 * sin(az * 6.0 + 0.8))

    def skull_pt(az, el):
        n = Vector((sin(az) * cos(el), -cos(az) * cos(el), sin(el)))
        bulge = 1.0 + 0.11 * smoothstep(0.0, 1.0, (n.y + 1) / 2)
        return center + Vector((r.x * n.x * bulge, r.y * n.y * bulge, r.z * n.z))

    VC = 0.46          # v < VC が垂れ下がる部分、v >= VC が頭に沿う部分

    def fn(u, v):
        az = 2 * pi * u
        if v >= VC:
            t = (v - VC) / (1 - VC)
            el = lerp(hairline(az), pi / 2 - 0.16, t ** 0.85)
            return skull_pt(az, el)
        # 生え際から下に流れる毛
        s = 1.0 - v / VC                       # 0 = 生え際, 1 = 毛先
        base = skull_pt(az, hairline(az))
        flare = 1.0 + 0.26 * s ** 1.3          # 下に行くほど外へ広がる
        wave = 0.011 * sin(az * 5.0 + s * 5.2)  # ゆるいウェーブ
        dx = (base.x - center.x) * flare + sin(az) * wave
        dy = (base.y - center.y) * flare - cos(az) * wave
        return Vector((center.x + dx, center.y + dy,
                       base.z - hair_len(az) * (s ** 0.92)))

    # ベースの毛量。この上に毛束を重ねるので、少し内側に作る
    base_shell = grid_mesh("hair_base", 76, 26,
                           lambda u, v: fn(u, v) * 1.0, hair_dk,
                           thickness=0.010, close_u=True)
    for vtx in base_shell.data.vertices:      # 毛束の下に隠れるよう一回り小さく
        vtx.co = center + (vtx.co - center) * 0.965
    parts.append(base_shell)
    parts.append(prim("sphere", "hair_crown", hair_dk,
                      scale=(r.x * 0.40, r.y * 0.40, r.z * 0.22),
                      loc=tuple(center + Vector((0, 0.004, r.z * 0.70)))))

    # ------------------------------------------------------------------
    # 毛束: 生え際から下へ流れる帯を何層も重ねる
    # ------------------------------------------------------------------
    profile = flat_profile("hair_profile", 1.0, 0.34)

    def strand_path(az, el, length, flare, wave_amp, wave_freq, phase,
                    swirl, tip, steps=10):
        """頭皮の 1 点から垂れ下がる毛束の軌跡と太さを返す."""
        start = skull_pt(az, el)
        shrink = cos(el)                      # 生え際での水平方向の縮み
        pts, radii = [], []
        for i in range(steps):
            t = i / (steps - 1)
            a = az + swirl * t
            grow = lerp(shrink, 1.0, min(1.0, t / 0.28))
            wob = wave_amp * sin(wave_freq * t * pi + phase)
            h = grow * (1.0 + flare * t ** 1.25) + wob
            pts.append(Vector((sin(a) * r.x * h + center.x,
                               -cos(a) * r.y * h + center.y,
                               start.z - length * (t ** 0.92))))
            # 根元は細く始めて地肌になじませ、毛先へ向けて絞る
            grow_in = smoothstep(0.0, 0.14, t)
            radii.append(grow_in * lerp(0.018, tip, t ** 1.35))
        return pts, radii

    layers = [
        # (本数, 半径のスケール, 長さの倍率, 広がり, ウェーブ量, 位相ずらし)
        ("hair_under", 30, 1.15, 0.84, 0.06, 0.006, 0.0),
        ("hair_mid", 42, 1.05, 0.96, 0.14, 0.012, 1.7),
        ("hair_top", 52, 0.92, 1.07, 0.22, 0.018, 3.4),
    ]
    for lname, count, rad_k, len_k, flare, wave, ph0 in layers:
        paths = []
        for i in range(count):
            # 顔の正面 (|az| < 0.78) は避け、こめかみから後頭部までに配置
            u = i / (count - 1)
            az = lerp(0.97, pi, u ** 0.95)
            for s in (-1, 1):
                jitter = sin(i * 2.7 + ph0) * 0.05
                length = hair_len(az) * len_k * (1.0 + 0.16 * sin(i * 1.9 + ph0))
                pts, radii = strand_path(
                    s * (az + jitter * 0.35),
                    hairline(az) + 0.04 * sin(i * 3.1 + ph0),
                    max(0.06, length),
                    flare,
                    wave,
                    2.4 + 0.6 * sin(i + ph0),
                    ph0 + i * 0.8,
                    s * (0.10 + 0.05 * sin(i * 1.3)),
                    0.0016)
                paths.append((pts, [x * rad_k for x in radii]))
        m = hair if lname != "hair_top" else hair_lt
        parts.append(strands(lname, paths, m, profile=profile))

    # ------------------------------------------------------------------
    # 前髪: 分け目から左右に流して顔を縁取る
    # ------------------------------------------------------------------
    fringe_paths = []
    for s in (-1, 1):
        for i in range(7):
            u = i / 6.0
            az = s * lerp(0.12, 0.80, u)
            el = lerp(0.86, 0.62, u)
            start = skull_pt(az, el)
            drop = lerp(0.030, 0.090, u)         # サングラスの上で止める
            side = s * lerp(0.045, 0.095, u)
            pts = [
                start,
                start + Vector((side * 0.42, -0.016, -drop * 0.30)),
                start + Vector((side * 0.82, -0.020, -drop * 0.68)),
                start + Vector((side * 1.08, -0.008, -drop)),
            ]
            fringe_paths.append((pts, [0.004, 0.014, 0.010, 0.002]))
    parts.append(strands("hair_fringe", fringe_paths, hair_lt, profile=profile))

    # 後れ毛 (細く跳ねる毛)
    wisp_paths = []
    for s in (-1, 1):
        for i, (az, el, ln) in enumerate(((1.05, 0.20, 0.16), (1.55, 0.02, 0.22),
                                          (2.30, -0.30, 0.18))):
            start = skull_pt(s * az, el)
            pts = [start,
                   start + Vector((s * 0.030, -0.010, -ln * 0.45)),
                   start + Vector((s * 0.058, 0.006, -ln * 0.85)),
                   start + Vector((s * 0.072, 0.018, -ln))]
            wisp_paths.append((pts, [0.002, 0.004, 0.003, 0.0008]))
    parts.append(strands("hair_wisps", wisp_paths, hair_lt, profile=profile))

    bpy.data.objects.remove(profile, do_unlink=True)
    return parts


def build_headphones():
    parts = []
    yellow = mat("hp_yellow", size=0.45, gloss=0.08)
    green = mat("hp_green", size=0.45, gloss=0.08)
    green_dk = mat("hp_green_dk", size=0.5, gloss=0.06)

    # 頭の上を通るヘッドバンド
    band_pts, band_r = [], []
    for i in range(7):
        t = i / 6.0
        a = lerp(-1.30, 1.30, t)               # 左右の耳をつなぐ弧
        band_pts.append(Vector((sin(a) * 0.178, 0.014, HEAD_C.z + cos(a) * 0.184)))
        band_r.append(0.014 if 0.15 < t < 0.85 else 0.012)
    parts.append(tube("hp_band", band_pts, band_r, yellow, order=4))

    for s in (-1, 1):
        x = s * 0.154
        rot = (0, radians(90), 0)
        # スライダー
        parts.append(prim("cube", f"hp_slider_{s}", yellow, scale=(0.020, 0.030, 0.062),
                          loc=(s * 0.170, 0.012, 0.982), rot=(0, radians(s * -9), 0)))
        # イヤーカップ
        parts.append(prim("cylinder", f"hp_cup_{s}", green, radius=0.060, depth=0.050,
                          loc=(x + s * 0.020, 0.012, 0.918), rot=rot))
        parts.append(prim("torus", f"hp_rim_{s}", green_dk, major_radius=0.060,
                          minor_radius=0.011, loc=(x + s * 0.042, 0.012, 0.918), rot=rot))
        parts.append(prim("cylinder", f"hp_plate_{s}", yellow, radius=0.040, depth=0.020,
                          loc=(x + s * 0.048, 0.012, 0.918), rot=rot))
        # 耳あて(パッド)
        parts.append(prim("torus", f"hp_pad_{s}", green_dk, major_radius=0.048,
                          minor_radius=0.017, loc=(x - s * 0.006, 0.012, 0.918), rot=rot))
    return parts


def build_glasses():
    parts = []
    frame = mat("frame", size=0.40, gloss=0.08)
    frame_hi = mat("frame_hi", size=0.40, gloss=0.08)
    lens_l = glow_mat("lens", 0.55, alpha=0.46)
    lens_r = glow_mat("lens_warm", 0.55, alpha=0.46)

    for s in (-1, 1):
        p, n = head_point(s * 0.50, 0.10, 0.028)
        rot = tuple(n.to_track_quat("Z", "Y").to_euler())
        parts.append(prim("cylinder", f"lens_{s}", lens_l if s < 0 else lens_r,
                          radius=0.050, depth=0.006, loc=tuple(p), rot=rot))
        parts.append(prim("torus", f"gframe_{s}", frame, major_radius=0.053,
                          minor_radius=0.011, loc=tuple(p), rot=rot))
        parts.append(prim("torus", f"gframe2_{s}", frame_hi, major_radius=0.059,
                          minor_radius=0.009, loc=tuple(p - n * 0.009), rot=rot))
        # つる
        temple_start, _ = head_point(s * 0.90, 0.11, 0.020)
        temple_end, _ = head_point(s * 1.45, 0.08, 0.010)
        parts.append(tube(f"temple_{s}",
                          [temple_start, (temple_start + temple_end) / 2 + Vector((0, 0.01, 0)),
                           temple_end],
                          [0.008, 0.007, 0.006], frame))

    # ブリッジ
    b, n = head_point(0.0, 0.145, 0.026)
    parts.append(prim("cube", "bridge", frame, scale=(0.060, 0.014, 0.011),
                      loc=tuple(b), rot=(radians(-8), 0, 0)))
    return parts


def build_torso():
    """胴体・Tシャツ・デニムジャケット・フード・ネックレス."""
    parts = []
    tee = mat("tee", size=0.5, smooth=0.12, bump=0.25, bump_scale=600)
    denim = mat("denim", size=0.5, smooth=0.12)
    denim_dk = mat("denim_dk", size=0.5)
    hood = mat("hood", size=0.5)

    # Tシャツに包まれた胴体
    body = tube("torso",
                [(0, 0.035, 0.315), (0, 0.010, 0.46), (0, -0.010, 0.60), (0, 0.005, 0.735)],
                [0.150, 0.140, 0.150, 0.128], tee, order=4)
    activate(body)
    body.scale = (1.0, 0.70, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    parts.append(body)
    parts.append(prim("sphere", "hips", tee, scale=(0.160, 0.115, 0.095),
                      loc=(0, 0.030, 0.325)))

    # Tシャツのプリント (胸の曲面に沿わせる)
    def chest_patch(name, cx, cz, rw, rh, material_key, rad):
        """Tシャツ表面(半径 ~0.150)より外、ジャケット内側(~0.170)より内側に貼る."""
        def fn(u, v):
            th = 2 * pi * u
            a = cx + rw * v * cos(th)
            z = cz + rh * v * sin(th)
            return Vector((sin(a) * rad, -cos(a) * rad * 0.70, z))
        return grid_mesh(name, 32, 10, fn, mat(material_key, size=0.75),
                         thickness=0.003, close_u=True)

    # 高さで分け、さらに半径をずらして重なっても Z ファイティングしないようにする
    parts.append(chest_patch("print_c", 0.0, 0.478, 0.42, 0.030, "print_cream", 0.158))
    parts.append(chest_patch("print_a", 0.0, 0.548, 0.52, 0.038, "print_pink", 0.161))
    parts.append(chest_patch("print_b", 0.0, 0.620, 0.46, 0.034, "print_yellow", 0.164))

    # パーカーのフード (オレンジ)
    parts.append(prim("sphere", "hood_back", hood, scale=(0.128, 0.088, 0.078),
                      loc=(0, 0.082, 0.742), rot=(radians(22), 0, 0)))
    parts.append(prim("torus", "hood_collar", hood, major_radius=0.086,
                      minor_radius=0.030, loc=(0, 0.020, 0.742),
                      rot=(radians(6), 0, 0), scale=(1.0, 0.86, 1.0)))
    # ドローコード
    for s in (-1, 1):
        parts.append(tube(f"cord_{s}",
                          [(s * 0.035, -0.088, 0.720), (s * 0.045, -0.105, 0.640),
                           (s * 0.030, -0.100, 0.560)],
                          [0.006, 0.005, 0.005], mat("print_cream", size=0.7)))

    # ------------------------------------------------------------------
    # デニムジャケット
    # ------------------------------------------------------------------
    denim_fab = mat("denim", size=0.5, smooth=0.12, bump=0.35, bump_scale=520)
    thread = mat("thread", size=0.6)

    def jacket_surface(a, z, out=0.0, folds=True):
        """ジャケットの外形。位置と外向き法線を返す (ステッチや装飾の基準)."""
        t = min(1.0, max(0.0, (0.735 - z) / 0.42))
        rad = lerp(0.176, 0.196, t)
        if folds:
            # 縦に流れるドレープ
            rad += 0.0055 * sin(a * 6.5 + 1.3) * smoothstep(0.0, 0.45, t)
            rad += 0.0035 * sin(a * 11.0 - 0.4) * t
        drop = 0.02 * smoothstep(0.0, 1.0, t)
        rx, ry = rad, (rad - drop) * 0.72
        n = Vector((sin(a) / rx, -cos(a) / ry, 0.0)).normalized()
        p = Vector((sin(a) * rx, -cos(a) * ry, z))
        return p + n * out, n

    def jacket_panel(name, a0, a1):
        def fn(u, v):
            return jacket_surface(lerp(a0, a1, u), lerp(0.735, 0.315, v))[0]
        obj = grid_mesh(name, 44, 22, fn, denim_fab, thickness=0.013)
        wrinkles(obj, scale=0.16, strength=0.004)
        return obj

    parts.append(jacket_panel("jacket_r", 0.20, pi))
    parts.append(jacket_panel("jacket_l", -0.20, -pi))

    def surface_box(name, a, z, size, material, out=0.008, tilt=0.0, bev=0.0):
        p, n = jacket_surface(a, z, out)
        rot = n.to_track_quat("Y", "Z").to_euler()
        rot.rotate_axis("Y", tilt)
        obj = prim("cube", name, material, scale=size, loc=tuple(p),
                   rot=tuple(rot), smooth=False)
        if bev:
            bevel(obj, bev, 3)
            shade_smooth(obj)
        return obj

    # 前立て (ボタンを付ける帯): 連続した帯として作る
    for s in (-1, 1):
        def placket_fn(u, v, s=s):
            z = lerp(0.722, 0.328, u)
            a = s * (0.255 + (v - 0.5) * 0.135)
            return jacket_surface(a, z, 0.006)[0]
        parts.append(grid_mesh(f"placket_{s}", 40, 5, placket_fn, denim_dk,
                               thickness=0.008))
        parts.append(stitching(
            f"stitch_placket_{s}",
            lambda t, s=s: jacket_surface(s * 0.322, lerp(0.716, 0.334, t), 0.010)[0],
            thread, count=30, dash=0.5, radius=0.0017))

    # 裾のバンド
    for s in (-1, 1):
        def hem_fn(u, v, s=s):
            a = s * lerp(0.21, pi - 0.01, u)
            z = lerp(0.315, 0.350, v)
            return jacket_surface(a, z, 0.006)[0]
        parts.append(grid_mesh(f"hem_{s}", 46, 4, hem_fn, denim_dk, thickness=0.009))
        parts.append(stitching(
            f"stitch_hem_{s}",
            lambda t, s=s: jacket_surface(s * lerp(0.24, pi - 0.05, t), 0.356, 0.009)[0],
            thread, count=34, dash=0.5, radius=0.0016))

    # 胸ポケット (フラップ + ボタン) と肩のヨーク線
    for s in (-1, 1):
        parts.append(surface_box(f"pocket_{s}", s * 0.62, 0.588,
                                 (0.052, 0.009, 0.048), denim_dk, out=0.007, bev=0.006))
        parts.append(surface_box(f"pocket_flap_{s}", s * 0.62, 0.630,
                                 (0.055, 0.011, 0.020), denim, out=0.010, bev=0.005))
        p, n = jacket_surface(s * 0.62, 0.612, 0.017)
        parts.append(prim("cylinder", f"pocket_btn_{s}", mat("gold", size=0.35, gloss=0.3),
                          radius=0.006, depth=0.004, loc=tuple(p),
                          rot=tuple(n.to_track_quat("Z", "Y").to_euler())))
        parts.append(stitching(
            f"stitch_pocket_{s}",
            lambda t, s=s: jacket_surface(s * (0.62 + 0.30 * (2 * t - 1)), 0.645, 0.010)[0],
            thread, count=14, dash=0.5, radius=0.0016))
        parts.append(stitching(
            f"stitch_yoke_{s}",
            lambda t, s=s: jacket_surface(s * lerp(0.30, 1.75, t), 0.664, 0.009)[0],
            thread, count=26, dash=0.5, radius=0.0017))

    # 前立てのボタン
    for i in range(4):
        z = 0.680 - i * 0.088
        p, n = jacket_surface(-0.255, z, 0.014)
        parts.append(prim("cylinder", f"jbutton_{i}", mat("gold", size=0.35, gloss=0.3),
                          radius=0.0075, depth=0.005, loc=tuple(p),
                          rot=tuple(n.to_track_quat("Z", "Y").to_euler())))

    # 襟
    for s in (-1, 1):
        parts.append(prim("cube", f"lapel_{s}", denim_dk, scale=(0.070, 0.030, 0.115),
                          loc=(s * 0.078, -0.098, 0.700),
                          rot=(radians(14), radians(s * 22), radians(s * 10))))
    parts.append(prim("torus", "collar", denim_dk, major_radius=0.098, minor_radius=0.024,
                      loc=(0, 0.030, 0.752), rot=(radians(10), 0, 0),
                      scale=(1.0, 0.80, 0.75)))
    parts.append(stitching(
        "stitch_collar",
        lambda t: (lambda a: Vector((sin(a) * 0.104, -cos(a) * 0.086 + 0.030, 0.735)))(
            lerp(-2.5, 2.5, t)),
        thread, count=30, dash=0.5, radius=0.0016))

    # ジャケットのワッペン (縁取り付き)
    patch_specs = [
        (0.98, 0.505, "print_yellow", (0.058, 0.005, 0.048)),
        (1.42, 0.408, "print_pink", (0.050, 0.005, 0.058)),
        (-1.02, 0.462, "print_cream", (0.056, 0.005, 0.050)),
        (-1.46, 0.378, "rb_green", (0.048, 0.005, 0.044)),
    ]
    for i, (a, z, key, sc) in enumerate(patch_specs):
        parts.append(surface_box(f"patch_edge_{i}", a, z,
                                 (sc[0] + 0.005, 0.005, sc[2] + 0.005),
                                 mat("print_cream", size=0.8), out=0.009))
        parts.append(surface_box(f"patch_{i}", a, z, sc, mat(key, size=0.75), out=0.011))

    # ビーズのネックレス
    gold = mat("gold", size=0.35, gloss=0.12)
    for i in range(26):
        t = lerp(-2.35, 2.35, i / 25.0)
        dip = 0.030 * max(0.0, cos(t)) ** 1.5
        parts.append(prim("sphere", f"bead_{i}", gold, scale=(0.0085,) * 3,
                          loc=(sin(t) * 0.082, -cos(t) * 0.060 + 0.012, 0.726 - dip),
                          segments=16, ring_count=8))
    return parts


def build_arms():
    parts = []
    denim = mat("denim", size=0.5, smooth=0.12)
    denim_fab = mat("denim", size=0.5, smooth=0.12, bump=0.35, bump_scale=520)
    cuff = mat("cuff", size=0.6)
    skin = mat("skin", size=0.62, smooth=0.16)
    thread = mat("thread", size=0.6)

    for s in (-1, 1):
        shoulder = Vector((s * 0.158, 0.005, 0.706))
        elbow = Vector((s * 0.246, -0.070, 0.472))
        wrist = Vector((s * 0.132, -0.258, 0.296))
        parts.append(prim("sphere", f"shoulder_{s}", denim_fab, scale=(0.072, 0.070, 0.066),
                          loc=tuple(shoulder)))

        def arm_center(t, sh=shoulder, el=elbow, wr=wrist, s=s):
            if t < 0.5:
                u, a, c = t * 2, sh, el
                b = (sh + el) / 2 + Vector((s * 0.014, 0.010, 0.008))
            else:
                u, a, c = (t - 0.5) * 2, el, wr
                b = (el + wr) / 2 + Vector((s * 0.016, -0.014, 0.004))
            return a * (1 - u) ** 2 + b * 2 * (1 - u) * u + c * u ** 2

        def arm_radius(t):
            return lerp(0.072, 0.043, smoothstep(0.05, 1.0, t)) \
                + 0.006 * smoothstep(0.38, 0.52, t) * (1 - smoothstep(0.52, 0.68, t))

        def arm_fold(t, a):
            # ひじの内側に寄るシワと、ゆったりした袖のたるみ
            elbow_w = 0.007 * sin(a * 4.0 + 0.4) * smoothstep(0.34, 0.52, t) \
                * (1 - smoothstep(0.60, 0.78, t))
            drape = 0.0045 * sin(a * 6.0 - 0.7) * (1 - smoothstep(0.10, 0.60, t))
            return elbow_w + drape

        sleeve, arm_surf = sweep(f"sleeve_{s}", arm_center, arm_radius, denim_fab,
                                 nt=36, na=28, fold=arm_fold)
        parts.append(sleeve)

        # 肩の切り替えと袖の外側の縫い目
        arm_out = Vector((s * 0.80, -0.42, 0.42))
        parts.append(stitching(
            f"stitch_shoulder_{s}",
            lambda t, surf=arm_surf: surf(0.10, 2 * pi * t, 0.0035),
            thread, count=24, dash=0.5, radius=0.0016))
        parts.append(stitching(
            f"stitch_sleeve_{s}",
            lambda t, surf=arm_surf, w=arm_out: surf(
                lerp(0.14, 0.92, t),
                dir_angle(surf, lerp(0.14, 0.92, t), w), 0.0035),
            thread, count=34, dash=0.5, radius=0.0016))

        # まくり上げた白いカフス
        d = (wrist - elbow).normalized()
        parts.append(prim("torus", f"cuff_{s}", cuff, major_radius=0.044,
                          minor_radius=0.017, loc=tuple(wrist + d * 0.010),
                          rot=tuple(d.to_track_quat("Z", "Y").to_euler())))
        parts.append(stitching(
            f"stitch_cuffarm_{s}",
            lambda t, surf=arm_surf: surf(0.955, 2 * pi * t, 0.004),
            thread, count=20, dash=0.5, radius=0.0014))
        # 前腕
        fore = wrist + d * 0.050
        parts.append(capsule(f"forearm_{s}", tuple(wrist + d * 0.02), tuple(fore + d * 0.05),
                             0.036, 0.032, skin))

        # レインボーのリストバンド / 腕時計
        band_cols = ["rb_red", "rb_orange", "rb_yellow", "rb_green", "rb_blue"]
        if s < 0:
            for i, c in enumerate(band_cols):
                p = wrist + d * (0.036 + i * 0.017)
                parts.append(prim("torus", f"band_{s}_{i}", mat(c, size=0.5),
                                  major_radius=0.037, minor_radius=0.007, loc=tuple(p),
                                  rot=tuple(d.to_track_quat("Z", "Y").to_euler())))
        else:
            for i, c in enumerate(band_cols[:3]):
                p = wrist + d * (0.034 + i * 0.016)
                parts.append(prim("torus", f"band_{s}_{i}", mat(c, size=0.5),
                                  major_radius=0.037, minor_radius=0.007, loc=tuple(p),
                                  rot=tuple(d.to_track_quat("Z", "Y").to_euler())))
            p = wrist + d * 0.082
            rot = tuple(d.to_track_quat("Z", "Y").to_euler())
            parts.append(prim("torus", "watch_strap", mat("rb_orange", size=0.5),
                              major_radius=0.036, minor_radius=0.009, loc=tuple(p), rot=rot))
            parts.append(prim("cylinder", "watch_case", mat("gold", size=0.3, gloss=0.12),
                              radius=0.024, depth=0.012,
                              loc=tuple(p + Vector((0, -0.030, 0.010))),
                              rot=(radians(80), 0, 0)))
            parts.append(prim("cylinder", "watch_face", mat("print_cream", size=0.5),
                              radius=0.018, depth=0.016,
                              loc=tuple(p + Vector((0, -0.033, 0.011))),
                              rot=(radians(80), 0, 0)))

        parts += build_hand(s)
    return parts


def build_hand(s):
    """足首の上で組む手。指は関節ごとに曲げ、爪も付ける (ローカルで作って配置)."""
    skin = mat("skin", size=0.62, smooth=0.16)
    shadow = mat("skin_shadow", size=0.65)
    nail = mat("nail", size=0.6, gloss=0.15)
    objs = []

    # 手の甲
    back = prim("cube", f"hand_back_{s}", skin, scale=(0.050, 0.060, 0.022),
                loc=(0, -0.008, 0), smooth=False)
    bevel(back, 0.016, 4)
    subsurf(back, 1)
    shade_smooth(back)
    objs.append(back)
    objs.append(prim("sphere", f"thenar_{s}", skin, scale=(0.020, 0.032, 0.016),
                     loc=(-0.030, -0.010, -0.004)))

    def curled_finger(name, base, direction, length, radius, curl, segs=6):
        """付け根から先端へ、少しずつ曲がる指を作る."""
        p = Vector(base)
        d = Vector(direction).normalized()
        pts, radii, joints = [p.copy()], [radius], []
        step = length / (segs - 1)
        for i in range(1, segs):
            d.rotate(Euler((-curl / (segs - 1), 0, 0)))
            p = p + d * step
            pts.append(p.copy())
            radii.append(radius * (1.0 - 0.34 * (i / (segs - 1)) ** 1.2))
            if i in (2, 4):
                joints.append((p.copy(), radius * 0.96))
        out = [tube(name, pts, radii, skin)]
        for k, (jp, jr) in enumerate(joints):
            out.append(prim("sphere", f"{name}_joint_{k}", skin,
                            scale=(jr, jr, jr * 0.9), loc=tuple(jp),
                            segments=16, ring_count=8))
        # 爪
        tipd = (pts[-1] - pts[-2]).normalized()
        out.append(prim("sphere", f"{name}_nail", nail,
                        scale=(radius * 0.62, radius * 0.72, radius * 0.30),
                        loc=tuple(pts[-1] + tipd * radius * 0.35
                                  + Vector((0, 0, radius * 0.55))),
                        rot=tuple(tipd.to_track_quat("Y", "Z").to_euler()),
                        segments=16, ring_count=8))
        return out

    # 人差し指〜小指 (長さと開き方を変える)
    finger_specs = [
        (-0.031, 0.070, 0.0135, 1.55, -0.10),
        (-0.011, 0.077, 0.0140, 1.62, -0.03),
        (0.010, 0.073, 0.0132, 1.60, 0.03),
        (0.030, 0.062, 0.0118, 1.52, 0.10),
    ]
    for i, (x, length, radius, curl, spread) in enumerate(finger_specs):
        objs.append(prim("sphere", f"knuckle_{s}_{i}", skin,
                         scale=(radius * 1.05, radius * 0.95, radius * 0.95),
                         loc=(x, -0.042, 0.0), segments=16, ring_count=8))
        objs += curled_finger(f"finger_{s}_{i}", (x, -0.046, 0.0),
                              (spread, -1.0, -0.06), length, radius, curl)

    # 親指
    objs += curled_finger(f"thumb_{s}", (-0.040, -0.004, -0.004),
                          (-0.62, -0.72, -0.10), 0.062, 0.0148, 0.85, segs=5)
    objs.append(prim("sphere", f"thumb_base_{s}", shadow,
                     scale=(0.016, 0.018, 0.013), loc=(-0.036, -0.006, -0.006)))

    # 手の甲を正面に向け、指は内側の下へ。左右は X 反転で作る
    finger_dir = Vector((-0.20, -0.16, -0.96)).normalized()
    back_dir = Vector((0.10, -0.92, 0.38))
    back_dir = (back_dir - finger_dir * back_dir.dot(finger_dir)).normalized()
    ax_y = -finger_dir
    ax_z = back_dir
    ax_x = ax_y.cross(ax_z).normalized()
    rot = Matrix(((ax_x.x, ax_y.x, ax_z.x),
                  (ax_x.y, ax_y.y, ax_z.y),
                  (ax_x.z, ax_y.z, ax_z.z))).to_euler()

    M = Matrix.LocRotScale(Vector((0.083, -0.318, 0.300)), rot,
                           Vector((0.92, 0.92, 0.92)))
    if s < 0:
        M = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0)) @ M
    for o in objs:
        o.matrix_world = M @ o.matrix_world
    return objs


def build_legs():
    """あぐらの脚 (ジーンズ) と裾のロールアップ."""
    parts = []
    jeans = mat("jeans", size=0.5, smooth=0.14)
    jeans_dk = mat("jeans_dk", size=0.5)
    cuff = mat("cuff", size=0.6)

    jeans_fab = mat("jeans", size=0.5, smooth=0.14, bump=0.35, bump_scale=520)
    thread = mat("thread", size=0.6)

    for s in (-1, 1):
        hip = Vector((s * 0.110, 0.030, 0.318))
        knee = Vector((s * 0.298, -0.150, 0.145))
        ankle = Vector((s * 0.132, -0.305, 0.158))

        def leg_center(t, hip=hip, knee=knee, ankle=ankle):
            """腰 → ひざ → 足首 を通る中心線 (2 次ベジエを 2 本つないだもの)."""
            if t < 0.5:
                u = t * 2
                a = hip
                b = hip + (knee - hip) * 0.55 + Vector((0, 0.015, 0.035))
                c = knee
            else:
                u = (t - 0.5) * 2
                a = knee
                b = knee + (ankle - knee) * 0.5 + Vector((0, -0.02, -0.025))
                c = ankle
            return a * (1 - u) ** 2 + b * 2 * (1 - u) * u + c * u ** 2

        def leg_radius(t):
            # 腿は太く、ひざで少し張り、足首へ細くなる
            base = lerp(0.114, 0.070, smoothstep(0.10, 1.0, t))
            return base + 0.012 * smoothstep(0.34, 0.52, t) * (1 - smoothstep(0.52, 0.72, t))

        def leg_fold(t, a):
            # ひざの裏や裾に寄るシワ
            crease = 0.006 * sin(a * 3.0 + 0.6) * smoothstep(0.30, 0.60, t)
            drape = 0.004 * sin(a * 5.0 - 1.1) * (1 - smoothstep(0.0, 0.35, t))
            hemline = 0.005 * sin(t * 46.0) * smoothstep(0.78, 0.94, t)
            return crease + drape + hemline

        leg, surf = sweep(f"leg_{s}", leg_center, leg_radius, jeans_fab,
                          nt=40, na=30, fold=leg_fold)
        parts.append(leg)

        # 外側の脇縫いと内側の股下縫い (表面にぴったり沿わせる)
        out_dir = Vector((s * 0.72, -0.60, 0.34))
        in_dir = Vector((-s * 0.20, -0.86, -0.46))

        def seam_pt(t, surf=surf, want=out_dir, t0=0.06, t1=0.94):
            tt = lerp(t0, t1, t)
            return surf(tt, dir_angle(surf, tt, want), 0.0035)

        parts.append(stitching(f"seam_out_{s}", seam_pt, thread,
                               count=42, dash=0.5, radius=0.0017))
        parts.append(stitching(
            f"seam_in_{s}",
            lambda t, surf=surf, w=in_dir: seam_pt(t, surf, w, 0.12, 0.92),
            thread, count=34, dash=0.5, radius=0.0016))
        # ひざの補強ステッチ (外側の角度を中心に扇状に)
        parts.append(stitching(
            f"seam_knee_{s}",
            lambda t, surf=surf, w=out_dir: surf(
                0.47, dir_angle(surf, 0.47, w) + lerp(-1.1, 1.1, t), 0.0035),
            thread, count=13, dash=0.5, radius=0.0015))

        # まくり上げた裾: 外側の折り返しと内側の生地
        d = (ankle - knee).normalized()
        rot = tuple(d.to_track_quat("Z", "Y").to_euler())
        parts.append(prim("torus", f"jcuff_{s}", cuff, major_radius=0.064,
                          minor_radius=0.021, loc=tuple(ankle + d * 0.020), rot=rot))
        parts.append(prim("cylinder", f"jcuff_in_{s}", jeans_dk, radius=0.062,
                          depth=0.026, loc=tuple(ankle + d * 0.034), rot=rot))
        # 折り返しの縁に沿った 1 周ステッチ
        parts.append(stitching(
            f"stitch_cuff_{s}",
            lambda t, surf=surf: surf(0.905, 2 * pi * t, 0.004),
            thread, count=22, dash=0.5, radius=0.0015))

        # 靴下 (グリーン): 足首からスニーカーの履き口へ
        collar = SHOE_LOC(s) + Vector((s * 0.020, 0.121, 0.140))
        parts.append(capsule(f"sock_{s}", tuple(ankle), tuple(collar),
                             0.048, 0.042, mat("tee", size=0.55)))
        parts += build_shoe(s)
    return parts


def SHOE_LOC(s):
    return Vector((s * 0.158, -0.400, 0.0))


def build_shoe(s):
    """オレンジのハイカットスニーカー (アウトソール/ミッドソール/フォクシング
    テープ/アッパー/ハトメ/靴ひも/ヒールカウンターまで作り分ける)."""
    objs = []
    orange = mat("shoe", size=0.45, smooth=0.12, gloss=0.04, bump=0.30, bump_scale=700)
    orange_dk = mat("shoe_dk", size=0.5)
    cream = mat("shoe_cream", size=0.55)
    rubber = mat("rubber", size=0.6)
    outsole_m = mat("outsole", size=0.55)
    green = mat("shoe_green", size=0.45)
    blue = mat("shoe_blue", size=0.45)
    metal = mat("eyelet", size=0.3, gloss=0.35)

    # 足型に沿った断面。つま先は丸く、土踏まずは細く、かかとは丸い
    def last_width(t):
        """t: 0 = つま先, 1 = かかと。その位置での半幅の比率."""
        return (0.62 + 0.38 * smoothstep(0.0, 0.28, t)) * \
               (1.0 - 0.18 * smoothstep(0.34, 0.62, t) * (1 - smoothstep(0.72, 1.0, t)))

    def last_xy(t, ang, w, d, y0, y1):
        """足型の輪郭上の点 (楕円断面)."""
        y = lerp(y0, y1, t)
        return Vector((sin(ang) * w * last_width(t), y, cos(ang) * d))

    # --- アウトソール (濃いラバー) ---
    outsole = prim("cube", "outsole", outsole_m, scale=(0.088, 0.208, 0.017),
                   loc=(0, 0, 0.010), smooth=False)
    bevel(outsole, 0.016, 4)
    subsurf(outsole, 1)
    shade_smooth(outsole)
    objs.append(outsole)
    # 靴底のトレッド
    for i in range(9):
        y = lerp(-0.090, 0.090, i / 8.0)
        objs.append(prim("cube", f"tread_{i}", outsole_m,
                         scale=(0.074 * last_width(abs(y / 0.115) * 0.5 + 0.25),
                                0.009, 0.010),
                         loc=(0, y, 0.003), smooth=False))

    # --- ミッドソール (白) + フォクシングテープ ---
    mid = prim("cube", "midsole", rubber, scale=(0.092, 0.212, 0.024),
               loc=(0, 0, 0.030), smooth=False)
    bevel(mid, 0.018, 4)
    subsurf(mid, 1)
    shade_smooth(mid)
    objs.append(mid)
    objs.append(prim("torus", "foxing", cream, major_radius=0.080, minor_radius=0.0075,
                     loc=(0, 0, 0.041), scale=(1.0, 1.32, 0.8)))

    # --- アッパー (キャンバス) ---
    upper = prim("cube", "upper", orange, scale=(0.100, 0.194, 0.124),
                 loc=(0, 0.010, 0.108), smooth=False)
    bevel(upper, 0.030, 5)
    subsurf(upper, 1)
    shade_smooth(upper)
    wrinkles(upper, scale=0.06, strength=0.0016)
    objs.append(upper)

    # つま先のラバーキャップ
    objs.append(prim("sphere", "toe_cap", cream, scale=(0.050, 0.040, 0.026),
                     loc=(0, -0.088, 0.046)))
    objs.append(prim("torus", "toe_welt", cream, major_radius=0.046,
                     minor_radius=0.005, loc=(0, -0.066, 0.052),
                     rot=(radians(72), 0, 0), scale=(1.0, 0.72, 1.0)))

    # --- ハイカットの履き口 / タン / ヒールカウンター ---
    objs.append(prim("torus", "collar", green, major_radius=0.048, minor_radius=0.017,
                     loc=(0, 0.062, 0.164), rot=(radians(-12), 0, 0)))
    objs.append(prim("cube", "tongue", cream, scale=(0.044, 0.014, 0.076),
                     loc=(0, 0.008, 0.146), rot=(radians(16), 0, 0)))
    objs.append(prim("cube", "tongue_label", blue, scale=(0.018, 0.006, 0.011),
                     loc=(0, -0.008, 0.172), rot=(radians(16), 0, 0), smooth=False))
    objs.append(prim("cube", "heel_counter", orange_dk, scale=(0.078, 0.030, 0.070),
                     loc=(0, 0.082, 0.130), smooth=False))
    objs.append(prim("cube", "heel_tab", green, scale=(0.042, 0.012, 0.038),
                     loc=(0, 0.098, 0.166), smooth=False))

    # --- ハトメと靴ひも ---
    eyelet_pos = []
    for i in range(4):
        z = 0.104 + i * 0.026
        y = -0.010 + i * 0.019
        for sx in (-1, 1):
            x = sx * (0.036 - i * 0.002)
            eyelet_pos.append((x, y, z))
            p = Vector((x, y, z))
            objs.append(prim("torus", f"eyelet_{i}_{sx}", metal,
                             major_radius=0.0062, minor_radius=0.0022,
                             loc=(x * 1.03, y - 0.030, z),
                             rot=(radians(96), 0, radians(sx * 8))))
    lace = mat("shoe_cream", size=0.6, gloss=0.08)
    for i in range(3):
        a = eyelet_pos[i * 2]
        b = eyelet_pos[i * 2 + 3]
        c = eyelet_pos[i * 2 + 1]
        d = eyelet_pos[i * 2 + 2]
        for k, (p0, p1) in enumerate(((a, b), (c, d))):
            mid_p = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - 0.030,
                     (p0[2] + p1[2]) / 2)
            objs.append(tube(f"lace_{i}_{k}",
                             [(p0[0], p0[1] - 0.026, p0[2]), mid_p,
                              (p1[0], p1[1] - 0.026, p1[2])],
                             [0.0048, 0.0055, 0.0048], lace))
    # 履き口まわりのひも
    objs.append(tube("lace_top",
                     [(-0.030, 0.048, 0.176), (0.0, 0.020, 0.184),
                      (0.030, 0.048, 0.176)],
                     [0.0048, 0.0055, 0.0048], lace))

    # --- サイドのサークルロゴ ---
    for sx in (-1, 1):
        objs.append(prim("cylinder", f"logo_{sx}", cream, radius=0.034, depth=0.012,
                         loc=(sx * 0.086, 0.030, 0.096), rot=(0, radians(90), 0)))
        objs.append(prim("torus", f"logo_ring_{sx}", blue, major_radius=0.030,
                         minor_radius=0.005, loc=(sx * 0.090, 0.030, 0.096),
                         rot=(0, radians(90), 0)))
        objs.append(prim("cylinder", f"logo_in_{sx}", blue, radius=0.019, depth=0.014,
                         loc=(sx * 0.090, 0.030, 0.096), rot=(0, radians(90), 0)))
        # 側面のステッチ
        objs.append(stitching(
            f"shoe_stitch_{sx}",
            lambda t, sx=sx: Vector((sx * (0.082 - 0.016 * (2 * t - 1) ** 2),
                                     lerp(-0.078, 0.086, t),
                                     0.070 + 0.012 * sin(t * pi))),
            cream, count=15, dash=0.5, radius=0.0018))

    move_group(objs, loc=tuple(SHOE_LOC(s)),
               rot=(radians(-6), 0, radians(s * 20)), scale=(s * 1.16, 1.16, 1.16))
    return objs


def build_boombox():
    """腰掛けているヴィンテージのラジカセ."""
    parts = []
    body_m = mat("radio", size=0.45, smooth=0.12, gloss=0.05)
    dark = mat("radio_dk", size=0.5)
    panel = mat("radio_panel", size=0.55)
    grill = mat("radio_grill", size=0.45, gloss=0.08)
    green = mat("radio_green", size=0.45)

    body = prim("cube", "radio_body", body_m, scale=(0.860, 0.290, 0.300),
                loc=(0, 0.055, 0.152), smooth=False)
    bevel(body, 0.030, 4)
    shade_smooth(body)
    parts.append(body)

    # 前面パネル
    parts.append(prim("cube", "radio_front", panel, scale=(0.800, 0.020, 0.250),
                      loc=(0, -0.092, 0.152), smooth=False))

    FRONT = -0.104            # 前面パネルの位置
    silver = mat("chrome", size=0.3, gloss=0.35)
    red = mat("rb_red", size=0.5)

    # ------------------------------------------------------------------
    # 左右のスピーカー: 外枠 + パンチングメタル風の同心リング + センターコーン
    # ------------------------------------------------------------------
    for s in (-1, 1):
        cx = s * 0.300
        rot = (radians(90), 0, 0)
        parts.append(prim("cylinder", f"sp_housing_{s}", dark, radius=0.112, depth=0.028,
                          loc=(cx, FRONT + 0.008, 0.150), rot=rot))
        parts.append(prim("torus", f"sp_bezel_{s}", green if s > 0 else mat("frame", size=0.45),
                          major_radius=0.104, minor_radius=0.013,
                          loc=(cx, FRONT - 0.006, 0.150), rot=rot))
        parts.append(prim("cylinder", f"sp_back_{s}", mat("radio_dk", size=0.6),
                          radius=0.096, depth=0.016, loc=(cx, FRONT + 0.002, 0.150),
                          rot=rot))
        # 同心リングでパンチングメタルらしい面を作る
        for k in range(5):
            rr = 0.030 + k * 0.016
            parts.append(prim("torus", f"sp_ring_{s}_{k}", grill,
                              major_radius=rr, minor_radius=0.0055,
                              loc=(cx, FRONT - 0.004, 0.150), rot=rot))
        # 放射状の桟
        for k in range(8):
            a = pi * k / 8.0
            parts.append(prim("cube", f"sp_spoke_{s}_{k}", grill,
                              scale=(0.086, 0.005, 0.005),
                              loc=(cx, FRONT - 0.004, 0.150),
                              rot=(0, radians(90) + a, 0)))
        parts.append(prim("sphere", f"sp_cone_{s}", dark, scale=(0.026, 0.016, 0.026),
                          loc=(cx, FRONT - 0.010, 0.150)))
        # ネジ
        for k in range(4):
            a = pi / 4 + k * pi / 2
            parts.append(prim("cylinder", f"sp_screw_{s}_{k}", silver,
                              radius=0.006, depth=0.008,
                              loc=(cx + cos(a) * 0.104, FRONT - 0.008,
                                   0.150 + sin(a) * 0.104), rot=rot))

    # ------------------------------------------------------------------
    # 中央: チューナー / カセットデッキ / 操作ボタン
    # ------------------------------------------------------------------
    parts.append(prim("cube", "tuner", dark, scale=(0.250, 0.020, 0.078),
                      loc=(0, FRONT, 0.246), smooth=False))
    parts.append(prim("cube", "tuner_glass", mat("print_cream", size=0.6),
                      scale=(0.226, 0.016, 0.056), loc=(0, FRONT - 0.008, 0.246),
                      smooth=False))
    for i in range(13):
        long_tick = (i % 3 == 0)
        parts.append(prim("cube", f"tick_{i}", dark,
                          scale=(0.0028, 0.006, 0.030 if long_tick else 0.018),
                          loc=(lerp(-0.100, 0.100, i / 12.0), FRONT - 0.014,
                               0.252 if long_tick else 0.256), smooth=False))
    parts.append(prim("cube", "band_line", mat("radio_green", size=0.5),
                      scale=(0.210, 0.006, 0.004), loc=(0, FRONT - 0.014, 0.232),
                      smooth=False))
    parts.append(prim("cube", "needle", red, scale=(0.0055, 0.007, 0.052),
                      loc=(0.034, FRONT - 0.017, 0.246), smooth=False))

    # カセットデッキの扉
    parts.append(prim("cube", "deck_door", mat("radio_dk", size=0.55),
                      scale=(0.215, 0.018, 0.098), loc=(0, FRONT + 0.002, 0.140),
                      smooth=False))
    parts.append(prim("cube", "deck_window", mat("deck_glass", size=0.5, gloss=0.25),
                      scale=(0.170, 0.014, 0.062), loc=(0, FRONT - 0.006, 0.146),
                      smooth=False))
    for sx in (-1, 1):
        parts.append(prim("cylinder", f"reel_{sx}", panel, radius=0.024, depth=0.012,
                          loc=(sx * 0.048, FRONT - 0.012, 0.146),
                          rot=(radians(90), 0, 0)))
        parts.append(prim("cylinder", f"reel_hub_{sx}", dark, radius=0.010, depth=0.016,
                          loc=(sx * 0.048, FRONT - 0.014, 0.146),
                          rot=(radians(90), 0, 0)))

    # 操作ボタン (再生・停止など)
    for i in range(6):
        x = lerp(-0.098, 0.098, i / 5.0)
        parts.append(prim("cube", f"btn_{i}", panel if i != 4 else red,
                          scale=(0.028, 0.020, 0.026), loc=(x, FRONT - 0.006, 0.070),
                          smooth=False))
        parts.append(prim("cube", f"btn_top_{i}", dark, scale=(0.022, 0.010, 0.006),
                          loc=(x, FRONT - 0.014, 0.078), smooth=False))

    # つまみ (ローレット付き)
    for i, x in enumerate((-0.160, 0.160)):
        parts.append(prim("cylinder", f"knob_{i}", dark, radius=0.030, depth=0.034,
                          loc=(x, FRONT - 0.004, 0.246), rot=(radians(90), 0, 0)))
        parts.append(prim("cylinder", f"knob_top_{i}", panel, radius=0.020, depth=0.038,
                          loc=(x, FRONT - 0.008, 0.246), rot=(radians(90), 0, 0)))
        parts.append(prim("cube", f"knob_mark_{i}", red, scale=(0.004, 0.006, 0.018),
                          loc=(x, FRONT - 0.026, 0.258), smooth=False))
        for k in range(16):
            a = 2 * pi * k / 16
            parts.append(prim("cube", f"knurl_{i}_{k}", dark,
                              scale=(0.003, 0.016, 0.004),
                              loc=(x + cos(a) * 0.030, FRONT - 0.004,
                                   0.246 + sin(a) * 0.030),
                              rot=(0, 0, -a), smooth=False))

    # ブランドプレート
    parts.append(prim("cube", "brand_plate", silver, scale=(0.088, 0.008, 0.016),
                      loc=(0, FRONT - 0.008, 0.300), smooth=False))

    # ------------------------------------------------------------------
    # ハンドル / アンテナ / 脚 / 側面のベント
    # ------------------------------------------------------------------
    parts.append(tube("handle",
                      [(-0.250, 0.150, 0.300), (-0.190, 0.150, 0.360),
                       (0.0, 0.150, 0.376), (0.190, 0.150, 0.360), (0.250, 0.150, 0.300)],
                      [0.015] * 5, dark, order=4))
    for sx in (-1, 1):
        parts.append(prim("cube", f"handle_hinge_{sx}", silver,
                          scale=(0.026, 0.030, 0.030),
                          loc=(sx * 0.252, 0.150, 0.296), smooth=False))
    # 伸縮アンテナ
    ant_base = Vector((0.360, 0.150, 0.300))
    parts.append(prim("cylinder", "antenna_base", silver, radius=0.010, depth=0.028,
                      loc=tuple(ant_base), rot=(radians(20), 0, 0)))
    parts.append(capsule("antenna", tuple(ant_base + Vector((0.010, 0.020, 0.020))),
                         tuple(ant_base + Vector((0.115, 0.130, 0.330))),
                         0.0055, 0.0018, silver))

    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(prim("cylinder", f"foot_{sx}_{sy}", dark, radius=0.024, depth=0.020,
                              loc=(sx * 0.360, 0.055 + sy * 0.100, 0.006)))
        # 側面のベント
        for k in range(5):
            parts.append(prim("cube", f"vent_{sx}_{k}", mat("radio_dk", size=0.6),
                              scale=(0.008, 0.070, 0.008),
                              loc=(sx * 0.428, 0.120, 0.090 + k * 0.030),
                              smooth=False))
    return parts


# ---------------------------------------------------------------------------
# 背景・ライト・カメラ・レンダー設定
# ---------------------------------------------------------------------------
def build_backdrop():
    floor = prim("plane", "floor", flat_mat("bg"), scale=(9, 9, 1), loc=(0, 0, 0),
                 coll=BACKDROP, smooth=False)
    wall = prim("plane", "wall", flat_mat("bg"), scale=(9, 6, 1), loc=(0, 2.6, 2.6),
                rot=(radians(90), 0, 0), coll=BACKDROP, smooth=False)
    return [floor, wall]


def aim(obj, target=(0, 0, 0.55)):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def build_lights():
    specs = [
        ("key", (-1.70, -1.85, 2.10), 72, "#FFF4E2", 2.2),
        ("fill", (1.95, -1.55, 1.05), 32, "#DCEBFF", 2.6),
        ("rim", (0.90, 1.70, 2.05), 62, "#FFD9A0", 1.8),
        ("bounce", (0.0, -1.20, 0.02), 18, "#FFF0DC", 2.6),
        ("feet", (0.0, -1.05, 0.42), 30, "#FFF2E0", 1.4),
    ]
    lights = []
    for name, loc, power, color, size in specs:
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = power
        data.size = size
        data.color = col(color)[:3]
        obj = bpy.data.objects.new(name, data)
        link(obj, "Lights")
        obj.location = loc
        aim(obj, (0, -0.25, 0.16) if name == "feet" else (0, 0, 0.55))
        lights.append(obj)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = col("bg")
    bg.inputs["Strength"].default_value = 0.75
    bpy.context.scene.world = world
    return lights


def setup_camera():
    data = bpy.data.cameras.new("Camera")
    data.lens = 72.0
    cam = bpy.data.objects.new("Camera", data)
    link(cam, "Lights")
    bpy.context.scene.camera = cam
    return cam


def place_camera(cam, angle_deg, dist=2.95, height=0.62, target=(0, 0, 0.48)):
    a = radians(angle_deg)
    cam.location = Vector((sin(a) * dist, -cos(a) * dist, height))
    aim(cam, target)


def setup_render(samples, res):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.015
    # ビルドによってはデノイザーが同梱されていないので、使える場合だけ有効にする
    denoisers = [i.identifier for i in
                 scene.cycles.bl_rna.properties["denoiser"].enum_items]
    if denoisers:
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = ("OPENIMAGEDENOISE" if "OPENIMAGEDENOISE" in denoisers
                                 else denoisers[0])
    else:
        scene.cycles.use_denoising = False
        print("[warn] no Cycles denoiser in this build - relying on sample count")
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 4
    scene.cycles.transparent_max_bounces = 6
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False

    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    # イラスト調の鮮やかさを保つため、フィルミックではなく Standard を使う
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0

    # Freestyle でイラスト調の輪郭線 (被写体のみ)
    scene.render.use_freestyle = True
    scene.render.line_thickness_mode = "ABSOLUTE"
    scene.render.line_thickness = 1.3

    vl = bpy.context.view_layer
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    lineset = fs.linesets.new("outline")
    lineset.select_silhouette = True
    lineset.select_border = True
    lineset.select_crease = True
    lineset.select_edge_mark = False
    lineset.select_by_collection = True
    lineset.collection = bpy.data.collections[SUBJECT]
    fs.crease_angle = radians(125)

    style = lineset.linestyle
    style.color = col("dark")[:3]
    style.thickness = 1.7
    style.thickness_position = "CENTER"


# ---------------------------------------------------------------------------
# 組み立て
# ---------------------------------------------------------------------------
def build_all():
    head_parts = build_head() + build_hair() + build_headphones() + build_glasses()

    # 頭部一式を少しだけあおり気味に傾ける
    pivot = bpy.data.objects.new("head_pivot", None)
    link(pivot, SUBJECT)
    pivot.location = (0, 0.0, 0.80)
    bpy.context.view_layer.update()
    for o in head_parts:
        o.parent = pivot
        o.matrix_parent_inverse = pivot.matrix_world.inverted()
    pivot.rotation_euler = Euler((HEAD_TILT, 0, radians(2.5)))

    build_torso()
    build_arms()
    build_legs()
    build_boombox()
    build_backdrop()
    build_lights()
    return setup_camera()


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------
# view -> (方位角, カメラ距離, カメラ高さ, 注視点)
VIEWS = {
    "front": (0.0, 2.85, 0.62, (0, -0.04, 0.50)),
    "hero": (32.0, 3.30, 0.74, (0, -0.14, 0.44)),
    "side": (72.0, 3.30, 0.68, (0, -0.16, 0.42)),
    "back": (156.0, 3.10, 0.72, (0, -0.02, 0.46)),
    "face": (12.0, 1.05, 0.95, (0, 0, 0.90)),
}


def parse_args(argv):
    args = {"out": "blender/renders", "samples": 96, "res": (900, 1350),
            "views": ["front", "hero", "side", "face"], "render": True}
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            args["out"] = argv[i + 1]; i += 2
        elif a == "--samples":
            args["samples"] = int(argv[i + 1]); i += 2
        elif a == "--res":
            args["res"] = (int(argv[i + 1]), int(argv[i + 2])); i += 3
        elif a == "--views":
            args["views"] = argv[i + 1].split(","); i += 2
        elif a == "--no-render":
            args["render"] = False; i += 1
        else:
            i += 1
    return args


def main():
    args = parse_args(sys.argv)
    out_dir = os.path.abspath(args["out"])
    os.makedirs(out_dir, exist_ok=True)

    reset_scene()
    cam = build_all()
    setup_render(args["samples"], args["res"])

    blend_path = os.path.join(out_dir, "illustration_3d.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"[saved] {blend_path}")

    try:
        bpy.ops.export_scene.gltf(
            filepath=os.path.join(out_dir, "illustration_3d.glb"),
            export_format="GLB", use_visible=True)
        print("[saved] illustration_3d.glb")
    except Exception as exc:                                  # noqa: BLE001
        print(f"[warn] glTF export skipped: {exc}")

    if not args["render"]:
        return

    for view in args["views"]:
        if view not in VIEWS:
            print(f"[skip] unknown view: {view}")
            continue
        angle, dist, height, target = VIEWS[view]
        place_camera(cam, angle, dist, height, target)
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"{view}.png")
        print(f"[render] {view} ...")
        bpy.ops.render.render(write_still=True)
        print(f"[done] {view}.png")


if __name__ == "__main__":
    main()
