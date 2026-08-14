# leisaac-usd-scene-anatomy

Scripts for dissecting the USD structure of [LeIsaac](https://github.com/LightwheelAI/leisaac)'s imitation-learning scene `kitchen_with_orange`, and for swapping in your own object.

[日本語](README.ja.md)

## What this does

- Dumps the prim tree, physics APIs, and composition arcs (Reference / Payload) of `scene.usd`
- Reproduces LeIsaac's `parse_usd_and_create_subassets()` logic so you can check **which prims become a `SceneEntityCfg`** before writing any code
- Generates a custom object USD with the same structure as the shipped assets
- Adds the object to the scene via USD layer composition, **without modifying `scene.usd`**
- Registers a custom task **without editing any existing LeIsaac file**

**Analysis needs neither a GPU nor Isaac Sim.** `usd-core` alone is enough.

## Requirements

| Purpose | Needed |
|---|---|
| USD analysis (`inspect_*.py` / `make_object.py` / `probe_bbox.py`) | Python 3.11 + `usd-core` only |
| Task registration and running (`install_donut_task.py`) | Isaac Sim 5.1 + Isaac Lab 2.3 + LeIsaac v0.4.0 |

Verified environment (August 2026):

- Amazon EC2 g5.xlarge (NVIDIA A10G 24GB / 4 vCPU / 16GB RAM)
- Ubuntu 22.04.5 LTS / NVIDIA driver 570.211.01 (CUDA Datacenter, **not GRID**)
- Isaac Sim 5.1.0.0 / Isaac Lab v2.3.0 / LeIsaac v0.4.0 (`24d3bcd`)
- PyTorch 2.7.0+cu128 / Python 3.11.15

## Setup

```bash
git clone https://github.com/furuya02/leisaac-usd-scene-anatomy.git
cd leisaac-usd-scene-anatomy
```

### For analysis only

```bash
conda create -n usdtool python=3.11 -y --override-channels -c conda-forge
conda activate usdtool
pip install usd-core
```

### For the full LeIsaac environment

Follow the [official installation guide](https://lightwheelai.github.io/leisaac/docs/getting_started/installation). As of August 2026, `isaaclab.sh --install` **exits successfully while failing to install `isaaclab` itself**, because `flatdict` fails to build.

```bash
# Always verify that isaaclab itself is installed
pip list | grep -iE '^isaaclab '

# Workaround if the above is empty
pip install "setuptools<82" wheel
pip install --no-build-isolation "flatdict==4.0.1"
pip install -e source/isaaclab
```

The root cause is the removal of `pkg_resources` in setuptools v82.0.0.

## Getting the scene assets

**Scene assets and the robot USD are not redistributed here.** Download them from the LeIsaac releases.

```bash
cd <leisaac>/assets
mkdir -p scenes robots

curl -L -o /tmp/kitchen_with_orange.zip \
  https://github.com/LightwheelAI/leisaac/releases/download/v0.1.0/kitchen_with_orange.zip
curl -L -o robots/so101_follower.usd \
  https://github.com/LightwheelAI/leisaac/releases/download/v0.1.0/so101_follower.usd

unzip -q /tmp/kitchen_with_orange.zip -d scenes/
```

Resulting layout:

```
assets/
├── robots/so101_follower.usd
└── scenes/kitchen_with_orange/
    ├── scene.usd
    ├── assets/
    └── objects/{Orange001, Orange002, Orange003, Plate}
```

## Scripts

| Script | Purpose | Isaac Sim |
|---|---|---|
| `scripts/inspect_usd.py` | Prim tree, physics APIs, composition arcs, `SceneEntityCfg` reproduction | Not needed |
| `scripts/inspect_payload.py` | Payload targets and physics materials (friction / restitution) | Not needed |
| `scripts/probe_bbox.py` | World-space bounding box of a prim | Not needed |
| `scripts/make_object.py` | Generate a custom object USD (torus) | Not needed |
| `scripts/setup_friction_test.py` | Build a friction comparison scene | Not needed |
| `scripts/install_donut_task.py` | Register a custom task in LeIsaac | At run time |
| `scripts/diag_donut.py` | Diagnose a task that fails to register | Needed |

## Walkthrough

### 1. Inspect the scene

```bash
cd <leisaac>/assets/scenes/kitchen_with_orange
python <this-repo>/scripts/inspect_usd.py scene.usd
```

Expected output:

```
prim total          : 921
RigidBodyAPI        : 91
CollisionAPI        : 237
MassAPI             : 91
ArticulationRootAPI : 24

SceneEntityCfg("Orange001")
    usd prim  : /Root/Orange001/Orange001
    cfg  prim : {ENV_REGEX_NS}/Scene/Orange001/Orange001
```

Of the 91 rigid bodies, 87 are kitchen fixtures. Only 4 are task objects, which is why `specific_name_list` exists.

### 2. Generate a custom object

```bash
python <this-repo>/scripts/make_object.py --name Donut001 \
  --approximation convexDecomposition --out objects/Donut001/Donut001.usd
```

| Option | Default | Note |
|---|---|---|
| `--approximation` | `convexDecomposition` | Use `convexHull` for convex shapes |
| `--mass` | 0.15 | kg |
| `--major-r` / `--minor-r` | 0.035 / 0.015 | Torus dimensions (m) |
| `--static-friction` / `--dynamic-friction` | 5.0 / 4.0 | Matches the shipped assets |

A concave shape (torus, bowl, box interior) needs `convexDecomposition`. With `convexHull`, the hole is capped.

### 3. Add it to the scene (without touching `scene.usd`)

Create `assets/scenes/kitchen_with_orange/scene_with_donut.usda`:

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

`#usda 1.0` must start at the very first byte of the file. Verify with `head -1 scene_with_donut.usda | cat -A`.

You can confirm recognition without launching Isaac Sim:

```bash
python <this-repo>/scripts/inspect_usd.py scene_with_donut.usda Donut001 Plate
# => prints SceneEntityCfg("Donut001")
```

### 4. Register the task

```bash
python <this-repo>/scripts/install_donut_task.py --leisaac-root ~/work/leisaac
```

Creates `leisaac/assets/scenes/donut.py` and `leisaac/tasks/pick_donut/`. **No existing file is modified** — `tasks/__init__.py` discovers sub-packages via `import_packages()`.

### 5. Run

```bash
cd <leisaac>
python scripts/environments/list_envs.py | grep -i donut
# => LeIsaac-SO101-PickDonut-v0

python scripts/environments/teleoperation/teleop_se3_agent.py \
  --task=LeIsaac-SO101-PickDonut-v0 --teleop_device=keyboard \
  --num_envs=1 --device=cuda --enable_cameras
```

The first GUI launch takes about 9 minutes on a g5.xlarge (shader compilation, CPU-bound). GNOME may report "not responding" — wait rather than force quit.

To see collision shapes: viewport eye icon, then `Show By Type → Physics → Colliders → All`.

## Notes

- GPU instances are billed while running. Stop them when you are done
- Scene assets and the robot USD are not redistributed here
- LeIsaac and its assets are Apache-2.0

## References

- LeIsaac: https://github.com/LightwheelAI/leisaac
- LeIsaac installation: https://lightwheelai.github.io/leisaac/docs/getting_started/installation
- Isaac Lab: https://github.com/isaac-sim/IsaacLab
- UsdPhysics schema: https://openusd.org/release/api/usd_physics_page_front.html
