from fastapi import FastAPI
from fastapi.responses import JSONResponse


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


app = FastAPI(title="Marco API", default_response_class=UTF8JSONResponse)


@app.get("/")
def home():
    return {"message": "Сайн байна уу! Би Марко байна."}


@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"Сайн уу, {name}! Би Марко."}