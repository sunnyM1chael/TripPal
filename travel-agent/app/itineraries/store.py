import json
import sqlite3
import time
from threading import Lock
from uuid import uuid4

from app.core.exceptions import NotFoundError, RequestLimitError
from app.itineraries.models import ItineraryUnavailable, RevisionConflict


SQLITE_SCHEMA = """CREATE TABLE IF NOT EXISTS itineraries (
    id TEXT PRIMARY KEY, owner TEXT NOT NULL, revision INTEGER NOT NULL,
    document TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS itineraries_owner ON itineraries(owner, updated);
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
    itinerary_id TEXT, is_read INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS notifications_owner ON notifications(owner, is_read, created);"""


class ItineraryStore:
    def __init__(self, memory):
        self.memory = memory
        self.mysql = hasattr(memory, "settings")
        self.ready = False
        self._check_lock = Lock()
        self._last_check = float("-inf")

    def initialize(self):
        # MySQL migrations are explicit; an old schema must not prevent chat startup.
        try:
            with self.memory.connection() as db:
                if not self.mysql:
                    db.executescript(SQLITE_SCHEMA)
                db.execute("SELECT id, owner, revision, document, created, updated FROM itineraries LIMIT 0")
            self.ready = True
        except Exception as exc:
            cause = exc.__cause__ or exc
            if self.mysql and getattr(cause, "args", ()) and cause.args[0] == 1146:
                self.ready = False
            else:
                raise

    @staticmethod
    def notify(db, owner, itinerary_id, document, action):
        title = {"created": "新行程已收好", "complete_stop": "又完成了一站", "visit_feedback": "这次体验已记下"}.get(action, "行程有了新安排")
        body = f"《{document['title']}》" + ("已保存，出发前记得确认营业与预约信息。" if action == "created" else "已更新，点击查看最新安排。")
        db.execute("INSERT INTO notifications(id,owner,title,body,itinerary_id,created) VALUES (?,?,?,?,?,?)",
                   (str(uuid4()), owner, title, body, itinerary_id, time.time()))

    def require_ready(self):
        if not self.check_ready():
            raise ItineraryUnavailable("行程数据表尚未就绪，请在 travel-agent 目录执行 uv run --no-sync python -m app.memory.admin init，完成后刷新页面。")

    def check_ready(self):
        # Retry read-only schema detection after an explicit migration, without a restart.
        # Throttle checks while the schema is missing, including concurrent requests.
        if not self.ready:
            with self._check_lock:
                if not self.ready and time.monotonic() - self._last_check >= 5:
                    self._last_check = time.monotonic()
                    self.initialize()
        return self.ready

    @staticmethod
    def decode(row):
        return {**json.loads(row["document"]), "id": row["id"], "revision": row["revision"],
                "created_at": row["created"], "updated_at": row["updated"]}

    def list(self, owner):
        self.require_ready()
        with self.memory.connection() as db:
            rows = db.execute("SELECT * FROM itineraries WHERE owner=? ORDER BY updated DESC LIMIT 50", (owner,)).fetchall()
        return [self.decode(row) for row in rows]

    def get(self, owner, itinerary_id):
        self.require_ready()
        with self.memory.connection() as db:
            row = db.execute("SELECT * FROM itineraries WHERE id=? AND owner=?", (itinerary_id, owner)).fetchone()
        if not row:
            raise NotFoundError("行程不存在或无权访问。")
        return self.decode(row)

    def create(self, owner, document):
        self.require_ready()
        now, itinerary_id = time.time(), str(uuid4())
        with self.memory.connection() as db:
            if isinstance(db, sqlite3.Connection):
                db.execute("BEGIN IMMEDIATE")
            else:
                self.memory.lock_owner(db, owner)
            count = db.execute("SELECT count(*) AS n FROM itineraries WHERE owner=?", (owner,)).fetchone()["n"]
            if count >= 50:
                raise RequestLimitError("最多保存50份行程，请先删除不需要的行程。")
            db.execute("INSERT INTO itineraries(id,owner,revision,document,created,updated) VALUES (?,?,1,?,?,?)",
                       (itinerary_id, owner, json.dumps(document, ensure_ascii=False), now, now))
            self.notify(db, owner, itinerary_id, document, "created")
        return {**document, "id": itinerary_id, "revision": 1, "created_at": now, "updated_at": now}

    def update(self, owner, itinerary_id, revision, document):
        self.require_ready()
        now = time.time()
        with self.memory.connection() as db:
            cursor = db.execute("UPDATE itineraries SET document=?,revision=revision+1,updated=? WHERE id=? AND owner=? AND revision=?",
                                (json.dumps(document, ensure_ascii=False), now, itinerary_id, owner, revision))
            if cursor.rowcount != 1:
                row = db.execute("SELECT id FROM itineraries WHERE id=? AND owner=?", (itinerary_id, owner)).fetchone()
                if not row:
                    raise NotFoundError("行程不存在或无权访问。")
                raise RevisionConflict("行程已在其他页面更新，请刷新后再调整。")
            self.notify(db, owner, itinerary_id, document, document.get("changes", [{}])[-1].get("action", "updated"))
        return {**document, "id": itinerary_id, "revision": revision + 1, "updated_at": now}

    def delete(self, owner, itinerary_id, revision):
        self.require_ready()
        with self.memory.connection() as db:
            row = db.execute("SELECT revision FROM itineraries WHERE id=? AND owner=?", (itinerary_id, owner)).fetchone()
            if not row:
                raise NotFoundError("行程不存在或无权访问。")
            cursor = db.execute("DELETE FROM itineraries WHERE id=? AND owner=? AND revision=?", (itinerary_id, owner, revision))
            if cursor.rowcount != 1:
                raise RevisionConflict("行程已更新，请刷新后再删除。")
            db.execute("UPDATE notifications SET itinerary_id=NULL WHERE owner=? AND itinerary_id=?", (owner, itinerary_id))

    def forget(self, owner):
        if self.check_ready():
            with self.memory.connection() as db:
                db.execute("DELETE FROM itineraries WHERE owner=?", (owner,))
                db.execute("DELETE FROM notifications WHERE owner=?", (owner,))
