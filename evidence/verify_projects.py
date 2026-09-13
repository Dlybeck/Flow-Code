"""Browser acceptance for real snapshots inside Portfolio; no service calls."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--origin', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
checks, errors = [], []


def check(label, condition):
    checks.append({'check': label, 'passed': bool(condition)})
    assert condition, label


with sync_playwright() as p:
    browser = p.chromium.launch(args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1440, 'height': 960})
    page.set_default_timeout(30000)
    page.on('pageerror', lambda error: errors.append(str(error)))

    def ready():
        page.wait_for_selector('body[data-ready="true"][data-renderer="webgl"]')
        page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')

    for project in ['portfolio', 'flowcode', 'scribblescan']:
        page.goto(args.origin + '/how-it-works?project=' + project, wait_until='domcontentloaded')
        ready()
        page.locator('#start-exploring').click()
        selection = page.locator('body').get_attribute('data-selected-node')
        check(project + ': entry selection', bool(selection))
        for layout in ['umap', 'fan']:
            page.locator('input[value="' + layout + '"]').check()
            check(project + ': ' + layout + ' finite layout', page.evaluate('Array.from(__debug.currentPositions.values()).flat().every(Number.isFinite)'))
            check(project + ': selection survives ' + layout, page.locator('body').get_attribute('data-selected-node') == selection)
        page.locator('#selected-info details').evaluate('(el) => el.open = true')
        check(project + ': source evidence', page.locator('#connection-evidence li').count() > 0)
        page.screenshot(path=str(args.output / (project + '-evidence.png')))
        page.reload(wait_until='domcontentloaded')
        ready()
        check(project + ': shared selection restores', page.locator('body').get_attribute('data-selected-node') == selection)
        page.locator('#scope-picker').select_option('overview')
        page.wait_for_url('**scope=overview*')
        ready()
        check(project + ': whole selected-source graph', page.evaluate('__debug.graph.nodes.length') > 100)
        check(project + ': selection survives scope change', page.locator('body').get_attribute('data-selected-node') == selection)
        page.locator('input[value="umap"]').check()
        check(project + ': whole graph by file', page.evaluate('Array.from(__debug.currentPositions.values()).flat().every(Number.isFinite)'))

    page.goto(args.origin + '/how-it-works?project=flowcode&from=/projects/flowcode', wait_until='domcontentloaded')
    ready()
    page.locator('#start-exploring').click()
    selected = page.locator('body').get_attribute('data-selected-node')
    ids = page.evaluate('__debug.graph.nodes.map(n => n.id)')
    themes = page.locator('#map-theme option').evaluate_all('(options) => options.map(o => o.value)')
    for theme in themes:
        page.set_viewport_size({'width': 1440, 'height': 960})
        page.locator('#map-theme').select_option(theme)
        page.wait_for_function('(id) => document.body.dataset.theme === id', arg=theme)
        page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
        check(theme + ': theme retains topology and selection', page.evaluate('__debug.graph.nodes.map(n => n.id)') == ids and page.locator('body').get_attribute('data-selected-node') == selected)
        page.screenshot(path=str(args.output / (theme + '-desktop.png')))
        page.set_viewport_size({'width': 390, 'height': 844})
        page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
        check(theme + ': phone has no horizontal overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        page.screenshot(path=str(args.output / (theme + '-phone.png')))
    page.locator('.home-link').click()
    page.wait_for_url('**/projects/flowcode?theme=vinyl')
    check('Return preserves project and selected theme', True)
    page.goto(args.origin + '/?theme=canonical')
    page.wait_for_function('window.themeEngine?.currentPack()?.id === "canonical"')
    page.locator('[data-code-map]').click()
    ready()
    check('Home opens Portfolio map', page.locator('#project-picker').input_value() == 'portfolio')
    page.goto(args.origin + '/projects/websites/scribblescan?theme=lily')
    page.frame_locator('.mini-window').locator('[data-code-map]').click()
    ready()
    check('ScribbleScan document opens its map and carries theme', page.locator('#project-picker').input_value() == 'scribblescan' and page.locator('body').get_attribute('data-theme') == 'lily')
    page.emulate_media(reduced_motion='reduce')
    page.goto(args.origin + '/how-it-works?project=flowcode')
    ready()
    check('Reduced motion disables orbit damping', page.evaluate('__debug.controls.enableDamping === false'))
    target = page.evaluate('''() => {
        for (const mesh of __debug.nodeById.values()) {
            const p = mesh.position.clone().project(__debug.camera);
            const x = (p.x + 1) * innerWidth / 2, y = (1 - p.y) * innerHeight / 2;
            if (Math.abs(p.z) <= 1 && document.elementFromPoint(x, y)?.tagName === 'CANVAS') return {x, y};
        }
    }''')
    check('A real function point is reachable', bool(target))
    page.mouse.click(target['x'], target['y'])
    check('Pointer selects a rendered function', bool(page.locator('body').get_attribute('data-selected-node')))
    before = page.evaluate('__debug.camera.position.toArray()')
    page.mouse.move(210, 370)
    page.mouse.wheel(0, -100)
    page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')
    check('Zoom changes the camera', page.evaluate('__debug.camera.position.toArray()') != before)
    page.locator('#reset-view').click()
    check('Reset clears the pinned selection', page.locator('body').get_attribute('data-selected-node') == '')
    page.locator('input[value="umap"]').check()
    page.reload()
    ready()
    check('Shared layout restores', page.evaluate('__debug.state.layout') == 'umap')
    fallback = browser.new_page(viewport={'width':390, 'height':844}, is_mobile=True, has_touch=True)
    fallback.add_init_script('''const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            return type.includes('webgl') ? null : original.call(this, type, ...args);
        };''')
    fallback.goto(args.origin + '/how-it-works?project=scribblescan&theme=planets')
    fallback.wait_for_selector('body[data-renderer="canvas2d"][data-theme="planets"]')
    fallback.locator('#start-exploring').tap()
    check('2D phone fallback retains selection and evidence', bool(fallback.locator('body').get_attribute('data-selected-node')) and fallback.locator('#connection-evidence li').count() > 0)
    fallback.screenshot(path=str(args.output / 'fallback-phone.png'))
    fallback.close()
    check('No uncaught browser errors', not errors)
    browser.close()

(args.output / 'receipt.json').write_text(json.dumps({'checks': checks, 'errors': errors}, indent=2))
print(json.dumps({'passed': len(checks), 'errors': errors}))
