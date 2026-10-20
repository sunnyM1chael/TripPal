"""MySQL repository. Each operation uses an independent transaction/connection.

The semaphore bounds concurrent database connections per worker. Connections are
closed on return, avoiding stale pooled sessions after MySQL restarts.
"""
import json
import threading
import time
from contextlib import contextmanager
from uuid import uuid4

from app.core.exceptions import ConversationBusyError, MemoryUnavailableError, NotFoundError, RequestLimitError
from app.memory.store import MemoryStore


class _Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, sql, parameters=()):
        self.cursor.execute(sql.replace("?", "%s"), parameters)
        return self.cursor


class MySQLMemoryStore(MemoryStore):
    def __init__(self, settings):
        self.settings = settings
        self.slots = threading.BoundedSemaphore(settings.memory_mysql_pool_size)

    @contextmanager
    def connection(self):
        if not self.slots.acquire(timeout=5):
            raise MemoryUnavailableError("记忆服务繁忙，请稍后重试。")
        db = None
        try:
            import pymysql
            options = {}
            if self.settings.memory_mysql_ssl_ca:
                options.update(ssl_ca=str(self.settings.memory_mysql_ssl_ca),
                               ssl_verify_cert=True, ssl_verify_identity=True)
            db = pymysql.connect(host=self.settings.memory_mysql_host,
                port=self.settings.memory_mysql_port, user=self.settings.memory_mysql_user,
                password=self.settings.memory_mysql_password.get_secret_value(),
                database=self.settings.memory_mysql_database, charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor, autocommit=False,
                connect_timeout=5, read_timeout=10, write_timeout=10, **options)
            with db.cursor() as cursor:
                yield _Cursor(cursor)
            db.commit()
        except (ImportError, OSError) as exc:
            if db:
                db.rollback()
            raise MemoryUnavailableError("MySQL 记忆服务不可用，请检查驱动、连接配置和建表步骤。") from exc
        except Exception as exc:
            if db:
                db.rollback()
            if type(exc).__module__.startswith("pymysql"):
                raise MemoryUnavailableError("MySQL记忆操作失败，请检查数据库状态与表结构。") from exc
            raise
        finally:
            if db:
                db.close()
            self.slots.release()

    def initialize(self, retention_days=90):
        with self.connection() as db:
            version = db.execute("SELECT version FROM memory_schema_version WHERE version=1").fetchone()
            if not version:
                raise MemoryUnavailableError("请先初始化 travel_agent 数据库。")
            db.execute("DELETE FROM conversations WHERE updated < ? AND lease_until < ?",
                       (time.time() - retention_days * 86400, time.time()))
            db.execute("DELETE FROM request_limits WHERE bucket < ?", (int(time.time() // 60)-2,))

    @staticmethod
    def require(db, owner, conversation_id):
        row = db.execute("SELECT * FROM conversations WHERE id=? AND owner=? FOR UPDATE", (conversation_id, owner)).fetchone()
        if not row:
            raise NotFoundError("会话不存在或无权访问。")
        return row

    @staticmethod
    def lock_owner(db, owner):
        db.execute("INSERT IGNORE INTO memory_owners(owner) VALUES (?)", (owner,))
        db.execute("SELECT owner FROM memory_owners WHERE owner=? FOR UPDATE", (owner,)).fetchone()

    def check_rate(self, owner, limit):
        bucket = int(time.time() // 60)
        with self.connection() as db:
            db.execute("INSERT INTO request_limits(owner,bucket,request_count) VALUES (?,?,1) ON DUPLICATE KEY UPDATE request_count=request_count+1", (owner, bucket))
            count = db.execute("SELECT request_count FROM request_limits WHERE owner=? AND bucket=?", (owner, bucket)).fetchone()["request_count"]
            if count > limit:
                raise RequestLimitError("请求过于频繁，请稍后再试。")
            db.execute("DELETE FROM request_limits WHERE bucket < ?", (bucket-2,))

    def begin(self, owner, conversation_id, prompt):
        now, lease = time.time(), str(uuid4())
        with self.connection() as db:
            self.lock_owner(db, owner)
            if conversation_id:
                row = self.require(db, owner, conversation_id)
                if row["lease_until"] > now:
                    raise ConversationBusyError("这段对话仍在生成回复，请稍后继续。")
            else:
                count = db.execute("SELECT count(*) AS n FROM conversations WHERE owner=?", (owner,)).fetchone()["n"]
                if count >= 100:
                    raise RequestLimitError("最多保留100段对话，请先删除不需要的历史。")
                conversation_id = str(uuid4())
                db.execute("INSERT INTO conversations(id,owner,title,created,updated,summary) VALUES (?,?,?,?,?,'[]')", (conversation_id, owner, prompt[:40], now, now))
            db.execute("UPDATE conversations SET lease=?,lease_until=? WHERE id=? AND owner=?", (lease, now+150, conversation_id, owner))
        return conversation_id, lease

    def finish(self, owner, conversation_id, lease, prompt, result):
        with self.connection() as db:
            row = self.require(db, owner, conversation_id)
            if row["lease"] != lease:
                raise ConversationBusyError("会话已发生变化，请刷新后继续。")
            db.execute("INSERT INTO turns(conversation_id,prompt,output,tools,mode,stopped,created) VALUES (?,?,?,?,?,?,?)", (conversation_id, prompt, result.output, json.dumps(result.tool_results, ensure_ascii=False), result.mode, result.stopped, time.time()))
            db.execute("UPDATE conversations SET lease=NULL,lease_until=0,updated=? WHERE id=?", (time.time(), conversation_id))
            self._summarize(db, conversation_id, row)
            boundary = db.execute("SELECT id FROM turns WHERE conversation_id=? ORDER BY id DESC LIMIT 1 OFFSET 99", (conversation_id,)).fetchone()
            if boundary:
                db.execute("DELETE FROM turns WHERE conversation_id=? AND id<?", (conversation_id, boundary["id"]))

    def delete_conversation(self, owner, conversation_id):
        with self.connection() as db:
            row = self.require(db, owner, conversation_id)
            if row["lease_until"] > time.time():
                raise ConversationBusyError("对话仍在生成，请完成后再删除。")
            db.execute("DELETE FROM conversations WHERE id=? AND owner=?", (conversation_id, owner))

    def forget(self, owner):
        with self.connection() as db:
            self.lock_owner(db, owner)
            if db.execute("SELECT id FROM conversations WHERE owner=? AND lease_until>?", (owner, time.time())).fetchone():
                raise ConversationBusyError("有对话正在生成，请结束后再清除记忆。")
            db.execute("DELETE FROM conversations WHERE owner=?", (owner,))

    def preferences(self, owner):
        raise RuntimeError("Account preferences belong to Java")

    def update_preferences(self, owner, patch):
        raise RuntimeError("Account preferences belong to Java")
