# leisaac-usd-scene-anatomy

[LeIsaac](https://github.com/LightwheelAI/leisaac) の模倣学習シーン `kitchen_with_orange` の USD 構造を解析し、自作オブジェクトに差し替えるためのスクリプト集です。

関連記事: [Amazon EC2] Isaac Sim で LeIsaac の模倣学習シーン（kitchen_with_orange）を解剖して自作オブジェクトに差し替えてみました

[English](README.md)

## できること

- `scene.usd` の prim ツリー・物理 API・参照形態（Reference / Payload）を書き出す
- LeIsaac の `parse_usd_and_create_subassets()` と同じ判定を再現し、**どの prim が `SceneEntityCfg` になるか**を事前に確認する
- 自作オブジェクトの USD を、配布アセットと同じ構造で生成する
- `scene.usd` を変更せずに、USD のレイヤ合成でオブジェクトを追加する
- LeIsaac の既存ファイルを変更せずに、自作タスクを追加する

**解析だけであれば GPU も Isaac Sim も不要です。** `usd-core` だけで動きます。

## 前提

| 用途 | 必要なもの |
|---|---|
| USD の解析（`inspect_*.py` / `make_object.py` / `probe_bbox.py`） | Python 3.11 + `usd-core` のみ |
| タスクの追加と実行（`install_donut_task.py`） | Isaac Sim 5.1 + Isaac Lab 2.3 + LeIsaac v0.4.0 |

検証環境（2026 年 8 月時点）:

- Amazon EC2 g5.xlarge（NVIDIA A10G 24GB / 4 vCPU / メモリ 16GB）
- Ubuntu 22.04.5 LTS / NVIDIA driver 570.211.01（CUDA Datacenter 版）
- Isaac Sim 5.1.0.0 / Isaac Lab v2.3.0 / LeIsaac v0.4.0（`24d3bcd`）
- PyTorch 2.7.0+cu128 / Python 3.11.15

## セットアップ

```bash
git clone https://github.com/furuya02/leisaac-usd-scene-anatomy.git
cd leisaac-usd-scene-anatomy
```

### 解析だけを行う場合

```bash
conda create -n usdtool python=3.11 -y --override-channels -c conda-forge
conda activate usdtool
pip install usd-core
```

### LeIsaac 環境を用意する場合

[LeIsaac の公式手順](https://lightwheelai.github.io/leisaac/docs/getting_started/installation)に従ってください。2026 年 8 月時点では、`isaaclab.sh --install` が `flatdict` のビルドで失敗し、**`isaaclab` 本体だけがインストールされないまま正常終了する**という事象があります。

```bash
# isaaclab 本体が入っているか必ず確認する
pip list | grep -iE '^isaaclab '

# 空だった場合の回避策
pip install "setuptools<82" wheel
pip install --no-build-isolation "flatdict==4.0.1"
pip install -e source/isaaclab
```

原因は setuptools v82.0.0 での `pkg_resources` 削除です。

## シーンアセットの入手

**シーンアセットとロボット USD は本リポジトリに含めていません。** LeIsaac のリリースから取得してください。

```bash
cd <leisaac>/assets
mkdir -p scenes robots

curl -L -o /tmp/kitchen_with_orange.zip \
  https://github.com/LightwheelAI/leisaac/releases/download/v0.1.0/kitchen_with_orange.zip
curl -L -o robots/so101_follower.usd \
  https://github.com/LightwheelAI/leisaac/releases/download/v0.1.0/so101_follower.usd

unzip -q /tmp/kitchen_with_orange.zip -d scenes/
```

展開後の構造:

```
assets/
├── robots/so101_follower.usd
└── scenes/kitchen_with_orange/
    ├── scene.usd
    ├── assets/
    └── objects/{Orange001, Orange002, Orange003, Plate}
```

## スクリプト

| スクリプト | 用途 | Isaac Sim |
|---|---|---|
| `scripts/inspect_usd.py` | prim ツリー・物理 API・参照形態の書き出し。`SceneEntityCfg` の再現 | 不要 |
| `scripts/inspect_payload.py` | payload の解決先と物理マテリアル（摩擦・反発）の確認 | 不要 |
| `scripts/probe_bbox.py` | prim のワールド空間バウンディングボックスの計測 | 不要 |
| `scripts/make_object.py` | 自作オブジェクト USD の生成（トーラス） | 不要 |
| `scripts/setup_friction_test.py` | 摩擦係数の比較用シーンの生成 | 不要 |
| `scripts/install_donut_task.py` | LeIsaac に自作タスクを追加 | 実行時に必要 |
| `scripts/diag_donut.py` | タスクが登録されない場合の切り分け | 必要 |

## 動作確認手順

### 1. シーンを解析する

```bash
cd <leisaac>/assets/scenes/kitchen_with_orange
python <this-repo>/scripts/inspect_usd.py scene.usd
```

次のような出力が得られます。

```
prim 総数            : 921
RigidBodyAPI        : 91
CollisionAPI        : 237
MassAPI             : 91
ArticulationRootAPI : 24

5. parse_usd_and_create_subassets() の再現
  SceneEntityCfg("Orange001")
      usd prim  : /Root/Orange001/Orange001
      cfg  prim : {ENV_REGEX_NS}/Scene/Orange001/Orange001
```

### 2. 自作オブジェクトを生成する

```bash
python <this-repo>/scripts/make_object.py --name Donut001 \
  --approximation convexDecomposition --out objects/Donut001/Donut001.usd
```

主なオプション:

| オプション | 既定値 | 説明 |
|---|---|---|
| `--approximation` | `convexDecomposition` | コリジョン近似。凸形状なら `convexHull` で十分 |
| `--mass` | 0.15 | 質量（kg） |
| `--major-r` / `--minor-r` | 0.035 / 0.015 | トーラスの寸法（m） |
| `--static-friction` / `--dynamic-friction` | 5.0 / 4.0 | 配布アセットに合わせた高摩擦 |

### 3. シーンに追加する（`scene.usd` は変更しません）

`assets/scenes/kitchen_with_orange/scene_with_donut.usda` を作成します。

```usda
#usda 1.0
(
    subLayers = [
        @./scene.usd@
    ]
    defaultPrim = "Root"
    metersPerUnit = 1
    upAxis = "Z"
)

over "Root"
{
    def "Donut001" (
        prepend payload = @./objects/Donut001/Donut001.usd@
    )
    {
        double3 xformOp:translate = (2.05, -0.25, 0.95)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }
}
```

`#usda 1.0` はファイルの先頭バイトから始まる必要があります。作成後に `head -1 scene_with_donut.usda | cat -A` で確認してください。

認識されるかを、Isaac Sim を起動せずに確認できます。

```bash
python <this-repo>/scripts/inspect_usd.py scene_with_donut.usda Donut001 Plate
# => SceneEntityCfg("Donut001") が出力されれば OK
```

### 4. タスクを追加する

```bash
python <this-repo>/scripts/install_donut_task.py --leisaac-root ~/work/leisaac
```

`leisaac/assets/scenes/donut.py` と `leisaac/tasks/pick_donut/` を新規作成します。**既存ファイルの編集はありません**（`tasks/__init__.py` の `import_packages()` が自動探索するため）。

### 5. 実行する

```bash
cd <leisaac>
python scripts/environments/list_envs.py | grep -i donut
# => LeIsaac-SO101-PickDonut-v0

python scripts/environments/teleoperation/teleop_se3_agent.py \
  --task=LeIsaac-SO101-PickDonut-v0 --teleop_device=keyboard \
  --num_envs=1 --device=cuda --enable_cameras
```

GUI で起動する場合、初回はシェーダーコンパイルに時間がかかります（g5.xlarge で約 9 分）。GNOME が「応答していません」と表示しますが、待てば起動します。

コリジョン形状は、ビューポートの目のアイコンから `Show By Type → Physics → Colliders → All` で表示できます。

## 注意

- GPU インスタンスは起動しているだけで課金されます。作業後は必ず停止してください
- シーンアセットおよびロボット USD は再配布していません
- LeIsaac 本体および配布アセットは Apache-2.0 です

## 参考

- LeIsaac: https://github.com/LightwheelAI/leisaac
- LeIsaac インストール手順: https://lightwheelai.github.io/leisaac/docs/getting_started/installation
- Isaac Lab: https://github.com/isaac-sim/IsaacLab
- UsdPhysics スキーマ: https://openusd.org/release/api/usd_physics_page_front.html
