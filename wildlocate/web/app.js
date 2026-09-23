'use strict';
const $ = id => document.getElementById(id);
let config, token, regional = true, busy = false, activeJob = null, result = null;
let revision = 0, started = 0, elapsedTimer = null;
let map = null, overlay = null;
const colors = ['#b5423a', '#d88735', '#d5bb45', '#80a952', '#286648'];
const number = value => Number.isFinite(value) ? value.toFixed(3) : '—';
const coords = (lat, lon) => `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? 'N' : 'S'} / ${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? 'E' : 'W'}`;

function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function selection() {
  if (!$('latitude').value.trim() || !$('longitude').value.trim()) throw Error('Enter both latitude and longitude.');
  const latitude = Number($('latitude').value), longitude = Number($('longitude').value);
  if (!Number.isFinite(latitude) || Math.abs(latitude) > 90 || !Number.isFinite(longitude) || Math.abs(longitude) > 180) throw Error('Latitude must be −90 to 90; longitude must be −180 to 180.');
  if (!$('species').value) throw Error('No bundled models are available for this state.');
  return {species: $('species').value, region: $('region').value, latitude, longitude, ...(regional ? {radius_km: Number($('radius').value)} : {})};
}
function setBusy(value) {
  busy = value;
  document.body.classList.toggle('busy', value);
  $('inputs').disabled = value || !config;
  $('analyze').disabled = value || !$('species').value;
  $('cancel').hidden = !value;
  $('cancel').disabled = !activeJob;
  if (elapsedTimer) clearInterval(elapsedTimer);
  elapsedTimer = null;
  if (value) {
    started = Date.now();
    const update = () => { $('status').textContent = `Analyzing habitat · ${Math.floor((Date.now() - started) / 1000)}s`; };
    update(); elapsedTimer = setInterval(update, 1000);
  }
}
function clearResult() {
  revision++;
  result = null;
  $('result').hidden = true; $('empty').hidden = false;
  $('scores').open = false; $('conditions').open = false;
  error('');
}
function draw(recenter = false) {
  const lat = Number($('latitude').value), lon = Number($('longitude').value);
  const valid = $('latitude').value.trim() && $('longitude').value.trim() && Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
  $('selected-location').textContent = valid ? coords(lat, lon) : 'Enter valid coordinates';
  if (!map) return;
  overlay.clearLayers();
  if (!valid || Math.abs(lat) > 85) return;
  const center = [lat, lon];
  if (regional) {
    const circle = L.circle(center, {radius: Number($('radius').value) * 1000, color: '#315b48', weight: 1.4, fillOpacity: .025, interactive: false}).addTo(overlay);
    if (recenter) map.fitBounds(circle.getBounds(), {padding: [24, 24], animate: false});
  } else if (recenter) map.setView(center, 11, {animate: false});
  const points = result ? (result.points || [{...result, status: 'ok'}]) : [];
  if (!points.length) {
    L.marker(center, {icon: L.divIcon({className: 'center-pin', iconSize: [15, 15], iconAnchor: [7.5, 7.5]})}).addTo(overlay);
  }
  for (const point of points) {
    const ok = point.status === 'ok';
    const color = ok ? colors[Math.min(4, Math.floor(point.percentile / 20))] : '#858585';
    const content = document.createElement('div');
    content.textContent = `${coords(point.latitude, point.longitude)} — ${ok ? `${point.category} · score ${number(point.score)} · percentile ${point.percentile}` : 'Unavailable: outside coverage or incomplete data'}`;
    L.circleMarker([point.latitude, point.longitude], {radius: regional ? 4 : 7, color, weight: .6, fillColor: color, fillOpacity: .85, bubblingMouseEvents: false}).bindPopup(content).addTo(overlay);
  }
}
function changed(recenter = false) {
  if (busy) return;
  clearResult(); draw(recenter);
  $('status').textContent = $('species').value ? 'Ready to explore.' : 'Choose a state with bundled models.';
}
function mode(value) {
  if (busy) return;
  regional = value;
  $('point-mode').setAttribute('aria-pressed', String(!value));
  $('area-mode').setAttribute('aria-pressed', String(value));
  $('radius-field').hidden = !value;
  changed(true);
}
function changeRegion() {
  const state = config.regions.find(r => r.code === $('region').value);
  $('species').replaceChildren(...state.species.map(name => new Option(name, name)));
  if (state.species.includes('Bobcat')) $('species').value = 'Bobcat';
  $('latitude').value = state.center[0]; $('longitude').value = state.center[1];
  $('species-note').textContent = state.species.length ? `${state.species.length} bundled species models available.` : 'No bundled models for this state. Custom models can be used in the desktop app.';
  $('analyze').disabled = !state.species.length;
  changed(true);
}
async function api(path, payload) {
  const response = await fetch(path, payload === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Wildlocate-Token': token}, body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok) {
    const failure = Error(data.error || 'Could not contact the local server.');
    failure.status = response.status;
    throw failure;
  }
  return data;
}
function metric(value, title) {
  const box = document.createElement('div'); box.className = 'metric';
  const strong = document.createElement('strong'); strong.textContent = value;
  const caption = document.createElement('span'); caption.textContent = title;
  box.append(strong, caption); $('metrics').append(box);
}
function showResult(data) {
  result = data;
  const area = data.analysis_type === 'regional';
  $('empty').hidden = true; $('result').hidden = false;
  $('result-kind').textContent = area ? 'REGIONAL ASSESSMENT' : 'POINT ASSESSMENT';
  $('result-title').textContent = area ? `${data.species} · ${data.radius_km} km radius` : data.species;
  $('metrics').replaceChildren();
  if (area) {
    metric(number(data.mean_score), 'Mean suitability score');
    metric(String(data.evaluated_points), 'Points scored');
    metric(`${data.grid_spacing_km} km`, 'Grid spacing');
    if (data.unavailable_points) metric(String(data.unavailable_points), 'Unavailable');
  } else {
    metric(number(data.score), 'Suitability score');
    metric(String(data.percentile), 'Percentile');
    metric(data.category, 'Habitat suitability');
  }
  $('result-note').textContent = `${data.model} · ${data.training_observations.toLocaleString()} training observations` + (area && !data.evaluated_points ? ' · No grid points could be evaluated. Try another location or a smaller radius.' : '');
  $('scores').hidden = !area; $('conditions').hidden = area;
  $('score-rows').replaceChildren(); $('feature-values').replaceChildren();
  for (const point of data.points || []) {
    const tr = document.createElement('tr'), ok = point.status === 'ok';
    for (const value of [coords(point.latitude, point.longitude), ok ? number(point.score) : '—', ok ? String(point.percentile) : '—', ok ? point.category : 'Unavailable']) {
      const td = document.createElement('td'); td.textContent = value; tr.append(td);
    }
    $('score-rows').append(tr);
  }
  for (const [name, value] of Object.entries(data.features || {})) {
    const term = document.createElement('dt'), detail = document.createElement('dd');
    term.textContent = name.replaceAll('_', ' '); detail.textContent = number(value);
    $('feature-values').append(term, detail);
  }
  $('status').textContent = 'Assessment complete. Select a map point for details.';
  draw();
}
async function poll(id, version) {
  if (activeJob !== id || revision !== version) return;
  try {
    const job = await api(`/api/jobs/${id}`);
    if (activeJob !== id || revision !== version) return;
    error('');
    if (job.status === 'running') { setTimeout(() => poll(id, version), 600); return; }
    activeJob = null; setBusy(false);
    if (job.status === 'complete') showResult(job.result);
    else if (job.status === 'cancelled') $('status').textContent = 'Analysis cancelled. Ready when you are.';
    else { error(job.error); $('status').textContent = 'Analysis unavailable.'; }
  } catch (exc) {
    if (activeJob !== id || revision !== version) return;
    if (exc.status && exc.status < 500) {
      activeJob = null; setBusy(false); error(exc.message);
      $('status').textContent = 'Analysis unavailable. Reload the page if the server restarted.';
      return;
    }
    // Retain the job ID and cancel button; a lost response doesn't stop the worker.
    error('Connection interrupted. Retrying; you can still cancel the analysis.');
    setTimeout(() => poll(id, version), 2000);
  }
}
$('analysis-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  let request;
  try { request = selection(); } catch (exc) { error(exc.message); return; }
  clearResult(); draw(); const version = revision;
  setBusy(true);
  try {
    const job = await api('/api/jobs', request);
    activeJob = job.id; $('cancel').disabled = false;
    poll(job.id, version);
  } catch (exc) { setBusy(false); error(exc.message); $('status').textContent = 'Could not start analysis.'; }
});
$('cancel').addEventListener('click', async () => {
  if (!activeJob) return;
  const id = activeJob;
  const version = ++revision; // Invalidate in-flight results immediately on cancellation intent.
  $('cancel').disabled = true;
  try {
    await api(`/api/jobs/${id}/cancel`, {});
    if (activeJob !== id) return;
    revision++; activeJob = null; setBusy(false); error('');
    $('status').textContent = 'Analysis cancelled. Ready when you are.';
  } catch (exc) {
    error(`Could not cancel: ${exc.message}`);
    if (activeJob === id) {
      $('cancel').disabled = false;
      poll(id, version);
    }
  }
});
$('export').addEventListener('click', () => {
  if (!result) return;
  const payload = {...result, note: 'Suitability is relative, not a probability of species presence.'};
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = `wild-locate-${result.species.toLowerCase().replaceAll(' ', '-')}.json`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$('point-mode').addEventListener('click', () => mode(false));
$('area-mode').addEventListener('click', () => mode(true));
$('region').addEventListener('change', changeRegion);
$('species').addEventListener('change', () => changed());
$('radius').addEventListener('change', () => changed(true));
for (const id of ['latitude', 'longitude']) {
  $(id).addEventListener('input', () => changed());
  $(id).addEventListener('change', () => draw(true));
}
$('reset-map').addEventListener('click', () => { if (config && map) map.setView(config.regions.find(r => r.code === $('region').value).center, 7); });
async function init() {
  if (window.L) {
    map = L.map('map', {scrollWheelZoom: false, minZoom: 3, maxZoom: 18}).setView([42.37, -72.28], 9);
    overlay = L.layerGroup().addTo(map);
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 18, noWrap: true, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
    tiles.on('tileerror', () => { $('map-status').hidden = false; $('map-status').textContent = 'Map tiles are unavailable. You can still enter coordinates and analyze habitat.'; });
    map.on('click', event => {
      if (busy) return;
      $('latitude').value = event.latlng.lat.toFixed(6); $('longitude').value = event.latlng.wrap().lng.toFixed(6); changed();
    });
    new ResizeObserver(() => map.invalidateSize({pan: false})).observe($('map'));
  } else {
    $('map-status').hidden = false; $('map-status').textContent = 'Map unavailable. Use manual coordinates below the location selector.';
    document.querySelector('.manual').open = true;
  }
  try {
    config = await api('/api/config'); token = config.token;
    $('region').replaceChildren(...config.regions.map(state => new Option(state.name, state.code)));
    $('inputs').disabled = false; changeRegion();
  } catch (exc) { error('Could not connect to Wild-Locate. Check that the terminal server is still running, then reload this page.'); }
}
init();
