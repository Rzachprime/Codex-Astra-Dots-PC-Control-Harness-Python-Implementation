# Windows Python control: runnable paste kit

The setup paste block writes the reviewed stdlib Python harness, fixture and original tests into a new folder. It performs no desktop action, downloads nothing, changes no settings, and refuses to reuse a destination. The four original Python files are copied unchanged. `selftest.py` and `run_control.py` are small new packaging helpers; they do not replace the input backend.

Use Windows Python 3 with no additional packages for the backend. The optional fixture also needs tkinter/Tk. The prior functional checks used 64-bit Python 3.12. Keep this kit outside generated runtime/plugin caches. It is a fallback backend, not a repair for missing official native/MCP tools.

## Setup

Open `setup-windows-control.ps1`, review it, and paste the complete contents into an authorized PowerShell session in a writable working directory. It creates a new `windows-python-control-*` directory and prints its location. It does not launch the harness or fixture. If an execution policy blocks running the saved `.ps1` as a file, do not change policy or use a bypass switch.

The separately supplied folder already contains the same runnable files; no setup script is required when those files have been copied together.

## Permission to paste into the agent

> I authorize a bounded Windows desktop diagnostic using this Python harness: status and window discovery, launching one disposable test fixture, inspecting screenshots, and testing pointer movement, one button click, Unicode text, Ctrl+A, one wheel notch, and normal closure only in that fixture. Use the host's supported execution approval process, including a scoped require_escalated request if needed and permitted. Preserve and report denials; stop if review rejects an action. Do not control other applications, send messages, alter settings/security, use another identity, copy host metadata, or bypass approvals. Inspect after each action and never blindly replay uncertain input.

This text supplies task scope; it does not override host policy or confer Windows administrator rights. It does not authorize terminal/assistant UI messaging or arbitrary application control.

## Self-test: no desktop query or input

In the kit folder, set the real path to your Windows Python interpreter:

```powershell
$pythonControl = 'C:\PATH\TO\python.exe'
& $pythonControl -X utf8 .\selftest.py
```

Expected: 17 cases considered, 16 pass, one skip. The skipped original `test_status_protocol` reads the desktop; the self-test deliberately blocks Desktop construction, WinDLL loading and child launches. It parses all Python files and runs the original ABI, Unicode, PNG, receipt and refusal checks. This does not constitute a new GUI acceptance test.

## Read-only status and discovery, when authorized

```powershell
& $pythonControl -X utf8 .\run_control.py status
& $pythonControl -X utf8 .\run_control.py windows
```

Run separately and inspect each result. `run_control.py` bounds the unchanged harness command to eight seconds and saves a receipt. It performs no retries or elevation. Status/window outputs contain local identifiers: keep them private. An accepted status call is not proof of input acceptance.

If a call fails, preserve the failing API, error and execution context. Do not continue into input. The previously observed default status failure was GetCursorPos / WinError 5. After explicit user authorization, normal review accepted a tool-level `require_escalated` request; the same Python, harness, status arguments and working directory passed with no environment overrides. The Windows administrator-token state and exact access-check cause were not measured.

## Exact host execution-call distinction

These are examples for a host that actually exposes this `tools.exec_command` schema. Replace the generic paths. They are separate requests, not an automatic retry script. `use_default` is also the documented default when the field is omitted:

```javascript
const result = await tools.exec_command({
  cmd: "& 'C:/PATH/TO/python.exe' -X utf8 'C:/PATH/TO/kit/run_control.py' status",
  workdir: "C:/PATH/TO/authorized-workspace",
  sandbox_permissions: "use_default"
});
```

Only when current user scope and host policy permit a supported approval request:

```javascript
const result = await tools.exec_command({
  cmd: "& 'C:/PATH/TO/python.exe' -X utf8 'C:/PATH/TO/kit/run_control.py' status",
  workdir: "C:/PATH/TO/authorized-workspace",
  sandbox_permissions: "require_escalated",
  justification: "Run the user-authorized bounded fixture diagnostic."
});
```

`require_escalated` is a host tool argument, not a Python flag, PowerShell switch or Windows administrator-token guarantee. The host may reject it. Keep the real review result; stop if rejected. Do not disable sandboxing/UAC, alter ACLs, use RunAs/another identity, copy credentials or host request metadata, or remove enforcement flags. No custom approval rules are needed or included.

## Start only the disposable fixture

After authorization and successful access checks, use a separate PowerShell session in the kit directory. This command intentionally opens one visible fixture and runs until it closes:

