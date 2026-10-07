"""SQLite structured store: documents, reviews (human approval) and audit log."""
import json
import sqlite3
import time
from pathlib import Path


class Database:
    def __init__(self, cfg):
        p = Path(cfg["paths"]["data_dir_abs"])
        p.mkdir(parents=True, exist_ok=True)
        self.path = p / "hld.sqlite"
        with self._c() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, project TEXT, doc_key TEXT, doc_id TEXT, version TEXT,
              filename TEXT, sha256 TEXT, pages INT, chunks INT, ingested_at TEXT, ingested_by TEXT, UNIQUE(project, doc_key));
            CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, project TEXT, ts TEXT, user TEXT, question TEXT, answer TEXT,
              sources TEXT, decision TEXT, edited_answer TEXT, comment TEXT);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, project TEXT, ts TEXT, user TEXT, action TEXT, detail TEXT);""")

    def _c(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    @staticmethod
    def _now():
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    def audit(self, project, user, action, detail=""):
        with self._c() as c:
            c.execute("INSERT INTO audit(project,ts,user,action,detail) VALUES(?,?,?,?,?)",
                      (project, self._now(), user, action, str(detail)[:500]))

    def upsert_doc(self, project, kb, chunks, user):
        with self._c() as c:
            c.execute("INSERT OR REPLACE INTO documents(project,doc_key,doc_id,version,filename,sha256,pages,chunks,ingested_at,ingested_by)"
                      " VALUES(?,?,?,?,?,?,?,?,?,?)", (project, kb["doc_key"], kb["doc_id"], kb["version"], kb["source_file"],
                                                       kb["sha256"], kb["pages"], chunks, self._now(), user))

    def docs(self, project):
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT * FROM documents WHERE project=? ORDER BY doc_key", (project,))]

    def add_review(self, project, user, r):
        with self._c() as c:
            c.execute("INSERT INTO reviews(project,ts,user,question,answer,sources,decision,edited_answer,comment) VALUES(?,?,?,?,?,?,?,?,?)",
                      (project, self._now(), user, r["question"], r["answer"], json.dumps(r.get("sources", []))[:20000],
                       r["decision"], r.get("edited_answer", ""), r.get("comment", "")))

    def reviews(self, project):
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT * FROM reviews WHERE project=? ORDER BY id DESC", (project,))]

    def audit_log(self, project):
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT * FROM audit WHERE project=? ORDER BY id DESC LIMIT 500", (project,))]
