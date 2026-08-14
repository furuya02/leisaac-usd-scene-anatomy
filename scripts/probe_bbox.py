#!/usr/bin/env python3
"""prim のワールド空間バウンディングボックスを測る。

自作オブジェクトを「皿の斜面の上」のような具体的な位置に置きたいときに、
当てずっぽうにならないよう寸法を先に確認するためのもの。

usage:
    python probe_bbox.py <usd> <prim path> [<prim path> ...]
"""
import sys

from pxr import Usd, UsdGeom

USD = sys.argv[1]
PATHS = sys.argv[2:] or ["/Root/Plate/Plate", "/Root/Donut001/Donut001"]

stage = Usd.Stage.Open(USD)
if stage is None:
    sys.exit(f"cannot open: {USD}")

cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])

for p in PATHS:
    prim = stage.GetPrimAtPath(p)
    if not prim or not prim.IsValid():
        print(f"\n{p}: not found")
        continue
    b = cache.ComputeWorldBound(prim)
    r = b.ComputeAlignedRange()
    if r.IsEmpty():
        print(f"\n{p}: empty bound")
        continue
    mn, mx = r.GetMin(), r.GetMax()
    size = (mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2])
    mid = ((mx[0] + mn[0]) / 2, (mx[1] + mn[1]) / 2, (mx[2] + mn[2]) / 2)
    print(f"\n{p}")
    print(f"  min    : ({mn[0]:.4f}, {mn[1]:.4f}, {mn[2]:.4f})")
    print(f"  max    : ({mx[0]:.4f}, {mx[1]:.4f}, {mx[2]:.4f})")
    print(f"  size   : ({size[0]:.4f}, {size[1]:.4f}, {size[2]:.4f})  [m]")
    print(f"  center : ({mid[0]:.4f}, {mid[1]:.4f}, {mid[2]:.4f})")

# 皿が取れていれば、斜面に置くための座標案を出す
plate = stage.GetPrimAtPath("/Root/Plate/Plate")
if plate and plate.IsValid():
    r = cache.ComputeWorldBound(plate).ComputeAlignedRange()
    mn, mx = r.GetMin(), r.GetMax()
    cx, cy = (mx[0] + mn[0]) / 2, (mx[1] + mn[1]) / 2
    rad = min(mx[0] - mn[0], mx[1] - mn[1]) / 2
    print("\n" + "=" * 60)
    print("皿の斜面に置くための座標案")
    print("=" * 60)
    print(f"  皿の中心      : ({cx:.4f}, {cy:.4f})")
    print(f"  皿の半径      : {rad:.4f} m")
    print(f"  皿の上端 z    : {mx[2]:.4f} / 底 z: {mn[2]:.4f}  (深さ {mx[2]-mn[2]:.4f} m)")
    print()
    print("  斜面（半径の 60% 付近）に置く案:")
    ox = cx + rad * 0.6
    oz = mn[2] + (mx[2] - mn[2]) * 0.55
    print(f"    xformOp:translate = ({ox:.3f}, {cy:.3f}, {oz:.3f})")
    print()
    print(f"  この皿に収めるなら、物体の外径は {rad*0.8:.3f} m 以下が望ましい")
    print(f"    => make_object.py --major-r {rad*0.25:.3f} --minor-r {rad*0.10:.3f}")
