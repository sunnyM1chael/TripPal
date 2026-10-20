import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

from app.core.config import Settings


def setup_module_script():
    spec = importlib.util.spec_from_file_location("mysql_setup", Path(__file__).parents[2] / "scripts/setup-mysql.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_uses_only_agent_databases_and_isolated_test_credentials(monkeypatch, capsys):
    script = setup_module_script()
    settings = Settings(_env_file=None, memory_mysql_user="test", memory_mysql_password="test-secret")
    monkeypatch.setattr(script, "Settings", lambda: settings)
    databases = []
    connection = SimpleNamespace(close=lambda: None)
    monkeypatch.setitem(sys.modules, "pymysql", SimpleNamespace(connect=lambda **kw: connection))
    monkeypatch.setattr(script, "install_schema", lambda db, name: databases.append(name))

    def run(command, **options):
        assert options["env"]["MEMORY_MYSQL_DATABASE"] == "travel_agent_test"
        assert options["env"]["MEMORY_MYSQL_PASSWORD"] == "test-secret"
        assert "test-secret" not in " ".join(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(script.subprocess, "run", run)
    assert script.main() == 0
    assert databases == ["travel_agent", "travel_agent_test"]
    assert "test-secret" not in capsys.readouterr().out
    assert settings.memory_backend == "sqlite"


def test_setup_redacts_connection_failure_and_skips_schema(monkeypatch, capsys):
    script = setup_module_script()
    monkeypatch.setattr(script, "Settings", lambda: Settings(_env_file=None,
        memory_mysql_user="test", memory_mysql_password="test-secret"))

    def fail(**kw):
        raise OSError(10013, "test-secret")

    monkeypatch.setitem(sys.modules, "pymysql", SimpleNamespace(connect=fail))
    monkeypatch.setattr(script, "install_schema", lambda *args: (_ for _ in ()).throw(AssertionError()))
    assert script.main() == 1
    assert "test-secret" not in capsys.readouterr().out


def test_setup_refuses_business_database(monkeypatch):
    script = setup_module_script()
    monkeypatch.setattr(script, "Settings", lambda: Settings(_env_file=None,
        memory_mysql_database="hmdp_0", memory_mysql_user="test", memory_mysql_password="test-secret"))
    monkeypatch.setitem(sys.modules, "pymysql", SimpleNamespace())
    assert script.main() == 1
