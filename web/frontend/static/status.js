// --------------------
// CONFIG & STATE
// --------------------

let map, hoverPopup;
const vessels = {}; // Collection of vessel objects keyed by ID

// Default route for visual reference
const routeCoords = [
  { lat: 50.36549641988576, lng: -4.164723457671051 }, // Stonehouse
  { lat: 50.36086978940922, lng: -4.174937309091103 }  // Cremyll
];

const toLngLat = p => [p.lng, p.lat];

// --------------------
// UI HELPERS
// --------------------

const getStatusTheme = (status) => {
  const themes = {
    in_transit: { label: "In Transit", cls: "green" },
    docked: { label: "Docked", cls: "amber" },
    delayed: { label: "Delayed", cls: "red" }
  };
  return themes[status] || themes.in_transit;
};

function formatHeading(deg) {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const idx = Math.round((deg % 360) / 45) % 8;
  return `${Math.round(deg)}° (${dirs[idx]})`;
}

function calculateBearing(start, end) {
  const toRad = d => (d * Math.PI) / 180;
  const toDeg = r => (r * 180) / Math.PI;
  const lon1 = toRad(start[0]), lat1 = toRad(start[1]);
  const lon2 = toRad(end[0]), lat2 = toRad(end[1]);
  const dLon = lon2 - lon1;
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  return (toDeg(Math.atan2(y, x)) + 360) % 360;
}

function getFitPadding() {
  const isMobile = window.innerWidth <= 720;
  return isMobile 
    ? { top: 120, bottom: 40, left: 40, right: 40 } 
    : { top: 120, bottom: 100, left: 380, right: 60 };
}

function fitAllVessels() {
  if (!map) return;

  const bounds = new maplibregl.LngLatBounds();

  // 1. Include the static route coordinates
  routeCoords.forEach(p => bounds.extend([p.lng, p.lat]));

  // 2. Include all active vessel positions
  const activeVessels = Object.values(vessels);
  activeVessels.forEach(v => {
    bounds.extend([v.lng, v.lat]);
  });

  // 3. Fit the map to these bounds
  // Padding helps keep markers away from the UI overlays (sidebar/header)
  map.fitBounds(bounds, {
    padding: getFitPadding(),
    maxZoom: 16, // Prevents zooming in too far if there's only one point
    duration: 1000 // Smooth animation
  });
}

// --------------------
// CORE LOGIC: DATA SYNC
// --------------------

/**
 * Updates or creates a vessel and syncs it to the Map and Sidebar
 */
let hasInitialFit = false;

function syncVesselData(id, lat, lng, extra = {}) {
  // 1. Initialize vessel if new
  if (!vessels[id]) {
    vessels[id] = {
      id: id,
      name: extra.name || id.replace(/-/g, ' ').toUpperCase(),
      route: extra.route.uuid ? `${extra.route.origin} ↔ ${extra.route.destination}` : "No Route",
      status: extra.status || "in_transit",
      speed: 0,
      heading: 0,
      lat: lat,
      lng: lng,
      marker: null,
      lastUpdated: null
    };
  }

  const v = vessels[id];

  // 2. Update movement logic
  if (v.lat !== lat || v.lng !== lng) {
    v.heading = calculateBearing([v.lng, v.lat], [lng, lat]);
  }

  v.lat = lat;
  v.lng = lng;
  v.speed = extra.speed || 8.0;
  v.lastUpdated = new Date().toLocaleTimeString();

  const now = new Date();
  const timestamp = now.toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit' 
  });
  v.lastUpdated = timestamp;

  // 3. Update the Top Bar Status Text
  const statusEl = document.getElementById("statusText");
  if (statusEl) {
    statusEl.innerHTML = `Status: <span style="color: var(--green)">Live</span> • Last update: ${timestamp}`;
  }

  // 3. Sync with Map (if map is ready)
  if (map) {
    if (!v.marker) {
      v.marker = createVesselMarker(v);
    }
    v.marker.setLngLat([lng, lat]);
    if (!hasInitialFit) {
      fitAllVessels();
      hasInitialFit = true;
    }
  }

  // 4. Update UI
  renderSidebar();
}

/**
 * Create a physical marker on the map for a specific vessel
 */
function createVesselMarker(v) {
  const el = document.createElement('div');
  el.className = `boat-marker ${v.status}`;

  const marker = new maplibregl.Marker({ element: el })
    .setLngLat([v.lng, v.lat])
    .addTo(map);

  el.addEventListener("mouseenter", () => showBoatPopup(v));
  el.addEventListener("mouseleave", () => hoverPopup.remove());
  el.addEventListener("click", (e) => {
    e.stopPropagation();
    focusVessel(v.id);
  });

  return marker;
}

// --------------------
// UI RENDERING
// --------------------

