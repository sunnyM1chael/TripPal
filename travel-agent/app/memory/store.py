"""SQLite WAL store; no Java business tables or bearer tokens are stored here.

Connections are short-lived, owner checks are part of every query, and leases are
claimed transactionally so multiple workers cannot write the same turn at once.
"""
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from app.core.exceptions import ConversationBusyError, NotFoundError, RequestLimitError
from app.memory.models import Preferences
from app.memory.summary import extend_summary


class MemoryStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self, retention_days: int = 90):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS preferences (
                    owner TEXT PRIMARY KEY, value TEXT NOT NULL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    lease TEXT, lease_until REAL NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS conversations_owner ON conversations(owner, updated);
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    prompt TEXT NOT NULL, output TEXT NOT NULL, tools TEXT NOT NULL,
                    mode TEXT NOT NULL, stopped INTEGER NOT NULL, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS turns_conversation ON turns(conversation_id, id);
                CREATE TABLE IF NOT EXISTS request_limits (
                    owner TEXT NOT NULL, bucket INTEGER NOT NULL, count INTEGER NOT NULL,
                    PRIMARY KEY(owner, bucket));
                PRAGMA user_version=1;
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(conversations)")}
            if "summary" not in columns:
                db.execute("ALTER TABLE conversations ADD COLUMN summary TEXT NOT NULL DEFAULT '[]'")
            if "summarized_through" not in columns:
                db.execute("ALTER TABLE conversations ADD COLUMN summarized_through INTEGER NOT NULL DEFAULT 0")
            db.execute("DELETE FROM conversations WHERE updated < ? AND lease_until < ?",
                       (time.time() - retention_days * 86400, time.time()))
            db.execute("DELETE FROM request_limits WHERE bucket < ?", (int(time.time() // 60) - 2,))

    def close(self):
        pass

    def check_rate(self, owner: str, limit: int):
        bucket = int(time.time() // 60)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO request_limits VALUES (?,?,1) ON CONFLICT(owner,bucket) DO UPDATE SET count=count+1", (owner, bucket))
            count = db.execute("SELECT count FROM request_limits WHERE owner=? AND bucket=?", (owner, bucket)).fetchone()[0]
            if count > limit:
                raise RequestLimitError("请求过于频繁，请稍后再试。")
            db.execute("DELETE FROM request_limits WHERE bucket < ?", (bucket - 2,))

    def preferences(self, owner: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT value FROM preferences WHERE owner=?", (owner,)).fetchone()
        return json.loads(row[0]) if row else {}

    def update_preferences(self, owner: str, patch: dict) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM preferences WHERE owner=?", (owner,)).fetchone()
            merged = {**(json.loads(row[0]) if row else {}), **patch}
            normalized = Preferences.model_validate(merged).model_dump(exclude_none=True)
            db.execute("INSERT INTO preferences VALUES (?,?,?) ON CONFLICT(owner) DO UPDATE SET value=excluded.value,updated=excluded.updated",
                       (owner, json.dumps(normalized, ensure_ascii=False), time.time()))
        return normalized

    def list_conversations(self, owner: str) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,title,created,updated,lease_until FROM conversations WHERE owner=? ORDER BY updated DESC LIMIT 50", (owner,))]

    @staticmethod
    def require(db, owner: str, conversation_id: str):
        row = db.execute("SELECT * FROM conversations WHERE id=? AND owner=?", (conversation_id, owner)).fetchone()
        if not row:
            raise NotFoundError("会话不存在或无权访问。")
        return row

    def conversation(self, owner: str, conversation_id: str) -> dict:
        with self.connection() as db:
            row = self.require(db, owner, conversation_id)
            turns = db.execute("SELECT * FROM turns WHERE conversation_id=? ORDER BY id DESC LIMIT 100", (conversation_id,)).fetchall()
        return {"id": row["id"], "title": row["title"], "summary": json.loads(row["summary"]), "busy": row["lease_until"] > time.time(),
                "turns": [{**dict(turn), "tools": json.loads(turn["tools"])} for turn in reversed(turns)]}

    def begin(self, owner: str, conversation_id: str | None, prompt: str) -> tuple[str, str]:
        now, lease = time.time(), str(uuid4())
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if conversation_id:
                row = self.require(db, owner, conversation_id)
                if row["lease_until"] > now:
                    raise ConversationBusyError("这段对话仍在生成回复，请稍后继续。")
            else:
                conversation_id = str(uuid4())
                count = db.execute("SELECT count(*) FROM conversations WHERE owner=?", (owner,)).fetchone()[0]
                if count >= 100:
                    raise RequestLimitError("最多保留100段对话，请先删除不需要的历史。")
                db.execute("INSERT INTO conversations(id,owner,title,created,updated) VALUES (?,?,?,?,?)",
                           (conversation_id, owner, prompt[:40], now, now))
            db.execute("UPDATE conversations SET lease=?,lease_until=? WHERE id=? AND owner=?",
                       (lease, now + 150, conversation_id, owner))
        return conversation_id, lease

    def finish(self, owner: str, conversation_id: str, lease: str, prompt: str, result):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.require(db, owner, conversation_id)
            if row["lease"] != lease:
                raise ConversationBusyError("会话已发生变化，请刷新后继续。")
            db.execute("INSERT INTO turns(conversation_id,prompt,output,tools,mode,stopped,created) VALUES (?,?,?,?,?,?,?)",
                       (conversation_id, prompt, result.output, json.dumps(result.tool_results, ensure_ascii=False),
                        result.mode, result.stopped, time.time()))
            db.execute("UPDATE conversations SET lease=NULL,lease_until=0,updated=? WHERE id=?", (time.time(), conversation_id))
            self._summarize(db, conversation_id, row)
            db.execute("DELETE FROM turns WHERE conversation_id=? AND id NOT IN (SELECT id FROM turns WHERE conversation_id=? ORDER BY id DESC LIMIT 100)", (conversation_id, conversation_id))

    @staticmethod
    def _summarize(db, conversation_id, conversation):
        boundary = db.execute("SELECT id FROM turns WHERE conversation_id=? ORDER BY id DESC LIMIT 1 OFFSET 6", (conversation_id,)).fetchone()
        if not boundary:
            return
        rows = db.execute("SELECT prompt,output FROM turns WHERE conversation_id=? AND id>? AND id<=? ORDER BY id",
                          (conversation_id, conversation["summarized_through"], boundary["id"])).fetchall()
        if rows:
            summary = extend_summary(conversation["summary"], [dict(row) for row in rows])
            db.execute("UPDATE conversations SET summary=?,summarized_through=? WHERE id=?", (summary, boundary["id"], conversation_id))

    def release(self, owner: str, conversation_id: str, lease: str):
        with self.connection() as db:
            db.execute("UPDATE conversations SET lease=NULL,lease_until=0 WHERE id=? AND owner=? AND lease=?", (conversation_id, owner, lease))

    def history(self, owner: str, conversation_id: str) -> list[dict]:
        turns = self.conversation(owner, conversation_id)["turns"][-6:]
        return [message for turn in turns if turn["mode"] == "live" for message in (
            {"role": "user", "content": turn["prompt"][:4000]},
            {"role": "assistant", "content": turn["output"][:4000]})]

    def recall(self, owner: str, prompt: str, conversation_id: str) -> list[dict]:
        # Bounded lexical retrieval. CJK bigrams work without an external tokenizer or vector service.
        tokens = set(re.findall(r"[a-z0-9]{2,}", prompt.lower()))
        for chunk in re.findall(r"[\u4e00-\u9fff]+", prompt):
            tokens.update(chunk[i:i+2] for i in range(len(chunk) - 1))
        with self.connection() as db:
            rows = db.execute("""SELECT t.prompt,t.output,c.title,t.created FROM turns t JOIN conversations c ON c.id=t.conversation_id
                WHERE c.owner=? AND c.id<>? AND t.mode='live' ORDER BY t.created DESC LIMIT 200""", (owner, conversation_id)).fetchall()
        ranked = sorted(((sum(token in (row["prompt"] + row["output"]).lower() for token in tokens), row) for row in rows), key=lambda item: item[0], reverse=True)
        return [{"title": row["title"], "user": row["prompt"][:350], "assistant": row["output"][:600]}
                for score, row in ranked[:3] if score >= 2]

    def delete_conversation(self, owner: str, conversation_id: str):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self.require(db, owner, conversation_id)
            if row["lease_until"] > time.time():
                raise ConversationBusyError("对话仍在生成，请完成后再删除。")
            db.execute("DELETE FROM conversations WHERE id=? AND owner=?", (conversation_id, owner))

    def forget(self, owner: str):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM conversations WHERE owner=? AND lease_until>?", (owner, time.time())).fetchone():
                raise ConversationBusyError("有对话正在生成，请结束后再清除记忆。")
            db.execute("DELETE FROM preferences WHERE owner=?", (owner,))
            db.execute("DELETE FROM conversations WHERE owner=?", (owner,))
