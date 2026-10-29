"""Phiên/workspace qua HTTP thật trước và sau restart đúng Compose ChatSAR."""

import json
import subprocess
import urllib.request
from typing import Any
from uuid import uuid4

from evaluations.oracle import ROOT


def inside(code: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-"],
        input=code,
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=ROOT,
        timeout=30,
        check=True,
    )
    return result.stdout


class TestSession:
    """Danh tính chỉ tạo trong harness; cookie không đi vào output hay source."""

    def __init__(self) -> None:
        self.state = json.loads(
            inside("""
import json
from uuid import uuid4
from sqlalchemy import insert
from app.database import get_engine
from app.schema import users
from app.auth import create_session,digest
user_id=uuid4()
with get_engine().begin() as c:
    c.execute(insert(users).values(id=user_id,provider='google',provider_subject='test:'+uuid4().hex,display_name='Controlled test'))
    token=create_session(c,user_id)
print(json.dumps({'user_id':str(user_id),'token':token,'csrf':digest('csrf:'+token)}))
get_engine().dispose()
""")
        )

    def request(
        self,
        path: str,
        body: Any = None,
        *,
        content_type: str = "application/json",
        request_key: str | None = None,
    ) -> Any:
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
        headers = {
            "Cookie": "chatsar_session=" + self.state["token"],
            "Origin": "http://localhost:18181",
            "X-CSRF-Token": self.state["csrf"],
            "Content-Type": content_type,
        }
        if request_key:
            headers["Idempotency-Key"] = request_key
        req = urllib.request.Request(
            "http://127.0.0.1:18181/api" + path, data=data, headers=headers
        )
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.load(response)

    def publish(
        self,
        workspace_id: str,
        content: bytes,
        kinds: dict[str, str],
        null_sentinel: str | None = None,
        nullable_columns: set[str] | None = None,
    ) -> dict[str, Any]:
        boundary = uuid4().hex
        multipart = (
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.csv"\r\n'
                "Content-Type: text/csv\r\n\r\n"
            ).encode()
            + content
            + f"\r\n--{boundary}--\r\n".encode()
        )
        uploaded = self.request(
            f"/workspaces/{workspace_id}/datasets",
            multipart,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        preview = self.request(f"/datasets/{uploaded['dataset_id']}/preview")
        allowed = {
            "id",
            "name",
            "data_type",
            "nullable",
            "primary_key",
            "null_values",
            "date_format",
            "decimal_separator",
            "unit",
        }
        columns = [{k: v for k, v in c.items() if k in allowed} for c in preview["columns"]]
        for column in columns:
            column["data_type"] = kinds[column["name"]]
            if nullable_columns is not None:
                column["nullable"] = column["name"] in nullable_columns
            column["null_values"] = (
                [null_sentinel]
                if null_sentinel is not None
                else [""]
                if column["data_type"] != "text"
                else []
            )
        published = self.request(
            f"/datasets/{uploaded['dataset_id']}/confirm",
            {
                "revision_id": uploaded["revision_id"],
                "columns": columns,
                "grain": "Một dòng dữ liệu tổng hợp",
                "timezone": "Asia/Ho_Chi_Minh",
                "data_classification": "synthetic",
            },
        )
        return {**uploaded, **published}

    def close(self) -> None:
        # Chỉ xóa UUID đã tạo trong harness, không nhận owner từ HTTP/người dùng.
        inside(
            '''
from uuid import UUID
from pathlib import Path
from sqlalchemy import delete,select,Table,MetaData
from app.database import get_engine
from app.schema import users,workspaces,datasets,revisions,jobs,conversations,messages,results
from app.config import get_settings
owner=UUID("'''
            + self.state["user_id"]
            + """")
with get_engine().begin() as c:
    owned=select(workspaces.c.id).where(workspaces.c.owner_id==owner)
    chats=select(conversations.c.id).where(conversations.c.workspace_id.in_(owned))
    message_ids=select(messages.c.id).where(messages.c.conversation_id.in_(chats))
    c.execute(delete(results).where(results.c.message_id.in_(message_ids)))
    c.execute(delete(messages).where(messages.c.conversation_id.in_(chats)))
    c.execute(delete(conversations).where(conversations.c.workspace_id.in_(owned)))
    sources=c.execute(select(revisions).join(datasets,revisions.c.dataset_id==datasets.c.id).where(datasets.c.workspace_id.in_(owned))).mappings().all()
    for row in sources:
        if row['physical_table']:
            assert row['physical_table']=='r_'+row['id'].hex
            Table(row['physical_table'],MetaData(),schema='data').drop(c)
        assert row['storage_name']==str(row['id'])+row['suffix']
        (Path(get_settings().storage_root)/row['storage_name']).unlink(missing_ok=True)
        c.execute(delete(jobs).where(jobs.c.revision_id==row['id']))
        c.execute(delete(revisions).where(revisions.c.id==row['id']))
    c.execute(delete(datasets).where(datasets.c.workspace_id.in_(owned)))
    c.execute(delete(workspaces).where(workspaces.c.owner_id==owner))
    c.execute(delete(users).where(users.c.id==owner))
get_engine().dispose()
"""
        )


def main() -> None:
    session = TestSession()
    try:
        before = session.request("/me")
        workspace = session.request("/workspaces", {"name": "Persistence test"})
        source = session.publish(
            workspace["id"],
            b"code,amount\n0007,0.10\n0012,0.20\n0100,\n",
            {"code": "text", "amount": "numeric"},
        )
        ready_before = session.request(f"/datasets/{source['dataset_id']}/preview")
        assert ready_before["rows"] == [["0007", "0.10"], ["0012", "0.20"], ["0100", None]]
        conversation = session.request("/conversations", {"workspace_id": workspace["id"]})
        # Không gọi model trong CI: private data phải bị chặn trước provider.
        inside(
            "from sqlalchemy import update\nfrom uuid import UUID\nfrom app.schema import revisions\nfrom app.database import get_engine\nwith get_engine().begin() as c:\n c.execute(update(revisions).where(revisions.c.id==UUID('"
            + source["revision_id"]
            + "')).values(data_classification='private'))\nget_engine().dispose()"
        )
        ready_before = session.request(f"/datasets/{source['dataset_id']}/preview")
        result = session.request(
            f"/conversations/{conversation['id']}/messages",
            {"question": "Tổng số tiền?", "dataset_revision_id": source["revision_id"]},
            request_key=uuid4().hex,
        )
        assert (
            result["status"] == "insufficient"
            and result["error_code"] == "DATA_PERMISSION_REQUIRED"
        )
        history = session.request(f"/conversations/{conversation['id']}")
        subprocess.run(["docker", "compose", "restart"], cwd=ROOT, check=True, timeout=60)
        subprocess.run(
            ["docker", "compose", "up", "-d", "--wait"], cwd=ROOT, check=True, timeout=90
        )
        assert session.request("/me") == before
        assert workspace in session.request("/workspaces")
        assert session.request(f"/datasets/{source['dataset_id']}/preview") == ready_before
        assert session.request(f"/conversations/{conversation['id']}") == history
        print(
            "PASS: HTTP ingestion/session/workspace/source/catalog/typed rows/chat refusal history persisted; no provider calls."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
