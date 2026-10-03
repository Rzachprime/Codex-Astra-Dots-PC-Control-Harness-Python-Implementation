"""Bound one unchanged harness command; preserve a local receipt, never retry."""
import datetime
import json
from pathlib import Path
import subprocess
import sys
import uuid


def main():
    arguments = sys.argv[1:]
    if not arguments or arguments[0] not in ("status", "windows", "observe", "act"):
        raise SystemExit("Usage: python run_control.py status|windows|observe|act [options]")
    root = Path(__file__).resolve().parent
    receipts = root / "command-receipts"
    receipts.mkdir(exist_ok=True)
    receipt = receipts / (uuid.uuid4().hex + ".json")
    command = [sys.executable, "-X", "utf8", str(root / "win_control.py"), *arguments]
    record = {"started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "command": command, "timeout_seconds": 8, "environment_overrides": False}
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=8,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        record.update(exit_code=result.returncode, stdout=result.stdout.decode("utf-8", errors="replace"),
                      stderr=result.stderr.decode("utf-8", errors="replace"),
                      cleanup="owned harness child exited and was reaped")
    except subprocess.TimeoutExpired as error:
        record.update(exit_code=124, stdout=(error.stdout or b"").decode("utf-8", errors="replace"),
                      stderr=(error.stderr or b"").decode("utf-8", errors="replace"),
                      error="Timeout: input may already have occurred; inspect and do not replay.",
                      cleanup="owned harness child terminated and reaped")
    record["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"receipt": str(receipt), **record}, ensure_ascii=True))
    return record["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
