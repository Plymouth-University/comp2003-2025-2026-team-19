// Slide-up panel
(function panelSetup() {
  const panel = document.getElementById('panel');
  const handle = document.getElementById('panelHandle');
  let startY = 0, startT = 0, dragging = false;

  const setOpen = (open) => {
    panel.classList.toggle('open', open);
    panel.setAttribute('aria-expanded', String(open));
  };
  const toggle = () => setOpen(!panel.classList.contains('open'));

  handle.addEventListener('click', toggle);
  handle.addEventListener('keydown', (e)=>{
    if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); toggle(); }
  });

  const onStart = (y) => { dragging = true; startY = y; startT = panel.getBoundingClientRect().top; panel.style.transition = 'none'; };
  const onMove  = (y) => {
    if(!dragging) return;
    const dy = y - startY;
    const h = window.innerHeight;
    let translate = Math.min(Math.max((startT + dy) / h * 100, 0), 62);
    panel.style.transform = `translateY(${translate}%)`;
  };
  const onEnd = () => {
    if(!dragging) return; dragging = false; panel.style.transition = '';
    const top = panel.getBoundingClientRect().top;
    const open = top < window.innerHeight * 0.6;
    setOpen(open);
  };

  handle.addEventListener('pointerdown', (e)=>{ handle.setPointerCapture(e.pointerId); onStart(e.clientY); });
  handle.addEventListener('pointermove', (e)=> onMove(e.clientY));
  handle.addEventListener('pointerup', onEnd);
  handle.addEventListener('pointercancel', onEnd);
})();

// Map
let map, boatMarker;

// Route coordinates: Stonehouse → Cremyll
// (Later, for a curved route, just add more points here)
const routeCoords = [
  { lat: 50.36549641988576, lng: -4.164723457671051 }, // Stonehouse
  { lat: 50.36086978940922, lng: -4.174937309091103 }  // Cremyll
];

const toLngLat = p => [p.lng, p.lat];

function initMap() {
  const startLL = toLngLat(routeCoords[0]);
  const endLL   = toLngLat(routeCoords[1]);

  map = new maplibregl.Map({
    container: 'map',
    style: 'https://tiles.stadiamaps.com/styles/osm_bright.json', // detailed OSM style
    center: startLL,
    zoom: 14
  });

  // Keep behaviour simple
  map.dragRotate.disable();
  map.touchZoomRotate.disableRotation();

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

    // Fit view to route with padding for header + bottom panel
    const bounds = new maplibregl.LngLatBounds();
    routeCoords.forEach(p => bounds.extend(toLngLat(p)));
    map.fitBounds(bounds, {
      padding: { top: 80, bottom: 220, left: 40, right: 40 }
    });

    // Boat marker – styled via .boat-marker in CSS
    const el = document.createElement('div');
    el.className = 'boat-marker';

    boatMarker = new maplibregl.Marker({ element: el })
      .setLngLat(startLL)
      .addTo(map);

    // Simulated updates every 10 seconds
    setInterval(updateFerryPosition, 10000);
  });
}

// Hardware integration (Isaac & Josh)

// Placeholder: update marker with hardware data
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

  const status = document.getElementById('statusText');
  const time = new Date().toLocaleTimeString();
  const locationName = isAtStart ? 'Cremyll' : 'Stonehouse';
  status.textContent = `Last updated: ${time} — Ferry approaching ${locationName}`;
}

document.addEventListener('DOMContentLoaded', initMap);
