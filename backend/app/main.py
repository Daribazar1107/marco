from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import engine


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


app = FastAPI(
    title=f"{settings.app_name} API",
    default_response_class=UTF8JSONResponse,
)


@app.get("/")
def home():
    return {"message": "Сайн байна уу! Би Марко байна."}


@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"Сайн уу, {name}! Би Марко."}


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT now() AS db_time, version() AS pg_version")
            ).one()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Database error: {error}")

    return {
        "status": "ok",
        "database": "connected",
        "db_time": row.db_time.isoformat(),
        "postgres": row.pg_version,
    }