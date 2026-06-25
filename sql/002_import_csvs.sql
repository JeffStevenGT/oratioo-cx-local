-- Importar CSVs descargados de Supabase
-- Ejecutar DESPUÉS de 001_schema.sql
-- Ajusta las rutas según donde guardes los archivos

-- 1. usuarios
\copy usuarios(usuario,password,nombre,email,rol,equipo,grupo,supervisor_id,activo,proxy_asignado,ultima_conexion,created_at) FROM 'usuarios.csv' CSV HEADER;

-- 2. perfiles
\copy perfiles(user_id,username,nombre,rol,pais,activo,ultimo_acceso,created_at) FROM 'perfiles.csv' CSV HEADER;

-- 3. documentos
\copy documentos(nombre_archivo,semana,total_dnis,procesados,pendientes,errores,no_encontrados,created_at,updated_at) FROM 'documentos.csv' CSV HEADER;

-- 4. lineas (la pesada — ejecutar con statement_timeout alto)
SET statement_timeout = '300s';
\copy lineas(dni,nombre,direccion,seg_fijo,seg_movil,paquete,linea,atributos_dinamicos,created_at) FROM 'lineas.csv' CSV HEADER;
