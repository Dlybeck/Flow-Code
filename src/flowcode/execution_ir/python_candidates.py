"""Bounded, source-only candidate discovery for Python object calls.

This is a may-call analysis, not a Python interpreter or a runtime proof. It
propagates finite sets of local classes, functions and literal strings through
assignments, return values, fields and calls. All added edges are heuristic;
unknown callsite evidence is retained. No project code is imported or executed.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Value:
    kind: str
    name: str
    receiver: str = ""


class CandidateAnalysis:
    def __init__(self, modules, symbol_names):
        self.modules = modules
        self.symbol_names = symbol_names
        self.functions = {}
        self.classes = {}
        self.context = {}
        self.globals = defaultdict(dict)
        self.fields = defaultdict(set)
        self.returns = defaultdict(set)
        self.parameters = defaultdict(set)
        self.edges = set()
        self.startup_calls = set()
        self.changed = False
        self.rounds = 0
        self.converged = False
        for module, (tree, imports, definitions) in modules.items():
            self._collect(tree.body, module, module, imports, definitions, None)
        self.bases = {}
        for name, (node, module, imports) in self.classes.items():
            self.bases[name] = [
                self._qualified(base, module, imports) for base in node.bases
            ]

    def _collect(self, body, scope, module, imports, definitions, owner):
        for node in body:
            if isinstance(node, ast.ClassDef):
                name = scope + "." + node.name
                self.classes[name] = (node, module, imports)
                self._collect(node.body, name, module, imports, definitions, name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = definitions.get(node.lineno, scope + "." + node.name)
                if name in self.symbol_names:
                    self.functions[name] = node
                    self.context[name] = (module, imports, owner)
                self._collect(node.body, name, module, imports, definitions, None)
            else:
                # Definitions under guards/try blocks remain source candidates.
                for field in ("body", "orelse", "finalbody"):
                    self._collect(
                        getattr(node, field, []),
                        scope,
                        module,
                        imports,
                        definitions,
                        owner,
                    )
                for handler in getattr(node, "handlers", []):
                    self._collect(
                        handler.body, scope, module, imports, definitions, owner
                    )

    @staticmethod
    def _qualified(node, module, imports):
        try:
            name = ast.unparse(node)
        except (ValueError, TypeError):
            return ""
        head, sep, tail = name.partition(".")
        return imports.get(head, module + "." + head) + (sep + tail if sep else "")

    def _merge(self, mapping, key, values):
        old = mapping[key]
        new = old | values
        if new != old:
            mapping[key] = new
            self.changed = True

    def _method(self, cls, attr, seen=frozenset()):
        if cls in seen:
            return None
        name = cls + "." + attr
        if name in self.functions:
            return name
        # Multiple inheritance is deliberately left unresolved. Correct MRO
        # needs a separate analysis, not an arbitrary first matching method.
        bases = self.bases.get(cls, [])
        if len(bases) == 1:
            return self._method(bases[0], attr, seen | {cls})
        return None

    def _lookup(self, name, function, env, module, imports):
        if name in env:
            return env[name]
        if name in self.globals[module]:
            return self.globals[module][name]
        scope = function.rsplit(".", 1)[0] if function else module
        candidates = [imports[name]] if name in imports else []
        while scope:
            if scope not in self.classes:
                candidates.append(scope + "." + name)
            scope = scope.rpartition(".")[0]
        for target in candidates:
            if target in self.classes:
                return {Value("class", target)}
            if target in self.functions:
                return {Value("function", target)}
        if name in imports:
            return {Value("module", imports[name])}
        return set()

    def _attribute(self, values, attr):
        result = set()
        for value in values:
            if value.kind in {"instance", "class"}:
                result |= self.fields[value.name, attr]
                target = self._method(value.name, attr)
                if target:
                    decorators = {
                        ast.unparse(d) for d in self.functions[target].decorator_list
                    }
                    bound = (
                        value.name
                        if (value.kind == "instance" or "classmethod" in decorators)
                        and "staticmethod" not in decorators
                        else ""
                    )
                    result.add(Value("function", target, bound))
            elif value.kind == "module":
                target = value.name + "." + attr
                if target in self.classes:
                    result.add(Value("class", target))
                elif target in self.functions:
                    result.add(Value("function", target))
                else:
                    result.add(Value("module", target))
        return result

    def _call(self, values, args, keywords, caller, line):
        result = set()
        for value in values:
            if value.kind == "class":
                result.add(Value("instance", value.name))
                init = self._method(value.name, "__init__")
                if init:
                    self._call(
                        {Value("function", init, value.name)},
                        args,
                        keywords,
                        caller,
                        line,
                    )
            elif value.kind == "function" and value.name in self.functions:
                target = value.name
                if caller:
                    self.edges.add((caller, target, line))
                else:
                    self.startup_calls.add((target, line))
                fn = self.functions[target]
                params = [a.arg for a in fn.args.posonlyargs + fn.args.args]
                decorators = {ast.unparse(d) for d in fn.decorator_list}
                receiver_kind = "class" if "classmethod" in decorators else "instance"
                supplied = (
                    [{Value(receiver_kind, value.receiver)}] if value.receiver else []
                ) + args
                for param, arg in zip(params, supplied):
                    self._merge(self.parameters, (target, param), arg)
                for key, arg in keywords.items():
                    if key:
                        self._merge(self.parameters, (target, key), arg)
                result |= self.returns[target]
        return result

    def _expr(self, node, env, fn, module, imports):
        if node is None:
            return set()
        recur = lambda value: self._expr(value, env, fn, module, imports)
        if isinstance(node, ast.Name):
            return self._lookup(node.id, fn, env, module, imports)
        if isinstance(node, ast.Constant):
            return (
                {Value("string", node.value)} if isinstance(node.value, str) else set()
            )
        if isinstance(node, ast.Attribute):
            return self._attribute(recur(node.value), node.attr)
        if isinstance(node, ast.Call):
            args = [recur(arg) for arg in node.args]
            keywords = {kw.arg: recur(kw.value) for kw in node.keywords}
            builtin = (
                isinstance(node.func, ast.Name)
                and node.func.id not in env
                and node.func.id not in imports
                and node.func.id not in self.globals[module]
                and not recur(node.func)
            )
            if builtin and node.func.id == "getattr" and len(args) >= 2:
                result = set()
                for attr in args[1]:
                    if attr.kind == "string":
                        result |= self._attribute(args[0], attr.name)
                return result
            if builtin and node.func.id == "super" and fn and not args:
                owner = self.context[fn][2]
                bases = self.bases.get(owner, [])
                if len(bases) == 1:
                    return {Value("instance", bases[0])}
                return set()
            # A starred argument makes subsequent positional bindings unknown.
            first_star = next(
                (i for i, arg in enumerate(node.args) if isinstance(arg, ast.Starred)),
                len(args),
            )
            return self._call(
                recur(node.func), args[:first_star], keywords, fn, node.lineno
            )
        if isinstance(node, ast.Dict):
            # Factory dictionaries: values are possible alternatives, never a
            # claim that all providers run. Keys are not callable candidates.
            return {
                Value("collection", v.name, v.kind)
                for item in node.values
                for v in recur(item)
            }
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return {
                Value("collection", v.name, v.kind)
                for item in node.elts
                for v in recur(item)
            }
        if isinstance(node, ast.Subscript):
            recur(node.slice)
            return {
                Value(v.receiver, v.name)
                for v in recur(node.value)
                if v.kind == "collection"
            }
        if isinstance(node, ast.IfExp):
            recur(node.test)
            return recur(node.body) | recur(node.orelse)
        if isinstance(node, ast.Await):
            return recur(node.value)
        # Visit nested calls in expressions (operators, comprehensions, etc.)
        # without guessing the resulting object type.
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                recur(child)
        return set()

    def _assign(self, target, values, env, fn, module, imports):
        if isinstance(target, ast.Name):
            env[target.id] = values
        elif isinstance(target, ast.Attribute):
            for owner in self._expr(target.value, env, fn, module, imports):
                if owner.kind in {"class", "instance"}:
                    self._merge(self.fields, (owner.name, target.attr), values)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._assign(item, set(), env, fn, module, imports)

    def _body(self, body, env, fn, module, imports):
        expr = lambda node: self._expr(node, env, fn, module, imports)
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                from flowcode.execution_ir.python_from_raw import _import_name_to_qual

                bindings = _import_name_to_qual(
                    ast.Module(body=[node], type_ignores=[]), module
                )
                imports.update(bindings)
                for local, target in bindings.items():
                    kind = (
                        "class"
                        if target in self.classes
                        else "function"
                        if target in self.functions
                        else "module"
                    )
                    env[local] = {Value(kind, target)}
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = expr(node.value)
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                for target in targets:
                    self._assign(target, value, env, fn, module, imports)
            elif isinstance(node, ast.Return):
                value = expr(node.value)
                if fn:
                    self._merge(self.returns, fn, value)
            elif isinstance(node, ast.If):
                expr(node.test)
                left, right = dict(env), dict(env)
                self._body(node.body, left, fn, module, dict(imports))
                self._body(node.orelse, right, fn, module, dict(imports))
                for key in left.keys() | right.keys():
                    env[key] = left.get(key, set()) | right.get(key, set())
            else:
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.expr):
                        expr(child)
                # Conservatively merge alternatives in loops/try/with. This
                # analysis never claims that a branch was actually executed.
                branches = [
                    getattr(node, f, []) for f in ("body", "orelse", "finalbody")
                ]
                branches += [h.body for h in getattr(node, "handlers", [])]
                for branch in branches:
                    local = dict(env)
                    self._body(branch, local, fn, module, dict(imports))
                    for key, values in local.items():
                        env[key] = env.get(key, set()) | values

    @staticmethod
    def _local_bindings(body):
        names = set()
        stack = list(body)
        while stack:
            node = stack.pop()
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
            ):
                continue
            if isinstance(node, ast.Name) and isinstance(
                node.ctx, (ast.Store, ast.Del)
            ):
                names.add(node.id)
            stack.extend(ast.iter_child_nodes(node))
        return names

    def run(self):
        # A bounded fixed point covers factories returning providers, fields set
        # by constructors, and wrappers forwarding literal operation strings.
        for iteration in range(24):
            self.changed = False
            for module, (tree, imports, _) in self.modules.items():
                env = dict(self.globals[module])
                self._body(tree.body, env, None, module, dict(imports))
                if env != self.globals[module]:
                    self.globals[module] = env
                    self.changed = True
            for name, node in self.functions.items():
                module, imports, owner = self.context[name]
                params = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                env = {local: set() for local in self._local_bindings(node.body)}
                env.update({p.arg: set(self.parameters[name, p.arg]) for p in params})
                decorators = {ast.unparse(d) for d in node.decorator_list}
                if owner and params and "staticmethod" not in decorators:
                    kind = "class" if "classmethod" in decorators else "instance"
                    env[params[0].arg].add(Value(kind, owner))
                    # Inherited bodies may dispatch to source-defined overrides.
                    for cls in self.classes:
                        if self._method(cls, node.name) == name:
                            env[params[0].arg].add(Value(kind, cls))
                self._body(node.body, env, name, module, dict(imports))
            self.rounds = iteration + 1
            if not self.changed:
                self.converged = True
                break
        return sorted(self.edges)
