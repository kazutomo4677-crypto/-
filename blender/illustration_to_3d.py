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
    "blush":       "#F0967E",
    "mouth":       "#A83E42",
    "teeth":       "#FFF6EC",
    "tongue":      "#E06E82",
    "eye":         "#4A2B18",
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

    "radio":       "#E4561F",
    "radio_dk":    "#B23B14",
    "radio_panel": "#F3DFA8",
    "radio_grill": "#D9AE55",
    "radio_green": "#4FAE3C",
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
SUBJECT = "Subject"   # Freestyle の輪郭線を掛けるコレクション
BACKDROP = "Backdrop"


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll_name in (SUBJECT, BACKDROP, "Lights"):
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


def mat(key, size=0.55, smooth=0.10, gloss=0.0, alpha=1.0, name=None):
    """トゥーン(拡散)+ 少量のトゥーン(光沢)を混ぜたマテリアルを返す(キャッシュ付き)."""
    cache_key = (key, round(size, 3), round(smooth, 3), round(gloss, 3), round(alpha, 3))
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

    # 鼻
    p, _ = head_point(0.0, -0.19, -0.004)
    parts.append(prim("sphere", "nose", mat("skin_shadow", size=0.7),
                      scale=(0.016, 0.014, 0.013), loc=tuple(p)))

    # 笑顔の口: 暗い開口 + 上の歯 + 舌
    parts.append(head_patch("mouth", 0.0, -0.415, 0.30, 0.165,
                            mat("mouth", size=0.7), out=0.0015, squash=1.0))
    parts.append(head_arc("teeth", 0.0, -0.332, 0.245, -0.018,
                          mat("teeth", size=0.75), width=0.055, out=0.006,
                          thickness=0.004))

    # 笑って細めた目と眉
    for s in (-1, 1):
        parts.append(head_arc(f"eye_{s}", s * 0.50, 0.115, 0.170, 0.078,
                              mat("eye", size=0.75), width=0.021))
        parts.append(head_arc(f"brow_{s}", s * 0.50, 0.315, 0.175, 0.06,
                              mat("hair_dark", size=0.7), width=0.013))
    # ほお
    for s in (-1, 1):
        parts.append(head_patch(f"blush_{s}", s * 0.70, -0.20, 0.19, 0.10,
                                mat("blush", size=0.8), out=0.0012, thickness=0.002))
    return parts


