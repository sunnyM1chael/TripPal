"""Absolute-path launcher for MCP clients that do not support a cwd field."""
import asyncio
import os
import sys
from pathlib import Path

project = Path(__file__).resolve().parents[1]
os.chdir(project)
sys.path.insert(0, str(project))

from app.mcp_server import main

if __name__ == "__main__":
    asyncio.run(main())
