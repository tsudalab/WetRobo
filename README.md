# WetRobo

A reproducible environment for policy self-improvement towards automated
biological research.

The environment is four components:

| component | where |
|---|---|
| Skill | `AGENTS.md` — operating rules and the starting workflow for the agent |
| Code exemplar | branch `wetrobo+petri+cap+door` — the repository after a coding agent evolved it in this environment through three trials (Petri dish lid, culture-media bottle cap, incubator door) |
| Arm | one AgileX Piper arm with a string-driven Dynamixel gripper, a fixed head RGB-D camera (iPhone via Record3D), and a wrist RGB camera |
| Incubator | a laboratory incubator in front of the arm |

The task is not part of the environment; the operator gives it at run time.

## Branches

- `main` — **wetrobo**, the base control stack the agent starts from: one-demo
  replay, live bias, safety layer, camera streaming, and the arm RPC server.
  This is the tree the trials began with.
- `wetrobo+petri`, `wetrobo+petri+cap`, `wetrobo+petri+cap+door` — byte-exact
  snapshots of the working repository at the end of each trial, in the order
  the trials ran (Petri dish lid, then bottle cap, then incubator door). They
  form a chain, so `git diff` between adjacent branches shows what one trial
  added. `wetrobo+petri+cap+door` is the code exemplar: the final form of the
  three task programs at the paths where they run.

## Provenance

All branches are extracted from the working repository's git history; no file
was edited by hand except `AGENTS.md`, `README.md`, and `.gitignore` on `main`.
The snapshot branches add `AGENTS.md` and a note at the end of `README.md`;
every other file is identical to the source commit.

- `main`: the tree at commit `d8a618d` (2026-07-21, "Add safe one-demo replay
  workflow"), the state the first trial started from, restricted to the control
  stack and its imports. Neural-policy inference and training scripts, unused
  simulation assets, and scratch files are omitted.
- `wetrobo+petri`: the tree at commit `3a1706b` (2026-08-06 11:03 JST, "Add
  checkpointed thin-object grasp orchestration"), the last commit before the
  bottle cap trial began.
- `wetrobo+petri+cap`: the tree at commit `1f07761` (2026-08-06 18:37 JST,
  "Promote verified cylindrical cap transfer").
- `wetrobo+petri+cap+door`: the tree at commit `676981b` (2026-08-08 23:45 JST,
  "Add cross-lab appliance frame retargeting"). The incubator door files are
  those of commit `283b913` (the revision measured in the paper) plus this one
  later commit, which adds cross-laboratory appliance-frame registration.

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
