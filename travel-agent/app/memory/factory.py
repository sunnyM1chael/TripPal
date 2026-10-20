from app.memory.store import MemoryStore


def create_memory(settings):
    if settings.memory_backend == "mysql":
        from app.memory.mysql import MySQLMemoryStore
        return MySQLMemoryStore(settings)
    return MemoryStore(settings.memory_db_path)
