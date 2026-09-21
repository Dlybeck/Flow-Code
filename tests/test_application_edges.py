from pathlib import Path

from flowcode import generate_graph


def test_external_imports_and_unresolved_runtime_dispatch_stay_distinct(tmp_path):
    (tmp_path / "server.py").write_text("""import requests
def send(client):
    requests.post('/elsewhere')
    client.run()
""")
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    unknown = [e for e in graph["edges"] if e["confidence"] == "unknown"]
    assert {e["boundary_kind"] for e in unknown} == {"external", "unresolved"}


def test_literal_browser_request_links_to_matching_http_method_and_router_prefix(
    tmp_path: Path,
):
    (tmp_path / "server.py").write_text("""router = APIRouter(prefix="/api")
@router.post('/digitize')
async def digitize(): return "done"
@router.get('/digitize')
async def preview(): return "preview"
""")
    (tmp_path / "client.js").write_text("""async function submitDocument() {
  return fetch('/api/digitize', {method: 'POST'});
}
function boot() {
  document.addEventListener('click', submitDocument);
}
""")
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    routes = [e for e in graph["edges"] if e["kind"] == "routes_to"]
    assert len(routes) == 1
    edge = routes[0]
    assert edge["from"] == "ts:fn:client.submitDocument"
    assert edge["to"] == "py:fn:server.digitize"
    assert edge["confidence"] == "heuristic"
    assert edge["callsite"]["path"] == "client.js"
    assert edge["callsite"]["line"] == 2
    assert edge["evidence"] == "literal_http_method_and_route_match"
    callbacks = [e for e in graph["edges"] if e.get("relation") == "event_callback"]
    assert any(
        e["from"] == "ts:fn:client.boot"
        and e["to"] == "ts:fn:client.submitDocument"
        and e["confidence"] == "heuristic"
        for e in callbacks
    )


def test_template_routes_and_async_service_dispatch_keep_evidence(tmp_path):
    (tmp_path / "server.py").write_text("""router = APIRouter()
class DemoService:
    async def process(self): return "done"
demo_service = DemoService()
@router.post('/demo/{task_id}')
async def digitize():
    asyncio.create_task(demo_service.process())
""")
    (tmp_path / "client.js").write_text("""async function submit(id) {
  return fetch(`/demo/${id}`, {method: 'POST'});
}""")
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    links = [e for e in graph["edges"] if e.get("relation") == "http_request"]
    assert len(links) == 1
    assert links[0]["evidence"] == "template_http_route_match"
    dispatch = [e for e in graph["edges"] if e.get("relation") == "async_dispatch"]
    assert len(dispatch) == 1
    assert dispatch[0]["to"] == "py:fn:server.DemoService.process"
    assert dispatch[0]["confidence"] == "heuristic"
    assert dispatch[0]["callsite"]["line"] == 7


def test_ambiguous_and_dynamic_http_requests_are_not_presented_as_routes(tmp_path):
    (tmp_path / "server.py").write_text("""router = APIRouter()
@router.get('/same')
def first(): pass
@router.get('/same')
def second(): pass
dynamic = APIRouter(prefix=PREFIX)
@dynamic.get('/hidden')
def hidden(): pass
@router.get('/unique')
def unique(): pass
""")
    (tmp_path / "client.js").write_text("""function requests() {
fetch('/same'); fetch('https://elsewhere.test/same'); fetch('/hidden');
fetch('/same', options);
fetch('/unique', {...options});
}""")
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    assert not [e for e in graph["edges"] if e["kind"] == "routes_to"]


def test_express_route_callback_links_to_literal_browser_request(tmp_path: Path):
    (tmp_path / "server.js").write_text(
        """const express = require('express');
const app = express();
app.get('/reservations', async (req, res) => {
  return Reservation.find();
});
"""
    )
    (tmp_path / "client.js").write_text(
        """async function loadReservations() {
  return fetch('/reservations');
}
"""
    )
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    route_node = next(
        node for node in graph["nodes"] if node.get("routes")
    )
    assert route_node["routes"] == [
        {
            "method": "GET",
            "path": "/reservations",
            "source": "server.js",
            "line": 3,
        }
    ]
    assert route_node["id"] in graph["entrypoints"]
    edge = next(edge for edge in graph["edges"] if edge["kind"] == "routes_to")
    assert edge["from"] == "ts:fn:client.loadReservations"
    assert edge["to"] == route_node["id"]
    assert edge["confidence"] == "heuristic"


def test_non_express_get_with_a_literal_path_is_not_a_server_route(tmp_path: Path):
    (tmp_path / "client.js").write_text(
        """const cache = new Map();
function callback() { return 1; }
cache.get('/reservations', callback);
$.get('/users', callback);
"""
    )
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    assert not [node for node in graph["nodes"] if node.get("routes")]


def test_express_route_receiver_respects_function_scope(tmp_path: Path):
    (tmp_path / "server.js").write_text(
        """const express = require('express');
const app = express();
function registerFake(app) {
  app.get('/fake', callback);
}
function callback() { return 1; }
app.get('/real', callback);
"""
    )
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    routes = [route for node in graph["nodes"] for route in node.get("routes", [])]
    assert [route["path"] for route in routes] == ["/real"]


def test_express_route_receiver_respects_catch_scope(tmp_path: Path):
    (tmp_path / "server.js").write_text(
        """const express = require('express');
const app = express();
function callback() { return 1; }
try { throw new Error('demo'); }
catch (app) { app.get('/fake', callback); }
app.get('/real', callback);
"""
    )
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    routes = [route for node in graph["nodes"] for route in node.get("routes", [])]
    assert [route["path"] for route in routes] == ["/real"]


def test_express_route_receiver_is_invalid_after_reassignment(tmp_path: Path):
    (tmp_path / "server.js").write_text(
        """const express = require('express');
let app = express();
function callback() { return 1; }
app = new Map();
app.get('/fake', callback);
"""
    )
    graph = generate_graph(tmp_path, include_overlay=False, use_llm=False)
    assert not [node for node in graph["nodes"] if node.get("routes")]
