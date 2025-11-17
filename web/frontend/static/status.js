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
let map, polyline, boatMarker;
// change for pull
// Route coordinates: Stonehouse → Cremyll
const routeCoords = [
  { lat: 50.36549641988576, lng: -4.164723457671051 },
  { lat: 50.36086978940922, lng: -4.174937309091103 }
];

function initMap() {
  map = new google.maps.Map(document.getElementById('map'), {
    center: routeCoords[0],
    zoom: 14,
    streetViewControl: false,
    fullscreenControl: true,
    mapTypeControl: false,
  });

  // Ferry route
  polyline = new google.maps.Polyline({
    path: routeCoords,
    geodesic: true,
    strokeColor: '#5aa7ff',
    strokeOpacity: 0.9,
    strokeWeight: 4,
    map,
  });

  const bounds = new google.maps.LatLngBounds();
  routeCoords.forEach(p => bounds.extend(p));
  map.fitBounds(bounds, { top: 80, bottom: 220, left: 20, right: 20 });

  // Boat marker
  const svg = encodeURIComponent(`
    <svg xmlns='http://www.w3.org/2000/svg' width='48' height='48' viewBox='0 0 48 48'>
      <g fill='none' stroke='none'>
        <path d='M6 30l18-8 18 8-4 8H10z' fill='#1f3ea5ff'/>
        <path d='M12 22h12v-6l6-4v10h6' stroke='white' stroke-width='2' fill='none' opacity='.9'/>
        <path d='M6 38c3 2 6 2 9 0 3 2 6 2 9 0 3 2 6 2 9 0 3 2 6 2 9 0' stroke='#89c2ff' stroke-width='2' fill='none' opacity='.9'/>
      </g>
    </svg>`);
  const icon = {
    url: `data:image/svg+xml;charset=UTF-8,${svg}`,
    scaledSize: new google.maps.Size(36, 36),
    anchor: new google.maps.Point(18, 18)
  };

  boatMarker = new google.maps.Marker({ position: routeCoords[0], map, icon, title: 'MV Edgcumbe' });

  // Updates every 10 seconds
  setInterval(updateFerryPosition, 10000);
}

// Hardware integration (Isaac & Josh)

// Placeholder: update marker with hardware data
function updateFerryPosition() {
  // Example: just toggling between start and end to simulate movement
  const current = boatMarker.getPosition();
  const next = (current.lat() === routeCoords[0].lat) ? routeCoords[1] : routeCoords[0];
  boatMarker.setPosition(next);

  const status = document.getElementById('statusText');
  const time = new Date().toLocaleTimeString();
  status.textContent = `Last updated: ${time}`;
}

// Boat Image
// 200 OK
const boatData = {
    "entity_id": "entity_id",
    "name": "Entity Name",
    "image_url": "https://example.com/image",
    "route": {
        "route_id": "route_id",
        "start": {
            "destination_id": "destination_id",
            "destination_name": "Destination Name",
            "lat": 40.6892,
            "long": -74.0445
        },
        "end": {
            "destination_id": "destination_id",
            "destination_name": "Destination Name",
            "lat": 40.7580,
            "long": -73.9855
        }
    }
}

//Updates boat's data by getting the required element
//Needs to be updated later with API calls
function updateBoatData(boatData) {
    document.getElementById("entity_id").textContent = boatData.entity_id;
    document.getElementById("nameId").textContent = boatData.name;
    document.getElementById("imageId").src = boatData.image_url;

    document.getElementById("routeId").textContent = boatData.route.route_id;

    document.getElementById("startDestinationId").textContent = boatData.route.start.destination_id;
    document.getElementById("startDestinationNameId").textContent = boatData.route.start.destination_name;
    document.getElementById("startDestinationLatId").textContent = boatData.route.start.lat;
    document.getElementById("startDestinationLotId").textContent = boatData.route.start.long;

    document.getElementById("endDestinationId").textContent = boatData.route.end.destination_id;
    document.getElementById("endDestinationNameId").textContent = boatData.route.end.destination_name;
    document.getElementById("endDestinationLatId").textContent = boatData.route.end.lat;
    document.getElementById("endDestinationLotId").textContent = boatData.route.end.long;

}

document.addEventListener("DOMContentLoaded", () => {
    updateBoatData(boatData);
});

window.initMap = initMap;
