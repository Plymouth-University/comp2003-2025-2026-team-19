import requests
from fastapi import FastAPI

app = FastAPI()

SENTRY_TOKEN = "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"
ORG_SLUG = "isaac-taylor"

@app.get("/api/sentry/metrics")
def get_sentry_metrics():
    url = f"https://sentry.io/api/0/organizations/{ORG_SLUG}/events/"

    params = {
        "field": ["count()", "avg(span.duration)", "p95(span.duration)"],
        "query": "event.type:transaction",
        "statsPeriod": "7d",
        "interval": "1h",              
    }

    headers = {
        "Authorizatio": f"Bearer {SENTRY_TOKEN}"
    }

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    return data