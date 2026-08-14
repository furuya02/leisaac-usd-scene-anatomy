#!/usr/bin/env python3
"""kitchen_with_orange の payload 実体と物理マテリアルを調べる。

inspect_usd.py で「参照形態は Payload」と分かったので、その実体を追う。
自作オブジェクトを追加するときに「どこにファイルを置き、scene.usd にどう書くか」を
決めるための情報を集める。

Isaac Sim ランタイムは不要。pxr（usd-core）だけで動く。

usage:
    python inspect_payload.py [scene.usd のパス]
"""
import os
import sys

from pxr import Pcp, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

USD = sys.argv[1] if len(sys.argv) > 1 else "assets/scenes/kitchen_with_orange/scene.usd"
TARGETS = ["Orange001", "Orange002", "Orange003", "Plate"]


def head(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def size(path):
    try:
        return f"{os.path.getsize(path) / 1024:.1f} KB"
    except OSError:
        return "?"


stage = Usd.Stage.Open(USD)
if stage is None:
    sys.exit(f"cannot open: {USD}")

root = stage.GetRootLayer()

# ---------------------------------------------------------------- 1
head("1. scene.usd 自体のサイズと形式")
print("path   :", root.identifier)
print("size   :", size(root.identifier))
print("format :", root.GetFileFormat().formatId)
print("prim 総数:", len(list(stage.Traverse())))

# ---------------------------------------------------------------- 2
head("2. payload がどこに、どう書かれているか（authored な prim spec を読む）")
for name in TARGETS:
    path = Sdf.Path(f"/Root/{name}")
    spec = root.GetPrimAtPath(path)
    if spec is None:
        print(f"\n-- {path} : root layer に prim spec なし")
        continue
    print(f"\n-- {path} --")
    print("   specifier :", spec.specifier)
    print("   typeName  :", spec.typeName)
    pl = spec.payloadList
    for label in ("explicitItems", "addedItems", "prependedItems", "appendedItems"):
        items = getattr(pl, label, [])
        for it in items:
            print(f"   payload({label}) assetPath = {it.assetPath}")
            if it.primPath:
                print(f"                     primPath  = {it.primPath}")
    rl = spec.referenceList
    for label in ("explicitItems", "addedItems", "prependedItems", "appendedItems"):
        for it in getattr(rl, label, []):
            print(f"   reference({label}) assetPath = {it.assetPath}")

# ---------------------------------------------------------------- 3
head("3. payload の解決先ファイル（実体）")
resolved = {}
for name in TARGETS:
    prim = stage.GetPrimAtPath(f"/Root/{name}")
    if not prim:
        continue
    q = Usd.PrimCompositionQuery(prim)
    for a in q.GetCompositionArcs():
        if a.GetArcType() != Pcp.ArcTypePayload:
            continue
        node = a.GetTargetNode()
        if node is None:
            continue
        lyr = node.layerStack.identifier.rootLayer
        resolved[name] = lyr.identifier
        print(f"  {name:<10} -> {lyr.identifier}")
        print(f"  {'':<10}    size={size(lyr.identifier)} format={lyr.GetFileFormat().formatId}")

# ---------------------------------------------------------------- 4
head("4. payload 実体ファイルの中身")
for name, f in resolved.items():
    print(f"\n---- {name}: {os.path.basename(f)} ----")
    sub = Usd.Stage.Open(f)
    if sub is None:
        print("   open failed")
        continue
    dp = sub.GetDefaultPrim()
    print("   defaultPrim :", dp.GetPath() if dp else "(none)")
    prims = list(sub.Traverse())
    print("   prim 総数   :", len(prims))
    for p in prims:
        t = []
        if p.HasAPI(UsdPhysics.RigidBodyAPI):
            t.append("RigidBody")
        if p.HasAPI(UsdPhysics.CollisionAPI):
            t.append("Collision")
        if p.HasAPI(UsdPhysics.MassAPI):
            t.append("Mass")
        d = len(p.GetPath().pathString.strip("/").split("/")) - 1
        mark = f"  [{','.join(t)}]" if t else ""
        print("     " + "  " * d + f"{p.GetName()} ({p.GetTypeName()}){mark}")

# ---------------------------------------------------------------- 5
head("5. 物理マテリアル（摩擦・反発係数）")
mats = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.MaterialAPI)]
print("UsdPhysics.MaterialAPI を持つ prim:", len(mats))
seen = set()
for p in mats:
    ma = UsdPhysics.MaterialAPI(p)
    vals = (
        ma.GetStaticFrictionAttr().Get(),
        ma.GetDynamicFrictionAttr().Get(),
        ma.GetRestitutionAttr().Get(),
        ma.GetDensityAttr().Get(),
    )
    key = str(vals)
    tag = "" if key not in seen else "   (同じ値)"
    seen.add(key)
    print(f"\n  {p.GetPath()}{tag}")
    print(f"    staticFriction  = {vals[0]}")
    print(f"    dynamicFriction = {vals[1]}")
    print(f"    restitution     = {vals[2]}")
    print(f"    density         = {vals[3]}")

head("6. 対象オブジェクトの物理マテリアル束縛")
for name in TARGETS:
    for prim in [p for p in stage.Traverse() if p.GetName() == name and p.HasAPI(UsdPhysics.RigidBodyAPI)]:
        print(f"\n-- {prim.GetPath()} --")
        for d in Usd.PrimRange(prim):
            mb = UsdShade.MaterialBindingAPI(d)
            b = mb.GetDirectBinding("physics")
            if b and b.GetMaterialPath():
                print(f"   physics binding: {d.GetPath()} -> {b.GetMaterialPath()}")
