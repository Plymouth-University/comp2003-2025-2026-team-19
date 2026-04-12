//Settings preferences
const adminSettings = {
  mute_404: false,
  mute_slow: false,
  barInterval: 3,
  pause_bars: false
};

function saveSetting(key, value) {
  adminSettings[key] = value;
  startMetricsPolling();
}

//Ferry data
let entity_list = [
  {
    "id": "b85e5637-4791-4aa4-abec-a2ac3e4a946e",
    "name": "Plymouth Venturer",
    "route": null,
    "active": false,
    "last_updated": null
  },
  {
    "id": "fa7fa868-8eac-4e20-a69c-b7b7c17364bb",
    "name": "Plymouth Sound",
    "route": null,
    "active": false,
    "last_updated": null
  },
  {
    "id": "fa0a1599-8de1-4e08-aee8-f1607e1359cb",
    "name": "Tamar Belle",
    "route": null,
    "active": false,
    "last_updated": null
  },
  {
    "id": "add9ce40-e60c-41b4-b6e9-e7dc3185849c",
    "name": "Plymouth Princess",
    "route": null,
    "active": false,
    "last_updated": null
  },
  {
    "id": "9e2f2cbd-2671-4972-9115-c0bd8d5cef2d",
    "name": "Island Princess",
    "route": null,
    "active": false,
    "last_updated": null
  },
  {
    "id": "072caf2a-a921-4128-8369-75b237c42161",
    "name": "Edgcumbe Belle",
    "route": null,
    "active": false,
    "last_updated": null
  }
]

function updateEntityList(entity_list) {
    //Gets ID for where the entries will be assigned
    const entity_container = document.getElementById("entity_list_container");
    
    //Clears previous container content which is good for new data
    entity_container.innerHTML = "";
    
    //Goes through entities in the json
    entity_list.forEach(entity => {
      const li = document.createElement("li");
      
      //Used for checking ferry status
      const active = isTrackerActive(entity.last_updated, 60);
      const statusClass = active ? "status-green" : "status-red";

      //List acts differently depending if route data is null or not
      if (!entity.route) {
      //Uses innerHTML to display entities and use break
      li.innerHTML = `
      <a href="/status/${entity.id}">
      ${entity.name}
      <div class="status_row">
        Status:
        <span class="status_circle ${statusClass}"></span>
        <span class="timestamp">Last updated: ${entity.last_updated}</span>
        </div>
      </a>
    `;
    } else {
        //Not really needed anymore but keeping in case we *do* want to show routes on the ferry tra
        li.innerHTML = `
        <a href="/status/${entity.id}">
           ${entity.name}:<br>
           ${entity.route.start_location.name}
           →
           ${entity.route.end_location.name}
          <div class="status_row">
            Status:
            <span class="status_circle ${statusClass}"></span>
            <span class="timestamp">Last updated: ${entity.last_updated}</span>
           </div>
        </a>
        `;
    }
    //Adds list to container
    entity_container.appendChild(li);
    entity_container.appendChild(document.createElement("br"));
  });
}

//Checks what trackers are active
function isTrackerActive(last_updated, timeoutSeconds = 30) {
  const last = new Date(last_updated).getTime();
  if (isNaN(last)) return false //Stops crashing if no data
  const now = Date.now();
  return (now - last) / 1000 <= timeoutSeconds;
}

//Checks for and returns ferry status to be shown on the trackers
async function fetchEntities() {
  try {
    const result = await fetch("/api/v1/entities");
    if (!result.ok) return;
    const data = await result.json();
    entity_list = data;
    updateEntityList(data);
    console.log("On correct endpoint");
  } catch (err) {
    console.error("Failed to fetch entity data", err);
  }
}

//Gets functions working as soon as application starts
document.addEventListener("DOMContentLoaded", () => {
  startMetricsPolling();
  fetchMetrics();
  fetchEntities();
});

//Activty Graph Functionality

//Constructs the activity graph
const maxBars = 40;
const activityData = Array.from({length: maxBars}, () => 0);

