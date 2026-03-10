let map, boatMarker, hoverPopup;

// Fixed route endpoints
const routeCoords = [
  { lat: 50.36549641988576, lng: -4.164723457671051 }, // Stonehouse
  { lat: 50.36086978940922, lng: -4.174937309091103 }  // Cremyll
];

// Ling, lat conversion for MapLibre
const toLngLat = p => [p.lng, p.lat];

// Current vessel list, more can be added
const vessels = [
  {
    id: "edgcumbe-belle",
    name: "EDGCUMBE BELLE",
    route: "Stonehouse ↔ Cremyll",
    status: "in_transit",  // in_transit | docked | delayed
    speed: 8.0,
    eta: "—",
    heading: 0,
    getLngLat: () => boatMarker?.getLngLat()
  }
];

// Sidebar filter/search
let currentFilter = "all";
let searchQuery = "";

// --------------------
// UI HELPERS
// --------------------

const statusToPill = (s) => {
  if (s === "in_transit") return { label: "In Transit", cls: "green", markerCls: "in-transit" };
  if (s === "docked") return { label: "Docked", cls: "amber", markerCls: "docked" };
  return { label: "Delayed", cls: "red", markerCls: "delayed" };
};

function formatHeading(deg) {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const idx = Math.round(((deg % 360) / 45)) % 8;
  return `${Math.round(deg)}° (${dirs[idx]})`;
}

// Bearing from A -> B (direction in degrees)
function bearing(fromLngLat, toLngLat) {
  const toRad = d => d * Math.PI / 180;
  const toDeg = r => r * 180 / Math.PI;

  const lon1 = toRad(fromLngLat[0]);
  const lat1 = toRad(fromLngLat[1]);
  const lon2 = toRad(toLngLat[0]);
  const lat2 = toRad(toLngLat[1]);

  const dLon = lon2 - lon1;
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  let brng = toDeg(Math.atan2(y, x));
  brng = (brng + 360) % 360;
  return brng;
}

// Sidebar becomes a drawer on mobile
function getFitPadding() {
  const isMobile = window.innerWidth <= 720;
  if (isMobile) return { top: 90, bottom: 80, left: 16, right: 70 };
  return { top: 90, bottom: 80, left: 340, right: 70 };
}

//Used for obtaining UUID from url
function entityIdUrl() {
  const pathUrl = window.location.pathname.split("/");
  return pathUrl[pathUrl.length - 1];
}

// --------------------
// SIDEBAR RENDER
// --------------------

// Summary counts from the filter tab
function computeCounts() {
  const all = vessels.length;
  const active = vessels.filter(v => v.status === "in_transit" || v.status === "delayed").length;
  const docked = vessels.filter(v => v.status === "docked").length;
  return { all, active, docked };
}

// Applies the search/filter to vessel list before rendering the cards
function applyFilterAndSearch(list) {
  const q = searchQuery.trim().toLowerCase();
  let out = list;

  if (currentFilter === "active") {
    out = out.filter(v => v.status === "in_transit" || v.status === "delayed");
  } else if (currentFilter === "docked") {
    out = out.filter(v => v.status === "docked");
  }

  // Search matches vessel name or route text
  if (q) {
    out = out.filter(v => v.name.toLowerCase().includes(q) || v.route.toLowerCase().includes(q));
  }
  return out;
}

// Rebuilds the sidebar list and updates the filter counts
function renderSidebar() {
  const counts = computeCounts();
  document.getElementById("countAll").textContent = counts.all;
  document.getElementById("countActive").textContent = counts.active;
  document.getElementById("countDocked").textContent = counts.docked;

  const vesselList = document.getElementById("vesselList");
  vesselList.innerHTML = "";

  const shown = applyFilterAndSearch(vessels);

  shown.forEach(v => {
    const st = statusToPill(v.status);

    const card = document.createElement("div");
    card.className = "vessel-card";
    card.dataset.id = v.id;

    const headingTxt = formatHeading(v.heading);
    const etaTxt = v.eta || "—";

    // Render one vessel summary card
    card.innerHTML = `
      <div class="vessel-top">
        <div class="vessel-name">${v.name}</div>
        <div class="pill ${st.cls}">${st.label}</div>
      </div>
      <div class="vessel-sub">${v.route}</div>
      <div class="vessel-meta">
        <div>${v.speed.toFixed(1)} kts</div>
        <div>${headingTxt}</div>
        <div style="color: var(--muted)">ETA ${etaTxt}</div>
      </div>
    `;

    // Clicking the card centers the map on the vessel
    card.addEventListener("click", () => focusVessel(v.id));
    vesselList.appendChild(card);
  });
}

