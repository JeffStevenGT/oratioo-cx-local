# Oratioo CX — Local

Stack: PostgreSQL VPS + Node.js API + Vite React + Python Bot

## Estructura

```
oratioo-cx-local/
├── api-server/              # API REST (reemplaza PostgREST)
│   ├── server.js            # Express + pg → VPS PostgreSQL
│   └── package.json
├── bot/                     # Bot de extracción Pangea Orange
│   ├── coordinator.py       # Orquestador multi-worker
│   ├── worker.py            # Worker individual
│   ├── login.py             # Automatización login Pangea
│   ├── extraction.py        # Extracción de datos
│   ├── browser_setup.py     # Config navegador + proxy
│   ├── pg_client.py         # Cliente PostgreSQL directo
│   └── requirements.txt
├── web/                     # Frontend React + Vite
│   ├── src/
│   │   ├── api.js           # Cliente API (fetch)
│   │   ├── App.jsx
│   │   ├── pages/           # Login, Dashboard, Clientes, Documentos
│   │   └── components/      # Sidebar, FilaExpandible, StatCard, etc.
│   └── package.json
├── sql/
│   └── 001_schema.sql       # Schema para VPS (4 tablas)
├── .env.example
├── .gitignore
└── README.md
```

## Requisitos

- **PostgreSQL** en VPS (`srv.oratioo.com`) — ya configurado
- **Node.js 20+** (para API + frontend)
- **Python 3.12+** (para el bot)
- **Playwright** (navegador para el bot)

## Setup

### 1. Clonar

```powershell
git clone https://github.com/JeffStevenGT/oratioo-cx-local.git
cd oratioo-cx-local
```

### 2. Variables de entorno

```powershell
copy .env.example .env
# Editar .env con credenciales reales de Pangea y VPS
```

### 3. API Server

```powershell
cd api-server
npm install
node server.js
# Corre en http://localhost:3001
```

### 4. Web (Frontend)

```powershell
cd web
npm install
npm run dev
# Corre en http://localhost:5173
```

### 5. Bot (Python)

```powershell
cd bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

# Ejecutar
python coordinator.py --workers 4
```

## Tablas

| Tabla | Contenido |
|-------|-----------|
| `lineas` | 137,718 registros de clientes (atributos_dinamicos JSONB) |
| `usuarios` | Login y roles |
| `perfiles` | Datos de perfil de usuario |
| `documentos` | Registro de archivos Excel subidos |

## Login

- **URL:** `http://localhost:5173`
- **Usuario:** `admin@oratioo.com` / `admin123`

## Flujo de datos

1. **Web** → API (port 3001) → PostgreSQL VPS
2. **Bot** → PostgreSQL VPS (directo vía pg_client.py)
3. Bot extrae datos de Pangea Orange → guarda en `lineas` del VPS
4. **Web** → Dashboard y Clientes muestran resultados filtrados server-side

## Filtros JSONB

La API usa alias `ad_*` para filtrar campos dentro de `atributos_dinamicos`:
- `ad_fecha_procesado` → `atributos_dinamicos->>'fecha_procesado'`
- `ad_estado` → `atributos_dinamicos->>'estado'`
- etc.
