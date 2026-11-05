"""Chạy harness trong API container hiện hữu; không tạo môi trường hay endpoint bypass."""

import subprocess
from pathlib import Path

from evaluations.oracle import ROOT


def main() -> None:
    for path in sorted((ROOT / "backend" / "tests").glob("integration_*.py")):
        print(f"Integration: {path.name}", flush=True)
        subprocess.run(
            ["docker", "compose", "exec", "-T", "api", "python", "-"],
            input=(
                "import atexit\nfrom app.database import get_engine,get_reader_engine\n"
                "atexit.register(lambda: get_engine().dispose())\n"
                "atexit.register(lambda: get_reader_engine().dispose())\n"
                + path.read_text(encoding="utf-8")
            ),
            encoding="utf-8",
            text=True,
            cwd=ROOT,
            check=True,
            timeout=120,
        )


if __name__ == "__main__":
    main()
