#!/usr/bin/env python3
"""LeIsaac に自作オブジェクト（Donut001）のタスクを追加する。

LeIsaac の `tasks/__init__.py` は `import_packages()` で `tasks/` 配下を自動探索するため、
**既存ファイルを 1 行も編集せずに**新しいタスクを追加できる。このスクリプトは
以下の 3 ファイルを新規作成するだけ。

    source/leisaac/leisaac/assets/scenes/donut.py
    source/leisaac/leisaac/tasks/pick_donut/__init__.py
    source/leisaac/leisaac/tasks/pick_donut/pick_donut_env_cfg.py

pick_orange からの変更点は 3 か所のみ:
    1. シーンの USD パス      -> scene_with_donut.usda
    2. specific_name_list     -> ["Donut001", "Plate"]
    3. ランダマイズ / 成功判定 -> Donut001 を対象に

usage:
    python install_donut_task.py --leisaac-root ~/work/leisaac
"""
import argparse
import os

SCENE_PY = '''from pathlib import Path

import isaaclab.sim as sim_utils
from isaaclab.assets import AssetBaseCfg
from leisaac.utils.constant import ASSETS_ROOT

"""Configuration for the Kitchen Scene with a self-made donut."""
SCENES_ROOT = Path(ASSETS_ROOT) / "scenes"

# scene.usd を subLayer で下敷きにし、Donut001 を payload で足した overlay レイヤ。
# 元の scene.usd（39MB）は 1 バイトも変更していない。
KITCHEN_WITH_DONUT_USD_PATH = str(SCENES_ROOT / "kitchen_with_orange" / "scene_with_donut.usda")

KITCHEN_WITH_DONUT_CFG = AssetBaseCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=KITCHEN_WITH_DONUT_USD_PATH,
    )
)
'''

INIT_PY = '''import gymnasium as gym

gym.register(
    id="LeIsaac-SO101-PickDonut-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.pick_donut_env_cfg:PickDonutEnvCfg",
    },
)
'''

ENV_CFG_PY = '''import torch

from isaaclab.assets import AssetBaseCfg
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.utils import configclass

from leisaac.assets.scenes.donut import (
    KITCHEN_WITH_DONUT_CFG,
    KITCHEN_WITH_DONUT_USD_PATH,
)
from leisaac.utils.domain_randomization import (
    domain_randomization,
    randomize_camera_uniform,
    randomize_object_uniform,
)
from leisaac.utils.general_assets import parse_usd_and_create_subassets

from ..pick_orange import mdp
from ..template import (
    SingleArmObservationsCfg,
    SingleArmTaskEnvCfg,
    SingleArmTaskSceneCfg,
    SingleArmTerminationsCfg,
)


@configclass
class PickDonutSceneCfg(SingleArmTaskSceneCfg):
    """Scene configuration for the pick donut task."""

    scene: AssetBaseCfg = KITCHEN_WITH_DONUT_CFG.replace(prim_path="{ENV_REGEX_NS}/Scene")


@configclass
class ObservationsCfg(SingleArmObservationsCfg):

    @configclass
    class SubtaskCfg(ObsGroup):
        """Observations for subtask group."""

        pick_donut001 = ObsTerm(func=mdp.orange_grasped, params={"object_cfg": SceneEntityCfg("Donut001")})
        put_donut001_to_plate = ObsTerm(
            func=mdp.put_orange_to_plate,
            params={"object_cfg": SceneEntityCfg("Donut001"), "plate_cfg": SceneEntityCfg("Plate")},
        )

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = False

    subtask_terms: SubtaskCfg = SubtaskCfg()


@configclass
class TerminationsCfg(SingleArmTerminationsCfg):

    # task_done は「対象物が皿の範囲内 + アームが rest pose」を見るだけなので、
    # オレンジ専用ではなくそのまま流用できる。
    success = DoneTerm(
        func=mdp.task_done,
        params={
            "oranges_cfg": [SceneEntityCfg("Donut001")],
            "plate_cfg": SceneEntityCfg("Plate"),
        },
    )


@configclass
class PickDonutEnvCfg(SingleArmTaskEnvCfg):
    """Configuration for the pick donut environment."""

    scene: PickDonutSceneCfg = PickDonutSceneCfg(env_spacing=8.0)

    observations: ObservationsCfg = ObservationsCfg()

    terminations: TerminationsCfg = TerminationsCfg()

    task_description: str = "Pick the donut and put it into the plate, then reset the arm to rest state."

    def __post_init__(self) -> None:
        super().__post_init__()

        # ここで指定した名前が、そのまま SceneEntityCfg の名前になる。
        # 指定しないと scene 内の剛体 92 個すべてが登録されてしまう。
        parse_usd_and_create_subassets(
            KITCHEN_WITH_DONUT_USD_PATH, self, specific_name_list=["Donut001", "Plate"]
        )

        domain_randomization(
            self,
            random_options=[
                randomize_object_uniform(
                    "Donut001", pose_range={"x": (-0.03, 0.03), "y": (-0.03, 0.03), "z": (0.0, 0.0)}
                ),
                randomize_object_uniform("Plate", pose_range={"x": (-0.03, 0.03), "y": (-0.03, 0.03), "z": (0.0, 0.0)}),
                randomize_camera_uniform(
                    "front",
                    pose_range={
                        "x": (-0.025, 0.025),
                        "y": (-0.025, 0.025),
                        "z": (-0.025, 0.025),
                        "roll": (-2.5 * torch.pi / 180, 2.5 * torch.pi / 180),
                        "pitch": (-2.5 * torch.pi / 180, 2.5 * torch.pi / 180),
                        "yaw": (-2.5 * torch.pi / 180, 2.5 * torch.pi / 180),
                    },
                    convention="ros",
                ),
            ],
        )
'''


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  wrote {path} ({len(content)} bytes)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leisaac-root", default=os.path.expanduser("~/work/leisaac"))
    a = ap.parse_args()

    root = os.path.abspath(os.path.expanduser(a.leisaac_root))
    pkg = os.path.join(root, "source", "leisaac", "leisaac")
    if not os.path.isdir(pkg):
        raise SystemExit(f"leisaac package not found: {pkg}")

    print("installing pick_donut task...")
    write(os.path.join(pkg, "assets", "scenes", "donut.py"), SCENE_PY)
    write(os.path.join(pkg, "tasks", "pick_donut", "__init__.py"), INIT_PY)
    write(os.path.join(pkg, "tasks", "pick_donut", "pick_donut_env_cfg.py"), ENV_CFG_PY)

    scene = os.path.join(root, "assets", "scenes", "kitchen_with_orange", "scene_with_donut.usda")
    print()
    print(f"scene overlay : {scene}")
    print(f"  exists      : {os.path.exists(scene)}")
    print()
    print("既存ファイルの編集は 0 件（tasks/__init__.py の import_packages が自動探索する）。")
    print()
    print("確認:")
    print("  python scripts/environments/list_envs.py | grep -i donut")


if __name__ == "__main__":
    main()
