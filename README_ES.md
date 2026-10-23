# SEUS AI Backend

Servidor inicial de SEUS AI construido con FastAPI.

## Funciones
- Comprobación del servidor.
- Comprobación de conexión a PostgreSQL.
- Registro de usuarios de prueba.
- Registro de solicitudes de video.
- Consulta de solicitudes.
- Consulta del plan del usuario.

## Endpoints
- `GET /`
- `GET /health`
- `GET /docs`
- `GET /v1/db-check`
- `POST /v1/users`
- `POST /v1/videos`
- `GET /v1/videos`
- `GET /v1/videos/{generation_id}`
- `GET /v1/me/plan`

## Configuración
Configura `DATABASE_URL` y `API_TOKEN` como variables de entorno en el alojamiento.

## Importante
Este proyecto todavía no genera videos reales. Hace falta conectar PostgreSQL con el esquema correcto y un proveedor de generación de video. El token compartido es solo para pruebas; antes de abrirlo al público hay que implementar autenticación y autorización por usuario.
