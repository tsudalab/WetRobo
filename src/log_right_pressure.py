#!/usr/bin/env python3
"""Log physical-right joint torque and native gripper effort via RPC only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from robot.rpc import RPCClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--hz", type=float, default=20.0)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rpc = RPCClient(args.host, args.port, timeout_ms=4000)
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    period = 1.0 / args.hz
    with args.output.open("a", encoding="utf-8", buffering=1) as stream:
        while running:
            started = time.monotonic()
            sample = {
                "time_unix_s": time.time(),
                "time_monotonic_s": started,
                "right_joint_torque_Nm": list(rpc.get_right_joint_torque()),
                "right_gripper_effort_Nm": float(
                    rpc.get_right_gripper_effort()
                ),
            }
            stream.write(json.dumps(sample, allow_nan=False) + "\n")
            time.sleep(max(0.0, period - (time.monotonic() - started)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
