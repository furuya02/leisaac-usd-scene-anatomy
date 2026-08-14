#!/usr/bin/env python3
"""pick_donut が読み込まれない原因を切り分ける。"""
import traceback

from isaaclab.app import AppLauncher

app = AppLauncher(headless=True).app

import pkgutil  # noqa: E402
import sys  # noqa: E402

print("\n" + "=" * 70)
print("A. leisaac パッケージの実体")
print("=" * 70)
import leisaac  # noqa: E402
print("leisaac.__file__ :", leisaac.__file__)
print("leisaac.__path__ :", list(leisaac.__path__))

print("\n" + "=" * 70)
print("B. leisaac.tasks 配下で見えているサブパッケージ")
print("=" * 70)
try:
    import leisaac.tasks as T
    print("tasks.__path__ :", list(T.__path__))
    for m in pkgutil.iter_modules(T.__path__):
        print(f"   {'pkg ' if m.ispkg else 'mod '}{m.name}")
except Exception:
    traceback.print_exc()

print("\n" + "=" * 70)
print("C. leisaac.tasks.pick_donut を直接 import")
print("=" * 70)
try:
    import leisaac.tasks.pick_donut  # noqa: F401
    print("IMPORT OK")
except Exception:
    traceback.print_exc()

print("\n" + "=" * 70)
print("D. leisaac.assets.scenes.donut を直接 import")
print("=" * 70)
try:
    from leisaac.assets.scenes.donut import KITCHEN_WITH_DONUT_USD_PATH
    print("IMPORT OK :", KITCHEN_WITH_DONUT_USD_PATH)
    import os
    print("exists    :", os.path.exists(KITCHEN_WITH_DONUT_USD_PATH))
except Exception:
    traceback.print_exc()

print("\n" + "=" * 70)
print("E. gym に登録されている LeIsaac 環境")
print("=" * 70)
import gymnasium as gym  # noqa: E402
ids = sorted(k for k in gym.registry if "LeIsaac" in k)
for i in ids:
    print("   ", i)
print(f"   合計 {len(ids)} 件")

print("\n" + "=" * 70)
print("F. sys.path 上の editable install の痕跡")
print("=" * 70)
for p in sys.path:
    if "leisaac" in p.lower():
        print("   ", p)
import glob  # noqa: E402
for sp in sys.path:
    for f in glob.glob(f"{sp}/__editable__*leisaac*"):
        print("   finder:", f)
