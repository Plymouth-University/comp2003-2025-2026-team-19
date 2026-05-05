// --------------------
// CONFIG & STATE
// --------------------

let map, hoverPopup;
const vessels = {}; // Collection of vessel objects keyed by ID
const loadedRoutes = new Set(); // Track which routes have been loaded
let globalRouteBounds = null;

// // Default route for visual reference
// const routeCoords = [
//   { lat: 50.36549641988576, lng: -4.164723457671051 }, // Stonehouse
//   { lat: 50.36086978940922, lng: -4.174937309091103 }  // Cremyll
// ];

const toLngLat = p => [p.lng, p.lat];

// Pub markers
const placeMarkers = [
  {
    name: "The Edgcumbe Arms Waterfront Country Pub & Inn",
    lat: 50.36048523305711,
    lng: -4.175217262906168,
    image: "/assets/icons/edgcumbe-arms.png"
  },
  {
    name: "The VOT",
    lat: 50.36340164623572,
    lng: -4.162515981862114,
    image: "/assets/icons/VOT.png"
  }
];

// --------------------
// VESSEL ICON COLOURS
// --------------------
// Add/change vessel colour schemes here.
// The colours are applied in this order:
// hull, stripe, lowerHull, cabinBase, cabin, window, trim, pipe
const vesselColourSchemes = [
  {
    hull: "#1a1fa3",
    stripe: "#f2f2f2",
    lowerHull: "#c4002b",
    cabinBase: "#6fd6d8",
    cabin: "#f2f2f2",
    window: "#1a1a1f",
    trim: "#f1e600",
    pipe: "#f2f2f2"
  },
  {
    hull: "#0f766e",
    stripe: "#f2f2f2",
    lowerHull: "#dc2626",
    cabinBase: "#93c5fd",
    cabin: "#f2f2f2",
    window: "#1a1a1f",
    trim: "#facc15",
    pipe: "#f2f2f2"
  },
  {
    hull: "#7c3aed",
    stripe: "#f2f2f2",
    lowerHull: "#ea580c",
    cabinBase: "#67e8f9",
    cabin: "#f2f2f2",
    window: "#1a1a1f",
    trim: "#fde047",
    pipe: "#f2f2f2"
  }
];

function getVesselColourScheme(vesselId) {
  let hash = 0;

  for (let i = 0; i < vesselId.length; i++) {
    hash = vesselId.charCodeAt(i) + ((hash << 5) - hash);
  }

  const index = Math.abs(hash) % vesselColourSchemes.length;
  return vesselColourSchemes[index];
}

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

// Mobile
function getFitPadding() {
  const isMobile = window.innerWidth <= 720;
  return isMobile
    ? { top: 100, bottom: 80, left: 20, right: 20 }
    : { top: 100, bottom: 60, left: 320, right: 20 };
}

function updateVesselSource() {
  if (!map || !map.getSource('vessels')) return;

  const features = Object.values(vessels)
    .filter(v => v.lat && v.lng)
    .map(v => {
      // Direction rule: Stonehouse = left, Cremyll = right
      let direction = "left";
      if (v.origin?.toLowerCase().includes("cremyll")) {
        direction = "right";
      }

      const colours = getVesselColourScheme(v.id);

      const params = new URLSearchParams({
        type: "ferry",
        direction,
        hull: colours.hull,
        stripe: colours.stripe,
        lowerHull: colours.lowerHull,
        cabinBase: colours.cabinBase,
        cabin: colours.cabin,
        window: colours.window,
        trim: colours.trim,
        pipe: colours.pipe
      });

      // Ferry-colour for demo change back to `/assets/icons/icon?${params.toString()}` when done
      return {
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [v.lng, v.lat]
        },
        properties: {
          id: v.id,
          icon: `/assets/icons/ferry-colour.svg#${direction}`
        }
      };
    });

  map.getSource('vessels').setData({
    type: 'FeatureCollection',
    features
  });
}

