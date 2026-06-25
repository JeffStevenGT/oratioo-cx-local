-- ===========================================================================
-- Oratioo CX Local — Schema PostgreSQL
-- Requiere PostgreSQL 13+ (testeado en PG 17.10)
-- 4 tablas: lineas, usuarios, perfiles, documentos
-- ===========================================================================

BEGIN;

-- ===========================================================================
-- EXTENSIONES
-- ===========================================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ===========================================================================
-- ROLES para PostgREST
-- ===========================================================================

-- Rol anónimo: solo lectura a ciertas tablas
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'web_anon') THEN
        CREATE ROLE web_anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
        CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'oratioo_authenticator_2024';
    END IF;
END $$;

-- ===========================================================================
-- TABLAS
-- ===========================================================================

-- 1. lineas — Tabla principal con atributos_dinamicos JSONB
CREATE TABLE IF NOT EXISTS lineas (
    id          SERIAL PRIMARY KEY,
    dni         VARCHAR(20)  NOT NULL,
    nombre      VARCHAR(255) DEFAULT 'N/A',
    direccion   VARCHAR(500) DEFAULT 'N/A',
    linea       VARCHAR(50)  DEFAULT '',
    seg_fijo    VARCHAR(50)  DEFAULT 'N/A',
    seg_movil   VARCHAR(50)  DEFAULT 'N/A',
    paquete     VARCHAR(255) DEFAULT 'N/A',
    atributos_dinamicos JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- 2. usuarios — Login y roles
CREATE TABLE IF NOT EXISTS usuarios (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    nombre          VARCHAR(255),
    rol             VARCHAR(50)  DEFAULT 'asesor'
                    CHECK (rol IN ('asesor','supervisor','it','back_office','jefe_area','desarrollador')),
    equipo          VARCHAR(255),
    activo          BOOLEAN      DEFAULT true,
    ultima_conexion TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- 3. perfiles — IDs UUID de Supabase
CREATE TABLE IF NOT EXISTS perfiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT,           -- UUID de Supabase (sin FK local)
    username        VARCHAR(255),
    nombre          VARCHAR(255),
    rol             VARCHAR(50) DEFAULT 'asesor',
    pais            VARCHAR(10),
    equipo_id       VARCHAR(255),
    activo          BOOLEAN DEFAULT true,
    ultimo_acceso   TIMESTAMPTZ,
    proxy_asignado  VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 4. documentos — Upload de Excel
CREATE TABLE IF NOT EXISTS documentos (
    id              SERIAL PRIMARY KEY,
    nombre_archivo  VARCHAR(500),
    semana          VARCHAR(20),
    total_dnis      INTEGER DEFAULT 0,
    procesados      INTEGER DEFAULT 0,
    pendientes      INTEGER DEFAULT 0,
    errores         INTEGER DEFAULT 0,
    no_encontrados  INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ===========================================================================
-- ÍNDICES
-- ===========================================================================

CREATE INDEX IF NOT EXISTS idx_lineas_dni           ON lineas (dni);
CREATE INDEX IF NOT EXISTS idx_lineas_estado        ON lineas ((atributos_dinamicos->>'estado'));
CREATE INDEX IF NOT EXISTS idx_lineas_fecha_proc    ON lineas ((atributos_dinamicos->>'fecha_procesado'));
CREATE INDEX IF NOT EXISTS idx_lineas_created       ON lineas (created_at);
CREATE INDEX IF NOT EXISTS idx_lineas_doc_id        ON lineas ((atributos_dinamicos->>'documento_id'));
CREATE INDEX IF NOT EXISTS idx_lineas_nombre_trgm   ON lineas USING gin (nombre gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_lineas_dni_trgm      ON lineas USING gin (dni gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_usuarios_email       ON usuarios (email);
CREATE INDEX IF NOT EXISTS idx_usuarios_rol         ON usuarios (rol);

CREATE INDEX IF NOT EXISTS idx_perfiles_user        ON perfiles (user_id);
CREATE INDEX IF NOT EXISTS idx_perfiles_rol         ON perfiles (rol);

CREATE INDEX IF NOT EXISTS idx_documentos_created   ON documentos (created_at DESC);

-- ===========================================================================
-- TRIGGER: updated_at automático para lineas
-- ===========================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lineas_updated_at ON lineas;
CREATE TRIGGER trg_lineas_updated_at
    BEFORE UPDATE ON lineas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ===========================================================================
-- PERMISOS PostgREST
-- ===========================================================================

-- web_anon: solo lectura
GRANT USAGE ON SCHEMA public TO web_anon;
GRANT SELECT ON lineas TO web_anon;
GRANT SELECT ON usuarios TO web_anon;
GRANT SELECT ON perfiles TO web_anon;
GRANT SELECT ON documentos TO web_anon;

-- authenticator: full access
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO authenticator;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticator;

-- ===========================================================================
-- SEED: Usuario admin por defecto (bcrypt hash de "admin123")
-- ===========================================================================

INSERT INTO usuarios (email, password_hash, nombre, rol, equipo, activo)
VALUES ('admin@oratioo.com',
        '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy',
        'Administrador',
        'desarrollador',
        'IT',
        true)
ON CONFLICT (email) DO NOTHING;

COMMIT;
