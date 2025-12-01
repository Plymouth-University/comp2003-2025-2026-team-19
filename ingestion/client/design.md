```mermaid
sequenceDiagram
participant client
participant server (fastapi)
participant db

loop Every 10s
client->>+server (fastapi):id,lat,lon,time,auth key
server (fastapi)->>server (fastapi):validate auth
server (fastapi)->>server (fastapi):validate data
server (fastapi)->>-db:data
end
```