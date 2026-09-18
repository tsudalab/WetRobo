---
name: wetrobo
description: Operate the WetRobo environment — a Piper arm, an incubator, this repository's base control stack, and an exemplar of evolved task programs — to perform the task the operator gives at run time. Use when the operator asks for a manipulation on the incubator or the bench in front of it, points at an object in the head-camera image, or asks to reproduce a task after the object has been moved.
---

# WetRobo

WetRobo is a reproducible environment for policy self-improvement towards
automated biological research. The environment is four things:

| component | what it is here |
|---|---|
| Skill | this file: the rules and the starting workflow |
| Code exemplar | branch `wetrobo+petri+cap+door`: the repository as it stood after a coding agent evolved the base stack through the Petri dish lid, bottle cap, and incubator door trials — an example of what a finished policy in this environment looks like, not a fixed policy to run |
| Arm | one Piper arm with a gripper, plus a head camera looking at the workspace |
| Incubator | a laboratory incubator in front of the arm; the tasks act on it and on objects placed at it |

The `main` branch of this repository, `wetrobo`, is the base control stack
(replay, bias, safety, camera, arm RPC); that is where a trial starts. The
task is not part of the environment: the operator gives it at run time. Start
from the base stack, read the exemplar for what a finished policy looks like,
choose any additional tool or method you need, and improve the policy by
trying the task; nothing beyond this file and the code is prescribed.

## Start

1. Run `bash src/check_setup.sh` and confirm every check passes. It verifies
   that `rollout/controller.py` is the merged version that carries both the
   camera handling and the bias/safety layer.
2. Start the arm RPC server (`robot/cone_e.py` bringup) the usual way for your
   robot host; nothing here changes it.
3. Confirm no other process owns the arm you will use, the gripper is open,
   and the arm is at its home pose.
4. Read the control path before commanding motion:

   ```
   trajectory source ─┬─ replay_demo.py     (recorded HDF5)        <- use this
                      └─ cloud_inference_control_collect_v2.py (policy server)
                                │
                       PolicyController.apply_action()   (rollout/controller.py)
                                │
                      xyz_bias  (per-arm, robot frame, live-settable, magnitude-capped)
                                │
                      SafetyLayer (rollout/safety.py)
                         • keep-out zones            (src/configs/safety.json)
                         • per-step motion cap, set from the demos' largest step
                         • reject → arm holds
                                │
                      cone_e.set_*_ee_target()  ->  clamp_ee_target()  (robot/cone_e.py)
                         • workspace box, calibrated so no demo frame is clipped
   ```

   Both trajectory sources pass through the same bias + safety + clamp path.

| file | role |
|---|---|
| `replay_demo.py` | replay one HDF5 demo through the pipeline |
| `rollout/controller.py` | camera handling + bias + safety + `set_bias` |
| `rollout/safety.py` | keep-out zones + per-step cap; a rejected step holds the arm |
| `robot/cone_e.py` | workspace clamp, bounds calibrated from demos |
| `src/set_bias.py` | change the live bias without restarting |
| `src/configs/safety.json` | keep-out zones (ships empty) + step cap |
| `robot/camera_id.py`, `robot/camera_map.json` | camera index map for your host |

## Baseline workflow: one demo, replay, bias

For a task where the object barely moves between attempts, record one good
demonstration, replay its end-effector trajectory, and shift the whole
trajectory with a bias when the object sits a little off.

1. Record one demo per task with the existing teleop `--record` path. It writes
   an HDF5 with `{left,right}_ee_pos/_ee_quat/_gripper` + `timestamps`.
2. Replay it:

   ```bash
   python replay_demo.py path/to/episode.hdf5 --safety-config src/configs/safety.json --rate <hz>
   # 's' start, 'e' end, 'q' quit.  Use a reduced rate for a first run, then the demo's rate.
   ```

3. Adjust when the object is off, live, from another shell:

   ```bash
   python src/set_bias.py                 # show current bias + safety rejection count
   python src/set_bias.py --z <offset_m>  # shift the whole path along z
   python src/set_bias.py --y <offset_m>  # shift along y
   python src/set_bias.py --reset
   ```

   The bias magnitude is capped in `rollout/controller.py`. A live change
   resets the safety step reference so the resulting jump is not rejected.

4. Vision-in-the-loop bias (optional): crop the head-camera frame to the object
   ROI, contrast-stretch, upscale, and ask a vision model for a lateral offset
   relative to the demo; convert it to a bias and call `set_bias`. Do this once
   per attempt while the arm is stationary at the start, never inside the
   motion (a vision model answers in seconds; the control loop runs at tens of
   hertz).

Assumptions the baseline relies on; measure them for your setup:

- Object placement varies only slightly across demos of a task, small relative
  to the gripper opening. That is why a fixed trajectory plus a small bias is
  viable at all.
