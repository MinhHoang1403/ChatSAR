"""Phiên/workspace qua HTTP thật trước và sau restart đúng Compose ChatSAR."""

import json
import subprocess
import urllib.request

from evaluations.oracle import ROOT


def inside(code: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-"],
        input=code, text=True, encoding="utf-8", capture_output=True,
        cwd=ROOT, timeout=30, check=True,
    )
    return result.stdout


def main() -> None:
    state = json.loads(inside('''
import json
from uuid import uuid4
from sqlalchemy import insert
from app.database import get_engine
from app.schema import users
from app.auth import create_session,digest
user_id=uuid4()
with get_engine().begin() as c:
    c.execute(insert(users).values(id=user_id,provider='google',provider_subject='test:'+uuid4().hex,display_name='Persistence test'))
    token=create_session(c,user_id)
print(json.dumps({'user_id':str(user_id),'token':token,'csrf':digest('csrf:'+token)}))
'''))
    headers = {"Cookie": "chatsar_session=" + state["token"],
               "Origin": "http://localhost:18181", "X-CSRF-Token": state["csrf"],
               "Content-Type": "application/json"}

    def request(path: str, data: bytes | None = None) -> object:
        req = urllib.request.Request("http://127.0.0.1:18181/api" + path,
                                     data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.load(response)

    try:
        before = request("/me")
        workspace = request("/workspaces", json.dumps({"name": "Persistence test"}).encode())
        subprocess.run(["docker", "compose", "restart"], cwd=ROOT, check=True, timeout=60)
        subprocess.run(["docker", "compose", "up", "-d", "--wait"],
                       cwd=ROOT, check=True, timeout=90)
        assert request("/me") == before, "Session/principal changed after restart"
        assert workspace in request("/workspaces"), "Workspace missing after restart"
        print("PASS: actual HTTP session and owner workspace persisted through Compose restart.")
    finally:
        # UUID tạo riêng cho test, không nhận owner từ nguồn ngoài.
        inside('''
from uuid import UUID
from sqlalchemy import delete
from app.database import get_engine
from app.schema import users,workspaces
owner=UUID("''' + state["user_id"] + '''")
with get_engine().begin() as c:
    c.execute(delete(workspaces).where(workspaces.c.owner_id==owner))
    c.execute(delete(users).where(users.c.id==owner))
''')


if __name__ == "__main__":
    main()
