"""Browser acceptance for the reskin and its preserved upstream comparison."""
import hashlib
import json
import math
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path('/out')
URL = 'http://100.118.63.4:8096/'
report = {'checks': [], 'browser': 'Chromium with SwiftShader WebGL2', 'status': 'running'}

def check(name, condition, **details):
    assert condition, name
    report['checks'].append({'name': name, **details})

def snapshot(page):
    result = page.evaluate('''() => {
      const {scene, terrainMesh} = window.__debug;
      const terrain = {positions: Array.from(terrainMesh.geometry.attributes.position.array), indices: Array.from(terrainMesh.geometry.index.array)};
      const nodes = scene.children.filter(x => x.userData.node).map(x => ({id:x.userData.node.id, position:x.position.toArray()})).sort((a,b)=>a.id.localeCompare(b.id));
      const edges = scene.children.filter(x => x.userData.edge).map(x => {
        let points;
        if(x.isLine2) {
          const a=x.geometry.attributes.instanceStart,b=x.geometry.attributes.instanceEnd;
          points=[a.getX(0),a.getY(0),a.getZ(0)];
          for(let i=0;i<b.count;i++)points.push(b.getX(i),b.getY(i),b.getZ(i));
        } else points=Array.from(x.geometry.attributes.position.array);
        return {edge:x.userData.edge,points};
      });
      return {terrain,nodes,edges};
    }''')
    assert len(result['nodes']) == 46, 'Scene must contain all functions, not a stale disposed mesh'
    assert len(result['edges']) == 49, 'Scene must contain all call edges'
    assert all(isinstance(x, (int,float)) and math.isfinite(x) for x in result['terrain']['positions']), 'Terrain coordinates must be finite'
    return result