- A vision model's position estimate has a noise floor of the order of the
  gripper-jaw width. It beats replaying the demo unchanged only when the object
  is off by clearly more than that.

### Regression check before any real task

1. `bash src/check_setup.sh` → all pass.
2. Replay a known-good demo at a reduced rate with bias 0. `[Workspace]
   Position clamped` and `[safety] REJECTED` must not appear in normal motion.
   If the per-step cap fires during fast transport, raise `max_step_m` in
   `src/configs/safety.json`.
3. `python src/set_bias.py` answers (the bias thread is up).
4. Apply the task's known-good bias and confirm the arm reaches the same depth.

Abort and revert (`git checkout -- <file>`) if the arm drifts during replay,
the clamp fires in normal motion, or safety rejects repeatedly.

## Commanding the arm directly

The replay path above hides these; a task program that drives the arm itself has to
handle them, and each one has been mistaken for a hardware fault at least once.

- **After the RPC server restarts, the arm ignores commands until MIT mode is
  reasserted and the gains are raised.** The default gains are holding gains, too soft
  to move anything, and the driver accepts commands it then does not execute. Bring up
  in this order: hold the *measured* pose, set holding gains, reassert MIT mode (raw CAN
  frame, id `0x151`, payload `010400AD00000000`, on that arm's CAN interface), ramp the
  gains to motion gains in a few steps while re-holding the measured pose, reassert MIT
  mode again. Expect the arm to sag slightly while the server is down.
- **One setpoint is not a motion.** `set_*_joint_target(q, preview_time=t)` says "be at
  `q` in `t` seconds"; sending it once and waiting produces a fraction of the travel.
  Stream the trajectory at ~30 Hz along a minimum-jerk profile and watch tracking error
  and torque every step.
- **The arm undershoots, by an amount that depends on direction and pose** — measured
  between 30% and 100% of the commanded displacement. Do not trust one command to land:
  after a streamed move, measure the residual and command it again, two or three passes,
  until it is inside the tolerance the *task* needs. Millimetre-level endpoint accuracy
  is not available; judge the last few millimetres from the wrist camera instead.
- **Take torque limits from the arm, not from a baseline.** Static gravity load changes
  with pose, so a threshold derived from torques measured in one pose fires immediately
  in another. Use the arm's own limits with a three-strike rule, and treat a trip as a
  stop, never as a number to raise.
- **Open the jaws fully before a descent and confirm the measured opening.** A grasp
  commanded from a partly open jaw closes on nothing, and the failure looks like a
  positioning error.
- **Check the measured joint angles against the model's limits before planning.** A
  joint can sit outside the MJCF range after manual handling, and IK will happily plan
  from there.
- **The URDF must not carry the arm's mounting rotation** — the mount belongs to the
  MJCF, and the URDF is what the controller uses for gravity compensation. If the
  descriptions are missing, restore the real ones; a hand-written stand-in with the
  mount folded in makes every pose and every gravity term wrong, and the arm drifts
  sideways while every log still looks self-consistent.

## Where the time actually goes

Measured on a real task: each streamed move takes about three seconds, while a phase of
the task takes one to four minutes. Almost all of it is the agent looking, measuring and
deciding between moves. If you are trying to make a task faster, time the deliberation
separately from the actuation — the actuation is rarely the bottleneck.

## Operating rules

- Lab work is not in a hurry. Stop at the point that matters — where the
  gripper is about to touch the object — show the operator the camera images,
  adjust, and resume only after the pose looks right.
- Do not impose a safety boundary of your own on the motion; the operator
  decides whether one is needed.
- Find the object yourself first: locate it in the current head-camera image
  from the task description and show the operator what you found. Ask the
  operator for a single tap on the head-camera image only when you cannot find
  it. Either way, locate the object from the current image; do not guess from
  a stale one.
- The object will be moved. Whatever you build must adapt to a placement it
  has not seen — for example the object placed at either end of the reachable area — by
  measuring where the object is now and computing how much to move, not by
  replaying fixed coordinates.
- When a task is repeated later, the object will be in a different place.
  Reproduce the full procedure from the current observation, not from the
  previous run's numbers.
- Lighting may differ from the demonstration data. Dark regions that look
  like gripper jaws may be shadows; confirm from shape before treating them as
  objects.
- Show the operator what you detected (markers, the selected object) before
  acting on it, and let them confirm or correct it.
- Keep a hand on the stop. No collision reaction exists; every safety layer is
  preventive and geometric.
- Watching a recorded demonstration of the task can help; it shows where the
  arm approaches, where it makes contact, and how the object is held.
- Carry the previous task's system over unchanged to a new task. Change only
  how the target is specified; keep the motion, safety, and confirmation
  pipeline as it is.
- Do not take a vision model's answer at face value. Check it yourself in the
  image before acting on it.
- Prefer measurement to estimation. A marker on the object, or geometry
  measured directly from depth, is more precise than a vision model's guess
  and can be tracked in real time.
