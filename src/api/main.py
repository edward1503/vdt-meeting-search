from fastapi import FastAPI
from elasticsearch import Elasticsearch

from src.core.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health():
    es = Elasticsearch(settings.es_host)
    try:
        es_health = es.cluster.health()
        es_status = es_health["status"]
    except Exception as e:
        es_status = f"unavailable: {e}"
    finally:
        es.close()
    return {"status": "ok", "elasticsearch": es_status}
