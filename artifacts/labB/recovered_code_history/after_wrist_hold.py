#!/usr/bin/env python3
"""Reproducible right-only controls for the Lab B bottle-cap trial.

This script never initializes, homes, reads, or commands the left arm.  Every
motion is linearly interpolated, torque-monitored, and appended to a JSONL
audit log.  Camera capture remains a separate process so images retain their
observation-only provenance.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from robot.rpc import RPCClient
from robot.arm.ik_solver import SingleArmIK


DEFAULT_LIMIT_NM = np.array([4.0, 4.0, 4.0, 3.0, 3.0, 5.0])
DEFAULT_AUDIT = Path("artifacts/labB/right_cap_commands.jsonl")
MODEL = Path(__file__).resolve().parents[1] / "robot/cone-e-description/robot-welded-base-and-lift.mjcf"


def state(rpc):
    pose = rpc.get_right_ee_pose()
    return {
        "q_rad": np.asarray(rpc.get_right_joint_positions(), float).tolist(),
        "ee_xyz_m": np.asarray(pose.translation(), float).tolist(),
        "ee_quaternion_wxyz": np.asarray(pose.rotation().wxyz, float).tolist(),
        "joint_torque_Nm": np.asarray(rpc.get_right_joint_torque(), float).tolist(),
        "gripper_open_ratio": float(rpc.get_right_gripper_exact()),
        "gripper_effort_Nm": float(rpc.get_right_gripper_effort()),
    }


def append_audit(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n")


def jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def move_joints(rpc, delta, duration_s, rate_hz, limits):
    before = state(rpc)
    start = np.asarray(before["q_rad"], float)
    target = start + np.asarray(delta, float)
    steps = max(1, int(round(duration_s * rate_hz)))
    peak = np.zeros(6)
    for index in range(1, steps + 1):
        command = start + (target - start) * index / steps
        rpc.set_right_joint_target(command, gripper_target=None, preview_time=0.15)
        torque = np.asarray(rpc.get_right_joint_torque(), float)
        peak = np.maximum(peak, np.abs(torque))
        if np.any(np.abs(torque) > limits):
            raise RuntimeError(
                f"torque stop at {index}/{steps}: {torque.tolist()} > {limits.tolist()}"
            )
        time.sleep(1.0 / rate_hz)
    time.sleep(0.5)
    return before, state(rpc), peak.tolist()


def position_joint_delta(q, delta_xyz, max_joint_delta=0.18, hold_wrist=False):
    """Linearized position-only IK for the physical right arm.

    Joint 6 is held fixed because its absolute tracking on this installation is
    unreliable.  The MJCF translation is used only as a local differential
    model; every executed probe is checked again from live cameras.
    """
    q = np.asarray(q, float)
    requested = np.asarray(delta_xyz, float)
    if requested.shape != (3,) or not np.all(np.isfinite(requested)):
        raise ValueError("delta_xyz must contain three finite values")
    if np.linalg.norm(requested) > 0.04 + 1e-12:
        raise ValueError("one position probe is limited to 40 mm")
    solver = SingleArmIK(
        str(MODEL),
        joint_names=[f"left_arm_joint{i}" for i in range(1, 7)],
        ee_frame="left_arm_ee",
    )
    solver.init(q)
    base = np.asarray(solver.forward_kinematics().translation(), float)
    epsilon = 1e-4
    active_joints = 3 if hold_wrist else 5
    jacobian = np.empty((3, active_joints))
    for axis in range(active_joints):
        perturbed = q.copy()
        perturbed[axis] += epsilon
        solver.update_configuration(perturbed)
        jacobian[:, axis] = (
            np.asarray(solver.forward_kinematics().translation(), float) - base
        ) / epsilon
    damping = 1e-4
    dq5 = jacobian.T @ np.linalg.solve(
        jacobian @ jacobian.T + damping * np.eye(3), requested
    )
    delta = np.r_[dq5, np.zeros(6 - active_joints)]
    if np.max(np.abs(delta)) > max_joint_delta:
        raise ValueError(
            f"position probe needs {np.max(np.abs(delta)):.3f} rad joint delta; "
            f"limit is {max_joint_delta:.3f}"
        )
    predicted = jacobian @ dq5
    return delta, predicted, jacobian


def grip_sweep(rpc, target, step, settle_s):
    before = state(rpc)
    start = before["gripper_open_ratio"]
    count = max(1, int(np.ceil(abs(target - start) / step)))
    samples = []
    q_hold = rpc.get_right_joint_positions()
    for value in np.linspace(start, target, count + 1)[1:]:
        rpc.set_right_joint_target(
            q_hold, gripper_target=float(value), preview_time=0.15
        )
        time.sleep(settle_s)
        samples.append({
            "command_ratio": float(value),
            "measured_ratio": float(rpc.get_right_gripper_exact()),
            "effort_Nm": float(rpc.get_right_gripper_effort()),
        })
    return before, state(rpc), samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--note")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("state")
    move = sub.add_parser("move-joints")
    move.add_argument("--delta", nargs=6, type=float, required=True)
    move.add_argument("--duration-s", type=float, default=4.0)
    move.add_argument("--rate-hz", type=float, default=20.0)
    move.add_argument("--torque-limits", nargs=6, type=float, default=DEFAULT_LIMIT_NM)
    plan_position = sub.add_parser("plan-position")
    plan_position.add_argument("--delta-xyz", nargs=3, type=float, required=True)
    plan_position.add_argument("--max-joint-delta", type=float, default=0.18)
    plan_position.add_argument("--hold-wrist", action="store_true")
    move_position = sub.add_parser("move-position")
    move_position.add_argument("--delta-xyz", nargs=3, type=float, required=True)
    move_position.add_argument("--max-joint-delta", type=float, default=0.18)
    move_position.add_argument("--hold-wrist", action="store_true")
    move_position.add_argument("--duration-s", type=float, default=4.0)
    move_position.add_argument("--rate-hz", type=float, default=20.0)
    move_position.add_argument("--torque-limits", nargs=6, type=float, default=DEFAULT_LIMIT_NM)
    grip = sub.add_parser("grip-sweep")
    grip.add_argument("--target", type=float, required=True)
    grip.add_argument("--step", type=float, default=0.1)
    grip.add_argument("--settle-s", type=float, default=0.4)
    ratchet = sub.add_parser("ratchet-unscrew")
    ratchet.add_argument("--cycles", type=int, default=1)
    ratchet.add_argument("--release-ratio", type=float, default=0.45)
    ratchet.add_argument("--grip-ratio", type=float, default=0.10)
    ratchet.add_argument("--return-rad", type=float, default=1.0)
    ratchet.add_argument("--twist-rad", type=float, default=-1.0)
    ratchet.add_argument("--duration-s", type=float, default=14.0)
    ratchet.add_argument("--rate-hz", type=float, default=20.0)
    ratchet.add_argument(
        "--torque-limits", nargs=6, type=float,
        default=np.array([4.0, 4.0, 4.0, 3.0, 3.0, 0.6]),
    )
    args = parser.parse_args()

    rpc = RPCClient(args.host, args.port, timeout_ms=4000)
    record = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "command": args.command,
        "arguments": jsonable(vars(args)),
        "status": "started",
    }
    try:
        if args.command == "state":
            record["after"] = state(rpc)
        elif args.command == "move-joints":
            before, after, peak = move_joints(
                rpc,
                args.delta,
                args.duration_s,
                args.rate_hz,
                np.asarray(args.torque_limits, float),
            )
            record.update(before=before, after=after, peak_abs_torque_Nm=peak)
        elif args.command == "plan-position":
            before = state(rpc)
            delta, predicted, jacobian = position_joint_delta(
                before["q_rad"], args.delta_xyz, args.max_joint_delta, args.hold_wrist
            )
            record.update(
                before=before,
                planned_joint_delta_rad=delta,
                predicted_delta_xyz_m=predicted,
                local_position_jacobian_m_per_rad=jacobian,
            )
        elif args.command == "move-position":
            initial = state(rpc)
            delta, predicted, jacobian = position_joint_delta(
                initial["q_rad"], args.delta_xyz, args.max_joint_delta, args.hold_wrist
            )
            before, after, peak = move_joints(
                rpc, delta, args.duration_s, args.rate_hz,
                np.asarray(args.torque_limits, float),
            )
            record.update(
                before=before,
                after=after,
                planned_joint_delta_rad=delta,
                predicted_delta_xyz_m=predicted,
                measured_delta_xyz_m=np.asarray(after["ee_xyz_m"]) - np.asarray(before["ee_xyz_m"]),
                local_position_jacobian_m_per_rad=jacobian,
                peak_abs_torque_Nm=peak,
            )
        elif args.command == "ratchet-unscrew":
            if args.cycles < 1:
                raise ValueError("cycles must be positive")
            limits = np.asarray(args.torque_limits, float)
            stages = []
            for cycle in range(1, args.cycles + 1):
                before_release, after_release, release_samples = grip_sweep(
                    rpc, args.release_ratio, 0.07, 0.35
                )
                _, after_return, return_peak = move_joints(
                    rpc, [0, 0, 0, 0, 0, args.return_rad],
                    args.duration_s, args.rate_hz, limits,
                )
                _, after_grip, grip_samples = grip_sweep(
                    rpc, args.grip_ratio, 0.05, 0.45
                )
                _, after_twist, twist_peak = move_joints(
                    rpc, [0, 0, 0, 0, 0, args.twist_rad],
                    args.duration_s, args.rate_hz, limits,
                )
                stages.append({
                    "cycle": cycle,
                    "before_release": before_release,
                    "after_release": after_release,
                    "release_samples": release_samples,
                    "after_return": after_return,
                    "return_peak_abs_torque_Nm": return_peak,
                    "after_grip": after_grip,
                    "grip_samples": grip_samples,
                    "after_twist": after_twist,
                    "twist_peak_abs_torque_Nm": twist_peak,
                })
            record.update(stages=stages, after=state(rpc))
        else:
            before, after, samples = grip_sweep(
                rpc, args.target, args.step, args.settle_s
            )
            record.update(before=before, after=after, samples=samples)
        record["status"] = "complete"
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        try:
            record["after"] = state(rpc)
        except Exception as snapshot_exc:
            record["snapshot_error"] = repr(snapshot_exc)
        raise
    finally:
        serializable = jsonable(record)
        append_audit(args.audit, serializable)
        print(json.dumps(serializable, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
