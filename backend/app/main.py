from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.db import Base, engine
from app.routers import auth, cases, devices, observations, ownership


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Prototype shortcut: create tables on startup. Replace with Alembic
    # migrations if the schema must change on a database that holds data.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="TraceLink AI", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 body repeats the submitted value ("input"). That would
    # send passwords and IMEIs back over the wire and into logs, so keep only
    # where the problem is and what kind it is.
    errors = [
        {"loc": list(e.get("loc", [])), "msg": e.get("msg", "Invalid value"), "type": e.get("type", "")}
        for e in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(ownership.router)
app.include_router(cases.router)
app.include_router(observations.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
