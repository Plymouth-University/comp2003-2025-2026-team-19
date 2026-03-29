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
    ? { top: 120, bottom: 80, left: 20, right: 20 }
    : { top: 120, bottom: 40, left: 342, right: 60 };
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

  map.fitBounds(bounds, {
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
  updateStatusText("Live")

  // 3. Sync with Map (if map is ready)
  if (map) {
    if (!v.marker) {
      v.marker = createVesselMarker(v);
    }
    v.marker.setLngLat([lng, lat]);
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

function updateCounts() {
  const totalEl = document.getElementById("countAll");
  const activeEl = document.getElementById("countActive");
  const dockedEl = document.getElementById("countDocked");

  let total = 0;
  let active = 0;
  let docked = 0;

  Object.values(vessels).forEach(v => {
    total++;
    if (v.status === "in_transit") active++;
    if (v.status === "docked") docked++;
  });

  if (totalEl) totalEl.textContent = total;
  if (activeEl) activeEl.textContent = active;
  if (dockedEl) dockedEl.textContent = docked;
}

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
    updateCounts();
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
    map.setPadding(getFitPadding());

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
    document.getElementById("btnFit")?.addEventListener("click", () => {
      fitAllVessels();
    });

    if (!hasInitialFit) {
      fitAllVessels();
      hasInitialFit = true;
    }
  });
}

function updateStatusText(text, color = "var(--green)") {
  const statusEl = document.getElementById("status");
  const statusText = statusEl.querySelector("span#statusText");
  if (statusText) {
    statusText.style.color = color;
    statusText.innerHTML = `${text}`;
  }

  const timestampEl = statusEl.querySelector("span#statusTimestamp");
  if (timestampEl) {
    const now = new Date();
    timestampEl.innerHTML = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
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
        console.log("Received message:", msg);
        if (msg.status === "subscribed" && msg.entities) {
          console.log("Subscribed to entities:", msg.entities);
          Object.entries(msg.entities).forEach(([id, data]) => {
            onUpdate(id, data.last_location.lat, data.last_location.lng, data);
          });
        }
        // Live updates
        else if (msg.type === "update" && msg.data) {
          console.log("Received update for", msg.data.entity_id, "at", msg.data.latitude, msg.data.longitude);
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
  let params = new URLSearchParams(window.location.search);
  let entityIds = params.get("entity_ids");
  if (entityIds) {
    console.log("Subscribing to specific entities from URL:", entityIds);
    try {
      entityIds = entityIds.split(",").map(id => id.trim()).filter(id => id);
    } catch (e) {
      console.error("Error parsing entity_ids from URL:", e);
      entityIds = [];
    }
  } else {
    console.log("Subscribing to all entities");
    entityIds = [];
  };

  // If the URL has a specific ID, use it, otherwise subscribe to all active entities
  const initialSubs = entityIds.length ? entityIds : "all";
  tracker.subscribe(initialSubs);
});

window.addEventListener("resize", () => {
  if (map) {
    // This dynamically updates the 'logical center' for zoomIn/Out
    map.setPadding(getFitPadding());
  }
});