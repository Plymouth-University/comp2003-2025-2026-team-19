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