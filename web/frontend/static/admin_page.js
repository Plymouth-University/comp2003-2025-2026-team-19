//Ferry data
const entity_list = [
  {
    "id": "b85e5637-4791-4aa4-abec-a2ac3e4a946e",
    "name": "Plymouth Venturer",
    "route": null,
    "active": false,
    "last_updated": "10-03-10 18:35"
  },
  {
    "id": "fa7fa868-8eac-4e20-a69c-b7b7c17364bb",
    "name": "Plymouth Sound",
    "route": null,
    "active": false,
    "last_updated": "10-03-10 18:35"
  },
  {
    "id": "fa0a1599-8de1-4e08-aee8-f1607e1359cb",
    "name": "Tamar Belle",
    "route": null,
    "active": false,
    "last_updated": "10-03-10 18:35"
  },
  {
    "id": "add9ce40-e60c-41b4-b6e9-e7dc3185849c",
    "name": "Plymouth Princess",
    "route": null,
    "active": false,
    "last_updated": "10-03-10 18:35"
  },
  {
    "id": "9e2f2cbd-2671-4972-9115-c0bd8d5cef2d",
    "name": "Island Princess",
    "route": null,
    "active": false,
    "last_updated": "10-03-10 18:35"
  },
  {
    "id": "072caf2a-a921-4128-8369-75b237c42161",
    "name": "Edgcumbe Belle",
    "route": null,
    "active": false,
    "last_updated": "10-03-10 18:35"
  },
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
      const statusClass = entity.active ? "status-green" : "status-red";

      //List acts differently depending if route data is null or not
      if (entity.route === null) {
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

document.addEventListener("DOMContentLoaded", () => {
  updateEntityList(entity_list);
});

//Used for opening and closing the settings menu
function openSettings() {
  document.getElementById("settings_panel").style.display = "flex";
} 

function closeSettings() {
  document.getElementById("settings_panel").style.display = "none";
}

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
      pushActivityBar(metricsData.length); //Used to display requests on the activity graph
    } catch (err) {
      console.error("Failed to fetch the metrics data", err);
    }
  }

//Checks metrics every 3 seconds
setInterval(fetchMetrics, 3000);
fetchMetrics();

//Security Alerts functionality

//For rendering the security alerts into the security container
function renderingSecurityAlerts(alerts) {
  const container = document.getElementById("security_list");
  container.innerHTML = "";

  if (alerts.length === 0) {
    container.innerHTML = `<li class="no_alerts">No alerts detected</li>`;
    return;
  }

  //Most recent alerts bumped
  [...alerts].reverse().forEach(alert => {
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