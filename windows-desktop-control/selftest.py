"""Run existing pure/guard tests without opening or querying the desktop."""
import ast
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def main():
    if sys.platform != "win32":
        raise SystemExit("Use Windows Python: ctypes Windows ABI sizes differ elsewhere.")
    root = Path(__file__).resolve().parent
    sources = sorted(root.glob("*.py"))
    for source in sources:
        ast.parse(source.read_text(encoding="utf-8"), filename=source.name)
    import test_core
    import test_guards
    import win_control
    test_core.CoreTests.test_status_protocol = unittest.skip(
        "Desktop-query integration test intentionally excluded from this no-desktop run."
    )(test_core.CoreTests.test_status_protocol)
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromModule(test_core),
        unittest.defaultTestLoader.loadTestsFromModule(test_guards),
    ])
    blocked = AssertionError("No desktop construction or child-process launch in selftest")
    with patch.object(win_control.Desktop, "__init__", side_effect=blocked), \
         patch("ctypes.WinDLL", side_effect=blocked), \
         patch("subprocess.Popen", side_effect=blocked):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("Parsed %d Python files; no desktop API session or input was started." % len(sources))
    return 0 if result.wasSuccessful() and result.testsRun == 17 and len(result.skipped) == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
