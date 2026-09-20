// The viewer consumes portable snapshots; it never reads repositories or runs code.
export const config = JSON.parse(document.getElementById('viewer-config')?.textContent || '{}');
const params = new URLSearchParams(location.search);
const projects = config.projects || [{id: 'graph', label: 'Codebase'}];
export const project = projects.find(p => p.id === params.get('project')) || projects.find(p => p.id === config.project) || projects[0];
export const scope = params.get('scope') === 'overview' ? 'overview' : 'feature';
export function updateURL(values, navigate = false) {
  const url = new URL(location.href);
  for (const [key, value] of Object.entries(values)) {
    if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
  }
  if (navigate) location.assign(url); else history.replaceState(null, '', url);
}
const mapURL = params.get('example') === 'saved'
  ? 'graph.json'
  : config.mapUrl || `${config.dataRoot || 'maps'}/${project.id}.json`;
const response = await fetch(mapURL);
if (!response.ok) throw new Error(`This code map is unavailable (${response.status}).`);
export const snapshot = await response.json();
if (snapshot.views && !snapshot.analysis?.embedding) {
  throw new Error('This map needs a semantic rebuild before it can be displayed.');
}
export const graph = snapshot.views ? snapshot.views[scope] : snapshot;
export const saved = !snapshot.views;
export const initialSelection = params.get('node');

export function setupSnapshotUI(selectFunction) {
  const projectPicker = document.getElementById('project-picker');
  for (const p of projects) projectPicker.add(new Option(p.label, p.id));
  projectPicker.value = project.id;
  projectPicker.parentElement.hidden = projects.length < 2;
  projectPicker.addEventListener('change', () => updateURL({project: projectPicker.value, node: null}, true));
  const scopePicker = document.getElementById('scope-picker');
  const guide = saved ? null : snapshot.guide;
  if (guide) {
    scopePicker.querySelector('[value="feature"]').textContent = guide.title;
    document.querySelector('#empty-info h2').textContent = guide.title;
    document.querySelector('#empty-info p').textContent = guide.summary;
    document.getElementById('empty-info').classList.add('has-guide');
    document.getElementById('start-exploring').textContent = 'Start the source tour →';
  }
  scopePicker.value = scope;
  scopePicker.addEventListener('change', () => updateURL({scope: scopePicker.value}, true));
  document.querySelector('.graph-label').textContent = guide && scope === 'feature'
    ? `${project.label} · ${guide.title}` : `Exploring ${project.label}`;
  function explainLayout() {
    const layout = document.querySelector('input[name="layout"]:checked')?.value;
    const purposeHint = snapshot.analysis?.purpose
      ? 'closer to the human-written project purpose'
      : 'more distinctive, substantive, and connected in this codebase';
    document.querySelector('#legend small').textContent = layout === 'umap'
      ? `Nearby: similar code · Higher: ${purposeHint} · Height contrast expanded`
      : 'Follow calls downhill · Important functions descend gently, forming ridges · Height scaled to fit';
  }
  document.querySelectorAll('input[name="layout"]').forEach(r => r.addEventListener('change', explainLayout));
  queueMicrotask(explainLayout);
  const summary = document.getElementById('snapshot-summary');
  if (snapshot.analysis) {
    const a = snapshot.analysis;
    summary.textContent = `${a.embedding ? 'Precomputed locally with ' + a.embedding.model + ' @ ' + a.embedding.revision.slice(0, 12) + '. Flow-Code uses code vectors and deterministic analysis; no generative AI is required. Importance method: ' + a.terrain.method + '. Scores are relative to the selected project and are not measured business value. ' : ''}${a.files.length} files · ${a.function_count} functions in selected sources. Snapshot ${a.source_digest.slice(0, 12)}. Roots: ${a.source_roots.join(', ')}. ${a.known_limits.join(' ')} Excludes: ${[...a.excluded_directories, ...a.excluded_patterns].join(', ')}.`;
    if (a.purpose) summary.textContent = `Project purpose: ${a.purpose.text} ${summary.textContent}`;
    const failed = a.files.filter(f => !f.analysis?.parse_ok).map(f => f.path);
    summary.textContent += failed.length ? ` Files that did not parse: ${failed.join(', ')}.` : ' All selected files parsed.';
  } else summary.textContent = 'The preserved 46-function Flow-Code example.';
  const returnLink = document.querySelector('.home-link');
  function setReturn() {
    const destination = new URL(config.returnTo || config.homeUrl || './', location.href);
    if (params.get('theme')) destination.searchParams.set('theme', params.get('theme'));
    returnLink.href = destination.pathname + destination.search;
    returnLink.querySelector('span').textContent = config.returnLabel || (config.returnTo ? '↖ back to project' : '↖ visualizer');
    const about = document.querySelector('.compare');
    if (config.aboutUrl) {
      about.href = config.aboutUrl;
      about.hidden = false;
    } else if (config.themes?.length && new URL(about.href).origin === location.origin) {
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
  const tour = document.getElementById('source-tour');
  const tourNavigation = document.getElementById('tour-navigation');
  const previous = document.getElementById('tour-previous');
  const next = document.getElementById('tour-next');
  const restart = document.getElementById('tour-restart');
  const tourEvidence = document.getElementById('tour-evidence');
  let tourIndex = -1;
  function visitStop(index) {
    const stop = guide?.stops[index];
    if (!stop) return;
    selectFunction(stop.node);
    document.getElementById('info').scrollTop = 0;
  }
  previous.addEventListener('click', () => visitStop(tourIndex - 1));
  next.addEventListener('click', () => visitStop(tourIndex + 1));
  restart.addEventListener('click', () => visitStop(0));
  return function showEvidence(node) {
    evidence.replaceChildren();
    const similar = document.getElementById('similar-functions');
    similar.replaceChildren();
    tour.hidden = !node || !guide;
    tourIndex = guide?.stops.findIndex(stop => stop.node === node?.id) ?? -1;
    const stop = guide?.stops[tourIndex];
    tourNavigation.hidden = !stop;
    restart.hidden = !!stop;
    tourEvidence.hidden = !stop;
    if (stop) {
      document.getElementById('i-qname').textContent = stop.title;
      document.getElementById('i-desc').textContent = stop.summary;
      document.getElementById('tour-progress').textContent = `Source tour · ${tourIndex + 1} / ${guide.stops.length}`;
      previous.disabled = tourIndex === 0;
      next.disabled = tourIndex === guide.stops.length - 1;
      tourEvidence.textContent = stop.via
        ? `${stop.via.confidence === 'resolved' ? 'Resolved' : 'Inferred'} connection from the previous step`
        : 'An explanation of the source, not a recorded run';
    }
    if (!node || saved) return;
    const allNodes = new Map(snapshot.views.overview.nodes.map(n => [n.id, n]));
    for (const match of node.similar || []) {
      const other = allNodes.get(match.id);
      if (!other) continue;
      const item = document.createElement('li');
      const link = document.createElement('a');
      const url = new URL(location.href);
      url.searchParams.set('node', match.id);
      if (!graph.nodes.some(n => n.id === match.id)) url.searchParams.set('scope', 'overview');
      link.href = url.pathname + url.search;
      link.textContent = `${other.displayName || other.label} · ${(match.cosine * 100).toFixed(0)}% similarity`;
      link.title = `${other.file}:${other.location.start_line}. Cosine similarity, not a probability.`;
      item.append(link); similar.append(item);
    }
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
    const themeRoot = config.themeRoot || '/_theme-packs';
    const response = await fetch(`${themeRoot}/${encodeURIComponent(id)}.json`);
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
