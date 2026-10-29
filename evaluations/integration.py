"""Chạy harness trong API container hiện hữu; không tạo môi trường hay endpoint bypass."""

import subprocess
from pathlib import Path

from evaluations.oracle import ROOT


def main() -> None:
    for path in sorted((ROOT / "backend" / "tests").glob("integration_*.py")):
        print(f"Integration: {path.name}", flush=True)
        subprocess.run(
            ["docker", "compose", "exec", "-T", "api", "python", "-"],
            input=path.read_text(encoding="utf-8"), encoding="utf-8", text=True,
            cwd=ROOT, check=True, timeout=120,
        )


if __name__ == "__main__":
    main()
