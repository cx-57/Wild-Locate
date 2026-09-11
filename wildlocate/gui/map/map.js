"use strict";

const map = L.map("map", {scrollWheelZoom: false, minZoom: 3, maxZoom: 18})
  .setView([42.2, -71.7], 7);
const pinIcon = L.divIcon({className: "location-pin", html: "<span></span>", iconSize: [32, 32], iconAnchor: [16, 16]});
let marker = null;
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
document.getElementById("reset").addEventListener("click", () => map.setView([42.2, -71.7], 7));

window.setLocationState = (state) => {
  enabled = state.enabled;
  document.body.setAttribute("aria-busy", String(!enabled));
  if (marker) { map.removeLayer(marker); marker = null; }
  // Mercator cannot display the poles; manual latitude remains unmodified.
  if (!Number.isFinite(state.latitude) || !Number.isFinite(state.longitude) || Math.abs(state.latitude) > 85.05112878) return;
  const latlng = L.latLng(state.latitude, state.longitude);
  marker = L.marker(latlng, {icon: pinIcon, draggable: enabled, title: "Selected location. Drag to move.", alt: "Selected habitat location"}).addTo(map);
  marker.on("dragend", () => selectLocation(marker.getLatLng()));
  if (state.recenter) map.panTo(latlng, {animate: false});
};

new QWebChannel(qt.webChannelTransport, (channel) => {
  bridge = channel.objects.locationBridge;
  bridge.mapReady();
  bridge.tilesAvailable(tilesAvailable);
});

// Qt resizes this view when the desktop switches between stacked and wide layouts.
new ResizeObserver(() => map.invalidateSize({pan: false})).observe(document.getElementById("map"));
