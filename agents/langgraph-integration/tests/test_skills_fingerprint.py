"""Skill fingerprint tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from skills.fingerprint import skill_fingerprint


class TestSkillFingerprint(unittest.TestCase):
    def test_single_issue_differs_from_multi(self) -> None:
        a = skill_fingerprint(["CrashLoop"], ["restart_pod"])
        b = skill_fingerprint(["CrashLoop", "OOM"], ["restart_pod"])
        self.assertNotEqual(a, b)

    def test_issue_order_irrelevant(self) -> None:
        a = skill_fingerprint(["CrashLoop", "OOM"], ["restart_pod"])
        b = skill_fingerprint(["OOM", "CrashLoop"], ["restart_pod"])
        self.assertEqual(a, b)

    def test_action_order_irrelevant(self) -> None:
        a = skill_fingerprint(["CrashLoop"], ["restart_pod", "scale_up"])
        b = skill_fingerprint(["CrashLoop"], ["scale_up", "restart_pod"])
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
