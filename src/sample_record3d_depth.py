#!/usr/bin/env python3
"""Sample metric Record3D depth at landscape-preview RGB coordinates.

Coordinates are specified in the lossless landscape RGB preview written by
``capture_record3d_bundle.py``.  The script rotates the aligned low-resolution
depth map the same way, takes a robust local median, and back-projects it with
the captured (not assumed) camera intrinsics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def load_frame(session: Path) -> dict:
    with (session / "frames.jsonl").open(encoding="utf-8") as stream:
        return json.loads(next(stream))


def sample(session: Path, label: str, u: float, v: float, radius_px: float) -> dict:
    frame = load_frame(session)
    rgb_path = session / frame["files"]["rgb_png"]["path"]
    depth_path = session / frame["files"]["depth_npy"]["path"]
    rgb = cv2.rotate(cv2.imread(str(rgb_path)), cv2.ROTATE_90_CLOCKWISE)
    depth = cv2.rotate(np.load(depth_path), cv2.ROTATE_90_CLOCKWISE)

    scale_u = rgb.shape[1] / depth.shape[1]
    scale_v = rgb.shape[0] / depth.shape[0]
    du = int(round(u / scale_u))
    dv = int(round(v / scale_v))
    radius_u = max(1, int(round(radius_px / scale_u)))
    radius_v = max(1, int(round(radius_px / scale_v)))
    patch = depth[
        max(0, dv - radius_v): min(depth.shape[0], dv + radius_v + 1),
        max(0, du - radius_u): min(depth.shape[1], du + radius_u + 1),
    ]
    valid = patch[np.isfinite(patch) & (patch > 0)]
    if valid.size == 0:
        raise RuntimeError(f"no valid depth around ({u}, {v})")
    z = float(np.median(valid))

    K = np.asarray(frame["intrinsics"]["K_rgb_rotated_clockwise"], float)
    x = (float(u) - K[0, 2]) * z / K[0, 0]
    y = (float(v) - K[1, 2]) * z / K[1, 1]
    return {
        "label": label,
        "rgb_uv_px": [float(u), float(v)],
        "depth_uv_px": [du, dv],
        "radius_rgb_px": float(radius_px),
        "valid_samples": int(valid.size),
        "depth_m": z,
        "camera_xyz_m": [x, y, z],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument(
        "--point", action="append", nargs=3, metavar=("LABEL", "U", "V"),
        required=True,
    )
    parser.add_argument("--radius-px", type=float, default=6.0)
    args = parser.parse_args()
    result = [
        sample(args.session, label, float(u), float(v), args.radius_px)
        for label, u, v in args.point
    ]
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
