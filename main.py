import secrets
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    api_token: str = ""
    video_provider: str = "stub"
    video_provider_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

app = FastAPI(
    title="SEUS AI Backend",
    description="API inicial de SEUS AI",
    version="0.2.0",
)


def get_conn():
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Falta configurar DATABASE_URL.")
    try:
        return psycopg.connect(settings.database_url, row_factory=dict_row)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="No se pudo conectar a PostgreSQL.") from exc


def require_token(authorization: Optional[str] = Header(default=None)):
    if not settings.api_token:
        raise HTTPException(status_code=503, detail="Falta configurar API_TOKEN.")
    expected = f"Bearer {settings.api_token}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Token no válido.")
    return True


class CreateUser(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    display_name: str = Field(default="Usuario", min_length=1, max_length=80)
    age_confirmed: bool = False


class CreateVideo(BaseModel):
    user_id: str
    prompt: str = Field(min_length=3, max_length=4000)
    input_type: str = "text_to_video"
    style: str = "Realista"
    aspect_ratio: str = "9:16"
    duration_seconds: Optional[float] = Field(default=5.0, gt=0, le=60)


@app.get("/")
def home():
    return {"app": "SEUS AI", "status": "online", "message": "Servidor iniciado correctamente"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "SEUS AI Backend"}


@app.get("/v1/db-check", dependencies=[Depends(require_token)])
def db_check():
    with get_conn() as conn:
        conn.execute("SELECT 1")
    return {"database": "connected"}


@app.post("/v1/users", dependencies=[Depends(require_token)])
def create_user(payload: CreateUser):
    if not payload.age_confirmed:
        raise HTTPException(status_code=400, detail="Confirma que tienes la edad requerida.")
    with get_conn() as conn:
        row = conn.execute(
            """
            INSERT INTO app_users (email, display_name, age_confirmed)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                age_confirmed = EXCLUDED.age_confirmed,
                updated_at = NOW()
            RETURNING id, email, display_name, role, age_confirmed, status, created_at
            """,
            (payload.email.lower(), payload.display_name, payload.age_confirmed),
        ).fetchone()
    return row


@app.post("/v1/videos", dependencies=[Depends(require_token)])
def create_video(payload: CreateVideo):
    allowed_types = {"text_to_video", "image_to_video", "video_to_video"}
    if payload.input_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Tipo de generación no compatible.")
    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, status, age_confirmed FROM app_users WHERE id = %s",
            (payload.user_id,),
        ).fetchone()
        if not user or user["status"] != "active":
            raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo.")
        if not user["age_confirmed"]:
            raise HTTPException(status_code=403, detail="Falta confirmar la edad.")
        row = conn.execute(
            """
            INSERT INTO video_generations (
                user_id, input_type, prompt, style, aspect_ratio,
                duration_seconds, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'queued')
            RETURNING id, user_id, input_type, prompt, style, aspect_ratio,
                      duration_seconds, status, created_at
            """,
            (payload.user_id, payload.input_type, payload.prompt, payload.style,
             payload.aspect_ratio, payload.duration_seconds),
        ).fetchone()
    return {
        "generation": row,
        "note": "Solicitud guardada. Falta conectar un proveedor de generación de video.",
    }


@app.get("/v1/videos/{generation_id}", dependencies=[Depends(require_token)])
def get_video(generation_id: str):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, input_type, prompt, style, aspect_ratio,
                   duration_seconds, provider, provider_job_id, status,
                   error_code, created_at, started_at, completed_at
            FROM video_generations WHERE id = %s
            """,
            (generation_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Generación no encontrada.")
    return row


@app.get("/v1/videos", dependencies=[Depends(require_token)])
def list_videos(user_id: str, limit: int = 20):
    limit = max(1, min(limit, 100))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, input_type, prompt, style, status, created_at, completed_at
            FROM video_generations
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return {"items": rows}


@app.get("/v1/me/plan", dependencies=[Depends(require_token)])
def get_plan(user_id: str):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT p.code, p.name, p.price_minor_units, p.currency,
                   s.status AS subscription_status, s.current_period_end
            FROM app_users u
            LEFT JOIN subscriptions s
                ON s.user_id = u.id AND s.status = 'active'
            LEFT JOIN plans p ON p.id = s.plan_id
            WHERE u.id = %s
            ORDER BY s.created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return row