def build_hair():
    parts = []
    hair = mat("hair", size=0.5, smooth=0.14, gloss=0.05)
    hair_lt = mat("hair_light", size=0.55, gloss=0.05)

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

    parts.append(grid_mesh("hair", 76, 26, fn, hair, thickness=0.012, close_u=True))
    # 頭頂の穴をふさぐクラウン
    parts.append(prim("sphere", "hair_crown", hair,
                      scale=(r.x * 0.40, r.y * 0.40, r.z * 0.22),
                      loc=tuple(center + Vector((0, 0.004, r.z * 0.70)))))

    # 顔の脇に流れる細い毛束 (シルエットに動きを出す)
    for s in (-1, 1):
        base = skull_pt(s * 1.34, hairline(s * 1.34))
        pts = [base,
               base + Vector((s * 0.014, -0.026, -0.085)),
               base + Vector((s * 0.030, -0.022, -0.165)),
               base + Vector((s * 0.038, 0.000, -0.225))]
        parts.append(tube(f"strand_{s}", pts, [0.016, 0.014, 0.011, 0.005], hair_lt))
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
    tee = mat("tee", size=0.5, smooth=0.12)
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

    # デニムジャケット: 前を開けたシェル
    def jacket(name, a0, a1, material):
        def fn(u, v):
            a = lerp(a0, a1, u)
            z = lerp(0.735, 0.315, v)
            t = v
            rad = lerp(0.176, 0.196, t)
            drop = 0.02 * smoothstep(0.0, 1.0, t)
            return Vector((sin(a) * rad, -cos(a) * (rad - drop) * 0.72, z))
        return grid_mesh(name, 26, 14, fn, material, thickness=0.013)

    parts.append(jacket("jacket_r", 0.20, pi, denim))
    parts.append(jacket("jacket_l", -0.20, -pi, denim))

    # 襟
    for s in (-1, 1):
        parts.append(prim("cube", f"lapel_{s}", denim_dk, scale=(0.070, 0.030, 0.115),
                          loc=(s * 0.078, -0.098, 0.700),
                          rot=(radians(14), radians(s * 22), radians(s * 10))))
    parts.append(prim("torus", "collar", denim_dk, major_radius=0.098, minor_radius=0.024,
                      loc=(0, 0.030, 0.752), rot=(radians(10), 0, 0),
                      scale=(1.0, 0.80, 0.75)))

    # ジャケットのワッペン
    patch_specs = [
        (0.62, 0.640, "print_yellow", (0.050, 0.006, 0.040)),
        (0.95, 0.545, "print_pink", (0.044, 0.006, 0.052)),
        (-0.70, 0.590, "print_cream", (0.048, 0.006, 0.044)),
        (-1.05, 0.470, "rb_green", (0.042, 0.006, 0.038)),
    ]
    for i, (a, z, key, sc) in enumerate(patch_specs):
        # ジャケットのシェルと同じ式で位置を求め、外表面より少しだけ外に出す
        t = (0.735 - z) / 0.42
        rad = lerp(0.176, 0.196, t) + 0.010
        drop = 0.02 * smoothstep(0.0, 1.0, t)
        parts.append(prim("cube", f"patch_{i}", mat(key, size=0.75), scale=sc,
                          loc=(sin(a) * rad, -cos(a) * (rad - drop) * 0.72, z),
                          rot=(0, 0, -a), smooth=False))

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
    cuff = mat("cuff", size=0.6)
    skin = mat("skin", size=0.62, smooth=0.16)

    for s in (-1, 1):
        shoulder = Vector((s * 0.158, 0.005, 0.706))
        elbow = Vector((s * 0.246, -0.070, 0.472))
        wrist = Vector((s * 0.132, -0.258, 0.296))
        parts.append(prim("sphere", f"shoulder_{s}", denim, scale=(0.072, 0.070, 0.066),
                          loc=tuple(shoulder)))
        parts.append(tube(f"sleeve_{s}",
                          [shoulder, (shoulder + elbow) / 2 + Vector((s * 0.010, 0.006, 0)),
                           elbow, (elbow + wrist) / 2 + Vector((s * 0.012, -0.010, 0)), wrist],
                          [0.070, 0.064, 0.058, 0.050, 0.043], denim, order=4))
        # まくり上げた白いカフス
        d = (wrist - elbow).normalized()
        parts.append(prim("torus", f"cuff_{s}", cuff, major_radius=0.044,
                          minor_radius=0.017, loc=tuple(wrist + d * 0.010),
                          rot=tuple(d.to_track_quat("Z", "Y").to_euler())))
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
    """足首の上で組む手 (ローカルで作ってから配置)."""
    skin = mat("skin", size=0.62, smooth=0.16)
    objs = []
    palm = prim("sphere", f"palm_{s}", skin, scale=(0.052, 0.064, 0.027), loc=(0, 0, 0))
    objs.append(palm)
    for i in range(4):
        x = lerp(-0.030, 0.030, i / 3.0)
        length = 0.080 - abs(i - 1.2) * 0.008
        objs.append(tube(f"finger_{s}_{i}",
                         [(x, -0.045, 0.004), (x * 1.05, -0.045 - length * 0.55, -0.006),
                          (x * 1.08, -0.045 - length, -0.026)],
                         [0.015, 0.014, 0.011], skin))
    objs.append(tube(f"thumb_{s}",
                     [(-0.038, -0.010, 0.006), (-0.062, -0.030, 0.002),
                      (-0.070, -0.058, -0.004)],
                     [0.015, 0.013, 0.011], skin))

    # 前腕の先(手首)からつながる位置へ
    move_group(objs,
               loc=(s * 0.058, -0.348, 0.290),
               rot=(radians(-30), radians(s * 10), radians(s * 30)),
               scale=(s, 1, 1))
    return objs


