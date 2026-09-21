from pathlib import Path

from flowcode import generate_graph


def graph(tmp_path: Path, source: str):
    (tmp_path / "app.py").write_text(source)
    return generate_graph(tmp_path, include_overlay=False)


def calls(document):
    return {
        (e["from"].removeprefix("py:fn:"), e["to"].removeprefix("py:fn:"))
        for e in document["edges"]
        if e["kind"] == "calls"
    }


def test_factory_inherited_method_and_literal_dispatch(tmp_path):
    doc = graph(
        tmp_path,
        """
class Base:
    def run(self):
        return self.send()
class Local(Base):
    def send(self):
        return 'ok'
def factory():
    providers = {'local': Local}
    return providers['local']()
class Worker:
    def __init__(self):
        self.provider = factory()
    def dispatch(self, operation):
        return getattr(self.provider, operation)()
    def start(self):
        return self.dispatch('run')
def main():
    worker = Worker()
    return worker.start()
""",
    )
    pairs = calls(doc)
    for pair in [
        ("app.main", "app.Worker.__init__"),
        ("app.main", "app.Worker.start"),
        ("app.Worker.start", "app.Worker.dispatch"),
        ("app.Worker.dispatch", "app.Base.run"),
        ("app.Base.run", "app.Local.send"),
    ]:
        assert pair in pairs
    inferred = [
        e for e in doc["edges"] if e.get("evidence") == "python_static_candidate"
    ]
    assert inferred and all(e["confidence"] == "heuristic" for e in inferred)


def test_unknown_receiver_is_not_matched_by_method_name(tmp_path):
    doc = graph(
        tmp_path,
        """
class A:
    def save(self): pass
def main(unknown):
    unknown.save()
""",
    )
    assert ("app.main", "app.A.save") not in calls(doc)
    assert any(e["confidence"] == "unknown" for e in doc["edges"])


def test_reassignment_kills_local_receiver(tmp_path):
    doc = graph(
        tmp_path,
        """
class A:
    def send(self): pass
def main(other):
    a = A()
    a = other
    a.send()
""",
    )
    assert ("app.main", "app.A.send") not in calls(doc)


def test_branch_receivers_are_alternatives_and_cycle_terminates(tmp_path):
    doc = graph(
        tmp_path,
        """
class A:
    def send(self): return self.send()
class B:
    def send(self): return 2
def main(flag):
    if flag: x = A()
    else: x = B()
    return x.send()
""",
    )
    assert ("app.main", "app.A.send") in calls(doc)
    assert ("app.main", "app.B.send") in calls(doc)


def test_static_and_inherited_constructor_across_import(tmp_path):
    (tmp_path / "worker.py").write_text("""
class Base:
    def __init__(self): self.ready()
    def ready(self): pass
class Worker(Base):
    @staticmethod
    def encode(): pass
""")
    doc = graph(
        tmp_path,
        """
from worker import Worker
def main():
    w = Worker()
    Worker.encode()
""",
    )
    assert ("app.main", "worker.Base.__init__") in calls(doc)
    assert ("app.main", "worker.Worker.encode") in calls(doc)


def test_static_and_class_methods_preserve_argument_binding(tmp_path):
    doc = graph(
        tmp_path,
        """
class A:
    def send(self): pass
class Factory:
    @classmethod
    def create(cls, item): return item
    @staticmethod
    def keep(item): return item
def main():
    Factory().keep(A()).send()
    Factory.create(A()).send()
""",
    )
    edges = [e for e in doc["edges"] if e["to"] == "py:fn:app.A.send"]
    assert {e["callsite"]["line"] for e in edges} == {10, 11}
    assert doc["analysis"]["candidate_analysis"]["python"]["converged"]


def test_shadowed_getattr_does_not_invent_dispatch(tmp_path):
    doc = graph(
        tmp_path,
        """
class A:
    def send(self): pass
def main(getattr):
    getattr(A(), 'send')()
""",
    )
    assert ("app.main", "app.A.send") not in calls(doc)


def test_module_initialization_has_entry_evidence(tmp_path):
    doc = graph(
        tmp_path,
        """
class Worker:
    def __init__(self): self.prepare()
    def prepare(self): pass
worker = Worker()
def main(): pass
""",
    )
    node = next(n for n in doc["nodes"] if n["id"] == "py:fn:app.Worker.__init__")
    assert node["id"] in doc["entrypoints"]
    assert "module_initialization_candidate" in node["entry_evidence"]


def test_future_local_assignment_does_not_use_global_receiver(tmp_path):
    doc = graph(
        tmp_path,
        """
class A:
    def send(self): pass
value = A()
def main(other):
    value.send()
    value = other
""",
    )
    assert ("app.main", "app.A.send") not in calls(doc)


def test_function_import_overrides_same_named_module_global(tmp_path):
    (tmp_path / "other.py").write_text("class Worker:\n    def send(self): pass\n")
    doc = graph(
        tmp_path,
        """
class A:
    def send(self): pass
Worker = A
def main():
    from other import Worker
    Worker().send()
""",
    )
    assert ("app.main", "other.Worker.send") in calls(doc)
    assert ("app.main", "app.A.send") not in calls(doc)
