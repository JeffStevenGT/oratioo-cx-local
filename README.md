# Oratioo CX — PostgreSQL Local

Stack: PostgreSQL + PostgREST + Python (bot) + React/Vite (frontend)
Entorno: Windows (España), todo local, sin dependencias cloud.

## Estructura
```
oratioo-cx-local/
├── bot/          # Python + psycopg2 → PostgreSQL
├── web/          # React/Vite → PostgREST → PostgreSQL
├── postgrest/    # Configuración PostgREST
├── sql/          # Schema + migraciones
└── .env          # Credenciales locales
```

## Requisitos
- PostgreSQL 15+
- Python 3.11+
- Node.js 18+
- PostgREST (descargable standalone)

## Setup
1. Instalar PostgreSQL
2. Ejecutar `sql/schema.sql`
3. Copiar `.env.example` → `.env`
4. `cd web && npm install && npm run dev`
5. `cd bot && python coordinator.py`
