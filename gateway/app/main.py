"""API Gateway for Punto y Sal.

Single public entry point for the frontend. It forwards HTTP requests to
the three microservices over the internal network (real HTTP proxying, not
imported routers) and exposes health information for itself and for the
downstream services.

Routing map (versioned, under /api/v1/):
    /api/v1/clientes/**  -> CLIENTES_SERVICE_URL
    /api/v1/reservas/**  -> RESERVAS_SERVICE_URL
    /api/v1/catalogo/**  -> CATALOGO_SERVICE_URL
"""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root, where the optional local .env file is located.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Service identifiers used in responses (never expose internal URLs).
SERVICES = {
    "clientes": "CLIENTES_SERVICE_URL",
    "reservas": "RESERVAS_SERVICE_URL",
    "catalogo": "CATALOGO_SERVICE_URL",
}


class GatewaySettings(BaseSettings):
    """Gateway configuration loaded from environment variables.

    Defaults keep the gateway usable on the local machine; inside Docker
    Compose the URLs are provided as environment variables using the
    Compose service names.
    """

    CLIENTES_SERVICE_URL: str = "http://localhost:8001"
    RESERVAS_SERVICE_URL: str = "http://localhost:8002"
    CATALOGO_SERVICE_URL: str = "http://localhost:8003"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = GatewaySettings()

# Downstream request timeout in seconds.
DOWNSTREAM_TIMEOUT = 10.0

# Hop-by-hop headers must not be forwarded by a proxy.
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create one shared HTTP client for the gateway lifetime."""
    app.state.client = httpx.AsyncClient(timeout=DOWNSTREAM_TIMEOUT)
    yield
    await app.state.client.aclose()


app = FastAPI(
    title="API Gateway",
    description=(
        "Centralized entry point for the Punto y Sal backend. "
        "Routes /api/v1/ requests to the clientes, reservas and catalogo "
        "microservices."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def _service_url(service: str) -> str:
    """Return the configured base URL for a service."""
    return {
        "clientes": settings.CLIENTES_SERVICE_URL,
        "reservas": settings.RESERVAS_SERVICE_URL,
        "catalogo": settings.CATALOGO_SERVICE_URL,
    }[service]


def _original_path(request: Request) -> str:
    """Return the path exactly as the client sent it.

    Starlette may rewrite scope["path"] (redirect-slashes adds a trailing
    slash), which would make the downstream service answer with a 307 to
    an internal URL. raw_path is the untouched original path.
    """
    raw_path = request.scope.get("raw_path")
    if isinstance(raw_path, bytes):
        return raw_path.decode("utf-8")
    return request.url.path


def _rewrite_location(location: str) -> str:
    """Strip internal service origins from redirect targets.

    A downstream 307 may point at http://servicio:puerto/... — the gateway
    must not expose internal hostnames to the frontend.
    """
    for base in (
        settings.CLIENTES_SERVICE_URL,
        settings.RESERVAS_SERVICE_URL,
        settings.CATALOGO_SERVICE_URL,
    ):
        prefix = base.rstrip("/")
        if location.startswith(prefix):
            rewritten = location[len(prefix):]
            return rewritten or "/"
    return location


async def _proxy_request(service: str, request: Request) -> JSONResponse:
    """Forward the incoming request to the given service and return its response.

    Errors are translated into consistent JSON responses that never expose
    internal URLs, credentials or stack traces.
    """
    url = _service_url(service).rstrip("/") + _original_path(request)
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }
    body = await request.body()

    try:
        upstream = await request.app.state.client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            headers=headers,
            content=body,
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={
                "detail": f"Service '{service}' did not respond in time",
                "service": service,
            },
        )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=503,
            content={
                "detail": f"Service '{service}' is unavailable",
                "service": service,
            },
        )

    media_type = upstream.headers.get("content-type", "application/json")
    response_headers = {}
    location = upstream.headers.get("location")
    if location:
        response_headers["location"] = _rewrite_location(location)

    # Non-JSON bodies (e.g. redirects) are passed through untouched.
    if "application/json" not in media_type:
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=media_type,
            headers=response_headers,
        )

    # Some upstream responses declare JSON but carry an empty body;
    # never crash while parsing them.
    if upstream.content:
        try:
            content = upstream.json()
        except ValueError:
            content = upstream.text
    else:
        content = None

    return JSONResponse(
        status_code=upstream.status_code,
        content=content,
        media_type=media_type,
        headers=response_headers,
    )


@app.get("/health")
async def gateway_health():
    """Gateway liveness (does not depend on downstream services)."""
    return {"service": "gateway", "status": "ok"}


@app.get("/health/services")
async def services_health(request: Request):
    """Aggregate the /health of the three microservices."""
    results = {}
    overall = "ok"

    for service in SERVICES:
        url = _service_url(service).rstrip("/") + "/health"
        try:
            response = await request.app.state.client.get(url)
            if response.status_code == 200:
                results[service] = "ok"
            else:
                results[service] = "unhealthy"
                overall = "degraded"
        except httpx.HTTPError:
            results[service] = "unavailable"
            overall = "degraded"

    return {
        "service": "gateway",
        "status": overall,
        "downstream": results,
    }


# Sprint 1 is read-only: only GET is proxied. Mutation methods (POST/PUT/
# PATCH/DELETE) will be enabled here when the services implement them in a
# later sprint; until then the services would reject them anyway.
# Two routes per service: the exact collection path (e.g. /api/v1/clientes)
# and the catch-all for nested paths (e.g. /api/v1/clientes/123).
@app.get("/api/v1/clientes")
@app.get("/api/v1/clientes/{path:path}")
async def route_clientes(request: Request):
    """Proxy /api/v1/clientes/** to the clientes microservice."""
    return await _proxy_request("clientes", request)


@app.get("/api/v1/reservas")
@app.get("/api/v1/reservas/{path:path}")
async def route_reservas(request: Request):
    """Proxy /api/v1/reservas/** to the reservas microservice."""
    return await _proxy_request("reservas", request)


@app.get("/api/v1/catalogo")
@app.get("/api/v1/catalogo/{path:path}")
async def route_catalogo(request: Request):
    """Proxy /api/v1/catalogo/** to the catalogo microservice."""
    return await _proxy_request("catalogo", request)
