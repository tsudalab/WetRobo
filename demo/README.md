# Demonstrations

Fifteen teleoperated demonstrations per task, recorded on the kit's own equipment
with a Meta Quest interface.

```
demo/
  petri_lid/        lifting the Petri dish lid
  bottle_cap/       lifting the bottle cap
  incubator_door/   opening the incubator door
```

Each episode is one `*.hdf5` file plus a head-camera preview `*_head.mp4`.

The HDF5 holds the recorded end-effector trajectory used by the replay path
(`replay_demo.py`, `rollout/controller.py`):

| dataset | shape | meaning |
|---|---|---|
| `left_ee_pos`, `right_ee_pos` | (T, 3) | end-effector position, metres |
| `left_ee_quat`, `right_ee_quat` | (T, 4) | end-effector orientation, quaternion wxyz |
| `left_gripper`, `right_gripper` | (T,) | gripper opening, 1 = open |
| `timestamps`, `rgb_frame_timestamps` | (T,) | seconds |

Depth frames from the original recordings are not included here; the previews
are downscaled to 360p. Replay uses the trajectory datasets only.

```bash
python replay_demo.py demo/bottle_cap/<episode>.hdf5 \
    --safety-config src/configs/safety.json --rate 30
```
