"""Verify the configured physical-right home with the production Piper FK."""

from __future__ import annotations

import json
from pathlib import Path

from robot.arm.home import physical_home_q
from rollout.gripper_level import JawLevelReference, assess_jaw_level
from rollout.teleop_trajectory_stream import ProductionRightFK


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "robot/cone-e-description/robot-welded-base-and-lift.mjcf"


def main() -> int:
    home_q = physical_home_q("right")
    fk = ProductionRightFK(MODEL)
    assessment = assess_jaw_level(
        fk.pose(home_q).parameters(), JawLevelReference()
    )
    print(
        json.dumps(
            {
                "model": str(MODEL.relative_to(ROOT)),
                "physical_right_home_q": home_q.tolist(),
                "assessment": assessment.to_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if assessment.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
