#!/usr/bin/env python3
"""Locate the white cap above a magenta culture-medium bottle in Record3D RGB-D.

The detector uses only the supplied capture bundle.  It first finds compact
magenta liquid/label regions, then scores low-saturation bright components
immediately above them.  This makes the target selection reproducible without
embedding a pixel picked by an operator from one frame.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def _first_frame(session: Path) -> dict:
    with (session / "frames.jsonl").open(encoding="utf-8") as stream:
        return json.loads(next(stream))


def _components(mask: np.ndarray, minimum_area: int):
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    for index in range(1, count):
        x, y, width, height, area = map(int, stats[index])
        if area >= minimum_area:
            yield index, labels, (x, y, width, height, area), centers[index]


def detect(rgb_bgr: np.ndarray) -> dict:
    hsv = cv2.cvtColor(rgb_bgr, cv2.COLOR_BGR2HSV)
    magenta = cv2.inRange(hsv, np.array((135, 50, 50)), np.array((179, 255, 255)))
    magenta = cv2.morphologyEx(
        magenta, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)
    )
    bright = ((hsv[:, :, 1] < 65) & (hsv[:, :, 2] > 145)).astype(np.uint8)

    candidates = []
    for _, _, body, body_center in _components(magenta, 100):
        bx, by, bw, bh, body_area = body
        if not (10 <= bw <= 100 and 10 <= bh <= 100):
            continue
        x0 = max(0, int(round(body_center[0] - 1.2 * bw)))
        x1 = min(rgb_bgr.shape[1], int(round(body_center[0] + 1.2 * bw)))
        y0 = max(0, int(round(by - 2.5 * bh)))
        y1 = min(rgb_bgr.shape[0], by + 3)
        region = bright[y0:y1, x0:x1]
        for _, _, local_cap, cap_center_local in _components(region, 25):
            cx, cy, cw, ch, cap_area = local_cap
            cap_center = np.asarray((x0, y0), float) + cap_center_local
            alignment = abs(cap_center[0] - body_center[0]) / max(bw, 1)
            vertical_gap = by - (y0 + cy + ch)
            if alignment > 0.65 or not (-4 <= vertical_gap <= bh):
                continue
            if not (0.35 * bw <= cw <= 2.0 * bw and 0.25 * bh <= ch <= 2.5 * bh):
                continue
            fill = cap_area / (cw * ch)
            score = cap_area * fill / (1.0 + alignment + 0.1 * max(vertical_gap, 0))
            candidates.append({
                "score": float(score),
                "body_bbox_xywh": list(body[:4]),
                "body_area_px": body_area,
                "cap_bbox_xywh": [x0 + cx, y0 + cy, cw, ch],
                "cap_center_uv_px": cap_center.tolist(),
                "cap_area_px": cap_area,
                "alignment_body_width": float(alignment),
                "vertical_gap_px": int(vertical_gap),
            })

    if not candidates:
        raise RuntimeError("no white cap / magenta bottle pair found")
    candidates.sort(key=lambda item: item["score"], reverse=True)
    best = candidates[0]
    if len(candidates) > 1:
        best["score_margin_ratio"] = best["score"] / max(candidates[1]["score"], 1e-9)
    else:
        best["score_margin_ratio"] = None
    best["candidate_count"] = len(candidates)
    return best


def add_metric_depth(session: Path, frame: dict, detection: dict) -> None:
    depth = cv2.rotate(
        np.load(session / frame["files"]["depth_npy"]["path"]),
        cv2.ROTATE_90_CLOCKWISE,
    )
    rgb_height, rgb_width = frame["rgb_shape"][1], frame["rgb_shape"][0]
    u, v = detection["cap_center_uv_px"]
    du = int(round(u * depth.shape[1] / rgb_width))
    dv = int(round(v * depth.shape[0] / rgb_height))
    radius = 3
    patch = depth[
        max(0, dv - radius):min(depth.shape[0], dv + radius + 1),
        max(0, du - radius):min(depth.shape[1], du + radius + 1),
    ]
    valid = patch[np.isfinite(patch) & (patch > 0)]
    if valid.size == 0:
        raise RuntimeError("no valid aligned depth at detected cap")
    z = float(np.median(valid))
    K = np.asarray(frame["intrinsics"]["K_rgb_rotated_clockwise"], float)
    xyz = [(u - K[0, 2]) * z / K[0, 0], (v - K[1, 2]) * z / K[1, 1], z]
    detection["depth_m"] = z
    detection["camera_xyz_m"] = [float(value) for value in xyz]
    detection["depth_valid_samples"] = int(valid.size)
    detection["estimated_cap_width_m"] = float(
        detection["cap_bbox_xywh"][2] * z / K[0, 0]
    )


def annotate(rgb: np.ndarray, detection: dict) -> np.ndarray:
    result = rgb.copy()
    bx, by, bw, bh = detection["body_bbox_xywh"]
    cx, cy, cw, ch = detection["cap_bbox_xywh"]
    u, v = (int(round(value)) for value in detection["cap_center_uv_px"])
    cv2.rectangle(result, (bx, by), (bx + bw, by + bh), (255, 0, 255), 3)
    cv2.rectangle(result, (cx, cy), (cx + cw, cy + ch), (0, 255, 0), 3)
    cv2.drawMarker(result, (u, v), (0, 0, 255), cv2.MARKER_CROSS, 24, 3)
    label = f"CAP z={detection['depth_m']:.3f}m width~{detection['estimated_cap_width_m']*1000:.0f}mm"
    cv2.putText(result, label, (max(0, cx - 40), max(25, cy - 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2, cv2.LINE_AA)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    frame = _first_frame(args.session)
    rgb = cv2.rotate(
        cv2.imread(str(args.session / frame["files"]["rgb_png"]["path"])),
        cv2.ROTATE_90_CLOCKWISE,
    )
    if rgb is None:
        raise RuntimeError("could not read captured RGB frame")
    detection = detect(rgb)
    add_metric_depth(args.session, frame, detection)
    output = args.output or args.session / "derived" / "cap_detection.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), annotate(rgb, detection)):
        raise RuntimeError(f"could not write {output}")
    detection["source_session"] = str(args.session)
    detection["annotated_image"] = str(output)
    print(json.dumps(detection, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
