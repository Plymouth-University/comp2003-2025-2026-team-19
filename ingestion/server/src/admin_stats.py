import requests
from fastapi import FastAPI
from core.settings import settings

app = FastAPI()

SENTRY_TOKEN = settings.SENTRY_TOKEN
ORG_SLUG = settings.SENTRY_ORG

@app.get("/sentry/metrics")
def get_sentry_metrics():
    url = f"https://sentry.io/api/0/organizations/{ORG_SLUG}/events/"

    params = {
        "field": ["count()", "avg(span.duration)", "p95(span.duration)"],
        "query": "event.type:transaction",
        "statsPeriod": "7d",
        "interval": "1h",              
    }

    headers = {
        "Authorization": f"Bearer {SENTRY_TOKEN}"
    }

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    return data