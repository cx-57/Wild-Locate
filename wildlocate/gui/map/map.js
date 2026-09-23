"use strict";

const map = L.map("map", {scrollWheelZoom: false, minZoom: 3, maxZoom: 18})
  .setView([42.2, -71.7], 7);
const pinIcon = L.divIcon({className: "location-pin", html: "<span></span>", iconSize: [32, 32], iconAnchor: [16, 16]});
let marker = null;
const areaLayer = L.layerGroup().addTo(map);
let areaKey = null;
let regionCenter = [42.2, -71.7];
let bridge = null;
let enabled = true;
let tilesAvailable = false;
let tileErrors = false;

function reportTiles(available) {
  tilesAvailable = available;
  if (bridge) bridge.tilesAvailable(available);
}

const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  noWrap: true,
  keepBuffer: 0,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
});
tiles.on("loading", () => { tileErrors = false; });
tiles.on("tileerror", () => { tileErrors = true; reportTiles(false); });
tiles.on("load", () => reportTiles(!tileErrors));
tiles.addTo(map);

function selectLocation(latlng) {
  if (!enabled || !bridge) return;
  const latitude = Number(latlng.lat.toFixed(6));
  const longitude = Number(latlng.wrap().lng.toFixed(6));
  // Python owns the selection; it sends the accepted coordinates back to the pin.
  bridge.selectLocation(latitude, longitude);
}

map.on("click", (event) => selectLocation(event.latlng));
document.getElementById("reset").addEventListener("click", () => map.setView(regionCenter, 7));

window.setLocationState = (state) => {
  if (state.regionCenter) regionCenter = state.regionCenter;
  enabled = state.enabled;
  document.body.setAttribute("aria-busy", String(!enabled));
  if (marker) { map.removeLayer(marker); marker = null; }
  areaLayer.clearLayers();
  // Mercator cannot display the poles; manual latitude remains unmodified.
  if (!Number.isFinite(state.latitude) || !Number.isFinite(state.longitude) || Math.abs(state.latitude) > 85.05112878) return;
  const latlng = L.latLng(state.latitude, state.longitude);
  marker = L.marker(latlng, {icon: pinIcon, draggable: enabled, title: "Selected location. Drag to move.", alt: "Selected habitat location"}).addTo(map);
  marker.on("dragend", () => selectLocation(marker.getLatLng()));
  if (state.radiusKm) {
    const outline = L.circle(latlng, {radius: state.radiusKm * 1000, color: "#315b48", weight: 2, fillOpacity: 0.04, interactive: false}).addTo(areaLayer);
    const key = [state.latitude, state.longitude, state.radiusKm].join(",");
    if (key !== areaKey || state.recenter) map.fitBounds(outline.getBounds(), {padding: [15, 15], animate: false});
    areaKey = key;
    const colors = ["#b5423a", "#d88735", "#d5bb45", "#80a952", "#286648"];
    const points = state.areaPoints || [];
    if (points.length && marker) { map.removeLayer(marker); marker = null; }
    for (const point of points) {
      const ok = point.status === "ok";
      const color = ok ? colors[Math.min(4, Math.floor(point.percentile / 20))] : "#858585";
      const text = document.createElement("div");
      text.textContent = `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)} — ` +
        (ok ? `${point.category}: score ${point.score.toFixed(3)}, percentile ${point.percentile}` : "Unavailable: outside coverage or incomplete data");
      L.circleMarker([point.latitude, point.longitude], {radius: 3.5, color: color, weight: 0.5, fillColor: color, fillOpacity: 0.8, bubblingMouseEvents: false})
        .bindPopup(text).addTo(areaLayer);
    }
  } else {
    areaKey = null;
    if (state.recenter) map.panTo(latlng, {animate: false});
  }
};

new QWebChannel(qt.webChannelTransport, (channel) => {
  bridge = channel.objects.locationBridge;
  bridge.mapReady();
  bridge.tilesAvailable(tilesAvailable);
});

// Qt resizes this view when the desktop switches between stacked and wide layouts.
new ResizeObserver(() => map.invalidateSize({pan: false})).observe(document.getElementById("map"));