function fitAllVessels() {
  if (!map) return;

  const bounds = new maplibregl.LngLatBounds();

  // 1. Include the static routes in the bounding box
  if (globalRouteBounds) {
    bounds.extend(globalRouteBounds.getSouthWest());
    bounds.extend(globalRouteBounds.getNorthEast());
  }

  // 2. Include the active vessels in the bounding box
  const activeVessels = Object.values(vessels).filter(v => v.lng !== null && v.lat !== null);
  if (activeVessels.length > 0) {
    activeVessels.forEach(v => {
      bounds.extend([v.lng, v.lat]);
    });
  }

  // 3. Center the map to the exact middle of the bounds
  if (!bounds.isEmpty()) {
    // Get the exact mathematical center of all the route lines and vessels
    const middlePoint = bounds.getCenter();

    map.flyTo({
      center: middlePoint, // Explicitly point the camera at the middle
      zoom: 13.5,          // Set a fixed zoom (adjust this to look best for your specific ferry route)
      duration: 1000,
      padding: getFitPadding(), // Still respects the sidebar/header offsets!
      essential: true
    });
  }
}

// --------------------
// CORE LOGIC: DATA SYNC
// --------------------

/**
 * Updates or creates a vessel and syncs it to the Map and Sidebar
 */
let hasInitialFit = false;

function syncVesselData(id, lat, lng, extra = {}) {
  // 1. Initialize vessel if new and extract route info if available
  const routeUuid = extra.route ? extra.route.uuid : null;

  if (!vessels[id]) {
    vessels[id] = {
      id: id,
      name: extra.name || id.replace(/-/g, ' ').toUpperCase(),
      route: extra.route?.uuid ? `${extra.route.origin} ↔ ${extra.route.destination}` : "No Route",
      origin: extra.route?.origin || "",
      destination: extra.route?.destination || "",
      status: extra.status || "in_transit",
      speed: 0,
      heading: 0,
      lat: lat,
      lng: lng,
      marker: null,
      lastUpdated: null
    };
  }

  if (routeUuid) {
    ensureRouteOnMap(routeUuid);
  }

  const v = vessels[id];

  v.origin = extra.route?.origin || v.origin || "";
  v.destination = extra.route?.destination || v.destination || "";

  if (extra.route?.uuid) {
    v.route = `${v.origin} ↔ ${v.destination}`;
  }

  // Update movement logic
  if (lat && lng) {
    if (v.lat !== lat || v.lng !== lng) {
      v.heading = calculateBearing([v.lng, v.lat], [lng, lat]);
    }
  } else {
    v.heading = null;
  }

  v.lat = lat;
  v.lng = lng;
  v.speed = extra.speed || null;
  v.lastUpdated = new Date().toLocaleTimeString();

  const now = new Date();
  const timestamp = now.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
  v.lastUpdated = timestamp;

  // Sync with Map
  updateVesselSource();
  
  renderSidebar();
}


// --------------------
// UI RENDERING
// --------------------

function openVesselList() {
  document.getElementById("sidebar")?.classList.add("open");
  document.getElementById("scrim")?.classList.add("open");
  document.getElementById("btnSidebar")?.setAttribute("aria-label", "Close vessel list");
}

function closeVesselList() {
  document.getElementById("sidebar")?.classList.remove("open");
  document.getElementById("scrim")?.classList.remove("open");
  document.getElementById("btnSidebar")?.setAttribute("aria-label", "Open vessel list");
}

