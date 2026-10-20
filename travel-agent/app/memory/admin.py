"""Explicit schema installation and non-destructive SQLite import commands."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

from app.core.config import Settings
from app.memory.models import Preferences
from app.memory.mysql import MySQLMemoryStore
from app.memory.summary import extend_summary


def import_sqlite(store, path):
    source = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    imported = skipped = 0
    try:
        source.execute("BEGIN")
        conversations = source.execute("SELECT * FROM conversations ORDER BY created").fetchall()
        with store.connection() as db:
            for raw in conversations:
                row = dict(raw)
                if row["lease_until"] > time.time():
                    raise ValueError("源数据库仍有生成中的对话，请停服务并等待请求结束后重试。")
                turns = [dict(t) for t in source.execute("SELECT * FROM turns WHERE conversation_id=? ORDER BY id", (row["id"],))]
                digest = hashlib.sha256(json.dumps([row, turns], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                store.lock_owner(db, row["owner"])
                previous = db.execute("SELECT source_digest FROM sqlite_imports WHERE conversation_id=?", (row["id"],)).fetchone()
                if previous:
                    if previous["source_digest"] != digest:
                        raise ValueError("源数据在导入后发生变化；为防覆盖，已回滚本次导入。")
                    skipped += 1
                    continue
                if db.execute("SELECT id FROM conversations WHERE id=?", (row["id"],)).fetchone():
                    raise ValueError("目标会话ID已存在；本次导入已回滚。")
                older = [t for t in turns[:-6] if t["id"] > row.get("summarized_through", 0)]
                summary = extend_summary(row.get("summary") or "[]", older)
                db.execute("INSERT INTO conversations(id,owner,title,created,updated,summary) VALUES (?,?,?,?,?,?)",
                           (row["id"], row["owner"], row["title"], row["created"], row["updated"], summary))
                for turn in turns:
                    db.execute("INSERT INTO turns(conversation_id,prompt,output,tools,mode,stopped,created) VALUES (?,?,?,?,?,?,?)",
                        (row["id"], turn["prompt"], turn["output"], turn["tools"], turn["mode"], turn["stopped"], turn["created"]))
                # Source IDs are not target IDs; all imported older turns are already summarized.
                boundary = db.execute("SELECT id FROM turns WHERE conversation_id=? ORDER BY id DESC LIMIT 1 OFFSET 6", (row["id"],)).fetchone()
                db.execute("UPDATE conversations SET summarized_through=? WHERE id=?", (boundary["id"] if boundary else 0, row["id"]))
                db.execute("INSERT INTO sqlite_imports(conversation_id,source_digest) VALUES (?,?)", (row["id"], digest))
                imported += 1
        return {"imported": imported, "unchanged": skipped,
                "notice": "原SQLite文件保持不变；旧偏好需登录账号后单独迁移。"}
    finally:
        source.close()


def import_preferences(settings, path):
    """Only migrate the account verified by Java, using an environment-held token."""
    import httpx
    token = os.environ.get("TRAVEL_MIGRATION_TOKEN")
    if not token:
        raise ValueError("请在当前终端设置 TRAVEL_MIGRATION_TOKEN；不要把登录令牌写入命令参数。")
    with httpx.Client(base_url=str(settings.hmdp_base_url), timeout=10,
                      headers={"authorization": token}) as client:
        me = client.get("/user/me")
        me.raise_for_status()
        payload = me.json()
        if not payload.get("success") or not payload.get("data", {}).get("id"):
            raise ValueError("Java未确认登录身份。")
        owner = "user:" + str(int(payload["data"]["id"]))
        with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as source:
            row = source.execute("SELECT value FROM preferences WHERE owner=?", (owner,)).fetchone()
        if not row:
            return {"migrated": False, "notice": "该登录账号没有旧偏好；访客偏好不会自动并入账号。"}
        patch = Preferences.model_validate_json(row[0]).model_dump(exclude_unset=True)
        current = client.get("/user/travel-preferences")
        current.raise_for_status()
        current_data = current.json()
        if not current_data.get("success"):
            raise ValueError("读取Java偏好失败。")
        if any(v not in (None, [], "") for v in (current_data.get("data") or {}).values()):
            raise ValueError("账号已有偏好，请在页面核对后手动合并，避免覆盖。")
        result = client.patch("/user/travel-preferences", json=patch)
        result.raise_for_status()
        if not result.json().get("success"):
            raise ValueError("Java未确认保存偏好。")
        return {"migrated": True, "notice": "已迁移当前登录账号偏好；原文件保持不变。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "import-sqlite", "import-preferences"])
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    settings = Settings()
    if args.command != "init" and (not args.source or not args.source.is_file()):
        parser.error("需要 --source 指向现有SQLite文件")
    try:
        if args.command == "import-preferences":
            result = import_preferences(settings, args.source)
        else:
            if settings.memory_backend != "mysql":
                parser.error("请先配置 MEMORY_BACKEND=mysql 和MySQL连接信息")
            store = MySQLMemoryStore(settings)
            if args.command == "init":
                # Database creation is an operator action; runtime only needs table DML privileges.
                with store.connection() as db:
                    sql = Path(__file__).with_name("mysql_schema.sql").read_text(encoding="utf-8")
                    for statement in sql.split(";"):
                        if statement.strip():
                            db.execute(statement)
                result = {"initialized": True}
            else:
                result = import_sqlite(store, args.source)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        # Never print connection exception strings: drivers may include usernames/addresses.
        print(f"操作失败（{type(exc).__name__}）。请检查配置、建表和源文件；原SQLite文件未修改。")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
