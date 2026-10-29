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

    def request(path: str, data: bytes | None = None, content_type: str = "application/json") -> Any:
        local_headers = {**headers, "Content-Type": content_type}
        req = urllib.request.Request("http://127.0.0.1:18181/api" + path,
                                     data=data, headers=local_headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            return json.load(response)

    try:
        before = request("/me")
        workspace = request("/workspaces", json.dumps({"name": "Persistence test"}).encode())
        boundary = uuid4().hex
        content = b'code,amount\n0007,0.10\n0012,0.20\n0100,\n'
        multipart = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="persistence.csv"\r\n'
                     'Content-Type: text/csv\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
        uploaded = request(f"/workspaces/{workspace['id']}/datasets", multipart,
                           f"multipart/form-data; boundary={boundary}")
        preview = request(f"/datasets/{uploaded['dataset_id']}/preview")
        allowed = {'id','name','data_type','nullable','primary_key','null_values','date_format','decimal_separator','unit'}
        columns = [{k:v for k,v in c.items() if k in allowed} for c in preview['columns']]
        columns[0]['primary_key'] = True
        columns[1]['null_values'] = ['']
        request(f"/datasets/{uploaded['dataset_id']}/confirm", json.dumps({
            'revision_id':uploaded['revision_id'],'columns':columns,'grain':'One synthetic row',
            'data_classification':'synthetic',
        }).encode())
        ready_before = request(f"/datasets/{uploaded['dataset_id']}/preview")
        assert ready_before['rows'] == [['0007','0.10'],['0012','0.20'],['0100',None]]
        subprocess.run(["docker", "compose", "restart"], cwd=ROOT, check=True, timeout=60)
        subprocess.run(["docker", "compose", "up", "-d", "--wait"],
                       cwd=ROOT, check=True, timeout=90)
        assert request("/me") == before, "Session/principal changed after restart"
        assert workspace in request("/workspaces"), "Workspace missing after restart"
        ready_after = request(f"/datasets/{uploaded['dataset_id']}/preview")
        assert ready_after == ready_before, "Source/checksum/catalog/typed rows changed after restart"
        print("PASS: HTTP upload/review/publish + session/workspace/source/catalog/typed rows persisted after restart.")
    finally:
        # UUID tạo riêng cho test, không nhận owner từ nguồn ngoài.
        inside('''
from uuid import UUID
from pathlib import Path
from sqlalchemy import delete,select,Table,MetaData
from app.database import get_engine
from app.schema import users,workspaces,datasets,revisions,jobs
from app.config import get_settings
owner=UUID("''' + state["user_id"] + '''")
with get_engine().begin() as c:
    sources=c.execute(select(revisions).join(datasets,revisions.c.dataset_id==datasets.c.id).join(workspaces,datasets.c.workspace_id==workspaces.c.id).where(workspaces.c.owner_id==owner)).mappings().all()
    for row in sources:
        if row['physical_table']:
            assert row['physical_table']=='r_'+row['id'].hex
            Table(row['physical_table'],MetaData(),schema='data').drop(c)
        assert row['storage_name']==str(row['id'])+row['suffix']
        (Path(get_settings().storage_root)/row['storage_name']).unlink(missing_ok=True)
        c.execute(delete(jobs).where(jobs.c.revision_id==row['id']))
        c.execute(delete(revisions).where(revisions.c.id==row['id']))
    owned=c.execute(select(workspaces.c.id).where(workspaces.c.owner_id==owner)).scalars().all()
    c.execute(delete(datasets).where(datasets.c.workspace_id.in_(owned)))
    c.execute(delete(workspaces).where(workspaces.c.owner_id==owner))
    c.execute(delete(users).where(users.c.id==owner))
''')


if __name__ == "__main__":
    main()
