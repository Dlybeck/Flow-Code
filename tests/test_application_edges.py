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