def wait_frame(page):
    page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    try:
        all_errors = []
        external_requests = []
        def new_page(**options):
            page = browser.new_page(**options)
            page.set_default_timeout(10000)
            page.on('pageerror', lambda e: all_errors.append(str(e)))
            page.on('console', lambda m: all_errors.append(m.text) if m.type == 'error' else None)
            page.on('requestfailed', lambda r: all_errors.append(f'{r.url}: {r.failure}'))
            page.on('request', lambda r: external_requests.append(r.url) if not r.url.startswith(URL) else None)
            return page

        original = new_page(viewport={'width':1440,'height':960})
        original.goto(URL+'original.html', wait_until='networkidle')
        original.wait_for_function('window.__debug && window.__debug.scene.children.filter(x=>x.userData.node).length===46')
        original_fan = snapshot(original)
        original.close()

        page = new_page(viewport={'width':1440,'height':960})
        page.goto(URL, wait_until='networkidle')
        page.wait_for_selector('body[data-renderer="webgl"][data-ready="true"]')
        current_fan = snapshot(page)
        check('Exact upstream terrain, node positions and edge paths: call layout', current_fan == original_fan,
              nodes=len(current_fan['nodes']), edges=len(current_fan['edges']), triangles=len(current_fan['terrain']['indices'])//3)
        report['fan_geometry_sha256'] = hashlib.sha256(json.dumps(current_fan,sort_keys=True).encode()).hexdigest()
        page.screenshot(path=str(OUT/'reskin-desktop.png'))

        page.locator('#start-exploring').click()
        root = page.evaluate('window.__debug.graph.peaks[0]')
        check('Entry point button selects the real root', page.locator('body').get_attribute('data-selected-node') == root)
        page.mouse.move(10,400)
        check('Selection persists after pointer leaves', page.locator('body').get_attribute('data-selected-node') == root and page.locator('#selected-info').is_visible())
        wait_frame(page)
        page.screenshot(path=str(OUT/'reskin-selected.png'))
        check('Selected node label follows the actual function', page.locator('#node-label').is_visible() and page.locator('#node-label').inner_text() == root)

        page.locator('input[value="umap"]').check()
        current_umap = snapshot(page)
        check('Similarity layout renders all real connections with valid new terrain',
              [e['edge'] for e in current_umap['edges']] == [e['edge'] for e in original_fan['edges']] and current_umap['terrain'] != current_fan['terrain'],
              triangles=len(current_umap['terrain']['indices'])//3)
        check('Selection survives layout change', page.locator('body').get_attribute('data-selected-node') == root)
        page.locator('#clear-selection').click()
        check('Clear selection restores browse state', page.locator('#empty-info').is_visible() and page.locator('body').get_attribute('data-selected-node') == '')
        wait_frame(page)
        page.screenshot(path=str(OUT/'reskin-similarity.png'))

        page.locator('input[value="fan"]').check()
        # Click the projected centre of the actual root sphere, without debug selection.
        point = page.evaluate('''() => {const d=window.__debug;d.camera.updateMatrixWorld();const v=d.nodeById.get(d.graph.peaks[0]).position.clone().project(d.camera);return {x:(v.x+1)*innerWidth/2,y:(1-v.y)*innerHeight/2};}''')
        page.mouse.click(point['x'],point['y'])
        check('Clicking the 3D sphere selects its function', page.locator('body').get_attribute('data-selected-node') == root)

        before = page.evaluate('window.__debug.camera.position.toArray()')
        page.mouse.move(1000,650)
        page.mouse.down()
        page.mouse.move(1090,680,steps=12)
        page.mouse.up()
        wait_frame(page)
        after = page.evaluate('window.__debug.camera.position.toArray()')
        check('Dragging rotates the real camera without clearing selection', before != after and page.locator('body').get_attribute('data-selected-node') == root)
        page.mouse.wheel(0,-200)
        wait_frame(page)
        check('Wheel zoom changes camera distance', page.evaluate('window.__debug.camera.position.toArray()') != after)
        page.locator('#reset-view').click()
        check('Reset clears selection and restores framing', page.locator('body').get_attribute('data-selected-node') == '' and all(abs(a-b)<0.01 for a,b in zip(before,page.evaluate('window.__debug.camera.position.toArray()'))))
        picker = page.locator('#function-picker')
        picker.focus()
        picker.press('Home')
        picker.press('ArrowDown')
        picker.press('Enter')
        check('Keyboard can select a function', bool(page.locator('body').get_attribute('data-selected-node')))
        check('Function picker includes the complete graph', page.locator('#function-picker option').count() == 47)
        page.close()

        for width,height in [(390,844),(360,740),(1024,768)]:
            phone = width < 600
            page = new_page(viewport={'width':width,'height':height},is_mobile=phone,has_touch=phone)
            page.goto(URL,wait_until='networkidle')
            page.wait_for_selector('body[data-renderer="webgl"][data-ready="true"]')
            check(f'UI fits {width}x{height}', page.evaluate('''() => [...document.querySelectorAll('[data-ui]')].every(x=>{const r=x.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;})'''))
            page.screenshot(path=str(OUT/f'reskin-{width}x{height}.png'))
            if phone:
                point=page.evaluate('''() => {const d=window.__debug;d.camera.updateMatrixWorld();const v=d.nodeById.get(d.graph.peaks[0]).position.clone().project(d.camera);return {x:(v.x+1)*innerWidth/2,y:(1-v.y)*innerHeight/2};}''')
                page.touchscreen.tap(point['x'],point['y'])
                check(f'Touch selects actual 3D function at {width}x{height}', page.locator('body').get_attribute('data-selected-node') == root)
                page.locator('#clear-selection').tap()
                page.locator('#function-picker').select_option(root)
                check(f'Function picker works at {width}x{height}', page.locator('body').get_attribute('data-selected-node') == root)
            page.close()

        page = new_page(viewport={'width':1440,'height':960},reduced_motion='reduce')
        page.goto(URL,wait_until='networkidle')
        page.wait_for_selector('body[data-ready="true"]')
        check('Reduced motion disables camera damping', page.evaluate('window.__debug.controls.enableDamping === false'))
        page.close()

        page = new_page(viewport={'width':1440,'height':960})
        page.add_init_script('''const originalGetContext=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){if(type.includes('webgl'))return null;return originalGetContext.call(this,type,...args);};''')
        page.goto(URL,wait_until='networkidle')
        page.wait_for_selector('body[data-renderer="canvas2d"][data-ready="true"]')
        check('Unsupported WebGL keeps the existing 2D graph available', not page.locator('#load-error').is_visible() and not page.locator('#controls').is_visible())
        page.screenshot(path=str(OUT/'fallback-desktop.png'))
        page.close()
        report['browser_errors'] = all_errors
        check('No browser errors or failed requests', not all_errors, errors=all_errors)
        check('No third-party runtime requests', not external_requests, requests=external_requests)
        report['status']='passed'
    except Exception as error:
        report['status']='failed'
        report['error']=str(error)
        raise
    finally:
        (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
        browser.close()