const activityChart = new Chart(document.getElementById("activityChart"), {
  type: "bar",
  data: {
    labels: Array(maxBars).fill(""),
    datasets: [{
      data: activityData,
      //Highlights most recent bar lighter so its more noticeable
      backgroundColor: activityData.map((_, i) =>
        i === activityData.length - 1 ? "#4d9de0" : "rgba(59,130,210,0.45)"
    ),
      borderWidth: 0, 
      borderRadius: 2,
      barPercentage: 0.75
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: { legend: { display: false } },
    plugins: { legend: { display: false } },
    scales: {
      x: { display: false },
      y: {
        min: 0, max: 100,
        ticks: {color: "#2a4a6a", font: { size: 20}, stepSize: 25 },
        grid: { color: "rgba(30,58,95,0.4)" },
        border: { display: false }
      }
    }
  }
});

//Adds new right side bar and drops the furthest left bar if container is full
function pushActivityBar(value) {
  activityChart.data.datasets[0].data.push(value);
  activityChart.data.datasets[0].data.shift();
  activityChart.data.labels.push("");
  activityChart.data.labels.shift();
  activityChart.data.datasets[0].backgroundColor =
    activityChart.data.datasets[0].data.map((_, i) =>
      //Reapplies highlist to latest bar after each individual update
      i === activityChart.data.datasets[0].data.length - 1
        ? "#4d9de0" : "rgba(59,130,210,0.45)"
    );
  activityChart.update();
}

//Used for getting the metrics data to be displayed on the admin page
let metricsData = [];

//Calculates and displays all requests, average latency, and status code count
function renderStats(data) {
  if (data.length === 0) return;

  const totalRequests = data.length;
  const avgLatency = (data.reduce((sum, row) => sum + row.latency_ms, 0)
  / totalRequests).toFixed(2);
    //Counts status codes
    const statusCounts = data.reduce((acc, row) => {
      acc[row.status] = (acc[row.status] || 0) + 1;
      return acc;
    }, {});

    document.getElementById("stat-total").textContent = totalRequests;
    document.getElementById("stat-avg-latency").textContent = `${avgLatency}ms`;
    document.getElementById("stat-statuses").innerHTML =
  Object.entries(statusCounts)
          .map(([status, count]) => `<span>${status}: ${count}</span>`)
          .join(" | ");
  }

  //Fetches latest metric data to be displayed on the frontend
  async function fetchMetrics() {
    try {
      const res = await fetch("/metrics");
      if (!res.ok) {
        console.warn("Metrics endpoint returned", res.status);
        return;
      }
      metricsData = await res.json();
      renderStats(metricsData);
      if (!adminSettings.pause_bars) {
        pushActivityBar(metricsData.length); //Used to display requests on the activity graph
      }
    } catch (err) {
      console.error("Failed to fetch the metrics data", err);
    }
  }

//Allows for pausing and changing interval of metric visualisation speed
//Also just controls activity bar in general
let metricsInterval;

function startMetricsPolling() {
  clearInterval(metricsInterval);
  if (!adminSettings.pause_bars) {
    metricsInterval = setInterval(fetchMetrics, adminSettings.barInterval * 1000)
  }
}

//Security Alerts functionality

//For rendering the security alerts into the security container
function renderingSecurityAlerts(alerts) {
  const container = document.getElementById("security_list");
  adminSettings.alertsData = alerts;
  container.innerHTML = "";

  const filtered = alerts.filter(alert => {
    if (adminSettings.mute_404 && alert.type === "404 Not Found") return false;
    if (adminSettings.mute_slow && alert.type === "Slow Response") return false;
    return true;
});

  if (filtered.length === 0) {
    container.innerHTML = `<li class="no_alerts">No alerts detected</li>`;
    return;
  }

  //Most recent alerts bumped
  [...filtered].reverse().forEach(alert => {
    const li = document.createElement("li");
    li.className = `security_alert severity_${alert.severity}`;
    li.innerHTML = `
      <span class="alert_type">${alert.type}</span>
      <span class="alert_message">${alert.message}</span>
      <div class="alert_meta">
        <span>${alert.ip}</span>
        <span>${alert.time}</span>
      </div>
    `;
    container.appendChild(li)
  });
}

//Finds alerts from backened to render in the container
async function fetchSecurityAlerts() {
  try {
    const res = await fetch("/security");
    if (!res.ok) {
      console.warn("Security endpoint found", res.status);
      return;
    }
    const alerts = await res.json();
    renderingSecurityAlerts(alerts);
  } catch (err) {
    console.error("Failed to find valid security alerts:", err);
  }
}

//Checks every five seconds
setInterval(fetchSecurityAlerts, 5000);
fetchSecurityAlerts();

//Used for opening and closing the settings menu
function openSettings() {
  document.getElementById("settings_panel").style.display = "flex";
  document.getElementById("mute_404").checked = adminSettings.mute_404;
  document.getElementById("mute_slow").checked = adminSettings.mute_slow;
  document.getElementById("barInterval").value = adminSettings.barInterval;
} 
function closeSettings() {
  document.getElementById("settings_panel").style.display = "none";
}

//Clears security alerts
async function clearAlerts() {
  await fetch("/security/clear", { method: "POST"});
  fetchSecurityAlerts();
}

//Clears metrics & reloads
async function clearMetrics() {
  await fetch("/metrics/clear", { method: "POST"});
  fetchMetrics();
}

//Downloads alerts as JSON
function exportAlerts() {
  const blob = new Blob([JSON.stringify(adminSettings.alertsData, null, 2)],
    { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "alerts.json";
  a.click(); 
}

//Downloads metrics as JSON
function exportMetrics() {
  const blob = new Blob([JSON.stringify(metricsData, null, 2)],
    { type: "application/json"  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "metrics.json";
  a.click(); 
}

//Fun websocket stuff
const entityClient = EntityWS(handleEntityUpdate);
entityClient.connect();
window.addEventListener("load", () => {
  entityClient.subscribe(entity_list.map(e => e.id))
});
function EntityWS(onUpdate, onStatus) {
  let ws = null;
  let subscribedIds = [];
  let reconnectTimeout = null;

  const connect = () => {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:"; //Protocol used for https enforcement
    const wsUrl = `${protocol}//${location.host}/api/v1/entities/ws`;

    try {
      ws = new WebSocket(wsUrl);
    } catch (err) {
      console.error("WebSocket init error:", err);
      return;
    }

    onStatus?.("connecting");

    ws.onopen = () => {
      console.log("WebSocket Connected");
      onStatus?.("connected");

      //if disconnect resubscribe
      if (subscribedIds.length > 0) {
        subscribe(subscribedIds);
      }
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        //Shows subscribed to entities
        if (message.status === "subscribed" && message.entities) {
          console.log("Subscribed:", message.entities);
          
          //Gets location data
          Object.entries(message.entities).forEach(([id, data]) => {
            const lat = data?.last_location?.lat ?? null;
            const lng = data?.last_location?.lng ?? null;

            onUpdate(id, lat, lng, data);
          });
        }

        //Gets active updates
        else if (message.type === "update" && message.data) {
          const { entity_id, latitude, longitude, ...extra } = message.data;

          onUpdate(entity_id, latitude, longitude, extra);
        }

        //Used for the websocket tester in the settings
        else if (message.type === "pong") {
        onStatus?.("alive"); 
        const statusEl = document.getElementById("ws_status");
        statusEl.textContent = "Working";
        statusEl.style.color = "green";
        }    

      } catch (err) {
        console.error("Message parse error:", err);
      }   
    };

    ws.onclose = () => {
      console.warn("WebSocket closed. Reconnecting...");
      onStatus?.("disconnected");
      //Waits before reconnect
      reconnectTimeout = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
      onStatus?.("error");
    };
  };

  //Gets entity data to track
  const subscribe = (ids) => {
    subscribedIds = ids;

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        action: "subscribe",
        entity_ids: ids
      }));
    } else {
      console.warn("WS not ready, connecting first...");
    }
  };

  //Pings to server
  const sendPing = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "ping" }));
    }
  };
  
  const disconnect = () => {
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    ws?.close();
    ws = null;
  };

  return {
    connect,
    subscribe,
    sendPing,
    disconnect,
    isConnected: () => ws?.readyState === WebSocket.OPEN
  };
}

//For websocket connection updates
function handleEntityUpdate(id, lat, lng, data) {
  const entity = entity_list.find(e => e.id === id);
  if (!entity) return;

  entity.last_updated = data?.timestamp || new Date().toISOString();

  if (lat != null) entity.latitude = lat;
  if (lng != null) entity.longitude = lng;

  updateEntityList(entity_list);
}

//Used for websocket test button
function testWebsocket() {
  const statusEl = document.getElementById("ws_status");

  if (!entityClient.isConnected()) {
    statusEl.textContent = "Not connected :(";
    statusEl.style.color = "red";
    return;
  }

  //Pending state
  statusEl.textContent = "Pinging...";
  statusEl.style.color = "orange";
  entityClient.sendPing();
}