// The viewer consumes portable snapshots; it never reads repositories or runs code.
export const config = JSON.parse(document.getElementById('viewer-config')?.textContent || '{}');
const params = new URLSearchParams(location.search);
const projects = config.projects || [
  {id: 'flowcode', label: 'Flow-Code'}, {id: 'portfolio', label: 'This portfolio'},
  {id: 'scribblescan', label: 'ScribbleScan'},
];
export const project = projects.find(p => p.id === params.get('project')) || projects.find(p => p.id === config.project) || projects[0];
export const scope = params.get('scope') === 'overview' ? 'overview' : 'feature';
export function updateURL(values, navigate = false) {
  const url = new URL(location.href);
  for (const [key, value] of Object.entries(values)) {
    if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
  }
  if (navigate) location.assign(url); else history.replaceState(null, '', url);
}
const response = await fetch(params.get('example') === 'saved' ? 'graph.json' : `${config.dataRoot || 'maps'}/${project.id}.json`);
if (!response.ok) throw new Error('This code map is unavailable. Please return to the portfolio.');
export const snapshot = await response.json();
export const graph = snapshot.views ? snapshot.views[scope] : snapshot;
export const saved = !snapshot.views;
export const initialSelection = params.get('node');

export function setupSnapshotUI(selectFunction) {
  const projectPicker = document.getElementById('project-picker');
  for (const p of projects) projectPicker.add(new Option(p.label, p.id));
  projectPicker.value = project.id;
  projectPicker.addEventListener('change', () => updateURL({project: projectPicker.value, node: null}, true));
  const scopePicker = document.getElementById('scope-picker');
  scopePicker.value = scope;
  scopePicker.addEventListener('change', () => updateURL({scope: scopePicker.value}, true));
  document.querySelector('.graph-label').textContent = `Exploring ${project.label}`;
  document.querySelector('#legend small').textContent = 'A static code map · height shows traversal depth, not runtime';
  if (!saved) document.getElementById('alternate-layout-label').textContent = 'By file';
  const summary = document.getElementById('snapshot-summary');
  if (snapshot.analysis) {
    const a = snapshot.analysis;
    summary.textContent = `${a.files.length} files · ${a.function_count} functions in selected sources. Snapshot ${a.source_digest.slice(0, 12)}. Roots: ${a.source_roots.join(', ')}. ${a.known_limits.join(' ')} Excludes: ${[...a.excluded_directories, ...a.excluded_patterns].join(', ')}.`;
    const failed = a.files.filter(f => !f.analysis?.parse_ok).map(f => f.path);
    summary.textContent += failed.length ? ` Files that did not parse: ${failed.join(', ')}.` : ' All selected files parsed.';
  } else summary.textContent = 'The preserved 46-function Flow-Code example.';
  const returnLink = document.querySelector('.home-link');
  function setReturn() {
    const destination = new URL(config.returnTo || '/', location.origin);
    if (params.get('theme')) destination.searchParams.set('theme', params.get('theme'));
    returnLink.href = destination.pathname + destination.search;
    returnLink.querySelector('span').textContent = config.returnTo && config.returnTo !== '/' ? '↖ back to project' : '↖ portfolio';
    if (config.themes?.length) {
      const about = document.querySelector('.compare');
      const aboutURL = new URL(about.href);
      if (params.get('theme')) aboutURL.searchParams.set('theme', params.get('theme'));
      about.href = aboutURL.pathname + aboutURL.search;
    }
  }
  setReturn();
  window.addEventListener('flowcode-theme', e => {
    params.set('theme', e.detail.id);
    setReturn();
  });
  document.getElementById('share-map').addEventListener('click', async e => {
    // Copying is optional; the ordinary address bar always contains this view.
    try { await navigator.clipboard.writeText(location.href); e.target.textContent = 'Link copied'; }
    catch { window.prompt('Copy this map link', location.href); }
  });
  const evidence = document.getElementById('connection-evidence');
  return function showEvidence(node) {
    evidence.replaceChildren();
    if (!node || saved) return;
    const links = [
      ...graph.edges.filter(e => e.from === node.id || e.to === node.id),
      ...(node.boundaries || []),
    ];
    const byId = new Map(graph.nodes.map(n => [n.id, n]));
    for (const edge of links) {
      const other = byId.get(edge.from === node.id ? edge.to : edge.from);
      const item = document.createElement('li');
      const status = edge.confidence === 'resolved' ? 'Resolved' : edge.confidence === 'heuristic' ? 'Inferred' : edge.boundary_kind === 'external' ? 'External / outside scope' : 'Unresolved';
      const text = `${status} · ${edge.relation || edge.kind} · ${other?.label || edge.target || edge.to}`;
      if (other) {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'ink-link'; button.textContent = text;
        button.addEventListener('click', () => selectFunction(other.id)); item.append(button);
      } else item.append(document.createTextNode(text));
      const source = document.createElement('small');
      const loc = edge.callsite;
      source.textContent = `${loc?.path || node.file}:${loc?.line || '?'}${edge.evidence ? ' · ' + edge.evidence : ''}`;
      item.append(source); evidence.append(item);
    }
  };
}

