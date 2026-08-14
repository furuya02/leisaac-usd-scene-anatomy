#!/usr/bin/env python3
"""摩擦係数の効果を1回の起動で比較するためのセットアップ。

配布アセットの物理マテリアルは staticFriction 5.0 / dynamicFriction 4.0 という
現実にはあり得ない高摩擦だった（デフォルトは 0.5）。その意味を確かめる。

皿の内側は斜面になっている。斜面で物体が滑り出す角度は arctan(mu)。
    mu = 5.0 -> 78.7 度（まず滑らない）
    mu = 0.5 -> 26.6 度
皿の中心から 77% の位置は約 30 度なので、ここに置けば挙動が分かれるはず。

摩擦違いの2個を同じ皿に置き、1回の起動で比較する。
specific_name_list に無い剛体も PhysX は計算するので、コード側の変更は不要。

usage:
    python setup_friction_test.py --scene-dir ~/work/leisaac/assets/scenes/kitchen_with_orange
"""
import argparse
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# probe_bbox.py の実測値（kitchen_with_orange の Plate）
PLATE_CX, PLATE_CY = 2.4153, -0.3384
PLATE_R = 0.1013
PLATE_BOTTOM_Z, PLATE_TOP_Z = 0.9375, 0.9746

OVERLAY = """#usda 1.0
(
    subLayers = [
        @./scene.usd@
    ]
    defaultPrim = "Root"
    metersPerUnit = 1
    upAxis = "Z"
)

over "Root"
{{
    # staticFriction 5.0 / dynamicFriction 4.0（配布アセットと同じ値）
    def "Donut001" (
        prepend payload = @./objects/Donut001/Donut001.usd@
    )
    {{
        double3 xformOp:translate = ({x1:.4f}, {y1:.4f}, {z1:.4f})
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }}

    # staticFriction 0.5 / dynamicFriction 0.5（PhysX のデフォルト値）
    def "Donut002" (
        prepend payload = @./objects/Donut002/Donut002.usd@
    )
    {{
        double3 xformOp:translate = ({x2:.4f}, {y2:.4f}, {z2:.4f})
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }}
}}
"""


def slope_z(r_from_center, sphere_r):
    """球冠と仮定したときの、中心から r の位置の高さ（皿の底からの相対）。"""
    return sphere_r - math.sqrt(max(sphere_r ** 2 - r_from_center ** 2, 0.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene-dir", default=os.path.expanduser(
        "~/work/leisaac/assets/scenes/kitchen_with_orange"))
    ap.add_argument("--major-r", type=float, default=0.015)
    ap.add_argument("--minor-r", type=float, default=0.006)
    ap.add_argument("--place-ratio", type=float, default=0.77,
                    help="皿の半径に対する配置位置（0.77 で約30度）")
    a = ap.parse_args()

    scene_dir = os.path.abspath(os.path.expanduser(a.scene_dir))
    if not os.path.isdir(scene_dir):
        sys.exit(f"scene dir not found: {scene_dir}")

    depth = PLATE_TOP_Z - PLATE_BOTTOM_Z
    sphere_r = (PLATE_R ** 2 + depth ** 2) / (2 * depth)
    off = PLATE_R * a.place_ratio
    angle = math.degrees(math.asin(min(off / sphere_r, 1.0)))
    z = PLATE_BOTTOM_Z + slope_z(off, sphere_r) + a.minor_r + 0.006  # 少し浮かせて落とす

    print("=" * 62)
    print("皿の形状（probe_bbox.py の実測値から算出）")
    print("=" * 62)
    print(f"  半径          : {PLATE_R:.4f} m")
    print(f"  深さ          : {depth:.4f} m")
    print(f"  球冠の曲率半径: {sphere_r:.4f} m")
    print(f"  配置位置      : 中心から {off:.4f} m（半径の {a.place_ratio*100:.0f}%）")
    print(f"  そこの斜面角度: 約 {angle:.1f} 度")
    print()
    print("  滑り出す角度 = arctan(mu)")
    print(f"    mu=5.0 -> {math.degrees(math.atan(5.0)):.1f} 度   （留まる想定）")
    print(f"    mu=0.5 -> {math.degrees(math.atan(0.5)):.1f} 度   （滑る想定）")
    if angle <= math.degrees(math.atan(0.5)):
        print("  !! 斜面が緩すぎて mu=0.5 でも滑らない。--place-ratio を上げること")
    print()

    # --- オブジェクト生成 -------------------------------------------------
    mk = os.path.join(HERE, "make_object.py")
    if not os.path.exists(mk):
        mk = os.path.expanduser("~/work/tools/make_object.py")

    common = [sys.executable, mk, "--approximation", "convexDecomposition",
              "--major-r", str(a.major_r), "--minor-r", str(a.minor_r),
              "--mass", "0.05"]

    print("=" * 62)
    print("オブジェクト生成")
    print("=" * 62)
    for name, sf, df, color in [
        ("Donut001", 5.0, 4.0, "0.85,0.55,0.25"),   # 配布アセットと同じ高摩擦
        ("Donut002", 0.5, 0.5, "0.25,0.45,0.90"),   # PhysX デフォルト
    ]:
        out = os.path.join(scene_dir, "objects", name, f"{name}.usd")
        cmd = common + ["--name", name, "--out", out,
                        "--static-friction", str(sf), "--dynamic-friction", str(df),
                        "--color", color]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            sys.exit(f"failed to create {name}")
        print(f"  {name}: staticFriction={sf} dynamicFriction={df} color={color}")
        print(f"           {out}")

    # --- overlay 生成 -----------------------------------------------------
    overlay_path = os.path.join(scene_dir, "scene_with_donut.usda")
    content = OVERLAY.format(
        x1=PLATE_CX + off, y1=PLATE_CY, z1=z,
        x2=PLATE_CX - off, y2=PLATE_CY, z2=z,
    )
    with open(overlay_path, "w", encoding="utf-8") as f:
        f.write(content)

    print()
    print("=" * 62)
    print("overlay レイヤ生成")
    print("=" * 62)
    print(f"  {overlay_path}")
    print(f"  Donut001 (mu=5.0) -> ({PLATE_CX + off:.4f}, {PLATE_CY:.4f}, {z:.4f})")
    print(f"  Donut002 (mu=0.5) -> ({PLATE_CX - off:.4f}, {PLATE_CY:.4f}, {z:.4f})")
    print()
    print("  先頭バイト確認:", repr(open(overlay_path, "rb").read(10)))


if __name__ == "__main__":
    main()
