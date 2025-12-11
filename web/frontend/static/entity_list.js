const entity_list = [
  {
    "id": "b85e5637-4791-4aa4-abec-a2ac3e4a946e",
    "name": "Plymouth Venturer",
    "route": null
  },
  {
    "id": "fa7fa868-8eac-4e20-a69c-b7b7c17364bb",
    "name": "Plymouth Sound",
    "route": null
  },
  {
    "id": "fa0a1599-8de1-4e08-aee8-f1607e1359cb",
    "name": "Tamar Belle",
    "route": null
  },
  {
    "id": "add9ce40-e60c-41b4-b6e9-e7dc3185849c",
    "name": "Plymouth Princess",
    "route": null
  },
  {
    "id": "9e2f2cbd-2671-4972-9115-c0bd8d5cef2d",
    "name": "Island Princess",
    "route": null
  },
  {
    "id": "072caf2a-a921-4128-8369-75b237c42161",
    "name": "Edgcumbe Belle",
    "route": {
      "id": "b7ce8114-7ca1-4a6e-8e03-37b261613d87",
      "start_location": {
        "id": "21817854-9c58-445d-bbfe-be9de592a214",
        "name": "Plymouth Stonehouse Ferry Terminal"
      },
      "end_location": {
        "id": "2300f6f1-6fd9-49a5-8cab-cc4415d02dc7",
        "name": "Cremyll Mount Edgcumbe Ferry Landing"
      }
    }
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
      
      //List acts differently depending if route data is null or not
      if (entity.route === null) {
      //Uses innerHTML to display entities and use break
      li.innerHTML = `
      <a href="/status/${entity.id}">
      ${entity.name}
      </a>
    `;
    } else {
        li.innerHTML = `
        <a href="/status/${entity.id}">
           ${entity.name}:<br>
           ${entity.route.start_location.name}
           →
           ${entity.route.end_location.name}
           </a>
        `;
    }
    //Adds list to container
    entity_container.appendChild(li);
    entity_container.appendChild(document.createElement("br"));
  });
}

//Calls function alongside the entity list
document.addEventListener("DOMContentLoaded", () => {
updateEntityList(entity_list);
})