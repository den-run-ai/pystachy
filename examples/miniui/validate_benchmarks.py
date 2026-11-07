#!/usr/bin/env python3
"""Compare real framebuffer pixels outside timing (requires a live display/Pillow)."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from PIL import Image

from run_benchmarks import run_one


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cpu", type=int, default=min(os.sched_getaffinity(0)))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    target = args.output_dir.resolve()
    target.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("PYSTACHY_"):
            del env[key]
    env.update(manifest.get("env", {}))
    env.update(PYTHONHASHSEED="0", LP_NUM_THREADS="1", OMP_NUM_THREADS="1")
    env["LD_LIBRARY_PATH"] = manifest["adapters"]["real"] + ":" + env.get("LD_LIBRARY_PATH", "")
    expected_pixels = None
    expected_checksum = None
    results = []
    for runtime in manifest["runtimes"]:
        path = target / (runtime["name"] + ".png")
        result = run_one(runtime["command"], env | runtime.get("env", {}), args.cpu,
                         "frame", 150, 13, 3, str(path))
        image = Image.open(path).convert("RGBA")
        pixels = image.tobytes()
        colors = image.getcolors(maxcolors=image.width * image.height)
        particle_colors = dict((color, count) for count, color in
                               image.crop((0, 320, 760, 520)).getcolors(152000))
        if (colors is None or len(colors) < 4
                or particle_colors.get((102, 194, 255, 255), 0) < 100):
            raise RuntimeError("framebuffer is blank or missing UI content: " + runtime["name"])
        if expected_pixels is None:
            expected_pixels = pixels
            expected_checksum = result["checksum"]
        if image.size != (760, 520) or pixels != expected_pixels:
            raise RuntimeError("framebuffer mismatch: " + runtime["name"])
        if result["checksum"] != expected_checksum:
            raise RuntimeError("state mismatch: " + runtime["name"])
        result.update(runtime=runtime["name"], pixel_sha256=hashlib.sha256(pixels).hexdigest(),
                      image=path.name)
        results.append(result)
        print(runtime["name"], "pixel/state parity passed", flush=True)
    (target / "validation.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
