"""Initialize Agent databases and run the isolated, real MySQL integration test."""
import os
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT))

from app.core.config import Settings


def install_schema(connection, database):
    # Identifiers are fixed application constants, never user/model-supplied SQL.
    if database not in {"travel_agent", "travel_agent_test"}:
        raise ValueError("Unexpected database")
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
        cursor.execute(f"USE `{database}`")
        schema = (PROJECT / "app/memory/mysql_schema.sql").read_text(encoding="utf-8")
        for statement in schema.split(";"):
            if statement.strip():
                cursor.execute(statement)
    connection.commit()


def main():
    try:
        import pymysql
    except ImportError:
        print("FAIL: Install requirements-mysql.txt with the project Python first.")
        return 1
    settings = Settings()
    if not settings.memory_mysql_user or settings.memory_mysql_password is None:
        print("FAIL: Fill MEMORY_MYSQL_USER and MEMORY_MYSQL_PASSWORD in .env.")
        return 1
    if settings.memory_mysql_database != "travel_agent":
        print("FAIL: This setup script only initializes travel_agent and travel_agent_test.")
        return 1
    options = {}
    if settings.memory_mysql_ssl_ca:
        options.update(ssl_ca=str(settings.memory_mysql_ssl_ca), ssl_verify_cert=True, ssl_verify_identity=True)
    connection = None
    try:
        connection = pymysql.connect(host=settings.memory_mysql_host, port=settings.memory_mysql_port,
            user=settings.memory_mysql_user, password=settings.memory_mysql_password.get_secret_value(),
            charset="utf8mb4", connect_timeout=5, read_timeout=10, write_timeout=10, **options)
        print("PASS: MySQL authentication and connection", flush=True)
        # No DROP/TRUNCATE and no access to Java business databases.
        for database in ("travel_agent", "travel_agent_test"):
            install_schema(connection, database)
            print(f"PASS: {database} schema initialized", flush=True)
    except Exception as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
        print(f"FAIL: MySQL connection/schema setup ({type(exc).__name__}, code={code}).")
        print("Check MySQL service, credentials and CREATE DATABASE/TABLE privileges. No backend setting changed.")
        return 1
    finally:
        if connection is not None:
            connection.close()

    # The integration test refuses non-test databases. Credentials stay in environment,
    # never command arguments or printed output. Disable unrelated auto-loaded plugins.
    env = {**os.environ, "TRAVEL_TEST_MYSQL": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "MEMORY_MYSQL_HOST": settings.memory_mysql_host,
           "MEMORY_MYSQL_PORT": str(settings.memory_mysql_port),
           "MEMORY_MYSQL_DATABASE": "travel_agent_test",
           "MEMORY_MYSQL_USER": settings.memory_mysql_user,
           "MEMORY_MYSQL_PASSWORD": settings.memory_mysql_password.get_secret_value(),
           "MEMORY_MYSQL_POOL_SIZE": str(settings.memory_mysql_pool_size),
           "MEMORY_MYSQL_SSL_CA": str(settings.memory_mysql_ssl_ca or "")}
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", "tests/integration/test_mysql_memory.py",
                                 "-q", "--tb=no", "-o", "addopts=", "-o", "asyncio_mode=auto"],
                                cwd=PROJECT, env=env, timeout=120, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        print("FAIL: MySQL integration test timed out. No backend setting changed.")
        return 1
    # Do not echo captured pytest failures; connection failures can contain credentials.
    if result.returncode:
        print(f"FAIL: MySQL integration test (exit={result.returncode}). No backend setting changed.")
        print("Run the dedicated test locally to inspect the failure; do not share credentials.")
        return 1
    print("PASS: Real MySQL persistence, owner isolation, leases, summary and SQLite import")
    print("MySQL integration passed. .env is unchanged; Java account preferences are a separate check.")
    print("Before switching MEMORY_BACKEND=mysql, stop Python and import existing SQLite history if needed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: Setup aborted ({type(exc).__name__}). Credentials omitted; .env unchanged.")
        raise SystemExit(1) from None