def build_legs():
    """あぐらの脚 (ジーンズ) と裾のロールアップ."""
    parts = []
    jeans = mat("jeans", size=0.5, smooth=0.14)
    jeans_dk = mat("jeans_dk", size=0.5)
    cuff = mat("cuff", size=0.6)

    for s in (-1, 1):
        hip = Vector((s * 0.110, 0.030, 0.318))
        knee = Vector((s * 0.298, -0.150, 0.145))
        ankle = Vector((s * 0.132, -0.305, 0.158))
        parts.append(tube(f"leg_{s}",
                          [hip,
                           hip + (knee - hip) * 0.45 + Vector((0, 0.01, 0.03)),
                           knee,
                           knee + (ankle - knee) * 0.5 + Vector((0, -0.02, -0.02)),
                           ankle],
                          [0.112, 0.106, 0.096, 0.084, 0.070], jeans, order=4))
        parts.append(prim("sphere", f"knee_{s}", jeans, scale=(0.094, 0.092, 0.084),
                          loc=tuple(knee)))
        # 縫い目のライン
        d = (ankle - knee).normalized()
        parts.append(tube(f"seam_{s}",
                          [hip + Vector((s * 0.055, -0.075, -0.01)),
                           knee + Vector((s * 0.02, -0.080, 0.01)),
                           ankle + Vector((s * 0.010, -0.060, 0.02))],
                          [0.006, 0.005, 0.004], jeans_dk))
        # まくり上げた裾
        parts.append(prim("torus", f"jcuff_{s}", cuff, major_radius=0.064,
                          minor_radius=0.021, loc=tuple(ankle + d * 0.020),
                          rot=tuple(d.to_track_quat("Z", "Y").to_euler())))
        # 靴下 (グリーン): 足首からスニーカーの履き口へ
        collar = SHOE_LOC(s) + Vector((s * 0.020, 0.121, 0.140))
        parts.append(capsule(f"sock_{s}", tuple(ankle), tuple(collar),
                             0.048, 0.042, mat("tee", size=0.55)))
        parts += build_shoe(s)
    return parts


def SHOE_LOC(s):
    return Vector((s * 0.158, -0.400, 0.0))


