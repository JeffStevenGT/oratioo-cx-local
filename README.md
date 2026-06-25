# Oratioo CX — Local (PC España)

Stack: PostgreSQL 17 + PostgREST + Vite React + Python Bot

## Requisitos previos

- PostgreSQL 17.10 (contraseña: `Pangea.2026`)
- Python 3.12+ (con pip)
- Node.js 20+
- PostgREST (descargar de https://postgrest.org)

---

## Setup paso a paso

### 1. Clonar el repo

```powershell
cd C:\Users\user\Documents
git clone https://github.com/JeffStevenGT/oratioo-cx-local.git
cd oratioo-cx-local
```

### 2. Copiar el dump de datos

Copiar `oratioo_data.dump` (13MB) a la raíz del proyecto:
```
C:\Users\user\Documents\oratioo-cx-local\oratioo_data.dump
```

### 3. Crear base de datos

```powershell
$env:PGPASSWORD = "Pangea.2026"
& "C:\Program Files\PostgreSQL\17\bin\createdb.exe" -U postgres oratioo_cx
```

### 4. Crear tablas (schema)

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d oratioo_cx -f sql\001_schema.sql
```

### 5. Importar datos

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" -U postgres -d oratioo_cx --data-only --no-owner --no-privileges oratioo_data.dump
```

### 6. Configurar .env

```powershell
copy .env.example .env
```

Editar `.env` y ajustar:
```
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=Pangea.2026
PG_DATABASE=oratioo_cx
PANGEA_USER=TU_USUARIO_PANGEA
PANGEA_PASSWORD=TU_CLAVE_PANGEA
```

### 7. Entorno virtual Python + bot

```powershell
cd bot
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

### 8. Frontend

```powershell
cd ..\web
npm install
```

### 9. PostgREST

Descargar `postgrest.exe` de https://postgrest.org y soltarlo en la carpeta `postgrest\`.

---

## Arrancar todo

Abrir **3 terminales** (con `$env:PGPASSWORD = "Pangea.2026"` si lo necesitan):

**Terminal 1 — PostgREST:**
```powershell
cd C:\Users\user\Documents\oratioo-cx-local
.\postgrest\postgrest.exe postgrest\postgrest.conf
```

**Terminal 2 — Frontend:**
```powershell
cd C:\Users\user\Documents\oratioo-cx-local\web
npm run dev
```

**Terminal 3 — Bot:**
```powershell
cd C:\Users\user\Documents\oratioo-cx-local\bot
.\venv\Scripts\activate
python coordinator.py --workers 4
```

---

## Acceso

- **Frontend:** http://localhost:5173
- **PostgREST API:** http://localhost:3001
- **Login:** `admin@oratioo.com` / `admin123`

## Tablas

| Tabla | Contenido |
|-------|-----------|
| `lineas` | 137,718 registros (122k completados, 15k pendientes) |
| `documentos` | Registro de archivos subidos |
| `perfiles` | Perfiles de usuario |
| `usuarios` | Login y roles |

## Notas

- La contraseña de PostgreSQL para todos los comandos es `Pangea.2026`
- Si `createdb` o `psql` no están en PATH, usar rutas completas: `C:\Program Files\PostgreSQL\17\bin\`
- Los 15k pendientes los procesa el bot automáticamente al arrancar
