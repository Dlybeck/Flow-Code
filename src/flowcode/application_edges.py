"""Source-backed application links. These are static hypotheses, not runtime calls.

Language adapters retain ordinary calls. This layer connects literal HTTP requests
and callback registrations without promoting framework inference to resolved facts.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from flowcode.sources import BROWSER_EXTENSIONS


def _walk(node):
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node, source):
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _string(node, source):
    if node is None:
        return None
    if node.type == "string":
        try:
            value = ast.literal_eval(_text(node, source))
            return value if isinstance(value, str) else None
        except (ValueError, SyntaxError):
            return None
    if node.type == "template_string":
        # Preserve interpolation as an unknown path component; never execute it.
        chunks = []
        cursor = node.start_byte + 1
        for child in node.named_children:
            if child.type == "template_substitution":
                chunks.append(source[cursor : child.start_byte].decode("utf-8"))
                chunks.append("{*}")
                cursor = child.end_byte
        chunks.append(source[cursor : node.end_byte - 1].decode("utf-8"))
        return "".join(chunks)
    return None


def _owner(functions, path, start, end):
    candidates = []
    for function in functions:
        loc = function["location"]
        if loc["path"] != path:
            continue
        lo = (loc["start_line"], loc.get("start_column", 1))
        hi = (loc["end_line"], loc.get("end_column", 1000000))
        if lo <= start and end <= hi:
            candidates.append(function)
    return min(
        candidates,
        key=lambda n: (
            n["location"]["end_line"] - n["location"]["start_line"],
            -len(n["label"]),
        ),
        default=None,
    )


def _resolve_callback(name, owner, functions):
    by_label = {
        n["label"]: n
        for n in functions
        if n["location"]["path"] == owner["location"]["path"]
    }
    scope = owner["label"].split(".")
    for length in range(len(scope), 0, -1):
        found = by_label.get(".".join(scope[:length] + [name]))
        if found:
            return found
    return None


def _python_routes(functions, trees):
    from flowcode.execution_ir.python_from_raw import _import_name_to_qual
    from flowcode.index import module_qualname_from_path

    routers = {}
    mounts = defaultdict(list)
    decorated = []

    def literal_prefix(call):
        keyword = next((k for k in call.keywords if k.arg == "prefix"), None)
        if keyword is None:
            return ""
        if isinstance(keyword.value, ast.Constant) and isinstance(
            keyword.value.value, str
        ):
            return keyword.value.value
        return None

    for path, tree in trees.items():
        module = module_qualname_from_path(Path(path))
        imports = _import_name_to_qual(tree, module)

        def qualified(expression):
            name = ast.unparse(expression)
            first, _, rest = name.partition(".")
            return imports.get(first, module + "." + first) + (
                "." + rest if rest else ""
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if ast.unparse(node.value.func).split(".")[-1] in {
                    "APIRouter",
                    "FastAPI",
                }:
                    prefix = literal_prefix(node.value)
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            routers[qualified(target)] = prefix
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "include_router"
                and node.args
            ):
                prefix = literal_prefix(node)
                mounts[qualified(node.args[0])].append(
                    (qualified(node.func.value), prefix)
                )
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = next(
                    (
                        f
                        for f in functions
                        if f["location"]["path"] == path
                        and f["location"]["start_line"] == node.lineno
                    ),
                    None,
                )
                if function is None:
                    continue
                for decorator in node.decorator_list:
                    if (
                        not isinstance(decorator, ast.Call)
                        or not isinstance(decorator.func, ast.Attribute)
                        or not decorator.args
                    ):
                        continue
                    method = decorator.func.attr.upper()
                    argument = decorator.args[0]
                    if (
                        method
                        not in {
                            "GET",
                            "POST",
                            "PUT",
                            "DELETE",
                            "PATCH",
                            "HEAD",
                            "OPTIONS",
                        }
                        or not isinstance(argument, ast.Constant)
                        or not isinstance(argument.value, str)
                    ):
                        continue
                    decorated.append(
                        (
                            function,
                            qualified(decorator.func.value),
                            method,
                            argument.value,
                            decorator.lineno,
                        )
                    )

    def prefixes(router, seen=frozenset()):
        if router in seen:
            return []
        own = routers.get(router, "")
        if own is None:
            return []
        if router not in mounts:
            return [own]
        return [
            base + prefix + own
            for parent, prefix in mounts[router]
            if prefix is not None
            for base in prefixes(parent, seen | {router})
        ]

    routes = []
    for function, router, method, path, line in decorated:
        if router not in routers:
            continue
        for prefix in sorted(set(prefixes(router))):
            route = {
                "method": method,
                "path": prefix.rstrip("/") + "/" + path.lstrip("/"),
                "node": function["id"],
                "source": function["location"]["path"],
                "line": line,
            }
            routes.append(route)
            function.setdefault("routes", []).append(
                {k: v for k, v in route.items() if k != "node"}
            )
    return routes


def _route_matches(route, path):
    pattern = re.sub(r"\{[^}]+:path\}", "\x01", route)
    pattern = re.sub(r"\{[^}]+\}", "\x00", pattern)
    pattern = re.escape(pattern).replace("\x00", "[^/]+").replace("\x01", ".+")
    return re.fullmatch(pattern, path) is not None


def _python_service_links(functions, trees, add):
    """Infer module-bound service methods; never claim runtime dispatch certainty."""
    from flowcode.execution_ir.python_from_raw import _import_name_to_qual
    from flowcode.index import module_qualname_from_path

    by_label = {f["label"]: f for f in functions}
    for path, tree in trees.items():
        module = module_qualname_from_path(Path(path))
        imports = _import_name_to_qual(tree, module)
        bindings = {}
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
            ):
                cls = imports.get(node.value.func.id, module + "." + node.value.func.id)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = cls
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for call in ast.walk(tree):
            if (
                not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Attribute)
                or not isinstance(call.func.value, ast.Name)
            ):
                continue
            cls = bindings.get(call.func.value.id)
            target = by_label.get(f"{cls}.{call.func.attr}") if cls else None
            if target is None:
                continue
            owner = _owner(
                functions,
                path,
                (call.lineno, call.col_offset + 1),
                (call.end_lineno, call.end_col_offset + 1),
            )
            if owner is None:
                continue
            # A local parameter/assignment can shadow the module service binding.
            enclosing = parents.get(call)
            while enclosing is not None and not isinstance(
                enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                enclosing = parents.get(enclosing)
            if enclosing and any(
                (isinstance(n, ast.arg) and n.arg == call.func.value.id)
                or (
                    isinstance(n, ast.Name)
                    and isinstance(n.ctx, ast.Store)
                    and n.id == call.func.value.id
                )
                for n in ast.walk(enclosing)
            ):
                continue
            parent = parents.get(call)
            async_task = isinstance(parent, ast.Call) and ast.unparse(parent.func) in {
                "asyncio.create_task",
                "asyncio.ensure_future",
            }
            add(
                owner,
                target,
                "calls",
                "async_dispatch" if async_task else "service_method",
                "module_constructor_binding",
                path,
                call.lineno,
            )


def attach_application_edges(graph: dict, raw: dict) -> None:
    root = Path(raw["root"])
    functions = [
        n for n in graph["nodes"] if n["kind"] == "function" and n.get("location")
    ]
    trees = {}
    browser_sources = []
    files = raw.get("files", [])
    for file in files:
        if not file.get("analysis", {}).get("parse_ok"):
            continue
        path = root / file["path"]
        try:
            source = path.read_bytes()
            if path.suffix == ".py":
                trees[file["path"]] = ast.parse(source)
            elif path.suffix in BROWSER_EXTENSIONS:
                browser_sources.append((file["path"], source))
        except (OSError, SyntaxError):
            continue
    routes = _python_routes(functions, trees)
    additions = []

    def add(owner, target, kind, relation, evidence, path, line, **details):
        identity = json.dumps(
            [owner["id"], target["id"], kind, relation, path, line],
            separators=(",", ":"),
        )
        additions.append(
            {
                "id": "application:"
                + hashlib.sha256(identity.encode()).hexdigest()[:20],
                "from": owner["id"],
                "to": target["id"],
                "kind": kind,
                "confidence": "heuristic",
                "relation": relation,
                "evidence": evidence,
                "callsite": {"path": path, "line": line, **details},
            }
        )

    _python_service_links(functions, trees, add)

    for path, source in browser_sources:
        from flowcode.execution_ir.typescript_from_raw import _get_parser

        tree = _get_parser(tsx=Path(path).suffix in {".jsx", ".tsx"}).parse(source)
        for call in _walk(tree.root_node):
            if call.type != "call_expression":
                continue
            callee = call.child_by_field_name("function")
            arguments = call.child_by_field_name("arguments")
            if callee is None or arguments is None:
                continue
            owner = _owner(
                functions,
                path,
                (call.start_point[0] + 1, call.start_point[1] + 1),
                (call.end_point[0] + 1, call.end_point[1] + 1),
            )
            if owner is None:
                continue
            name = _text(callee, source)
            args = [a for a in arguments.named_children if a.type != "comment"]
            line = call.start_point[0] + 1
            if name in {"fetch", "window.fetch"} and args:
                url = _string(args[0], source)
                if url is None or not url.startswith("/") or url.startswith("//"):
                    continue
                method = "GET"
                if len(args) > 1:
                    if args[1].type != "object":
                        continue
                    if any(
                        pair.type == "spread_element"
                        or (
                            pair.child_by_field_name("key") is not None
                            and pair.child_by_field_name("key").type
                            == "computed_property_name"
                        )
                        for pair in args[1].named_children
                    ):
                        continue
                    for pair in args[1].named_children:
                        key = pair.child_by_field_name("key")
                        if (
                            key is not None
                            and _text(key, source).strip("\"'") == "method"
                        ):
                            method = _string(pair.child_by_field_name("value"), source)
                    if method is None:
                        continue
                matching = {
                    r["node"]: r
                    for r in routes
                    if r["method"] == method.upper()
                    and _route_matches(r["path"], urlsplit(url).path)
                }
                if len(matching) == 1:
                    target = next(n for n in functions if n["id"] in matching)
                    add(
                        owner,
                        target,
                        "routes_to",
                        "http_request",
                        "template_http_route_match"
                        if "{*}" in url
                        else "literal_http_method_and_route_match",
                        path,
                        line,
                        url=url,
                        method=method.upper(),
                    )
            if name.endswith(".addEventListener") and len(args) >= 2:
                callback = args[1]
                if callback.type == "identifier":
                    target = _resolve_callback(
                        _text(callback, source), owner, functions
                    )
                else:
                    target = _owner(
                        functions,
                        path,
                        (callback.start_point[0] + 1, callback.start_point[1] + 1),
                        (callback.end_point[0] + 1, callback.end_point[1] + 1),
                    )
                if target is not None and target["id"] != owner["id"]:
                    add(
                        owner,
                        target,
                        "calls",
                        "event_callback",
                        "event_listener_registration",
                        path,
                        line,
                        event=_string(args[0], source),
                    )
    graph["edges"].extend(
        sorted({e["id"]: e for e in additions}.values(), key=lambda e: e["id"])
    )
    graph["entrypoints"] = sorted(
        set(graph["entrypoints"]) | {r["node"] for r in routes}
    )
    from flowcode.execution_ir.python_from_raw import _import_name_to_qual
    from flowcode.index import module_qualname_from_path

    by_id = {f["id"]: f for f in functions}
    modules = {module_qualname_from_path(Path(f["path"])) for f in files}
    imports = {
        path: _import_name_to_qual(tree, module_qualname_from_path(Path(path)))
        for path, tree in trees.items()
    }
    for edge in graph["edges"]:
        if edge["confidence"] != "unknown":
            continue
        owner = by_id.get(edge["from"])
        if owner is None:
            continue
        call = edge.get("callsite", {})
        name = call.get("callee_expression") or call.get("callee", "")
        reference = call.get("import_ref") or imports.get(
            owner["location"]["path"], {}
        ).get(name.split(".")[0])
        outside = bool(
            reference
            and not any(
                reference == module or reference.startswith(module + ".")
                for module in modules
            )
        )
        browser_runtime = owner["language"] in {
            "javascript",
            "typescript",
        } and name in {
            "fetch",
            "window.fetch",
            "setTimeout",
            "setInterval",
            "requestAnimationFrame",
            "queueMicrotask",
        }
        edge["boundary_kind"] = (
            "external" if outside or browser_runtime else "unresolved"
        )
    graph["analysis"] = {
        "completeness": "partial",
        "files": [
            {
                "path": f["path"],
                "sha256": f.get("sha256"),
                "analysis": f.get("analysis"),
            }
            for f in files
        ],
        "source_digest": hashlib.sha256(
            json.dumps(
                [
                    (f["path"], f.get("sha256"))
                    for f in sorted(files, key=lambda f: f["path"])
                ]
            ).encode()
        ).hexdigest(),
        "known_limits": [
            "Static analysis is not a runtime trace.",
            "Dynamic imports, values, framework mounting and runtime dispatch can remain unresolved.",
            "HTTP and event links are inferred from syntax and must not be treated as resolved calls.",
            "External marks an imported target outside selected source modules or a recognized browser API; other dynamic dispatch remains unresolved.",
        ],
    }