def build_shoe(s):
    """オレンジのハイカットスニーカー."""
    objs = []
    orange = mat("shoe", size=0.45, smooth=0.12, gloss=0.04)
    cream = mat("shoe_cream", size=0.55)
    rubber = mat("rubber", size=0.6)
    green = mat("shoe_green", size=0.45)
    blue = mat("shoe_blue", size=0.45)

    # ソール (白いラバー)
    sole = prim("cube", "sole", rubber, scale=(0.094, 0.232, 0.034), loc=(0, 0, 0.018),
                smooth=False)
    bevel(sole, 0.020, 4)
    subsurf(sole, 1)
    shade_smooth(sole)
    objs.append(sole)
    # ミッドソールのライン
    midsole = prim("cube", "midsole", cream, scale=(0.086, 0.208, 0.014),
                   loc=(0, 0, 0.036), smooth=False)
    bevel(midsole, 0.006, 2)
    objs.append(midsole)

    # アッパー
    upper = prim("cube", "upper", orange, scale=(0.104, 0.200, 0.118), loc=(0, 0.008, 0.096),
                 smooth=False)
    bevel(upper, 0.030, 5)
    subsurf(upper, 1)
    shade_smooth(upper)
    objs.append(upper)

    # つま先
    objs.append(prim("sphere", "toe", cream, scale=(0.050, 0.044, 0.028),
                     loc=(0, -0.092, 0.050)))
    # ハイカットの履き口 + タン
    objs.append(prim("torus", "collar", green, major_radius=0.049, minor_radius=0.018,
                     loc=(0, 0.068, 0.158), rot=(radians(-12), 0, 0)))
    objs.append(prim("cube", "tongue", cream, scale=(0.046, 0.016, 0.078),
                     loc=(0, 0.014, 0.142), rot=(radians(16), 0, 0)))
    # 靴ひも
    for i in range(4):
        z = 0.096 + i * 0.023
        y = -0.004 + i * 0.016
        objs.append(tube(f"lace_{i}",
                         [(-0.044, y, z), (0.0, y - 0.018, z + 0.010), (0.044, y, z)],
                         [0.006, 0.007, 0.006], cream))
    # サイドのサークルロゴ
    for sx in (-1, 1):
        objs.append(prim("cylinder", f"logo_{sx}", cream, radius=0.036, depth=0.012,
                         loc=(sx * 0.088, 0.028, 0.094), rot=(0, radians(90), 0)))
        objs.append(prim("cylinder", f"logo_in_{sx}", blue, radius=0.022, depth=0.016,
                         loc=(sx * 0.092, 0.028, 0.094), rot=(0, radians(90), 0)))
    # かかとのタブ
    objs.append(prim("cube", "heel_tab", green, scale=(0.046, 0.014, 0.046),
                     loc=(0, 0.104, 0.146), smooth=False))

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

    # 左右のスピーカー
    for s in (-1, 1):
        parts.append(prim("cylinder", f"sp_ring_{s}", dark, radius=0.106, depth=0.024,
                          loc=(s * 0.300, -0.100, 0.150), rot=(radians(90), 0, 0)))
        parts.append(prim("cylinder", f"sp_grill_{s}", grill, radius=0.090, depth=0.030,
                          loc=(s * 0.300, -0.104, 0.150), rot=(radians(90), 0, 0)))
        parts.append(prim("torus", f"sp_trim_{s}", green if s > 0 else mat("frame", size=0.45),
                          major_radius=0.100, minor_radius=0.012,
                          loc=(s * 0.300, -0.108, 0.150), rot=(radians(90), 0, 0)))

    # 中央のチューナーとグリル
    parts.append(prim("cube", "tuner", panel, scale=(0.230, 0.018, 0.070),
                      loc=(0, -0.104, 0.238), smooth=False))
    parts.append(prim("cube", "tuner_glass", mat("print_cream", size=0.6),
                      scale=(0.205, 0.014, 0.048), loc=(0, -0.110, 0.238), smooth=False))
    for i in range(9):
        parts.append(prim("cube", f"tick_{i}", dark, scale=(0.004, 0.008, 0.030),
                          loc=(lerp(-0.088, 0.088, i / 8.0), -0.116, 0.240), smooth=False))
    parts.append(prim("cube", "needle", mat("rb_red", size=0.5), scale=(0.006, 0.008, 0.042),
                      loc=(0.032, -0.118, 0.240), smooth=False))
    for i in range(7):
        parts.append(prim("cube", f"grill_bar_{i}", grill, scale=(0.190, 0.014, 0.010),
                          loc=(0, -0.104, 0.075 + i * 0.020), smooth=False))
    # つまみ
    for i, x in enumerate((-0.150, 0.150)):
        parts.append(prim("cylinder", f"knob_{i}", dark, radius=0.026, depth=0.030,
                          loc=(x, -0.108, 0.148), rot=(radians(90), 0, 0)))
    # ハンドル
    parts.append(tube("handle",
                      [(-0.270, 0.150, 0.290), (-0.200, 0.150, 0.356),
                       (0.0, 0.150, 0.372), (0.200, 0.150, 0.356), (0.270, 0.150, 0.290)],
                      [0.016] * 5, dark, order=4))
    # 脚
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(prim("cylinder", f"foot_{sx}_{sy}", dark, radius=0.024, depth=0.020,
                              loc=(sx * 0.360, 0.055 + sy * 0.100, 0.006)))
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