```powershell
$pythonControl = 'C:\PATH\TO\python.exe'
& $pythonControl -X utf8 .\test_window.py --out .\fixture-run-001
```

Use a new fixture directory. The fixture writes its PID/HWND and accepted event state to `fixture.json`, and closes after ten minutes or normal window closure. Discover its current window and match ownership; never use a historical PID/HWND. The kit does not automatically launch it or control any real application.

## One action at a time

Set values from current discovery and the inspected screenshot, never from an example. The following command templates are separate stages:

```powershell
$targetHwnd = [long](Read-Host 'Current owned fixture HWND')
$targetProcessId = [int](Read-Host 'Current owned fixture PID')
& $pythonControl -X utf8 .\run_control.py observe --hwnd $targetHwnd --pid $targetProcessId --out .\evidence\before
```

Open and inspect `evidence/before.png` before deciding any input. Then, for one currently authorized action:

```powershell
$pointX = [int](Read-Host 'Verified screenshot-relative x')
$pointY = [int](Read-Host 'Verified screenshot-relative y')
& $pythonControl -X utf8 .\run_control.py act --observation .\evidence\before.json --kind click --x $pointX --y $pointY --out .\evidence\after-click
```

Inspect `after-click.png`. Set `$observation` to the latest inspected JSON, `$nextOut` to a new output prefix, and `$textFile` to an exact UTF-8 text file without a BOM or trailing newline. Run only one of these templates at a time, refreshing those variables after inspection:

```powershell
& $pythonControl -X utf8 .\run_control.py act --observation $observation --kind move --x $pointX --y $pointY --out $nextOut
& $pythonControl -X utf8 .\run_control.py act --observation $observation --kind text --text-file $textFile --out $nextOut
& $pythonControl -X utf8 .\run_control.py act --observation $observation --kind key --key CTRL+A --out $nextOut
& $pythonControl -X utf8 .\run_control.py act --observation $observation --kind scroll --x $pointX --y $pointY --delta 120 --out $nextOut
```

Text uses UTF-16 code-unit key-down/up pairs, including surrogate pairs for emoji; no clipboard is involved. The range is 1–1,000 characters; control keys are separate. Supported actions also include normal `activate`, left/right/middle clicks, and named keys. Normal foreground activation can fail: do not force it. Any input may change state before an error or timeout is reported; inspect rather than replay.

The harness requires a fresh observation (at most 120 seconds), current HWND/PID, unchanged title/class/rectangle, visible target, pointer-point ownership, and foreground focus for keyboard/wheel input. It checks held buttons/modifiers and SendInput counts. These guards cannot prevent every race with human input; stop when the user types or the draft/focus changes unexpectedly.

## Verify and close only the fixture

Require inspected screenshots plus fixture state: pointer location matches, clicks=1, exact Unicode text/code points match, Ctrl+A visibly selects all text, and wheel_total=120. Use fresh observations for each stage. The previously tested Unicode included U+03A9, U+6F22 and U+1F600.

After verifying the owned fixture is foreground, normal closure is one action:

```powershell
& $pythonControl -X utf8 .\run_control.py act --observation $observation --kind key --key ALT+F4 --out $nextOut
```

Inspect `fixture.json` for `closed=true` and verify the fixture command exited normally. `post_observation_failed: Window no longer exists` after closing can be expected; never repeat the close blindly. Do not kill user processes. For programmatic launching, retain the actual child handle and clean up only that child; a timeout cannot undo inserted events.

## Limits and evidence

Capture is a visible desktop crop using BitBlt/GetDIBits; overlapping apps, protected surfaces and accelerated rendering may prevent useful captures. Stop at a wrong/black/obscured image. Negative virtual origins are handled. Mixed-DPI layouts need separate validation: requesting PMv2 and using GetSystemMetrics is not universal DPI certification. The existing DPI-awareness call's return is not validated. There is no OCR, accessibility tree, browser DOM, drag, app launcher, background control or global emergency hotkey.

Prior bounded acceptance covered the fixture and two separately authorized terminal messages. Those historical results do not authorize new messaging and do not restore native registration, a CLI queue API or an automatic Slack listener. This packaging run performs no GUI acceptance test.

API references: [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput), [GetCursorPos](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getcursorpos), [GetDIBits](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getdibits), [GetSystemMetrics](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetrics).

The harness needs no service, plugin or persistent worker. Stop invoking it to stop control. Public source excludes private screenshots, evidence archives, identifiers, paths and custom rules; newly generated local receipts can contain private information and must be reviewed before sharing.
