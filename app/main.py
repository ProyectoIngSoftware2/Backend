
from fastapi import FastAPI
from app.database import obtener_conexion

app = FastAPI(
    title="ReservasPyS API",
    description="API para la gestión de reservas del restaurante Punto y Sal",
    version="1.0.0"
)


@app.get("/")
def inicio():
    return {
        "mensaje": "API de ReservasPyS funcionando correctamente"
    }


@app.get("/health")
def health():
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

        return {
            "api": "ok",
            "base_de_datos": "conectada"
        }

    except Exception:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="No se pudo conectar con la base de datos"
        )
