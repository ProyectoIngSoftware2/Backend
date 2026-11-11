"""API Gateway for Punto y Sal.

Single public entry point for the frontend. It forwards HTTP requests to
the three microservices over the internal network (real HTTP proxying, not
imported routers) and exposes health information for itself and for the
downstream services.

Routing map (versioned, under /api/v1/):
    POST /api/v1/auth/login -> AUTH_SERVICE_URL (login; the gateway only
                                proxies it and performs no authentication)
    /api/v1/clientes/**  -> CLIENTES_SERVICE_URL
    /api/v1/reservas/**  -> RESERVAS_SERVICE_URL
    /api/v1/catalogo/**  -> CATALOGO_SERVICE_URL

All HTTP methods (GET, POST, PUT, PATCH, DELETE) are proxied. The
Authorization header is forwarded untouched (it is not hop-by-hop), but
token validation happens exclusively inside the microservices: the
gateway never authenticates, so routing through it can never bypass a
microservice's authorization rules.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, Response
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root, where the optional local .env file is located.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Service identifiers used in responses (never expose internal URLs).
SERVICES = {
    "auth": "AUTH_SERVICE_URL",
    "clientes": "CLIENTES_SERVICE_URL",
    "reservas": "RESERVAS_SERVICE_URL",
    "catalogo": "CATALOGO_SERVICE_URL",
}

# Every HTTP method supported by the proxied routes.
PROXIED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


class GatewaySettings(BaseSettings):
    """Gateway configuration loaded from environment variables.

    Defaults keep the gateway usable on the local machine; inside Docker
    Compose the URLs are provided as environment variables using the
    Compose service names.
    """

    CLIENTES_SERVICE_URL: str = "http://localhost:8001"
    RESERVAS_SERVICE_URL: str = "http://localhost:8002"
    CATALOGO_SERVICE_URL: str = "http://localhost:8003"
    AUTH_SERVICE_URL: str = "http://localhost:8004"

    # Comma-separated list of frontend origins allowed to make
    # cross-origin requests (e.g. https://app.example.com). Empty by
    # default: no CORS middleware is installed until it is configured,
    # so no unauthorized origin is ever allowed.
    CORS_ORIGINS: str = ""

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
        "Routes /api/v1/ requests to the auth, clientes, reservas and "
        "catalogo microservices."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Custom OpenAPI schema: adds Bearer JWT security scheme, request body
# declarations for write operations, response schemas, and security
# requirements on protected operations. This makes the gateway /docs
# usable for frontend developers.
# ---------------------------------------------------------------------------

# Request body schemas for write operations, keyed by (path, method).
# These document the JSON payload the gateway forwards to the downstream
# microservice. Schemas are intentionally conservative (only required
# fields marked) so they remain valid even if the service adds optional
# fields later.
_GATEWAY_REQUEST_BODIES = {
    ("/api/v1/auth/login", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["correo", "password"],
                    "properties": {
                        "correo": {"type": "string", "format": "email"},
                        "password": {"type": "string", "minLength": 1},
                    },
                    "additionalProperties": False,
                },
                "example": {"correo": "admin@puntoysal.test", "password": "ClaveSegura2026"},
            }
        },
    },
    ("/api/v1/clientes", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["nombre_completo", "correo", "password", "telefono"],
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "correo": {"type": "string", "format": "email"},
                        "password": {"type": "string", "minLength": 8, "maxLength": 72},
                        "telefono": {"type": "string", "minLength": 1, "maxLength": 30},
                        "numero_identidad": {"type": "string", "minLength": 1, "maxLength": 30},
                    },
                    "additionalProperties": False,
                },
                "example": {
                    "nombre_completo": "Ana López",
                    "correo": "ana@ejemplo.com",
                    "password": "ClaveSegura2026",
                    "telefono": "+504 9999-0001",
                },
            }
        },
    },
    ("/api/v1/clientes/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "telefono": {"type": "string", "minLength": 1, "maxLength": 30},
                        "correo": {"type": "string", "format": "email"},
                        "numero_identidad": {"type": "string", "minLength": 1, "maxLength": 30},
                    },
                    "additionalProperties": False,
                },
                "example": {"telefono": "+504 8888-2222"},
            }
        },
    },
    ("/api/v1/clientes/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "telefono": {"type": "string", "minLength": 1, "maxLength": 30},
                        "correo": {"type": "string", "format": "email"},
                        "numero_identidad": {"type": "string", "minLength": 1, "maxLength": 30},
                    },
                    "additionalProperties": False,
                },
                "example": {"nombre_completo": "Ana López"},
            }
        },
    },
    ("/api/v1/usuarios", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["nombre_completo", "correo", "password", "rol"],
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "correo": {"type": "string", "format": "email"},
                        "password": {"type": "string", "minLength": 8, "maxLength": 72},
                        "rol": {"type": "string", "enum": ["administrador", "cliente"]},
                    },
                    "additionalProperties": False,
                },
                "example": {
                    "nombre_completo": "Nuevo Usuario",
                    "correo": "nuevo@puntoysal.test",
                    "password": "ClaveNueva2026",
                    "rol": "cliente",
                },
            }
        },
    },
    ("/api/v1/usuarios/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "correo": {"type": "string", "format": "email"},
                        "rol": {"type": "string", "enum": ["administrador", "cliente"]},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"correo": "admin.nuevo@puntoysal.test"},
            }
        },
    },
    ("/api/v1/usuarios/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "correo": {"type": "string", "format": "email"},
                        "rol": {"type": "string", "enum": ["administrador", "cliente"]},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"rol": "administrador"},
            }
        },
    },
    ("/api/v1/roles", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["nombre"],
                    "properties": {
                        "nombre": {"type": "string", "minLength": 1, "maxLength": 40},
                        "descripcion": {"type": "string", "maxLength": 180},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"nombre": "recepcion", "descripcion": "Personal de recepción"},
            }
        },
    },
    ("/api/v1/roles/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string", "minLength": 1, "maxLength": 40},
                        "descripcion": {"type": "string", "maxLength": 180},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"activo": False},
            }
        },
    },
    ("/api/v1/roles/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string", "minLength": 1, "maxLength": 40},
                        "descripcion": {"type": "string", "maxLength": 180},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"nombre": "recepcion"},
            }
        },
    },
    ("/api/v1/catalogo/horarios", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["dia_semana", "hora_apertura", "hora_cierre", "intervalo_minutos"],
                    "properties": {
                        "dia_semana": {"type": "integer", "minimum": 1, "maximum": 7},
                        "hora_apertura": {"type": "string", "pattern": "^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"},
                        "hora_cierre": {"type": "string", "pattern": "^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"},
                        "intervalo_minutos": {"type": "integer", "minimum": 1, "maximum": 1440},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"dia_semana": 1, "hora_apertura": "08:00", "hora_cierre": "22:00", "intervalo_minutos": 30},
            }
        },
    },
    ("/api/v1/catalogo/horarios/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "dia_semana": {"type": "integer", "minimum": 1, "maximum": 7},
                        "hora_apertura": {"type": "string", "pattern": "^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"},
                        "hora_cierre": {"type": "string", "pattern": "^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"},
                        "intervalo_minutos": {"type": "integer", "minimum": 1, "maximum": 1440},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"activo": False},
            }
        },
    },
    ("/api/v1/catalogo/horarios/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "dia_semana": {"type": "integer", "minimum": 1, "maximum": 7},
                        "hora_apertura": {"type": "string", "pattern": "^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"},
                        "hora_cierre": {"type": "string", "pattern": "^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"},
                        "intervalo_minutos": {"type": "integer", "minimum": 1, "maximum": 1440},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"hora_apertura": "07:00", "hora_cierre": "23:00"},
            }
        },
    },
    ("/api/v1/catalogo/bloqueos", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["inicio", "fin", "motivo"],
                    "properties": {
                        "id_mesa": {"type": "integer"},
                        "inicio": {"type": "string", "format": "date-time"},
                        "fin": {"type": "string", "format": "date-time"},
                        "motivo": {"type": "string", "minLength": 1, "maxLength": 180},
                    },
                    "additionalProperties": False,
                },
                "example": {"id_mesa": 3, "inicio": "2026-12-01T14:00:00-06:00", "fin": "2026-12-01T16:00:00-06:00", "motivo": "Mantenimiento"},
            }
        },
    },
    ("/api/v1/catalogo/bloqueos/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "id_mesa": {"type": "integer"},
                        "inicio": {"type": "string", "format": "date-time"},
                        "fin": {"type": "string", "format": "date-time"},
                        "motivo": {"type": "string", "minLength": 1, "maxLength": 180},
                    },
                    "additionalProperties": False,
                },
                "example": {"motivo": "Mantenimiento programado"},
            }
        },
    },
    ("/api/v1/catalogo/bloqueos/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "id_mesa": {"type": "integer"},
                        "inicio": {"type": "string", "format": "date-time"},
                        "fin": {"type": "string", "format": "date-time"},
                        "motivo": {"type": "string", "minLength": 1, "maxLength": 180},
                    },
                    "additionalProperties": False,
                },
                "example": {"inicio": "2026-12-01T14:00:00-06:00", "fin": "2026-12-01T18:00:00-06:00"},
            }
        },
    },
    ("/api/v1/reservas/{path}", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["fecha_hora_inicio", "cantidad_personas"],
                    "properties": {
                        "fecha_hora_inicio": {"type": "string", "format": "date-time"},
                        "cantidad_personas": {"type": "integer", "minimum": 1},
                        "duracion_minutos": {"type": "integer", "minimum": 15, "maximum": 720},
                        "id_mesa": {"type": "integer"},
                        "observaciones": {"type": "string", "maxLength": 1000},
                        "id_cliente": {"type": "integer"},
                        "platillos": {
                            "type": "array",
                            "maxLength": 50,
                            "items": {
                                "type": "object",
                                "required": ["id_platillo", "cantidad"],
                                "properties": {
                                    "id_platillo": {"type": "integer", "minimum": 1},
                                    "cantidad": {"type": "integer", "minimum": 1, "maximum": 50},
                                    "observaciones": {"type": "string", "maxLength": 500},
                                },
                                "additionalProperties": False,
                            },
                        },
                    },
                    "additionalProperties": False,
                },
                "example": {
                    "fecha_hora_inicio": "2027-03-15T19:00:00-06:00",
                    "cantidad_personas": 4,
                    "duracion_minutos": 120,
                    "observaciones": "Cumpleaños",
                    "platillos": [{"id_platillo": 1, "cantidad": 2}],
                },
            }
        },
    },
    ("/api/v1/reservas/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "fecha_hora_inicio": {"type": "string", "format": "date-time"},
                        "duracion_minutos": {"type": "integer", "minimum": 15, "maximum": 720},
                        "cantidad_personas": {"type": "integer", "minimum": 1},
                        "id_mesa": {"type": "integer"},
                        "observaciones": {"type": "string", "maxLength": 1000},
                        "estado": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "example": {"estado": "cancelada"},
            }
        },
    },
    ("/api/v1/reservas/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "fecha_hora_inicio": {"type": "string", "format": "date-time"},
                        "duracion_minutos": {"type": "integer", "minimum": 15, "maximum": 720},
                        "cantidad_personas": {"type": "integer", "minimum": 1},
                        "id_mesa": {"type": "integer"},
                        "observaciones": {"type": "string", "maxLength": 1000},
                        "estado": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "example": {"cantidad_personas": 2},
            }
        },
    },
    ("/api/v1/reservas/{path}/platillos", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["id_platillo", "cantidad"],
                    "properties": {
                        "id_platillo": {"type": "integer", "minimum": 1},
                        "cantidad": {"type": "integer", "minimum": 1, "maximum": 50},
                        "observaciones": {"type": "string", "maxLength": 500},
                    },
                    "additionalProperties": False,
                },
                "example": {"id_platillo": 2, "cantidad": 2, "observaciones": "Poco sal"},
            }
        },
    },
    ("/api/v1/reservas/{path}/platillos/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "cantidad": {"type": "integer", "minimum": 1, "maximum": 50},
                        "observaciones": {"type": "string", "maxLength": 500},
                    },
                    "additionalProperties": False,
                },
                "example": {"cantidad": 3},
            }
        },
    },
    ("/api/v1/reservas/{path}/platillos/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "cantidad": {"type": "integer", "minimum": 1, "maximum": 50},
                        "observaciones": {"type": "string", "maxLength": 500},
                    },
                    "additionalProperties": False,
                },
                "example": {"observaciones": "Sin cebolla"},
            }
        },
    },
    ("/api/v1/usuarios", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["nombre_completo", "correo", "password", "rol"],
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "correo": {"type": "string", "format": "email"},
                        "password": {"type": "string", "minLength": 8, "maxLength": 72},
                        "rol": {"type": "string", "enum": ["administrador", "cliente"]},
                    },
                    "additionalProperties": False,
                },
                "example": {
                    "nombre_completo": "Nuevo Usuario",
                    "correo": "nuevo@puntoysal.test",
                    "password": "ClaveNueva2026",
                    "rol": "cliente",
                },
            }
        },
    },
    ("/api/v1/usuarios/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "correo": {"type": "string", "format": "email"},
                        "rol": {"type": "string", "enum": ["administrador", "cliente"]},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"correo": "admin.nuevo@puntoysal.test"},
            }
        },
    },
    ("/api/v1/usuarios/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre_completo": {"type": "string", "minLength": 1, "maxLength": 120},
                        "correo": {"type": "string", "format": "email"},
                        "rol": {"type": "string", "enum": ["administrador", "cliente"]},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"rol": "administrador"},
            }
        },
    },
    ("/api/v1/roles", "post"): {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["nombre"],
                    "properties": {
                        "nombre": {"type": "string", "minLength": 1, "maxLength": 40},
                        "descripcion": {"type": "string", "maxLength": 180},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"nombre": "recepcion", "descripcion": "Personal de recepción"},
            }
        },
    },
    ("/api/v1/roles/{path}", "patch"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string", "minLength": 1, "maxLength": 40},
                        "descripcion": {"type": "string", "maxLength": 180},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"activo": False},
            }
        },
    },
    ("/api/v1/roles/{path}", "put"): {
        "required": False,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "nombre": {"type": "string", "minLength": 1, "maxLength": 40},
                        "descripcion": {"type": "string", "maxLength": 180},
                        "activo": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "example": {"nombre": "recepcion"},
            }
        },
    },
}

def _gateway_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="API Gateway",
        version="1.0.0",
        description=(
            "Centralized entry point for the Punto y Sal backend. "
            "Routes /api/v1/ requests to the auth, clientes, reservas and "
            "catalogo microservices. All write operations require a valid "
            "Bearer JWT (except public registration and public reads)."
        ),
        routes=app.routes,
    )
    # Security scheme: Bearer JWT
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token from POST /api/v1/auth/login. "
            "Send as: Authorization: Bearer <access_token>",
        }
    }
    # Global security requirement (applies to all operations unless
    # overridden at the operation level)
    openapi_schema["security"] = [{"BearerAuth": []}]

    # Tag operations by service and mark public vs protected
    for path, methods in openapi_schema["paths"].items():
        for method, op in methods.items():
            op_id = op.get("operationId", "")
            is_auth_login = path == "/api/v1/auth/login" and method == "post"
            is_clientes_register = (
                path == "/api/v1/clientes" and method == "post"
            )
            is_public_read = (
                method == "get"
                and (
                    path.startswith("/api/v1/catalogo/")
                    or path == "/health"
                    or path == "/health/services"
                    or path.startswith("/api/v1/roles")
                )
            )

            if is_auth_login or is_clientes_register or is_public_read:
                # Public: no security required
                op.pop("security", None)
            else:
                # Protected: require BearerAuth
                op["security"] = [{"BearerAuth": []}]

            # Add request body schema for write operations
            if method in ("post", "put", "patch") and not is_auth_login:
                body_schema = _GATEWAY_REQUEST_BODIES.get((path, method))
                if body_schema is not None:
                    op["requestBody"] = body_schema
                elif "requestBody" not in op:
                    op["requestBody"] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"},
                                "example": {},
                            }
                        },
                    }

            # Tag by service
            if path.startswith("/api/v1/auth"):
                op.setdefault("tags", []).append("auth")
            elif path.startswith("/api/v1/clientes") or path.startswith("/api/v1/usuarios") or path.startswith("/api/v1/roles"):
                op.setdefault("tags", []).append("clientes")
            elif path.startswith("/api/v1/reservas"):
                op.setdefault("tags", []).append("reservas")
            elif path.startswith("/api/v1/catalogo"):
                op.setdefault("tags", []).append("catalogo")
            elif path.startswith("/health"):
                op.setdefault("tags", []).append("gateway")

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = _gateway_openapi

# CORS is opt-in: when CORS_ORIGINS names the frontend origins
# (comma-separated), exactly those origins may call the API and only
# with the Authorization/Content-Type headers; while it stays empty no
# middleware is installed (Sprint 1 behaviour preserved). Cookies are
# never accepted (the frontend sends a bearer token instead).
_cors_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=PROXIED_METHODS,
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )


def _service_url(service: str) -> str:
    """Return the configured base URL for a service."""
    return {
        "clientes": settings.CLIENTES_SERVICE_URL,
        "reservas": settings.RESERVAS_SERVICE_URL,
        "catalogo": settings.CATALOGO_SERVICE_URL,
        "auth": settings.AUTH_SERVICE_URL,
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
        settings.AUTH_SERVICE_URL,
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
    # Authentication challenges must reach the frontend through the
    # gateway (401 + WWW-Authenticate: Bearer on protected endpoints).
    www_authenticate = upstream.headers.get("www-authenticate")
    if www_authenticate:
        response_headers["www-authenticate"] = www_authenticate

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
    """Aggregate the /health of the four microservices."""
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


# Every method required by the implemented endpoints is proxied
# (GET, POST, PUT, PATCH, DELETE). Two paths per service: the exact
# collection path (e.g. /api/v1/clientes) and the catch-all for nested
# paths (e.g. /api/v1/clientes/123).
#
# One route object is registered per (path, method): FastAPI derives the
# OpenAPI operation id from the route name and path using only the first
# method of the route, so a multi-method route would produce duplicate
# ids and hide operations in Swagger UI.
def _register_proxy_routes(base_name, paths, methods, service):
    """Register single-method proxy routes with unique operation ids."""
    for path in paths:
        suffix = "item" if "{path:" in path else "collection"
        for method in methods:
            # Bind the current values in default arguments (no closure
            # late-binding surprises).
            async def handler(request: Request, _service=service):
                return await _proxy_request(_service, request)

            app.add_api_route(
                path,
                handler,
                methods=[method],
                name=f"{base_name}_{method.lower()}_{suffix}",
                operation_id=f"{base_name}_{method.lower()}_{suffix}",
            )


# Login: POST only, exact path, forwarded to the auth microservice (the
# gateway never authenticates; it only forwards requests, so routing
# through it can never bypass the auth service's own checks). The
# Authorization header of later requests is forwarded untouched.
async def _route_auth_login(request: Request):
    """Proxy POST /api/v1/auth/login to the auth microservice."""
    return await _proxy_request("auth", request)


app.add_api_route(
    "/api/v1/auth/login",
    _route_auth_login,
    methods=["POST"],
    name="route_auth_login",
    operation_id="route_auth_login",
)

_register_proxy_routes(
    "route_clientes",
    ["/api/v1/clientes", "/api/v1/clientes/{path:path}"],
    PROXIED_METHODS,
    "clientes",
)

_register_proxy_routes(
    "route_reservas",
    ["/api/v1/reservas", "/api/v1/reservas/{path:path}"],
    PROXIED_METHODS,
    "reservas",
)

_register_proxy_routes(
    "route_catalogo",
    ["/api/v1/catalogo", "/api/v1/catalogo/{path:path}"],
    PROXIED_METHODS,
    "catalogo",
)

_register_proxy_routes(
    "route_usuarios",
    ["/api/v1/usuarios", "/api/v1/usuarios/{path:path}"],
    PROXIED_METHODS,
    "clientes",
)

_register_proxy_routes(
    "route_roles",
    ["/api/v1/roles", "/api/v1/roles/{path:path}"],
    PROXIED_METHODS,
    "clientes",
)
