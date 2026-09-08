#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from robot.arm.arm import JointState, PiperNativeGripper


class FakePiper:
    def __init__(self):
        self.state = JointState(6)
        self.state.pos = np.arange(6, dtype=float)
        self.commands = []

    def get_joint_state(self):
        return self.state

    def get_timestamp(self):
        return 10.0

    def set_joint_cmd(self, cmd):
        self.commands.append(cmd)
        self.state.gripper_pos = cmd.gripper_pos


class FakeFeedback:
    def __init__(self):
        self.commands = []

    def GripperCtrl(self, **kwargs):
        self.commands.append(kwargs)

    def DisconnectPort(self):
        pass


class FakeCanMessage:
    data = bytes.fromhex("000088B804D24000")


class FakeCanBus:
    def __init__(self):
        self.first = True

    def recv(self, timeout):
        if self.first:
            self.first = False
            return FakeCanMessage()
        return None

    def shutdown(self):
        pass


class PiperNativeGripperTest(unittest.TestCase):
    def setUp(self):
        self.piper = FakePiper()
        self.feedback = FakeFeedback()
        self.gripper = PiperNativeGripper(
            self.piper,
            "unused",
            command_interface=self.feedback,
            feedback_bus=FakeCanBus(),
        )

    def test_ratio_command_and_feedback(self):
        self.gripper.set_open_ratio(0.5)
        cmd = self.feedback.commands[-1]
        self.assertEqual(cmd["gripper_angle"], 35000)
        self.assertEqual(cmd["gripper_effort"], 1000)
        self.assertAlmostEqual(self.gripper.get_open_ratio(), 0.5)

    def test_ratio_is_clipped(self):
        self.gripper.set_open_ratio(2.0)
        self.assertEqual(self.feedback.commands[-1]["gripper_angle"], 70000)

    def test_effort_is_si(self):
        self.assertAlmostEqual(self.gripper.get_effort(), 1.234)

    def test_streamed_arm_command_keeps_gripper_target(self):
        self.gripper.set_open_ratio(0.25)
        cmd = JointState(6)
        self.gripper.apply_to_joint_command(cmd)
        self.assertAlmostEqual(cmd.gripper_pos, 0.0)


if __name__ == "__main__":
    unittest.main()
