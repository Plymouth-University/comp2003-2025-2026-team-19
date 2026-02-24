let map, boatMarker, hoverPopup;

const routeCoords = [
  { lat: 50.36549641988576, lng: -4.164723457671051 }, // Stonehouse
  { lat: 50.36086978940922, lng: -4.174937309091103 }  // Cremyll
];

const toLngLat = p => [p.lng, p.lat];

// One vessel for now
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

// Bearing from A -> B (degrees)
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

// Responsive fitBounds padding: desktop/tablet vs mobile
function getFitPadding() {
  const isMobile = window.innerWidth <= 720;
  // On mobile, sidebar is a drawer (usually closed), so don't crush the map with left padding.
  if (isMobile) return { top: 90, bottom: 80, left: 16, right: 70 };
  // On tablet/desktop, leave space for the fixed sidebar.
  return { top: 90, bottom: 80, left: 340, right: 70 };
}

// --------------------
// SIDEBAR RENDER
// --------------------
function computeCounts() {
  const all = vessels.length;
  const active = vessels.filter(v => v.status === "in_transit" || v.status === "delayed").length;
  const docked = vessels.filter(v => v.status === "docked").length;
  return { all, active, docked };
}

function applyFilterAndSearch(list) {
  const q = searchQuery.trim().toLowerCase();
  let out = list;

  if (currentFilter === "active") {
    out = out.filter(v => v.status === "in_transit" || v.status === "delayed");
  } else if (currentFilter === "docked") {
    out = out.filter(v => v.status === "docked");
  }

  if (q) {
    out = out.filter(v => v.name.toLowerCase().includes(q) || v.route.toLowerCase().includes(q));
  }
  return out;
}

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

    card.addEventListener("click", () => focusVessel(v.id));
    vesselList.appendChild(card);
  });
}

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

  // Mobile drawer toggle
  const sidebar = document.getElementById("sidebar");
  const scrim = document.getElementById("scrim");
  const btnSidebar = document.getElementById("btnSidebar");

  const openSidebar = (open) => {
    sidebar.classList.toggle("open", open);
    scrim.classList.toggle("open", open);
    btnSidebar?.setAttribute("aria-expanded", String(open));
  };

  btnSidebar?.addEventListener("click", () => {
    openSidebar(!sidebar.classList.contains("open"));
  });
  scrim.addEventListener("click", () => openSidebar(false));

  // Close drawer on resize to desktop + keep map padding sane if you click recenter later
  window.addEventListener("resize", () => {
    if (window.innerWidth > 720) openSidebar(false);
  });
}

// --------------------
// CLOCK
// --------------------
function setClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  document.getElementById("clockText").textContent = `${hh}:${mm}`;
}

// --------------------
// MAP INIT (server-working behavior preserved)
// --------------------
function initMap() {
  const startLL = toLngLat(routeCoords[0]);
  const endLL   = toLngLat(routeCoords[1]);

  map = new maplibregl.Map({
    container: 'map',
    style: 'https://tiles.stadiamaps.com/styles/osm_bright.json',
    center: startLL,
    zoom: 14
  });

  map.dragRotate.disable();
  map.touchZoomRotate.disableRotation();

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

    // Fit view to route (now responsive)
    const bounds = new maplibregl.LngLatBounds();
    routeCoords.forEach(p => bounds.extend(toLngLat(p)));
    map.fitBounds(bounds, { padding: getFitPadding() });

    // Boat marker – uses your existing .boat-marker
    const el = document.createElement('div');
    el.className = 'boat-marker in-transit';
    el.setAttribute("aria-label", "Vessel position");

    boatMarker = new maplibregl.Marker({ element: el })
      .setLngLat(startLL)
      .addTo(map);

    // Hover popup (desktop hover + mobile tap)
    el.addEventListener("mouseenter", () => showBoatPopup());
    el.addEventListener("mouseleave", () => hoverPopup.remove());
    el.addEventListener("click", (e) => {
      // On touch devices click is the "hover"
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

    // Initial UI render
    renderSidebar();

    // Updates every 10s (same behavior as server)
    setInterval(updateFerryPosition, 10000);
  });
}

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

// Focus from sidebar/marker
function focusVessel(id) {
  if (!map || !boatMarker) return;
  const ll = boatMarker.getLngLat();
  map.easeTo({ center: [ll.lng, ll.lat], zoom: Math.max(map.getZoom(), 15), duration: 600 });
}

// --------------------
// POSITION UPDATE (server logic + your enhancements)
// --------------------
function updateFerryPosition() {
  if (!boatMarker) return;

  const current = boatMarker.getLngLat();
  const startLL = toLngLat(routeCoords[0]);
  const endLL   = toLngLat(routeCoords[1]);

  const isAtStart =
    Math.abs(current.lng - startLL[0]) < 1e-6 &&
    Math.abs(current.lat - startLL[1]) < 1e-6;

  const next = isAtStart ? endLL : startLL;
  boatMarker.setLngLat(next);

  // Update vessel stats used by sidebar + popup
  const v = vessels[0];
  v.heading = bearing([current.lng, current.lat], next);
  v.eta = "≈ 8 min";
  v.speed = 8.0;

  // Update top status text
  const status = document.getElementById('statusText');
  const time = new Date().toLocaleTimeString();
  const locationName = isAtStart ? 'Cremyll' : 'Stonehouse';
  status.textContent = `Last updated: ${time} — Ferry approaching ${locationName}`;

  renderSidebar();
}

// --------------------
// BOOT
// --------------------
document.addEventListener('DOMContentLoaded', () => {
  wireSidebarControls();
  setClock();
  setInterval(setClock, 1000 * 10);
  initMap();
});