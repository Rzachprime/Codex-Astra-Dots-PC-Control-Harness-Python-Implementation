"""Disposable Tk window; writes only its own state and exits after ten minutes."""
import argparse
import json
import os
from pathlib import Path
import time
import tkinter as tk
from win_control import Desktop

p = argparse.ArgumentParser()
p.add_argument("--out", required=True)
args = p.parse_args()
folder = Path(args.out).resolve()
folder.mkdir(parents=True, exist_ok=True)
if (folder / "fixture.json").exists():
    raise SystemExit("Choose a new fixture directory")
d = Desktop()
root = tk.Tk()
root.title(f"Python Control Test - {os.getpid()}")
root.geometry("600x330+80+100")
root.configure(bg="#eff6ff")
state = {"pid": os.getpid(), "clicks": 0, "wheel_total": 0, "motions": 0, "text": "", "closed": False}
tk.Label(root, text="Disposable Python control test", font=("Segoe UI", 17), bg="#eff6ff").pack(pady=12)
tk.Label(root, text="Only this window is used for the diagnostic.", bg="#eff6ff").pack()
text = tk.StringVar()
entry = tk.Entry(root, textvariable=text, font=("Segoe UI", 16), width=34)
entry.pack(pady=18)
counter = tk.StringVar(value="Clicks: 0 | Wheel: 0")


def save():
    state["text"] = text.get()
    state["updated_epoch"] = time.time()
    temp = folder / "fixture.tmp"
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(folder / "fixture.json")


def update():
    counter.set(f"Clicks: {state['clicks']} | Wheel: {state['wheel_total']}")
    save()


def click():
    state["clicks"] += 1
    update()


button = tk.Button(root, text="Test click", command=click, font=("Segoe UI", 14), width=20)
button.pack(pady=6)
tk.Label(root, textvariable=counter, font=("Segoe UI", 12), bg="#eff6ff").pack(pady=8)


def motion(event):
    state["motions"] += 1
    state["last_pointer"] = [event.x_root, event.y_root]
    save()


def wheel(event):
    state["wheel_total"] += event.delta
    update()


def close():
    state["closed"] = True
    save()
    root.destroy()


root.bind("<Motion>", motion)
root.bind("<MouseWheel>", wheel)
text.trace_add("write", lambda *_: save())
root.protocol("WM_DELETE_WINDOW", close)
root.update()
hwnd = int(d.u.GetAncestor(entry.winfo_id(), 2))
state["hwnd"] = hwnd
state["window"] = d.window(hwnd)
state["entry_screen"] = [entry.winfo_rootx() + entry.winfo_width() // 2, entry.winfo_rooty() + entry.winfo_height() // 2]
state["button_screen"] = [button.winfo_rootx() + button.winfo_width() // 2, button.winfo_rooty() + button.winfo_height() // 2]
save()
root.after(600_000, close)
root.mainloop()
