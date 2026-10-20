"""Check the actual stdio transport; add --live to query the Java backend."""
import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check(live: bool):
    launcher = Path(__file__).resolve().with_name("start-mcp.py")
    params = StdioServerParameters(command=sys.executable, args=[str(launcher)])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=35)) as session:
            await session.initialize()
            print("PASS: MCP stdio initialize")
            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            expected = {"list_categories", "search_shops", "shops_by_category", "shop_detail",
                        "shop_vouchers", "plan_day", "search_cities", "search_city_places", "plan_route"}
            if names != expected:
                raise RuntimeError("Unexpected MCP tool list")
            print(f"PASS: Discovered {len(names)} read-only tools")
            denied = await session.call_tool("remember_preferences", {})
            if not denied.isError:
                raise RuntimeError("Private write tool was not rejected")
            print("PASS: Private write tool rejected")
            if live:
                result = await session.call_tool("list_categories", {})
                if result.isError:
                    raise RuntimeError("Java category query failed; check Java service and HMDP_BASE_URL")
                print("PASS: Java category query through MCP")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(check(args.live))
