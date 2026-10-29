"""Kiểm tra HTTP, migration và cấu hình container thật của ChatSAR."""

import json
import subprocess
import urllib.request

from evaluations.oracle import ROOT, postgres


def main() -> None:
    raw = subprocess.check_output(
        ["docker", "compose", "ps", "--format", "json"], cwd=ROOT, text=True,
        encoding="utf-8", timeout=20,
    ).strip()
    containers = json.loads(raw) if raw.startswith("[") else [
        json.loads(line) for line in raw.splitlines() if line.strip()
    ]
    if {container["Service"] for container in containers} != {"api", "web", "db"}:
        raise AssertionError("Thiếu service ChatSAR")
    for container in containers:
        if container["State"] != "running" or container["Health"] != "healthy":
            raise AssertionError(f"Service chưa healthy: {container['Service']}")
        if container["Project"] != "chatsar":
            raise AssertionError("Sai Compose project")
    for port in [18081, 18181]:
        for path in ["/live", "/ready", "/health"]:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=8) as response:
                body = json.load(response)
                if response.status != 200 or body["status"] != "ok":
                    raise AssertionError(f"Health không đạt: {port}{path}")
                if path == "/health" and type(body["cloud_calls_allowed"]) is not bool:
                    raise AssertionError("Trạng thái quyền cloud không đúng kiểu")
    with urllib.request.urlopen("http://127.0.0.1:18181/", timeout=8) as response:
        html = response.read().decode("utf-8")
        if 'lang="vi"' not in html or "ChatSAR" not in html:
            raise AssertionError("Web build không đúng")
    with urllib.request.urlopen("http://127.0.0.1:18181/api/health", timeout=8) as response:
        if json.load(response)["status"] != "ok":
            raise AssertionError("Frontend proxy /api không kết nối được backend")
    version = postgres("SELECT name FROM app.schema_migrations ORDER BY name;")
    if "foundation" not in version.splitlines():
        raise AssertionError("Migration không tồn tại")
    print("PASS: web/api/db healthy; HTTP endpoints/proxy; web build; migration persisted.")


if __name__ == "__main__":
    main()
