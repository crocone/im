"""Master asset build: regenerates every GLB in public/assets.

Run with Blender:        blender -b --factory-startup --python-exit-code 1 -P tools/blender/build_all.py
or the bpy Python module: python3 tools/blender/build_all.py
(`npm run assets` picks whichever is available and then verifies the output.)
Any exception aborts the build with a non-zero exit code.
"""
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import build_city  # noqa: E402
import build_destructibles  # noqa: E402
import build_enemies  # noqa: E402
import build_player  # noqa: E402
import build_projectiles  # noqa: E402
from common import log  # noqa: E402

STAGES = [
    ("player", build_player.build),
    ("enemies", build_enemies.build),
    ("projectiles", build_projectiles.build),
    ("city kit", build_city.build),
    ("destructibles", build_destructibles.build),
]


def main():
    log(f"Blender {bpy.app.version_string}")
    start = time.time()
    for name, fn in STAGES:
        log(f"--- building {name}")
        fn()
    log(f"all assets built in {time.time() - start:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)
