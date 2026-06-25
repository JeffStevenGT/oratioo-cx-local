# Oratioo CX — Local

Stack PostgreSQL + PostgREST + Vite React (sin Supabase, sin Next.js).

## Estructura

```
oratioo-cx-local/
├── sql/                    # Schema PostgreSQL (4 tablas)
│   └── 001_schema.sql
├── bot/                    # Bot de extracción Pangea Orange
│   ├── pg_client.py        # Cliente PostgreSQL (psycopg2)
│   ├── coordinator.py      # Orquestador multi-worker
│   ├── worker.py           # Worker individual
│   ├── login.py            # Automatización login Pangea
│   ├── extraction.py       # Extracción de datos de cliente
│   ├── browser_setup.py    # Config de navegador + proxy
│   └── requirements.txt
├── postgrest/
│   └── postgrest.conf      # Config PostgREST
├── web/                    # Frontend React + Vite
│   ├── src/
│   │   ├── api.js          # Cliente PostgREST (fetch)
│   │   ├── App.jsx
│   │   ├── pages/          # Login, Dashboard, Clientes, Documentos
│   │   └── components/     # Sidebar, FilaExpandible, StatCard, etc.
│   └── package.json
├── .env.example
└── README.md
```

## Requisitos

- **PostgreSQL 15+** corriendo en `localhost:5433`
- **Python 3.12+** (para el bot)
- **Node.js 20+** (para el frontend)
- **PostgREST** (descargar de [postgrest.org](https://postgrest.org))
- **Playwright** (navegador para el bot)

## Setup

### 1. Base de datos

```bash
# Crear la BD (si no existe)
createdb -p 5433 -U postgres oratioo_cx

# Ejecutar el schema
psql -p 5433 -U postgres -d oratioo_cx -f sql/001_schema.sql
```

### 2. Variables de entorno

```bash
cp .env.example .env
# Editar .env con tus valores reales
```

### 3. PostgREST

```bash
# Descargar postgrest.exe y ejecutar
./postgrest.exe postgrest/postgrest.conf
# Corre en http://localhost:3001
```

### 4. Web (Frontend)

```bash
cd web
npm install
cp ../.env.example web/.env  # o crear web/.env con VITE_POSTGREST_URL
npm run dev
# Corre en http://localhost:5173
```

### 5. Bot

```bash
cd bot
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Instalar navegadores Playwright
python -m playwright install chromium

# Ejecutar
python coordinator.py --workers 4
```

## Tablas

| Tabla | Uso |
|-------|-----|
| `lineas` | Datos de clientes extraídos (atributos_dinamicos JSONB) |
| `usuarios` | Login y roles |
| `perfiles` | Datos de perfil de usuario |
| `documentos` | Registro de archivos Excel subidos |

## Login

- **URL:** `http://localhost:5173/login`
- **Usuario default:** `admin@oratioo.com` / `admin123`
- Roles: `asesor`, `supervisor`, `it`, `back_office`, `jefe_area`, `desarrollador`

## Flujo de datos

1. **Web** → Subir Excel con DNIs en Documentos
2. DNIs se insertan en `lineas` con estado `pendiente`
3. **Bot** (coordinator + workers) → Toma DNIs pendientes
4. Bot extrae datos de Pangea Orange vía Playwright
5. Resultados se guardan en `lineas` con estado `completado`/`no_cliente`/`error`
6. **Web** → Dashboard y Clientes muestran los resultados

## PostgREST Auth

- Rol anónimo (`web_anon`): solo lectura en `lineas`, `usuarios`, `documentos`
- Rol `authenticator`: acceso completo (usado por el frontend vía password en postgrest.conf)
- Login: el frontend consulta `usuarios` vía PostgREST, verifica password con bcryptjs
