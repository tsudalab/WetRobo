#!/usr/bin/env python3
"""Estimate median image motion inside an ROI using sparse optical flow."""

from __future__ import annotations

import argparse
import json

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--roi", nargs=4, type=int, metavar=("X0", "Y0", "X1", "Y1"), required=True)
    args = parser.parse_args()

    before = cv2.imread(args.before, cv2.IMREAD_GRAYSCALE)
    after = cv2.imread(args.after, cv2.IMREAD_GRAYSCALE)
    if before is None or after is None:
        raise SystemExit("could not read input image")
    x0, y0, x1, y1 = args.roi
    mask = np.zeros_like(before)
    mask[y0:y1, x0:x1] = 255
    points = cv2.goodFeaturesToTrack(before, 200, 0.01, 5, mask=mask)
    if points is None:
        raise SystemExit("no features found")
    tracked, status, error = cv2.calcOpticalFlowPyrLK(before, after, points, None)
    valid = status.reshape(-1).astype(bool)
    p0 = points.reshape(-1, 2)[valid]
    p1 = tracked.reshape(-1, 2)[valid]
    err = error.reshape(-1)[valid]
    delta = p1 - p0
    good = (err < np.percentile(err, 80)) & (np.linalg.norm(delta, axis=1) < 80)
    delta = delta[good]
    result = {
        "roi_xyxy": args.roi,
        "tracked_points": int(delta.shape[0]),
        "median_delta_uv_px": np.median(delta, axis=0).tolist(),
        "mean_delta_uv_px": np.mean(delta, axis=0).tolist(),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