export async function setupThemes(onChange) {
  const picker = document.getElementById('map-theme');
  const themes = config.themes || [];
  if (!themes.length) { picker.parentElement.hidden = true; return; }
  for (const theme of themes) picker.add(new Option(theme.label, theme.key));
  let request = 0;
  async function apply(id) {
    const ownRequest = ++request;
    const response = await fetch(`/_theme-packs/${encodeURIComponent(id)}.json`);
    if (!response.ok) throw new Error('Theme could not load');
    const pack = await response.json();
    if (request !== ownRequest) return;
    const v = pack.variables.board;
    const css = document.documentElement.style;
    const paper = v['nav-bg'];
    const rgb = v['board-bg-color'].match(/[a-f0-9]{2}/gi)?.map(n => parseInt(n, 16)) || [35, 59, 53];
    const light = rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722 > 145;
    const paperRGB = paper.match(/[a-f0-9]{2}/gi)?.map(n => parseInt(n, 16)) || [245, 238, 221];
    const darkPaper = paperRGB[0] * .2126 + paperRGB[1] * .7152 + paperRGB[2] * .0722 < 110;
    const colors = {board: v['board-bg-color'], chalk: light ? '#203840' : '#f3efe2', paper, ink: v['nav-ink'], red: darkPaper ? v['nav-ink'] : v.link,
      'font-body': v['font-expanded-text'], 'font-title': v['font-navbar']};
    for (const [key, value] of Object.entries(colors)) if (value) css.setProperty('--' + key, value);
    css.setProperty('--ok', light ? '#28563e' : '#a9cdb4');
    css.setProperty('--warn', light ? '#7a3820' : '#e7ae8a');
    css.setProperty('--accent', light ? '#58410a' : '#f0d982');
    css.setProperty('--map-backdrop', v['board-bg-image']);
    document.body.dataset.theme = id;
    // Same validated background assets as the board, now fixed behind the map.
    const background = document.getElementById('map-background');
    background.replaceChildren();
    for (const layer of pack.backgroundLayers) {
      const div = document.createElement('div');
      div.innerHTML = layer.svg; // Sanitized by the portfolio's ThemePackRegistry.
      background.append(div);
    }
    picker.value = id;
    document.getElementById('theme-error').textContent = '';
    updateURL({theme: id});
    onChange(v, id);
    window.dispatchEvent(new CustomEvent('flowcode-theme', {detail: {id}}));
  }
  picker.addEventListener('change', () => apply(picker.value).catch(() => {
    picker.value = document.body.dataset.theme;
    document.getElementById('theme-error').textContent = 'Theme unavailable; your current map is still here.';
  }));
  await apply(config.theme || 'canonical');
}