function renderSidebar() {
  const vesselList = document.getElementById("vesselList");
  if (!vesselList) return;

  vesselList.innerHTML = "";

  Object.values(vessels).forEach(v => {
    const theme = getStatusTheme(v.status);
    const card = document.createElement("div");
    card.className = "vessel-card";
    card.innerHTML = `
      <div class="vessel-top">
        <div class="vessel-name">${v.name}</div>
        <div class="pill ${theme.cls}">${theme.label}</div>
      </div>
      <div class="vessel-sub">${v.route}</div>
      <div class="vessel-meta">
        <div>${v.speed.toFixed(1)} kts</div>
        <div>${formatHeading(v.heading)}</div>
        <div style="color: var(--muted)">Updated ${v.lastUpdated}</div>
      </div>
    `;
    card.addEventListener("click", () => focusVessel(v.id));
    vesselList.appendChild(card);
  });
}

function showBoatPopup(v) {
  const html = `
    <div class="popup-title">${v.name}</div>
    <div class="popup-row"><span class="popup-muted">Speed</span> <span>${v.speed.toFixed(1)} kts</span></div>
    <div class="popup-row"><span class="popup-muted">Dir</span> <span>${formatHeading(v.heading)}</span></div>
  `;
  hoverPopup.setLngLat([v.lng, v.lat]).setHTML(html).addTo(map);
}

function focusVessel(id) {
  const v = vessels[id];
  if (!map || !v) return;

  map.flyTo({
    center: [v.lng, v.lat],
    zoom: 16,
    speed: 1.2,      
    curve: 1.42,     
    padding: getFitPadding(),
  });
}

// --------------------
// MAP INITIALIZATION
// --------------------

function initMap() {
  map = new maplibregl.Map({
    container: 'map',
    style: 'https://tiles.stadiamaps.com/styles/osm_bright.json',
    center: [routeCoords[0].lng, routeCoords[0].lat],
    zoom: 14,
    dragRotate: false
  });

  hoverPopup = new maplibregl.Popup({ closeButton: false, offset: 14 });

  map.on('load', () => {
    // Shared Route Line
    map.addSource('route', {
      type: 'geojson',
      data: {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: routeCoords.map(toLngLat) }
      }
    });

    map.addLayer({
      id: 'route-line',
      type: 'line',
      source: 'route',
      paint: { 'line-color': '#5aa7ff', 'line-width': 4 }
    });

    // Handle any vessels that were loaded via WS before the map was ready
    Object.values(vessels).forEach(v => {
      if (!v.marker) v.marker = createVesselMarker(v);
    });

    // Map Controls
    document.getElementById("btnZoomIn")?.addEventListener("click", () => map.zoomIn());
    document.getElementById("btnZoomOut")?.addEventListener("click", () => map.zoomOut());
    document.getElementById("btnRecenter")?.addEventListener("click", () => {
      fitAllVessels();
    });
  });
}

// --------------------
// WEBSOCKET LOGIC
// --------------------

function TrackerWS({ onUpdate, onStatus, onError }) {
  let ws = null;
  let subscribedIds = [];

  const connect = () => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/api/v1/entities/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      onStatus({ type: "connected" });
      if (subscribedIds.length) subscribe(subscribedIds);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        // Initial snapshot
        if (msg.status === "subscribed" && msg.entities) {
          Object.entries(msg.entities).forEach(([id, data]) => {
            onUpdate(id, data.last_location.lat, data.last_location.lng, data);
          });
        }
        // Live updates
        else if (msg.type === "update" && msg.data) {
          const { entity_id, latitude, longitude, extra } = msg.data;
          onUpdate(entity_id, latitude, longitude, extra);
        }
      } catch (e) {
        onError(e);
      }
    };

    ws.onclose = () => {
      onStatus({ type: "disconnected" });
      setTimeout(connect, 5000); // Reconnect loop
    };
  };

  const subscribe = (ids) => {
    subscribedIds = ids;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "subscribe", entity_ids: ids }));
    } else if (!ws) {
      connect();
    }
  };

  return { subscribe };
}

// --------------------
// BOOTSTRAP
// --------------------

document.addEventListener('DOMContentLoaded', () => {
  // 1. Setup UI Clock
  const updateClock = () => {
    const now = new Date();
    const clockEl = document.getElementById("clockText");
    if (clockEl) clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };
  updateClock();
  setInterval(updateClock, 10000);

  // 2. Init Map
  initMap();

  // 3. Init Tracker
  const tracker = TrackerWS({
    onUpdate: (id, lat, lng, extra) => syncVesselData(id, lat, lng, extra),
    onStatus: (s) => console.log("Tracker:", s),
    onError: (e) => console.error("Tracker Error:", e)
  });

  // 4. Subscribe based on URL or defaults
  const pathParts = window.location.pathname.split("/");
  const entityId = pathParts[pathParts.length - 1];

  // If the URL has a specific ID, use it, otherwise subscribe to a default set
  const initialSubs = (entityId && entityId !== "map") ? [entityId] : ["edgcumbe-belle"];
  tracker.subscribe(initialSubs);
});