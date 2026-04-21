"""Rapid-fire tool calls over real MCP stdio. Measures per-call latency and
catches anything that degrades under repeated use.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            t0 = time.perf_counter()
            for i in range(50):
                await session.call_tool("get_neighbors", {"ref": "main"})
            dt = time.perf_counter() - t0
            print(f"50x get_neighbors: {dt*1000:.0f} ms total, {dt*1000/50:.1f} ms/call")

            t0 = time.perf_counter()
            for i in range(20):
                await session.call_tool("grep_source", {"pattern": r"json\.dumps"})
            dt = time.perf_counter() - t0
            print(f"20x grep_source: {dt*1000:.0f} ms total, {dt*1000/20:.1f} ms/call")

            t0 = time.perf_counter()
            for i in range(20):
                await session.call_tool("get_source", {"ref": "main"})
            dt = time.perf_counter() - t0
            print(f"20x get_source (5KB): {dt*1000:.0f} ms total, {dt*1000/20:.1f} ms/call")

            # Concurrent burst
            t0 = time.perf_counter()
            await asyncio.gather(*[
                session.call_tool("get_ancestors", {"ref": "build_execution_ir_from_raw"}) for _ in range(20)
            ])
            dt = time.perf_counter() - t0
            print(f"20 concurrent get_ancestors: {dt*1000:.0f} ms")

            # Mixed burst — realistic pattern: AI might call several tools in parallel
            t0 = time.perf_counter()
            await asyncio.gather(
                session.call_tool("get_selection", {}),
                session.call_tool("get_source", {"ref": "main"}),
                session.call_tool("get_ancestors", {"ref": "_resolve_import_base"}),
                session.call_tool("get_descendants", {"ref": "main", "max_depth": 2}),
                session.call_tool("grep_source", {"pattern": r"raise\s+\w+Error"}),
                session.call_tool("search", {"query": "overlay"}),
                session.call_tool("list_nodes", {}),
            )
            dt = time.perf_counter() - t0
            print(f"mixed parallel burst (7 tools): {dt*1000:.0f} ms")

            # Reload
            r = await session.call_tool("reload_graph", {})
            print(f"reload_graph: {r.content[0].text}")


if __name__ == "__main__":
    asyncio.run(main())
