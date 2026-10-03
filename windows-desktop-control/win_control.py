"""Explicit, one-action Windows desktop CLI. Python stdlib; no server or elevation."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import datetime as dt
import getpass
import json
import os
from pathlib import Path
import struct
import sys
import time
import zlib

VERSION = "0.1.0"


class ControlError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code, self.details = code, details


def require(condition, code, message, **details):
    if not condition:
        raise ControlError(code, message, **details)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental replacement of existing evidence.
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


class MOUSEINPUT(C.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", C.c_size_t)]


class KEYBDINPUT(C.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", C.c_size_t)]


class HARDWAREINPUT(C.Structure):
    _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]


class INPUTUNION(C.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(C.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", W.DWORD), ("value", INPUTUNION)]


class BITMAPINFOHEADER(C.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG),
                ("biPlanes", W.WORD), ("biBitCount", W.WORD), ("biCompression", W.DWORD),
                ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG),
                ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD),
                ("biClrImportant", W.DWORD)]


def png_bgra(width, height, pixels):
    """Encode a top-down 32-bit GDI bitmap as RGB PNG (GDI alpha is undefined)."""
    require(len(pixels) == width * height * 4, "invalid_bitmap", "Wrong pixel buffer length")
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = pixels[2::4], pixels[1::4], pixels[0::4]
    raw = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


KEYS = {"BACKSPACE": 8, "TAB": 9, "ENTER": 13, "RETURN": 13, "SHIFT": 16,
        "CTRL": 17, "ALT": 18, "ESC": 27, "SPACE": 32, "PAGEUP": 33,
        "PAGEDOWN": 34, "END": 35, "HOME": 36, "LEFT": 37, "UP": 38,
        "RIGHT": 39, "DOWN": 40, "INSERT": 45, "DELETE": 46, "WIN": 91,
        "NUMPAD_ADD": 107, "NUMPAD_SUBTRACT": 109, "NUMPAD_MULTIPLY": 106,
        "NUMPAD_DIVIDE": 111, **{str(i): 48 + i for i in range(10)},
        **{chr(i): i for i in range(65, 91)}, **{f"F{i}": 111 + i for i in range(1, 25)}}
EXTENDED = {33, 34, 35, 36, 37, 38, 39, 40, 45, 46, 91, 111}


def keyboard_event(vk=0, scan=0, flags=0):
    return INPUT(type=1, ki=KEYBDINPUT(vk, scan, flags, 0, 0))


def key_events(key):
    names = key.upper().split("+")
    require(1 <= len(names) <= 4 and len(names) == len(set(names)), "invalid_key", "Use one key or a chord such as CTRL+A")
    require(all(k in KEYS for k in names), "invalid_key", "Unknown key name", supported=sorted(KEYS))
    keys = [KEYS[k] for k in names]
    return ([keyboard_event(vk=k, flags=int(k in EXTENDED)) for k in keys]
            + [keyboard_event(vk=k, flags=2 | int(k in EXTENDED)) for k in reversed(keys)])


def text_events(text):
    require(0 < len(text) <= 1000, "invalid_text", "Text must contain 1 to 1000 characters")
    require(all(ord(ch) >= 32 for ch in text), "invalid_text", "Use key commands for control characters")
    data = text.encode("utf-16-le", errors="strict")
    events = []
    for (unit,) in struct.iter_unpack("<H", data):
        events.extend([keyboard_event(scan=unit, flags=4), keyboard_event(scan=unit, flags=6)])
    return events


class Desktop:
    def __init__(self):
        require(sys.platform == "win32", "windows_required", "Run with a Windows Python interpreter")
        self.u = C.WinDLL("user32", use_last_error=True)
        self.g = C.WinDLL("gdi32", use_last_error=True)
        self.k = C.WinDLL("kernel32", use_last_error=True)
        self.callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

        def bind(lib, name, restype, *args):
            f = getattr(lib, name)
            f.restype, f.argtypes = restype, args
            return f

        bind(self.u, "SetProcessDpiAwarenessContext", W.BOOL, W.HANDLE)(C.c_void_p(-4))
        bind(self.u, "GetForegroundWindow", W.HWND)
        bind(self.u, "GetWindowThreadProcessId", W.DWORD, W.HWND, C.POINTER(W.DWORD))
        bind(self.u, "GetWindowTextLengthW", C.c_int, W.HWND)
        bind(self.u, "GetWindowTextW", C.c_int, W.HWND, W.LPWSTR, C.c_int)
        bind(self.u, "GetClassNameW", C.c_int, W.HWND, W.LPWSTR, C.c_int)
        bind(self.u, "GetWindowRect", W.BOOL, W.HWND, C.POINTER(W.RECT))
        for name in ("IsWindow", "IsWindowVisible", "IsIconic", "SetForegroundWindow"):
            bind(self.u, name, W.BOOL, W.HWND)
        bind(self.u, "EnumWindows", W.BOOL, self.callback, W.LPARAM)
        bind(self.u, "GetCursorPos", W.BOOL, C.POINTER(W.POINT))
        bind(self.u, "GetSystemMetrics", C.c_int, C.c_int)
        bind(self.u, "GetAncestor", W.HWND, W.HWND, W.UINT)
        bind(self.u, "WindowFromPoint", W.HWND, W.POINT)
        bind(self.u, "SendInput", W.UINT, W.UINT, C.POINTER(INPUT), C.c_int)
        bind(self.u, "GetAsyncKeyState", C.c_short, C.c_int)
        bind(self.u, "OpenInputDesktop", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
        bind(self.u, "CloseDesktop", W.BOOL, W.HANDLE)
        bind(self.u, "GetThreadDesktop", W.HANDLE, W.DWORD)
        bind(self.u, "GetUserObjectInformationW", W.BOOL, W.HANDLE, C.c_int, W.LPVOID, W.DWORD, C.POINTER(W.DWORD))
        bind(self.k, "GetCurrentThreadId", W.DWORD)
        bind(self.k, "ProcessIdToSessionId", W.BOOL, W.DWORD, C.POINTER(W.DWORD))
        bind(self.u, "GetDC", W.HDC, W.HWND)
        bind(self.u, "ReleaseDC", C.c_int, W.HWND, W.HDC)
        bind(self.g, "CreateCompatibleDC", W.HDC, W.HDC)
        bind(self.g, "CreateCompatibleBitmap", W.HBITMAP, W.HDC, C.c_int, C.c_int)
        bind(self.g, "SelectObject", W.HANDLE, W.HDC, W.HANDLE)
        bind(self.g, "DeleteObject", W.BOOL, W.HANDLE)
        bind(self.g, "DeleteDC", W.BOOL, W.HDC)
        bind(self.g, "BitBlt", W.BOOL, W.HDC, C.c_int, C.c_int, C.c_int, C.c_int, W.HDC, C.c_int, C.c_int, W.DWORD)
        bind(self.g, "GetDIBits", C.c_int, W.HDC, W.HBITMAP, W.UINT, W.UINT, W.LPVOID, C.POINTER(BITMAPINFOHEADER), W.UINT)
        require(C.sizeof(INPUT) == (40 if C.sizeof(C.c_void_p) == 8 else 28), "abi_error", "Incorrect INPUT structure size")

    def check(self, result, operation):
        require(bool(result), "win32_error", operation + " failed", winerror=C.get_last_error())
        return result

    def desktop_name(self, handle):
        buf, needed = C.create_unicode_buffer(256), W.DWORD()
        self.check(self.u.GetUserObjectInformationW(handle, 2, buf, C.sizeof(buf), C.byref(needed)), "GetUserObjectInformationW")
        return buf.value

    def desktop_access(self):
        current = self.desktop_name(self.u.GetThreadDesktop(self.k.GetCurrentThreadId()))
        C.set_last_error(0)
        handle = self.u.OpenInputDesktop(0, False, 1)  # DESKTOP_READOBJECTS only.
        if not handle:
            return {"current_desktop": current, "input_desktop_accessible": False, "winerror": C.get_last_error()}
        try:
            active = self.desktop_name(handle)
            return {"current_desktop": current, "input_desktop": active,
                    "input_desktop_accessible": True, "same_desktop_name": current == active}
        finally:
            self.u.CloseDesktop(handle)

    def require_desktop(self):
        access = self.desktop_access()
        require(access.get("input_desktop_accessible") and access.get("same_desktop_name"),
                "desktop_unavailable", "Caller is not on the accessible input desktop", access=access)
        return access

    def rect(self, hwnd):
        r = W.RECT()
        self.check(self.u.GetWindowRect(hwnd, C.byref(r)), "GetWindowRect")
        return [r.left, r.top, r.right, r.bottom]

    def window(self, hwnd):
        require(self.u.IsWindow(hwnd), "window_gone", "Window no longer exists")
        pid = W.DWORD()
        self.check(self.u.GetWindowThreadProcessId(hwnd, C.byref(pid)), "GetWindowThreadProcessId")
        title = C.create_unicode_buffer(self.u.GetWindowTextLengthW(hwnd) + 1)
        self.u.GetWindowTextW(hwnd, title, len(title))
        cls = C.create_unicode_buffer(256)
        self.u.GetClassNameW(hwnd, cls, len(cls))
        return {"hwnd": int(hwnd), "pid": pid.value, "title": title.value, "class_name": cls.value,
                "rect": self.rect(hwnd), "visible": bool(self.u.IsWindowVisible(hwnd)),
                "minimized": bool(self.u.IsIconic(hwnd)), "foreground": self.u.GetForegroundWindow() == hwnd}

    def windows(self):
        result = []

        @self.callback
        def visit(hwnd, _):
            if self.u.IsWindowVisible(hwnd):
                try:
                    w = self.window(hwnd)
                    if w["title"]:
                        result.append(w)
                except ControlError:
                    pass  # A window can disappear during enumeration.
            return True

        self.check(self.u.EnumWindows(visit, 0), "EnumWindows")
        return result

    def cursor(self):
        point = W.POINT()
        self.check(self.u.GetCursorPos(C.byref(point)), "GetCursorPos")
        return [point.x, point.y]

    def screen(self):
        return [self.u.GetSystemMetrics(i) for i in (76, 77, 78, 79)]

    def status(self):
        session = W.DWORD()
        self.check(self.k.ProcessIdToSessionId(os.getpid(), C.byref(session)), "ProcessIdToSessionId")
        return {"version": VERSION, "python": sys.executable, "user": getpass.getuser(), "pid": os.getpid(),
                "session_id": session.value, "desktop": self.desktop_access(), "cursor": self.cursor(),
                "virtual_screen_xywh": self.screen(), "input_structure_bytes": C.sizeof(INPUT),
                "control_enabled": "No global toggle; each explicit action uses caller permissions",
                "input_permission_verified": False}

    def target(self, hwnd, pid):
        self.require_desktop()
        w = self.window(hwnd)
        require(w["pid"] == pid, "target_changed", "Window PID no longer matches")
        require(w["visible"] and not w["minimized"], "window_not_visible", "Target must be visible and not minimized")
        return w

    def capture(self, rect, path):
        x, y, right, bottom = rect
        width, height = right - x, bottom - y
        sx, sy, sw, sh = self.screen()
        require(0 < width <= 16000 and 0 < height <= 16000 and width * height <= 40_000_000,
                "invalid_capture", "Capture dimensions are invalid or too large")
        require(x >= sx and y >= sy and right <= sx + sw and bottom <= sy + sh,
                "offscreen", "Target rectangle must fit entirely inside the virtual screen")
        dc = mem = bitmap = old = None
        try:
            dc = self.check(self.u.GetDC(None), "GetDC")
            mem = self.check(self.g.CreateCompatibleDC(dc), "CreateCompatibleDC")
            bitmap = self.check(self.g.CreateCompatibleBitmap(dc, width, height), "CreateCompatibleBitmap")
            old = self.check(self.g.SelectObject(mem, bitmap), "SelectObject")
            self.check(self.g.BitBlt(mem, 0, 0, width, height, dc, x, y, 0x40CC0020), "BitBlt")
            self.g.SelectObject(mem, old)
            old = None
            info = BITMAPINFOHEADER(C.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
            buf = C.create_string_buffer(width * height * 4)
            lines = self.g.GetDIBits(dc, bitmap, 0, height, buf, C.byref(info), 0)
            require(lines == height, "capture_failed", "GetDIBits returned incomplete pixels", lines=lines, winerror=C.get_last_error())
            with Path(path).open("xb") as f:
                f.write(png_bgra(width, height, buf.raw))
        finally:
            if old and mem:
                self.g.SelectObject(mem, old)
            if bitmap:
                self.g.DeleteObject(bitmap)
            if mem:
                self.g.DeleteDC(mem)
            if dc:
                self.u.ReleaseDC(None, dc)

    @staticmethod
    def output_paths(out):
        base = Path(out).resolve()
        png, receipt = Path(str(base) + ".png"), Path(str(base) + ".json")
        require(not png.exists() and not receipt.exists(), "output_exists", "Choose a new output prefix")
        base.parent.mkdir(parents=True, exist_ok=True)
        return png, receipt

    def observe(self, hwnd, pid, out):
        png, receipt = self.output_paths(out)
        w = self.target(hwnd, pid)
        self.capture(w["rect"], png)
        require(self.window(hwnd) == w, "window_changed", "Window changed during capture; observe again")
        result = {"version": VERSION, "captured_at": utc(), "captured_epoch": time.time(),
                  "window": w, "cursor_screen": self.cursor(), "screenshot": str(png),
                  "observation": str(receipt), "coordinates": "physical pixels relative to screenshot top-left",
                  "capture_method": "visible desktop crop; overlapping windows can appear"}
        write_json(receipt, result)
        return result

    def send(self, events):
        data = (INPUT * len(events))(*events)
        C.set_last_error(0)
        inserted = self.u.SendInput(len(data), data, C.sizeof(INPUT))
        require(inserted == len(data), "input_rejected", "SendInput did not insert all events; do not automatically retry",
                requested=len(data), inserted=inserted, winerror=C.get_last_error(),
                note="UIPI may block input without a distinguishing error; insertion is not app acceptance")
        return inserted

    def act(self, args):
        # Validate all outputs/parameters before sending any input.
        self.output_paths(args.out)
        previous = json.loads(Path(args.observation).read_text(encoding="utf-8"))
        age = time.time() - previous["captured_epoch"]
        require(0 <= age <= 120, "stale_observation", "Observe and inspect again; observation must be within 120 seconds", age_seconds=age)
        old = previous["window"]
        w = self.target(old["hwnd"], old["pid"])
        for field in ("title", "class_name", "rect"):
            require(w[field] == old[field], "target_changed", "Target changed since observation", field=field)
        hwnd = w["hwnd"]
        if args.kind == "activate":
            self.check(self.u.SetForegroundWindow(hwnd), "SetForegroundWindow")
            time.sleep(0.15)
            require(self.u.GetForegroundWindow() == hwnd, "focus_denied", "Windows did not grant foreground focus")
            return {"action": "activate", "after": self.observe(hwnd, w["pid"], args.out)}
        # An ordinary click can select a visible background window. Keyboard and
        # wheel input require verified focus; never force focus with thread attachment.
        if args.kind not in ("move", "click"):
            require(self.u.GetForegroundWindow() == hwnd, "not_foreground", "Target is not foreground; select it and inspect")
        held = [k for k in (1, 2, 4, 16, 17, 18, 91, 92) if self.u.GetAsyncKeyState(k) & 0x8000]
        require(not held, "physical_input_active", "A mouse button or modifier is held; no input sent", virtual_keys=held)
        if args.kind in ("move", "click", "scroll"):
            require(args.x is not None and args.y is not None, "coordinates_required", "x and y are required screenshot coordinates")
            x, y, right, bottom = w["rect"]
            require(0 <= args.x < right - x and 0 <= args.y < bottom - y, "out_of_bounds", "Coordinates are outside target")
            px, py = x + args.x, y + args.y
            hit = self.u.WindowFromPoint(W.POINT(px, py))
            require(self.u.GetAncestor(hit, 2) == hwnd, "target_occluded", "Another window covers the requested point")
            sx, sy, sw, sh = self.screen()
            move = INPUT(type=0, mi=MOUSEINPUT(round((px-sx)*65535/(sw-1)), round((py-sy)*65535/(sh-1)), 0, 0xC001, 0, 0))
            events = [move]
            if args.kind == "click":
                down, up = {"left": (2, 4), "right": (8, 16), "middle": (32, 64)}[args.button]
                events += [INPUT(type=0, mi=MOUSEINPUT(0, 0, 0, flag, 0, 0)) for flag in (down, up)]
            if args.kind == "scroll":
                require(args.delta is not None and args.delta != 0 and abs(args.delta) <= 1200,
                        "invalid_scroll", "delta must be nonzero and at most 1200; one notch is 120")
                events.append(INPUT(type=0, mi=MOUSEINPUT(0, 0, args.delta & 0xFFFFFFFF, 0x0800, 0, 0)))
        elif args.kind == "key":
            require(bool(args.key), "key_required", "--key is required")
            events = key_events(args.key)
        else:
            require(bool(args.text_file), "text_required", "--text-file UTF-8 path is required")
            events = text_events(Path(args.text_file).read_text(encoding="utf-8"))
        if args.kind not in ("move", "click"):
            require(self.u.GetForegroundWindow() == hwnd, "focus_changed", "Foreground changed before input")
        count = self.send(events)
        time.sleep(0.18)
        try:
            after = self.observe(hwnd, w["pid"], args.out)
        except (ControlError, OSError) as exc:
            # An action might legitimately close/move its window. Never imply it did not execute.
            return {"action": args.kind, "events_inserted": count, "application_acceptance": "requires verification",
                    "post_observation_failed": str(exc), "do_not_repeat_automatically": True}
        return {"action": args.kind, "events_inserted": count,
                "application_acceptance": "inspect after screenshot", "after": after}


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict")
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("windows")
    obs = sub.add_parser("observe")
    obs.add_argument("--hwnd", type=int, required=True)
    obs.add_argument("--pid", type=int, required=True)
    obs.add_argument("--out", required=True)
    act = sub.add_parser("act")
    act.add_argument("--observation", required=True)
    act.add_argument("--kind", choices=("activate", "move", "click", "scroll", "key", "text"), required=True)
    act.add_argument("--out", required=True)
    act.add_argument("--x", type=int)
    act.add_argument("--y", type=int)
    act.add_argument("--button", choices=("left", "right", "middle"), default="left")
    act.add_argument("--delta", type=int)
    act.add_argument("--key")
    act.add_argument("--text-file")
    args = p.parse_args(argv)
    try:
        desktop = Desktop()
        if args.command == "status":
            result = desktop.status()
        elif args.command == "windows":
            result = {"windows": desktop.windows()}
        elif args.command == "observe":
            result = desktop.observe(args.hwnd, args.pid, args.out)
        else:
            result = desktop.act(args)
        print(json.dumps({"ok": True, "time": utc(), "result": result}, ensure_ascii=False))
        return 0
    except (ControlError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok": False, "time": utc(), "error": {"code": getattr(exc, "code", type(exc).__name__),
              "message": str(exc), "details": getattr(exc, "details", {})}}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
