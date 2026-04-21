"""Spawn mcp_server.py as a real stdio MCP subprocess and exercise it over
JSON-RPC the way Claude Code / OpenCode would. Catches serialization /
protocol bugs the direct-import harness can't see.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "mcp_server.py")],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"tools registered: {[t.name for t in tools.tools]}")

            # Make sure the server sees our pin.
            Path("/tmp/flowcode-selection.json").write_text(
                json.dumps({"id": "build_execution_ir_from_raw"})
            )

            async def call(name: str, **args):
                r = await session.call_tool(name, args)
                # FastMCP puts list returns across multiple TextContent blocks
                # and structured returns in r.structuredContent when available.
                if getattr(r, "structuredContent", None) is not None:
                    sc = r.structuredContent
                    # structuredContent for list returns is {"result": [...]}
                    if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
                        return sc["result"]
                    return sc
                if not r.content:
                    return None
                if len(r.content) == 1:
                    try:
                        return json.loads(r.content[0].text)
                    except Exception:
                        return r.content[0].text
                # multi-block: parse each as JSON, return as list
                return [json.loads(c.text) for c in r.content]

            sel = await call("get_selection")
            print(f"get_selection: {sel}")

            nb = await call("get_neighbors", ref="build_execution_ir_from_raw")
            print(f"get_neighbors: callers={len(nb['callers'])} callees={len(nb['callees'])}")

            anc = await call("get_ancestors", ref="build_execution_ir_from_raw")
            print(f"get_ancestors: {len(anc)} nodes")

            desc = await call("get_descendants", ref="main", max_depth=1)
            print(f"get_descendants main d=1: {len(desc)} nodes")

            src = await call("get_source", ref="main")
            if src:
                print(f"get_source main: {len(src['body'])} chars at {src['abs_file']}:{src['line_start']}-{src['line_end']}")
            else:
                print("get_source main: None")

            grp = await call(
                "grep_source", pattern=r"json\.dumps|write_text", limit=5
            )
            print(f"grep_source writers (limit 5): {len(grp)}")

            srch = await call("search", query="overlay", limit=3)
            print(f"search overlay: {[h['qname'] for h in srch]}")

            # Edge cases
            bad = await call("get_node", ref="does_not_exist")
            print(f"get_node unknown: {bad}")

            empty = await call("search", query="")
            print(f"search empty: {empty}")

            # @flowcode: prefix canonicalization
            ns = await call("get_source", ref="@flowcode:main")
            print(f"get_source via @flowcode:main: {len(ns['body']) if ns else 0} chars")

            # set_selection (AI → viz)
            ss = await call("set_selection", ref="main")
            print(f"set_selection main: {ss}")
            ss = await call("set_selection", ref=None)
            print(f"set_selection unpin: {ss}")

            # similar (embedding cosine)
            sim = await call("similar", ref="main", limit=3)
            if sim is None:
                print("similar(main): None (embeddings.npz absent — rebuild graph to generate)")
            else:
                print(f"similar(main) top 3:")
                for s in sim:
                    print(f"  {s['similarity']:.3f}  {s['qname']}  ({s['file']})")


if __name__ == "__main__":
    asyncio.run(main())
