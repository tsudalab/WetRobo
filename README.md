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
| Demonstrations | `demo/` — fifteen teleoperated demonstrations per task |

The task is not part of the environment; the operator gives it at run time.

## Demonstrations

`demo/` holds fifteen teleoperated demonstrations per task, recorded on this
equipment with a Meta Quest interface:

```
demo/petri_lid/        lifting the Petri dish lid
demo/bottle_cap/       lifting the bottle cap
demo/incubator_door/   opening the incubator door
```

Each episode is one `*.hdf5` trajectory plus a head-camera preview
`*_head.mp4`. See `demo/README.md` for the datasets and a replay command.

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

## Dependencies

Declared in `pyproject.toml`. In addition, the code imports:

- `piperlib` — AgileX Piper CAN driver used by `robot/arm/arm.py`
- `record3d` — iPhone RGB-D streaming used by `rollout/camera.py`
- `scipy`, `opencv-python`, `h5py`

`robot/camera_map.json`, `src/configs/safety.json`, and the MJCF under
`robot/cone-e-description/` describe one installation; measure your own before
commanding motion.