function toggleVesselList() {
  const sidebar = document.getElementById("sidebar");

  if (sidebar?.classList.contains("open")) {
    closeVesselList();
  } else {
    openVesselList();
  }
}

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
        <div>${v.speed !== null ? v.speed.toFixed(1) : 'N/A'} kts</div>
        <div>${formatHeading(v.heading)}</div>
        <div style="color: var(--muted)">Updated ${v.lastUpdated}</div>
      </div>
    `;

    card.addEventListener("click", () => {
      focusVessel(v.id);
      closeVesselList();
    });

    vesselList.appendChild(card);
  });

  updateCounts();
}

function showBoatPopup(v) {
  const html = `
    <div class="popup-title">${v.name}</div>
    <div class="popup-row"><span class="popup-muted">Speed</span> <span>${v.speed !== null ? v.speed.toFixed(1) : 'N/A'} kts</span></div>
    <div class="popup-row"><span class="popup-muted">Dir</span> <span>${formatHeading(v.heading)}</span></div>
  `;
  hoverPopup.setLngLat([v.lng, v.lat]).setHTML(html).addTo(map);
}

function focusVessel(id) {
  const v = vessels[id];
  if (!map || !v || !v.lng || !v.lat) return;

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

function addPlaceMarkers() {
  placeMarkers.forEach(place => {
    const el = document.createElement("div");
    el.className = "place-marker";

    el.style.backgroundImage = `url("${place.image}")`;
    el.style.width = "52px";
    el.style.height = "52px";

    el.addEventListener("click", () => {
      new maplibregl.Popup({ offset: 18 })
        .setLngLat([place.lng, place.lat])
        .setHTML(`<div class="popup-title">${place.name}</div>`)
        .addTo(map);
    });

    new maplibregl.Marker({ element: el, anchor: "bottom" })
      .setLngLat([place.lng, place.lat])
      .addTo(map);
  });
}

function initMap() {
  map = new maplibregl.Map({
    container: 'map',
    style: 'https://tiles.stadiamaps.com/styles/osm_bright.json',
    center: [-4.164723457671051, 50.36549641988576],
    zoom: 14,
    dragRotate: false
  });

  hoverPopup = new maplibregl.Popup({ closeButton: false, offset: 14 });

  map.on('load', () => {
    map.setPadding(getFitPadding());

    // --------------------
    // Route line
    // --------------------
    map.addSource('route', {
      type: 'geojson',
      data: {
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: routeCoords.map(toLngLat)
        }
      }
    });

    map.addLayer({
      id: 'route-line',
      type: 'line',
      source: 'route',
      paint: {
        'line-color': '#5aa7ff',
        'line-width': 4
      }
    });

    // --------------------
    // Vessel source
    // --------------------
    map.addSource('vessels', {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: []
      }
    });

    // --------------------
    // Vessel icon layer
    // --------------------
    map.addLayer({
      id: 'vessels-layer',
      type: 'symbol',
      source: 'vessels',
      layout: {
        'icon-image': ['get', 'icon'],
        'icon-size': 0.06,
        'icon-allow-overlap': true
      }
    });

    // --------------------
    // SVG loader
    // --------------------
    const existingImages = new Set();

    map.on('styleimagemissing', async (e) => {
      const id = e.id;

      if (existingImages.has(id)) return;
      existingImages.add(id);

      try {
        const url = id;

        const params = new URLSearchParams(url.split("?")[1]);
        const direction = params.get("direction");

        const response = await fetch(url);
        let svgText = await response.text();

        if (direction === "right") {
          const match = svgText.match(/<svg[^>]*>([\s\S]*)<\/svg>/);
          const viewBoxMatch = svgText.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);

          if (match) {
            const inner = match[1];

            const width = viewBoxMatch ? parseFloat(viewBoxMatch[1]) : 608;
            const height = viewBoxMatch ? parseFloat(viewBoxMatch[2]) : 390;

            svgText = `
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}">
                <g transform="translate(${width},0) scale(-1,1)">
                  ${inner}
                </g>
              </svg>
            `;
          }
        }

        const svg = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgText);

        const image = new Image();
        await new Promise(res => {
          image.onload = res;
          image.src = svg;
        });

        map.addImage(id, image);
      } catch (err) {
        console.error('SVG load failed:', err);
      }
    });

    // --------------------
    // Interaction
    // --------------------
    map.on('click', 'vessels-layer', (e) => {
      const id = e.features[0].properties.id;
      focusVessel(id);
    });

    map.on('mouseenter', 'vessels-layer', (e) => {
      map.getCanvas().style.cursor = 'pointer';
      const v = vessels[e.features[0].properties.id];
      if (v) showBoatPopup(v);
    });

    map.on('mouseleave', 'vessels-layer', () => {
      map.getCanvas().style.cursor = '';
      hoverPopup.remove();
    });
    // Handle any vessels that were loaded via WS before the map was ready
    Object.values(vessels).forEach(v => {
      if (!v.marker && v.lat && v.lng) v.marker = createVesselMarker(v);
    });

    // --------------------
    // PUB MARKERS
    // --------------------
    addPlaceMarkers();

    // --------------------
    // INITIAL DATA SYNC
    // --------------------
    updateVesselSource();

    // --------------------
    // Map controls
    // --------------------
    document.getElementById("btnZoomIn")?.addEventListener("click", () => map.zoomIn());
    document.getElementById("btnZoomOut")?.addEventListener("click", () => map.zoomOut());
    document.getElementById("btnFit")?.addEventListener("click", () => {
      fitAllVessels();
    });

    // --------------------
    // Initial fit
    // --------------------
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

    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      onError(e);
    }
    ws.onopen = () => {
      onStatus({ type: "connected" });
      updateStatusText("Live");

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
            const lat = data.last_location ? data.last_location.lat : null;
            const lng = data.last_location ? data.last_location.lng : null;

            onUpdate(id, lat, lng, data);
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
      updateStatusText("Reconnecting...", "var(--amber)");
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
// MAP LOGIC
// --------------------
async function ensureRouteOnMap(routeUuid) {
  if (!map || !routeUuid || loadedRoutes.has(routeUuid)) return;

  loadedRoutes.add(routeUuid);

  try {
    // 1. Fetch the GeoJSON manually so we can read the coordinates
    const response = await fetch(`/api/v1/routes/${routeUuid}/trajectory`);
    const geojson = await response.json();

    // 2. Update the global route bounds
    if (geojson.features && geojson.features.length > 0) {
      if (!globalRouteBounds) globalRouteBounds = new maplibregl.LngLatBounds();

      const coords = geojson.features[0].geometry.coordinates;
      coords.forEach(coord => {
        globalRouteBounds.extend(coord);
      });
    }

    const routeColor = geojson.features[0]?.properties?.color || '#5aa7ff';

    // 3. Add to map using the fetched data
    const sourceId = `route-${routeUuid}`;
    map.addSource(sourceId, {
      type: 'geojson',
      data: geojson
    });

    map.addLayer({
      id: `route-line-${routeUuid}`,
      type: 'line',
      source: sourceId,
      paint: {
        'line-color': routeColor,
        'line-width': 4,
        'line-opacity': 0.7
      }
    });

    // 4. Trigger a re-center now that the route is loaded
    fitAllVessels();

  } catch (error) {
    console.error(`Failed to load route ${routeUuid}:`, error);
    loadedRoutes.delete(routeUuid); // Allow retry if it failed
  }
}

// --------------------
// BOOTSTRAP
// --------------------

document.addEventListener('DOMContentLoaded', () => {
  // Setup UI Clock
  const updateClock = () => {
    const now = new Date();
    const clockEl = document.getElementById("clockText");
    if (clockEl) clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };
  updateClock();
  setInterval(updateClock, 10000);

  // Init Map
  initMap();

  // Mobile button sidebar
  document.getElementById("btnSidebar")?.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleVesselList();
  });

  document.getElementById("scrim")?.addEventListener("click", closeVesselList);

  document.getElementById("sidebar")?.addEventListener("click", (e) => {
    e.stopPropagation();
  });

  // Init Tracker
  const tracker = TrackerWS({
    onUpdate: (id, lat, lng, extra) => syncVesselData(id, lat, lng, extra),
    onStatus: (s) => console.log("Tracker:", s),
    onError: (e) => console.error("Tracker Error:", e)
  });

  // Subscribe based on URL or defaults
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