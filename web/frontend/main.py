import fastapi
from fastapi import Request, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import time
import secrets
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from core.settings import settings

templates = Jinja2Templates(directory="static/")
static = StaticFiles(directory="static/")
app = fastapi.FastAPI(
    title="ferrytracker Web Backend",
    description="Backend API for ferrytracker web application, \
serving html pages and static assets.",
    version="0.1.0",
    docs_url=None,
)

app.mount("/static", static, name="static")

#Log in authentication
security = HTTPBasic()

#Checks presented log-in details
def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    valid_user = secrets.compare_digest(credentials.username, settings.ADMIN_USER)
    valid_pass = secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)
    #Rejects log-in if details aren't exactly what's presented in the .env
    if not (valid_user and valid_pass):
        raise HTTPException(status_code=401, detail="Unauthorised")

#Security vulnerability paths to check
SusPaths = ["/.env", "/wp-login.php", "/phpmyadmin", "/config", "/shell"]
SusExtensions = [".php", ".asp", ".aspx", ".cgi", ".sh"]

#Used for rate limiting
from collections import defaultdict
ip_requests_count = defaultdict(list)

#Security alert logging

alerts = []

#Used to protect visitor IPs in the frontend
def ip_mask(ip: str) -> str:
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
    return ip

#Needed as server will be constantly on and helps stop the security container from being flooded with info
maxAlerts = 300

def log_alert(alert_type: str, message: str, ip: str, severity: str):
    """Adds security alerts to list
    Args:
        alert_type (str): Label
        message (str): Description of alert
        ip (str): IP address of request
        severity (str): light or major alert
    """
    alerts.append({
        "type": alert_type,
        "message": message,
        "ip": ip_mask(ip),
        "time": time.strftime("%H:%M:%S"),
        "severity": severity
    })

    if len(alerts) > maxAlerts:
        alerts.pop(0)

@app.get("/security")
async def get_security():
    return alerts[-20:]

@app.post("/security/clear")
async def clear_security():
    alerts.clear()
    return {"message": "Alerts cleared"}

#Used for retrieving metric data as the server runs i.e. current request
#average latency, status codes, etc
metrics = []

@app.middleware("http")
async def record_metrics(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    if request.method == "GET":
        metrics.append ({
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round((time.time() - start ) * 1000, 2),
            "timestamp": time.strftime("%H:%M:%S")
        })
        ip = request.client.host
        #Used for looking for sus activity in file paths ඞ
        if request.url.path in SusPaths:
            log_alert(
                alert_type="Unusual activity",
                message=f"Probe attempt on {request.url.path}",
                ip=ip,
                severity="critical"
            )
        #In case any scanner asks for a .php or asp file
        if any(request.url.path.endswith(ext) for ext in SusExtensions):
            log_alert(
                alert_type="Suspicious File Request",
                message=f"Request for suspicious file type: {request.url.path}",
                ip=ip,
                severity="warning"
            )
        #If needed file is missing
        if response.status_code == 404:
            log_alert(
                alert_type="404 Not Found",
                message=f"Missing resource requested: {request.url.path}",
                ip=request.client.host,
                severity="warning"
            )
        #Flags internal server errors
        if response.status_code == 500:
            log_alert(
                alert_type="Server Error",
                message=f"Critical Server Error on {request.url.path}",
                ip=ip,
                severity="critical"
            )
        #Rate limits if too many requests are made
        now = time.time()
        ip_requests_count[ip] = [t for t in ip_requests_count[ip] if now -t < 60]
        ip_requests_count[ip].append(now)
        if len(ip_requests_count[ip]) > 50:
            log_alert(
                alert_type="Rate Limit",
                message=f"Unusually high request volume: {len(ip_requests_count[ip])} requests in 60s",
                ip=ip,
                severity="critical"
            )
        #For slow response times which could indicate server issues
        latency = round((time.time() - start) * 1000, 2)
        if latency > 2000:
            log_alert(
                alert_type="Slow Response",
                message=f"Request to {request.url.path} took {latency}ms",
                ip=ip,
                severity="warning"
            )
    return response

@app.get("/metrics")
async def get_metrics():
    return metrics [-50:]

@app.post("/metrics/clear")
async def clear_metrics():
    metrics.clear()
    return {"message": "Metrics cleared"}

#Routes
@app.get("/")
async def get_root():
    """Returns a welcome message or the index page.
    Returns:
        dict: A welcome message.
    """
    return {"message": "Welcome to the ferrytracker Web Backend!"}

    # TODO: Return index.html template
    # return templates.TemplateResponse("index.html", {"request": request})


@app.get("/status/{entity_id}")
async def get_status(
    request: fastapi.Request, entity_id: str
) -> fastapi.responses.HTMLResponse:
    """Returns the status page for a given entity_id.
    Args:
        request (fastapi.Request): The incoming request object.
        entity_id (str): The entity ID to fetch the status for.

    Returns:
        fastapi.responses.HTMLResponse: The rendered status HTML page.
    """
    # TODO: Check if entity_id exists and fetch its status

    return templates.TemplateResponse(
        "status.html", {"request": request, "entity_id": entity_id}
    )

@app.get("/admin/{entity_id}")
async def get_admin(
    request: fastapi.Request, entity_id: str, _=Depends(require_admin) #Forces a valid log-in for admin page access
) -> fastapi.responses.HTMLResponse:

    return templates.TemplateResponse(
        "admin_page.html", {"request": request, "entity_id": entity_id}
    )


@app.get("/health")
async def get_health():
    """Return a health check message.
    Returns:
        dict: A message indicating the service is healthy.
    """
    return {"message": "Service is healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
