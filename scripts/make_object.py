#!/usr/bin/env python3
"""LeIsaac の kitchen_with_orange に差し替える自作オブジェクトの USD を生成する。

解剖（Blog/解剖結果.md）で判明した Orange001.usd の構造をそのまま再現する:

    /root (Xform)                       <- defaultPrim
    |-- Looks/M_<Name> (Material) -> Shader (UsdPreviewSurface)
    |-- Physics/PhysicsMaterial (Material, UsdPhysics.MaterialAPI)
    `-- <Name> (Xform)  [RigidBodyAPI, MassAPI]
        |-- Collisions/<Name>_C (Mesh) [CollisionAPI, MeshCollisionAPI]  <- physics マテリアル束縛
        `-- Visuals/<Name> (Mesh) -> M_<Name>

形状はトーラス（ドーナツ）。**凹形状**なので、コリジョン近似を convexHull にすると
穴が塞がれて皿に乗る挙動が変わる。approximation の効果を確かめる題材として使う。

Isaac Sim ランタイムは不要。pxr（usd-core）だけで動く。

usage:
    python make_object.py --name Donut001 --out objects/Donut001/Donut001.usd
    python make_object.py --name Donut001 --approximation convexHull   # わざと失敗させる版
"""
import argparse
import math
import os

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, Vt


def torus(major_r, minor_r, nu=48, nv=24):
    """トーラスの点・面を作る。up 軸は Z。"""
    pts, counts, idx = [], [], []
    for i in range(nu):
        u = 2.0 * math.pi * i / nu
        cu, su = math.cos(u), math.sin(u)
        for j in range(nv):
            v = 2.0 * math.pi * j / nv
            cv, sv = math.cos(v), math.sin(v)
            pts.append(Gf.Vec3f((major_r + minor_r * cv) * cu,
                                (major_r + minor_r * cv) * su,
                                minor_r * sv))
    for i in range(nu):
        for j in range(nv):
            a = i * nv + j
            b = i * nv + (j + 1) % nv
            c = ((i + 1) % nu) * nv + (j + 1) % nv
            d = ((i + 1) % nu) * nv + j
            counts.append(4)
            idx.extend([a, b, c, d])
    return pts, counts, idx


def build(path, name, mass, major_r, minor_r, approximation, color,
          static_friction, dynamic_friction, restitution):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    stage = Usd.Stage.CreateNew(path)

    # シーン側と揃える（kitchen_with_orange は upAxis=Z / metersPerUnit=1.0）
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    root = UsdGeom.Xform.Define(stage, "/root")
    stage.SetDefaultPrim(root.GetPrim())

    # ---- 見た目のマテリアル -------------------------------------------------
    UsdGeom.Scope.Define(stage, "/root/Looks")
    mat = UsdShade.Material.Define(stage, f"/root/Looks/M_{name}")
    shader = UsdShade.Shader.Define(stage, f"/root/Looks/M_{name}/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    # ---- 物理マテリアル -----------------------------------------------------
    # オリジナルは staticFriction 5.0 / dynamicFriction 4.0 / restitution 0.0。
    # 現実にはあり得ない高摩擦だが、グリッパーが滑らないようにするための設定。
    UsdGeom.Scope.Define(stage, "/root/Physics")
    pmat = UsdShade.Material.Define(stage, "/root/Physics/PhysicsMaterial")
    pm = UsdPhysics.MaterialAPI.Apply(pmat.GetPrim())
    pm.CreateStaticFrictionAttr(static_friction)
    pm.CreateDynamicFrictionAttr(dynamic_friction)
    pm.CreateRestitutionAttr(restitution)

    # ---- 剛体本体（この prim 名が SceneEntityCfg("<name>") になる）----------
    body = UsdGeom.Xform.Define(stage, f"/root/{name}")
    UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    mass_api = UsdPhysics.MassAPI.Apply(body.GetPrim())
    mass_api.CreateMassAttr(mass)

    pts, counts, idx = torus(major_r, minor_r)
    lo = Gf.Vec3f(-(major_r + minor_r), -(major_r + minor_r), -minor_r)
    hi = Gf.Vec3f(major_r + minor_r, major_r + minor_r, minor_r)

    def mesh(prim_path):
        m = UsdGeom.Mesh.Define(stage, prim_path)
        m.CreatePointsAttr(Vt.Vec3fArray(pts))
        m.CreateFaceVertexCountsAttr(Vt.IntArray(counts))
        m.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
        m.CreateExtentAttr(Vt.Vec3fArray([lo, hi]))
        m.CreateSubdivisionSchemeAttr("none")
        return m

    # 見た目
    UsdGeom.Xform.Define(stage, f"/root/{name}/Visuals")
    vis = mesh(f"/root/{name}/Visuals/{name}")
    UsdShade.MaterialBindingAPI.Apply(vis.GetPrim()).Bind(mat)

    # 当たり判定。オリジナルは見た目と同じメッシュを複製して approximation に任せている
    UsdGeom.Xform.Define(stage, f"/root/{name}/Collisions")
    col = mesh(f"/root/{name}/Collisions/{name}_C")
    UsdPhysics.CollisionAPI.Apply(col.GetPrim())
    mc = UsdPhysics.MeshCollisionAPI.Apply(col.GetPrim())
    mc.CreateApproximationAttr(approximation)
    # 物理マテリアルは剛体ではなく「コリジョンメッシュ」に束縛する（オリジナルと同じ）
    UsdShade.MaterialBindingAPI.Apply(col.GetPrim()).Bind(
        pmat, bindingStrength=UsdShade.Tokens.weakerThanDescendants, materialPurpose="physics"
    )
    UsdGeom.Imageable(col).CreatePurposeAttr(UsdGeom.Tokens.guide)

    stage.GetRootLayer().Save()
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Donut001")
    ap.add_argument("--out", default=None)
    ap.add_argument("--mass", type=float, default=0.15, help="kg。オレンジは 0.15")
    ap.add_argument("--major-r", type=float, default=0.035, help="m。ドーナツの中心半径")
    ap.add_argument("--minor-r", type=float, default=0.015, help="m。輪の太さ")
    ap.add_argument("--approximation", default="convexDecomposition",
                    choices=["convexHull", "convexDecomposition", "boundingCube",
                             "boundingSphere", "meshSimplification", "none"])
    ap.add_argument("--color", default="0.85,0.55,0.25")
    ap.add_argument("--static-friction", type=float, default=5.0)
    ap.add_argument("--dynamic-friction", type=float, default=4.0)
    ap.add_argument("--restitution", type=float, default=0.0)
    a = ap.parse_args()

    out = a.out or f"objects/{a.name}/{a.name}.usd"
    color = tuple(float(x) for x in a.color.split(","))
    p = build(out, a.name, a.mass, a.major_r, a.minor_r, a.approximation, color,
              a.static_friction, a.dynamic_friction, a.restitution)

    print(f"created: {p}")
    print(f"  defaultPrim   : /root")
    print(f"  rigid body    : /root/{a.name}   -> SceneEntityCfg(\"{a.name}\")")
    print(f"  approximation : {a.approximation}")
    print(f"  mass          : {a.mass} kg")
    print()
    print("scene.usd に追記する内容:")
    print(f'  def "{a.name}" (')
    print(f'      prepend payload = @./objects/{a.name}/{a.name}.usd@')
    print(f'  )')
    print(f'  {{')
    print(f'  }}')


if __name__ == "__main__":
    main()
