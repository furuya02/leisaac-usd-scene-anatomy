#!/usr/bin/env python3
"""kitchen_with_orange/scene.usd を解剖する。

LeIsaac の leisaac/utils/general_assets.py::parse_usd_and_create_subassets() と
同じ判定（UsdPhysics.RigidBodyAPI の有無 + prim 名の部分一致）を再現し、
「自作オブジェクトに差し替えるとき USD 側に何を用意すればよいか」を明らかにする。

Isaac Sim ランタイムは不要。pxr（usd-core もしくは isaacsim 同梱）だけで動く。

usage:
    python inspect_usd.py [scene.usd のパス]
"""
import sys

from pxr import Usd, UsdGeom, UsdPhysics, UsdShade

USD = sys.argv[1] if len(sys.argv) > 1 else "assets/scenes/kitchen_with_orange/scene.usd"
# 第2引数以降で対象 prim 名を指定できる（省略時は PickOrange のデフォルト）
TARGETS = sys.argv[2:] or ["Orange001", "Orange002", "Orange003", "Plate"]


def head(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


stage = Usd.Stage.Open(USD)
if stage is None:
    sys.exit(f"cannot open: {USD}")

# ---------------------------------------------------------------- 1
head("1. ステージ / レイヤ構成")
root = stage.GetRootLayer()
dp = stage.GetDefaultPrim()
print("root layer    :", root.identifier)
print("defaultPrim   :", dp.GetPath() if dp else "(none)")
print("upAxis        :", UsdGeom.GetStageUpAxis(stage))
print("metersPerUnit :", UsdGeom.GetStageMetersPerUnit(stage))
subs = list(root.subLayerPaths)
print(f"subLayers     : {len(subs)}")
for x in subs:
    print("   -", x)

# ---------------------------------------------------------------- 2
head("2. prim 統計と物理 API の分布")
allp = list(stage.Traverse())
print("prim 総数            :", len(allp))
rb = [p for p in allp if p.HasAPI(UsdPhysics.RigidBodyAPI)]
col = [p for p in allp if p.HasAPI(UsdPhysics.CollisionAPI)]
ms = [p for p in allp if p.HasAPI(UsdPhysics.MassAPI)]
art = [p for p in allp if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
print("RigidBodyAPI        :", len(rb))
print("CollisionAPI        :", len(col))
print("MassAPI             :", len(ms))
print("ArticulationRootAPI :", len(art))
print("\n-- RigidBodyAPI を持つ prim（全件）--")
for p in rb:
    print("   ", p.GetPath())
print("\n-- ArticulationRootAPI を持つ prim（全件）--")
for p in art:
    print("   ", p.GetPath())

# ---------------------------------------------------------------- 3
head("3. prim ツリー（深さ3まで）")


def tags(prim):
    t = []
    if prim.HasAPI(UsdPhysics.RigidBodyAPI):
        t.append("RigidBody")
    if prim.HasAPI(UsdPhysics.CollisionAPI):
        t.append("Collision")
    if prim.HasAPI(UsdPhysics.MassAPI):
        t.append("Mass")
    if prim.HasAuthoredReferences():
        t.append("REF")
    if prim.HasAuthoredPayloads():
        t.append("PAYLOAD")
    return f"   [{','.join(t)}]" if t else ""


def walk(prim, d=0, maxd=3):
    print("  " * d + f"{prim.GetName()} ({prim.GetTypeName()}){tags(prim)}")
    if d >= maxd:
        n = len(prim.GetChildren())
        if n:
            print("  " * (d + 1) + f"... ({n} children)")
        return
    for c in prim.GetChildren():
        walk(c, d + 1, maxd)


for c in stage.GetPseudoRoot().GetChildren():
    walk(c)

# ---------------------------------------------------------------- 4
head("4. ターゲット prim の詳細")
for name in TARGETS:
    for prim in [p for p in allp if p.GetName() == name]:
        print(f"\n---- {prim.GetPath()} ----")
        print("  type          :", prim.GetTypeName())
        print("  appliedSchemas:", list(prim.GetAppliedSchemas()))
        print("  references    :", prim.HasAuthoredReferences())
        print("  payloads      :", prim.HasAuthoredPayloads())

        q = Usd.PrimCompositionQuery(prim)
        for a in q.GetCompositionArcs():
            at = str(a.GetArcType()).split(".")[-1]
            if at == "ArcTypeRoot":
                continue
            lay = a.GetIntroducingLayer()
            print(f"    arc: {at:<18} introducedBy={lay.identifier if lay else '-'}")

        xf = UsdGeom.Xformable(prim)
        if xf:
            m = xf.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            print("  world pos     :", tuple(round(v, 4) for v in m.ExtractTranslation()))

        if prim.HasAPI(UsdPhysics.MassAPI):
            ma = UsdPhysics.MassAPI(prim)
            print("  mass          :", ma.GetMassAttr().Get())
            print("  density       :", ma.GetDensityAttr().Get())

        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            rba = UsdPhysics.RigidBodyAPI(prim)
            print("  kinematic     :", rba.GetKinematicEnabledAttr().Get())
            print("  rigidBodyOn   :", rba.GetRigidBodyEnabledAttr().Get())

        nmesh = 0
        for d in Usd.PrimRange(prim):
            if d.HasAPI(UsdPhysics.MeshCollisionAPI):
                mc = UsdPhysics.MeshCollisionAPI(d)
                print(f"    collision : {d.GetPath()}")
                print(f"                approximation = {mc.GetApproximationAttr().Get()}")
            if d.GetTypeName() == "Mesh":
                nmesh += 1
                if nmesh <= 3:
                    pts = UsdGeom.Mesh(d).GetPointsAttr().Get()
                    print(f"    mesh      : {d.GetPath()}  points={len(pts) if pts else 0}")
        if nmesh > 3:
            print(f"    mesh      : ... 他 {nmesh - 3} 個（Mesh 合計 {nmesh}）")

        shown = 0
        for d in Usd.PrimRange(prim):
            b = UsdShade.MaterialBindingAPI(d).GetDirectBinding()
            if b and b.GetMaterialPath() and shown < 3:
                print(f"    material  : {d.GetName()} -> {b.GetMaterialPath()}")
                shown += 1

# ---------------------------------------------------------------- 5
head("5. parse_usd_and_create_subassets() の再現")
print("LeIsaac が specific_name_list=%s で拾う prim を、同じロジックで再現する。\n" % TARGETS)


def match(path, spec):
    return any(s in path for s in spec)


picked = {}
order = []
for p in allp:
    if not p.HasAPI(UsdPhysics.RigidBodyAPI):
        continue
    pp = p.GetPath().pathString
    if not match(pp, TARGETS):
        continue
    base = p.GetPath().name
    name = base
    i = 0
    while name in picked:
        i += 1
        name = f"{base}_{i}"
    sub = pp[pp.find("/", 1) + 1:]
    picked[name] = (pp, "{ENV_REGEX_NS}/Scene/" + sub)
    order.append(name)

if not order:
    print("  該当なし（RigidBodyAPI が付いていないか、名前が一致しない）")
for k in order:
    orig, prim_path = picked[k]
    print(f'  SceneEntityCfg("{k}")')
    print(f"      usd prim  : {orig}")
    print(f"      cfg  prim : {prim_path}")

print("\n※ 実装は get_all_prims()（GetChildren の再帰）で走査するが、")
print("  ここでは stage.Traverse() を使っている。有効かつ定義済みの prim を辿る点は同じ。")
