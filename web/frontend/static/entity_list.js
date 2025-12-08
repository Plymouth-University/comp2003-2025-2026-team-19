const entity_list = [
    {
        "entity_id": "e22f0bc9-f01f-4d7d-a37d-748af20165d4",
        "journey": {
            "name": "Cremyll to Royal William Yard"
        }
    },
    {
        "entity_id": "a91c3b1e-2c4a-4e8f-9a0d-5f3e2d1b0c9f",
        "journey": {
            "name": "Plymouth Hoe to Mount Batten"
        }
    },
    {
        "entity_id": "b3e8d7a2-7f6c-4b5d-8c1a-9e0f3d2c1b4a",
        "journey": {
            "name": "Torpoint to Devonport"
        }
    },
    {
        "entity_id": "c6f2a4d9-1b3e-4c5f-9d7b-8a9c0e1d2f3g",
        "journey": {
            "name": "Saltash to Brunel Green"
        }
    },
    {
        "entity_id": "d1g5h8i3-j2k4-l6m8-n0p9-q7r5s3t1u0v9",
        "journey": {
            "name": "Bovisand to Cawsand"
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
      //Uses innerHTML to display entities and use break
      li.innerHTML = `
      <a href="/status/${entity.entity_id}">
      ${entity.journey.name}
      </a><br>
    `;
    //Adds list to container
    entity_container.appendChild(li);
  });
}

//Calls function alongside the entity list
document.addEventListener("DOMContentLoaded", () => {
updateEntityList(entity_list);
})