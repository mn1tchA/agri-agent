"""
CI Test Runner for GitHub Actions.
Executes pytest with coverage, streams output, and generates GitHub Actions annotations on failure.
"""

import os
import subprocess
import sys


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "--tb=short",
    ]
    print(f"=== Running Pytest Command: {' '.join(cmd)} ===", flush=True)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    output_lines = []
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
        output_lines.append(line)

    retcode = proc.wait()
    print(f"\n=== Pytest finished with exit code {retcode} ===", flush=True)

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as sf:
                sf.write(f"\n### Pytest Run Results (Exit Code: {retcode})\n```text\n")
                sf.writelines(output_lines[-120:])
                sf.write("\n```\n")
        except Exception as e:
            print(f"Failed to write GITHUB_STEP_SUMMARY: {e}", flush=True)

    if retcode != 0:
        # Emit GitHub Actions annotations for failures so they are visible publicly
        failure_lines = [
            ln.strip()
            for ln in output_lines
            if any(k in ln for k in ("FAILED", "ERROR", "ModuleNotFoundError", "ImportError", "Coverage", "fail-under"))
        ]
        if failure_lines:
            for fl in failure_lines[:20]:
                print(f"::error title=Pytest Error::{fl}", flush=True)
        else:
            # Emit last 15 lines as fallback annotations
            for ln in [l.strip() for l in output_lines[-15:] if l.strip()]:
                print(f"::error title=Pytest Output::{ln}", flush=True)

    return retcode


if __name__ == "__main__":
    sys.exit(main())
