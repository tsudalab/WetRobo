# WetRobo

A reproducible environment for policy self-improvement towards automated
biological research.

The environment is four components:

| component | where |
|---|---|
| Skill | `SKILLS.md` — operating rules and the starting workflow for the agent |
| Code exemplar | branch `wetrobo-exemplar` — the programs a coding agent evolved in this environment for three trials (Petri dish lid, culture-media bottle cap, incubator door) |
| Arm | one AgileX Piper arm with a string-driven Dynamixel gripper, a fixed head RGB-D camera (iPhone via Record3D), and a wrist RGB camera |
| Incubator | a laboratory incubator in front of the arm |

The task is not part of the environment; the operator gives it at run time.

## Branches

- `main` — **wetrobo**, the base control stack the agent starts from: one-demo
  replay, live bias, safety layer, camera streaming, and the arm RPC server.
  This is the tree the trials began with.
- `wetrobo-exemplar` — `main` plus the final form of the programs the agent
  produced for the three trials, at the paths where they run. Only files that
  the final programs import or reference are included; intermediate attempts
  are not.

## Provenance

Both branches are extracted from the working repository's git history; no file
was edited by hand except `SKILLS.md`, `README.md`, and `.gitignore`.

- `main`: the tree at commit `d8a618d` (2026-07-21, "Add safe one-demo replay
  workflow"), the state the first trial started from, restricted to the control
  stack and its imports. Neural-policy inference and training scripts, unused
  simulation assets, and scratch files are omitted.
- `wetrobo-exemplar`: the tree at commit `05ab41e` (2026-08-12, tip of `main`
  in the trial window), plus the files that existed only in the working tree at
  the last lid trial (2026-08-14; modification time on or before that day).
  The set is the import closure of the three trials' entry points. The incubator
  door files are identical to commit `283b913` (the revision measured in the
  paper) except for one later commit, `676981b`, which adds cross-laboratory
  appliance-frame registration.

## Dependencies

Declared in `pyproject.toml`. In addition, the code imports:

- `piperlib` — AgileX Piper CAN driver used by `robot/arm/arm.py`
- `record3d` — iPhone RGB-D streaming used by `rollout/camera.py`
- `scipy`, `opencv-python`, `h5py`

`robot/camera_map.json`, `src/configs/safety.json`, and the MJCF under
`robot/cone-e-description/` describe one installation; measure your own before
commanding motion.

## Not to be confused with

A simulation package also named `wetrobo/` exists inside the working repository
this was extracted from. It is unrelated to this environment.