// Hooks up the sidebar search, filter tabs, and mobile drawer behaviour
function wireSidebarControls() {
  document.getElementById("searchInput").addEventListener("input", (e) => {
    searchQuery = e.target.value;
    renderSidebar();
  });

  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      renderSidebar();
    });
  });

  // Mobile drawer elements
  const sidebar = document.getElementById("sidebar");
  const scrim = document.getElementById("scrim");
  const btnSidebar = document.getElementById("btnSidebar");

  // Opens/closes the mobile drawer and background overlay
  const openSidebar = (open) => {
    sidebar.classList.toggle("open", open);
    scrim.classList.toggle("open", open);
    btnSidebar?.setAttribute("aria-expanded", String(open));
  };

  btnSidebar?.addEventListener("click", () => {
    openSidebar(!sidebar.classList.contains("open"));
  });
  scrim.addEventListener("click", () => openSidebar(false));

  // Close mobile drawer on resize to desktop size
  window.addEventListener("resize", () => {
    if (window.innerWidth > 720) openSidebar(false);
  });
}

// --------------------
// CLOCK
// --------------------

// Live clock updates in the top bar
function setClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  document.getElementById("clockText").textContent = `${hh}:${mm}`;
}

// --------------------
// MAP INIT
// --------------------

// Map, route line, marker, popup behaviour, and map controls
function initMap() {
  const startLL = toLngLat(routeCoords[0]);
  const endLL = toLngLat(routeCoords[1]);

  map = new maplibregl.Map({
    container: 'map',
    style: 'https://tiles.stadiamaps.com/styles/osm_bright.json',
    center: startLL,
    zoom: 14
  });

  // Disable map rotation for simplicity
  map.dragRotate.disable();
  map.touchZoomRotate.disableRotation();

  // Reused popup for hover/tap
  hoverPopup = new maplibregl.Popup({
    closeButton: false,
    closeOnClick: false,
    offset: 14
  });

  map.on('load', () => {
    // Route as GeoJSON LineString
    const routeGeoJSON = {
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: routeCoords.map(toLngLat)
      }
    };

    map.addSource('route', {
      type: 'geojson',
      data: routeGeoJSON
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

    // Route bounds for the map frame of the full route
    const bounds = new maplibregl.LngLatBounds();
    routeCoords.forEach(p => bounds.extend(toLngLat(p)));
    map.fitBounds(bounds, { padding: getFitPadding() });

    // Boat marker render
    const el = document.createElement('div');
    el.className = 'boat-marker in-transit';
    el.setAttribute("aria-label", "Vessel position");

    // Add the boat marker to the route start
    boatMarker = new maplibregl.Marker({ element: el })
      .setLngLat(startLL)
      .addTo(map);

    // Hover popup (desktop hover + mobile tap)
    el.addEventListener("mouseenter", () => showBoatPopup());
    el.addEventListener("mouseleave", () => hoverPopup.remove());
    el.addEventListener("click", (e) => {
      showBoatPopup();
      focusVessel("edgcumbe-belle");
      e.stopPropagation();
    });

    // Close popup if you tap elsewhere on the map
    map.on("click", () => hoverPopup.remove());

    // Map controls
    document.getElementById("btnZoomIn").addEventListener("click", () => map.zoomIn());
    document.getElementById("btnZoomOut").addEventListener("click", () => map.zoomOut());
    document.getElementById("btnRecenter").addEventListener("click", () => {
      map.fitBounds(bounds, { padding: getFitPadding() });
    });

    // Initial sidebar render
    renderSidebar();

    // Updates every 10s (same behavior as server)
    //setInterval(updateFerryPosition, 10000); (Disabled for now)
  });
}

// Builds the small marker popup
function showBoatPopup() {
  const v = vessels[0];
  if (!boatMarker) return;

  const ll = boatMarker.getLngLat();
  const html = `
    <div class="popup-title">${v.name}</div>
    <div class="popup-row"><span class="popup-muted">ETA</span> <span>${v.eta || "—"}</span></div>
    <div class="popup-row"><span class="popup-muted">Dir</span> <span>${formatHeading(v.heading)}</span></div>
  `;
  hoverPopup.setLngLat([ll.lng, ll.lat]).setHTML(html).addTo(map);
}

// Centers the map on the selected vessel
function focusVessel(id) {
  if (!map || !boatMarker) return;
  const ll = boatMarker.getLngLat();
  map.easeTo({ center: [ll.lng, ll.lat], zoom: Math.max(map.getZoom(), 15), duration: 600 });
}

// --------------------
// POSITION UPDATE
// --------------------

// Boat marker current position
function updateFerryPosition() {
  if (!boatMarker) return;

  const current = boatMarker.getLngLat();
  const startLL = toLngLat(routeCoords[0]);
  const endLL = toLngLat(routeCoords[1]);

  // Start point check
  const isAtStart =
    Math.abs(current.lng - startLL[0]) < 1e-6 &&
    Math.abs(current.lat - startLL[1]) < 1e-6;

  const next = isAtStart ? endLL : startLL;
  boatMarker.setLngLat(next);

  // Update vessel details used by sidebar + popup
  const v = vessels[0];
  v.heading = bearing([current.lng, current.lat], next);
  v.eta = "≈ 8 min";
  v.speed = 8.0;

  // Update top status (time + text)
  const status = document.getElementById('statusText');
  const time = new Date().toLocaleTimeString();
  const locationName = isAtStart ? 'Cremyll' : 'Stonehouse';
  status.textContent = `Last updated: ${time} — Ferry approaching ${locationName}`;

  renderSidebar();
}

// --------------------
// BOOT
// --------------------

// DOM check before building the map
document.addEventListener('DOMContentLoaded', () => {
  wireSidebarControls();
  setClock();
  setInterval(setClock, 1000 * 10); // Refresh the clock every 10 seconds
  initMap();
});

// Websocket stuff

//Used for initialising the object
const tracker = TrackerWS({
  onUpdate: (id, lat, lng, ts) => {

    if (!boatMarker) return;

    boatMarker.setLngLat([lng, lat]);
    map.flyTo({ center: [lng, lat], zoom: Math.max(map.getZoom(), 15), duration: 600 });

    const v = vessels.find(v => v.id === id);
    if (v) {
      v.eta = "Live Update";
      v.speed = 8.0;
    }

    renderSidebar();
  },

  onStatus: (s) => console.log("status", s),
  onError: (e) => console.error("err", e),
});

//Subscribes to the UUID
const entityId = entityIdUrl();

if (entityId) {
  tracker.subscribe([entityId]);
}


//Websocket connection function
function TrackerWS({
  baseUrl = "",
  onUpdate,
  onStatus = () => { },
  onError = console.error,
}) {
  let ws = null;
  let subscribedIds = [];

  function makeWsUrl(path) {
    if (!baseUrl) {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${window.location.host}${path}`;
    }
    const u = new URL(baseUrl);
    const wsProto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${u.host}${path}`;
  }

  const wsUrl = makeWsUrl("/api/v1/entities/ws");

  //Used for connecting to websocket

  function connect() {
    ws = new WebSocket(wsUrl);
    ws.addEventListener("open", () => {
      onStatus({ type: "connected" });

      if (subscribedIds.length) {
        subscribe(subscribedIds);
      }
    });

    //Listens for any messages
    ws.addEventListener("message", (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (e) {
        onError({ type: "bad_json", raw: event.data, error: e });
        return;
      }

      //Server Check
      if (msg.status === "subscribed") {
        onStatus({ type: "subscribed", entity_ids: msg.entity_ids });
        return;
      }

      //Location updates
      if (msg.type === "update" && msg.data) {
        const { entity_id, latitude, longitude, timestamp } = msg.data;

        if (
          typeof entity_id === "string" &&
          typeof latitude === "number" &&
          typeof longitude === "number"
        ) {
          onUpdate(entity_id, latitude, longitude, timestamp);
        } else {
          onError({ type: "bad_update_shape", msg });
        }
        return;
      }

      onStatus({ type: "unknown_message", msg });
    });

    ws.addEventListener("error", (err) => {
      onError({ type: "ws_error", err });
    });

    ws.addEventListener("close", () => {
      onStatus({ type: "disconnected" });
      ws = null;
    });
  }

  //Subscribes to the entity id
  function subscribe(entityIds) {
    subscribedIds = Array.from(new Set(entityIds));

    const payload = {
      action: "subscribe",
      entity_ids: subscribedIds,
    };

    console.log("Sending the", payload)

    if (!ws) {
      connect();
      return;
    }

    if (ws.readyState === WebSocket.CONNECTING) {
      ws.addEventListener(
        "open",
        () => ws.send(JSON.stringify(payload)),
        { once: true }
      );
      return
    }

    if (ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }

  //Used for disconnect
  function disconnect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState ===
      WebSocket.CONNECTING)) {
      ws.close();
    }
    ws = null;
  }
  window.addEventListener("pagehide", () => disconnect());

  return { connect, subscribe, disconnect };
}



