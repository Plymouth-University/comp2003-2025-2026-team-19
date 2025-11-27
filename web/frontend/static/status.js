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

const entity_list = [
    {
        "entity_id": "e22f0bc9-f01f-4d7d-a37d-748af20165d4",
        "start": {
            "name": "Cremyll"
        },
        "end": {
            "name": "Royal William Yard"
        }
    },
    {
        "entity_id": "a91c3b1e-2c4a-4e8f-9a0d-5f3e2d1b0c9f",
        "start": {
            "name": "Plymouth Hoe"
        },
        "end": {
            "name": "Mount Batten"
        }
    },
    {
        "entity_id": "b3e8d7a2-7f6c-4b5d-8c1a-9e0f3d2c1b4a",
        "start": {
            "name": "Torpoint"
        },
        "end": {
            "name": "Devonport"
        }
    },
    {
        "entity_id": "c6f2a4d9-1b3e-4c5f-9d7b-8a9c0e1d2f3g",
        "start": {
            "name": "Saltash"
        },
        "end": {
            "name": "Brunel Green"
        }
    },
    {
        "entity_id": "d1g5h8i3-j2k4-l6m8-n0p9-q7r5s3t1u0v9",
        "start": {
            "name": "Bovisand"
        },
        "end": {
            "name": "Cawsand"
        }
    }
]

function updateEntityList(entity_list) {
    document.getElementById("entity_id").textContent = entity_list.entity_id;
    document.getElementById("entity_start_id").textContent = entity_list.start.name;
    document.getElementById("entity_end_id").textContent = entity_list.end.name;
}

document.addEventListener("DOMContentLoaded", () => {
    updateEntityList(entity_list);
});

window.initMap = initMap;
