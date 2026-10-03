"""No-input regression tests for refusing stale or mismatched UI targets."""
import argparse
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock
import win_control as w


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.window = {"hwnd": 11, "pid": 22, "title": "Owned fixture", "class_name": "TkTopLevel",
                       "rect": [100, 100, 600, 400], "visible": True, "minimized": False, "foreground": True}
        self.obs = {"window": self.window.copy(), "captured_epoch": time.time()}
        self.d = w.Desktop.__new__(w.Desktop)
        self.d.u = Mock()
        self.d.u.GetForegroundWindow.return_value = 11
        self.d.u.GetAsyncKeyState.return_value = 0
        self.d.target = Mock(return_value=self.window)
        self.d.send = Mock(side_effect=AssertionError("A refused action must not call SendInput"))
        self.args = argparse.Namespace(out=str(self.base / "after"), observation=str(self.base / "before.json"),
                 kind="key", key="A", x=None, y=None, button="left", delta=None, text_file=None)

    def refuse(self, code):
        Path(self.args.observation).write_text(json.dumps(self.obs), encoding="utf-8")
        with self.assertRaises(w.ControlError) as caught:
            self.d.act(self.args)
        self.assertEqual(caught.exception.code, code)
        self.d.send.assert_not_called()

    def test_stale_receipt(self):
        self.obs["captured_epoch"] -= 121
        self.refuse("stale_observation")

    def test_future_receipt(self):
        self.obs["captured_epoch"] += 30
        self.refuse("stale_observation")

    def test_window_geometry_changed(self):
        self.window["rect"] = [101, 100, 601, 400]
        self.refuse("target_changed")

    def test_title_changed(self):
        self.window["title"] = "Another document"
        self.refuse("target_changed")

    def test_keyboard_focus_required(self):
        self.d.u.GetForegroundWindow.return_value = 99
        self.refuse("not_foreground")

    def test_held_modifier(self):
        self.d.u.GetAsyncKeyState.side_effect = lambda vk: 0x8000 if vk == 17 else 0
        self.refuse("physical_input_active")

    def test_occluded_click(self):
        self.args.kind, self.args.x, self.args.y = "click", 100, 100
        self.d.u.WindowFromPoint.return_value = 99
        self.d.u.GetAncestor.return_value = 99
        self.refuse("target_occluded")

    def test_outside_window(self):
        self.args.kind, self.args.x, self.args.y = "move", 500, 10
        self.refuse("out_of_bounds")

    def test_no_overwrite_before_input(self):
        Path(self.args.out + ".png").write_bytes(b"prior evidence")
        self.refuse("output_exists")

    def test_target_pid_changed(self):
        self.d.require_desktop = Mock()
        self.d.window = Mock(return_value=self.window)
        with self.assertRaises(w.ControlError) as caught:
            w.Desktop.target(self.d, 11, 999)
        self.assertEqual(caught.exception.code, "target_changed")


if __name__ == "__main__":
    unittest.main()
