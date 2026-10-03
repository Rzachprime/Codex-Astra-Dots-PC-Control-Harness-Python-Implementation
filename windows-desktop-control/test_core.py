"""Protocol/ABI tests with no desktop input."""
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
import win_control as w


class CoreTests(unittest.TestCase):
    def test_abi(self):
        self.assertEqual(C.sizeof(w.INPUT), 40 if C.sizeof(C.c_void_p) == 8 else 28)
        self.assertEqual(C.sizeof(w.BITMAPINFOHEADER), 40)

    def test_unicode_events(self):
        events = w.text_events("AΩ漢😀")
        self.assertEqual([e.ki.wScan for e in events[::2]], [65, 937, 28450, 0xD83D, 0xDE00])
        self.assertTrue(all(e.type == 1 and e.ki.wVk == 0 for e in events))
        self.assertEqual([e.ki.dwFlags for e in events], [4, 6] * 5)

    def test_reject_control_text_and_bad_keys(self):
        for text in ("", "x\ny", "\0", "x" * 1001):
            with self.assertRaises(w.ControlError):
                w.text_events(text)
        for key in ("CTRL+CTRL+A", "BOGUS"):
            with self.assertRaises(w.ControlError):
                w.key_events(key)

    def test_chord_releases_reverse_order(self):
        events = w.key_events("CTRL+RIGHT")
        self.assertEqual([(e.ki.wVk, e.ki.dwFlags) for e in events], [(17, 0), (39, 1), (39, 3), (17, 2)])

    def test_png_colors_rows_and_crc(self):
        png = w.png_bgra(2, 2, bytes([0, 0, 255, 0, 0, 255, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0]))
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        offset, chunks = 8, {}
        while offset < len(png):
            size = struct.unpack(">I", png[offset:offset+4])[0]
            kind, data = png[offset+4:offset+8], png[offset+8:offset+8+size]
            self.assertEqual(struct.unpack(">I", png[offset+8+size:offset+12+size])[0], zlib.crc32(kind+data))
            chunks[kind] = data
            offset += 12 + size
        self.assertEqual(zlib.decompress(chunks[b"IDAT"]), b"\0\xff\0\0\0\xff\0\0\0\0\xff\xff\xff\xff")

    def test_unicode_receipt_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unicode.json"
            w.write_json(path, {"text": "Ω漢😀"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"text": "Ω漢😀"})
            with self.assertRaises(FileExistsError):
                w.write_json(path, {})

    def test_status_protocol(self):
        r = subprocess.run([sys.executable, str(Path(w.__file__)), "status"], capture_output=True, encoding="utf-8", timeout=8)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        result = json.loads(r.stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["result"]["input_permission_verified"])


if __name__ == "__main__":
    unittest.main()
