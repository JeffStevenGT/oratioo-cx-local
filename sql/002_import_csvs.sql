-- ===========================================================================
-- Importar CSVs exportados de Supabase
-- Ejecutar DESPUÉS de 001_schema.sql
-- 
-- ⚠️ CAMBIAR las rutas a donde copies los CSVs en la PC España
-- ===========================================================================

-- Ajusta estas rutas según donde pongas los archivos
-- Ejemplo Windows: 'C:\Oratioo\lineas_rows.csv'
-- Ejemplo Linux:   '/home/oratioo/lineas_rows.csv'

BEGIN;

SET client_min_messages = WARNING;

-- 1. lineas (el grande — 137k filas)
\echo '=== Importando lineas_rows.csv (esto tarda ~2-3 min) ==='
SET statement_timeout = '600s';
\copy lineas(id, dni, nombre, direccion, seg_fijo, seg_movil, paquete, linea, atributos_dinamicos, created_at) FROM 'REEMPLAZAR_RUTA\lineas_rows.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

SELECT setval(pg_get_serial_sequence('lineas', 'id'), COALESCE((SELECT MAX(id) FROM lineas), 1));
\echo '=== lineas: OK ==='

-- 2. documentos
RESET statement_timeout;
\echo '=== Importando documentos_rows.csv ==='
\copy documentos(id, nombre_archivo, semana, total_dnis, procesados, pendientes, errores, no_encontrados, created_at, updated_at) FROM 'REEMPLAZAR_RUTA\documentos_rows.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

SELECT setval(pg_get_serial_sequence('documentos', 'id'), COALESCE((SELECT MAX(id) FROM documentos), 1));
\echo '=== documentos: OK ==='

-- 3. perfiles
\echo '=== Importando perfiles_rows.csv ==='
\copy perfiles(id, user_id, username, nombre, rol, pais, equipo_id, activo, ultimo_acceso, created_at, proxy_asignado) FROM 'REEMPLAZAR_RUTA\perfiles_rows.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

\echo '=== perfiles: OK ==='

-- ===========================================================================
-- Verificación
-- ===========================================================================
\echo ''
\echo '=== RESUMEN ==='
SELECT 'lineas' AS tabla, COUNT(*) AS filas,
       COUNT(*) FILTER (WHERE atributos_dinamicos->>'estado' = 'completado') AS completados,
       COUNT(*) FILTER (WHERE atributos_dinamicos->>'estado' = 'no_cliente') AS no_clientes
FROM lineas
UNION ALL
SELECT 'documentos', COUNT(*), 0, 0 FROM documentos
UNION ALL
SELECT 'perfiles', COUNT(*), 0, 0 FROM perfiles;

COMMIT;
