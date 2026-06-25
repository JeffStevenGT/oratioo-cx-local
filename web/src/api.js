/**
 * api.js — Cliente PostgREST para Oratioo CX Local
 * ==================================================
 * Reemplaza supabaseClient.js. Usa fetch() contra PostgREST.
 * Incluye helpers para autenticación local (sin Supabase Auth).
 */

const POSTGREST_URL = import.meta.env.VITE_POSTGREST_URL || 'http://localhost:3001'

// ── Constantes ────────────────────────────────────
export const TABLA_CLIENTES = 'lineas'
export const TABLA_PERFILES = 'perfiles'
export const TABLA_USUARIOS = 'usuarios'
export const TABLA_DOCUMENTOS = 'documentos'

export const ROLES = {
  ASESOR: 'asesor',
  SUPERVISOR: 'supervisor',
  IT: 'it',
  BACK_OFFICE: 'back_office',
  JEFE_AREA: 'jefe_area',
  CEO: 'ceo',
  DESARROLLADOR: 'desarrollador',
}

// ══════════════════════════════════════════════════════════════
//  PostgREST Helpers
// ══════════════════════════════════════════════════════════════

/**
 * Ejecuta una query contra PostgREST.
 * Soporta filtros, ordenamiento, paginación y headers especiales.
 */
export async function query(table, options = {}) {
  const {
    select = '*',
    filters = [],
    order,
    limit,
    offset,
    range,
    single = false,
    method = 'GET',
    body,
    headers: extraHeaders = {},
  } = options

  let url = `${POSTGREST_URL}/${table}?select=${encodeURIComponent(select)}`

  // Filtros como query params
  for (const f of filters) {
    url += `&${encodeURIComponent(f)}`
  }

  if (order) url += `&order=${encodeURIComponent(order)}`
  if (limit && !range) url += `&limit=${limit}`
  if (offset && !range) url += `&offset=${offset}`

  const fetchHeaders = {
    ...extraHeaders,
  }

  // Si hay range, usar header
  if (range) {
    fetchHeaders['Range-Unit'] = 'items'
    fetchHeaders['Range'] = `${range[0]}-${range[1]}`
  }

  // Si es single, pedir que devuelva objeto en vez de array
  if (single) {
    fetchHeaders['Accept'] = 'application/vnd.pgrst.object+json'
  }

  // Si es count, pedir conteo
  if (options.count) {
    fetchHeaders['Prefer'] = 'count=exact'
  }

  const fetchOptions = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...fetchHeaders,
    },
  }

  if (body && method !== 'GET') {
    fetchOptions.body = JSON.stringify(body)
  }

  const res = await fetch(url, fetchOptions)

  if (!res.ok) {
    const errText = await res.text().catch(() => res.statusText)
    throw new Error(`PostgREST error ${res.status}: ${errText}`)
  }

  // Obtener conteo del header
  let count = null
  if (options.count) {
    const contentRange = res.headers.get('content-range')
    if (contentRange) {
      const parts = contentRange.split('/')
      count = parseInt(parts[parts.length - 1], 10)
    }
  }

  // Si es DELETE o no hay body
  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return { data: single ? null : [], count }
  }

  const data = await res.json()
  return { data: Array.isArray(data) ? data : [data], count, error: null }
}

/**
 * Helper: insert en PostgREST.
 */
export async function insert(table, rows) {
  const arr = Array.isArray(rows) ? rows : [rows]
  const res = await fetch(`${POSTGREST_URL}/${table}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Prefer': 'return=representation',
    },
    body: JSON.stringify(arr),
  })
  if (!res.ok) {
    const errText = await res.text().catch(() => res.statusText)
    return { data: null, error: { message: errText } }
  }
  const data = await res.json()
  return { data, error: null }
}

/**
 * Helper: update en PostgREST.
 * filters: array de strings como "id=eq.123"
 */
export async function update(table, filters, body) {
  const filterStr = filters.map(f => encodeURIComponent(f)).join('&')
  const url = `${POSTGREST_URL}/${table}?${filterStr}`
  const res = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Prefer': 'return=representation',
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const errText = await res.text().catch(() => res.statusText)
    return { data: null, error: { message: errText } }
  }
  if (res.status === 204) return { data: [], error: null }
  const data = await res.json()
  return { data, error: null }
}

/**
 * Helper: delete en PostgREST.
 */
export async function remove(table, filters) {
  const filterStr = filters.map(f => encodeURIComponent(f)).join('&')
  const url = `${POSTGREST_URL}/${table}?${filterStr}`
  const res = await fetch(url, { method: 'DELETE' })
  return { error: res.ok ? null : { message: await res.text() } }
}

// ══════════════════════════════════════════════════════════════
//  Auth (local, sin Supabase Auth)
// ══════════════════════════════════════════════════════════════

/**
 * Verifica credenciales contra la tabla usuarios.
 * Usa bcryptjs para comparar el password hash.
 */
export async function loginWithPassword(email, password) {
  try {
    // 1. Buscar usuario por email
    const { data: users } = await query(TABLA_USUARIOS, {
      select: 'id,email,nombre,password_hash,rol,equipo,activo',
      filters: [`email=eq.${encodeURIComponent(email)}`],
      single: true,
    })

    const user = users?.[0] || users
    if (!user) throw new Error('Usuario no encontrado')
    if (!user.activo) throw new Error('Usuario desactivado')

    // 2. Verificar contraseña con bcryptjs
    const bcrypt = await import('bcryptjs')
    const valid = await bcrypt.default.compare(password, user.password_hash)
    if (!valid) throw new Error('Contraseña incorrecta')

    // 3. Actualizar última conexión
    await update(TABLA_USUARIOS, [`id=eq.${user.id}`], {
      ultima_conexion: new Date().toISOString(),
    })

    // 4. Retornar datos de sesión
    return {
      user: {
        id: String(user.id),
        email: user.email,
      },
      profile: {
        id: user.id,
        email: user.email,
        nombre: user.nombre,
        rol: user.rol || 'asesor',
        equipo: user.equipo || '',
      },
    }
  } catch (err) {
    throw new Error(err.message || 'Error de autenticación')
  }
}

/**
 * Obtiene el perfil del usuario actual desde localStorage.
 */
export function getCurrentProfile() {
  try {
    const raw = localStorage.getItem('oratioo_session')
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

/**
 * Cierra sesión (limpia localStorage).
 */
export function signOut() {
  localStorage.removeItem('oratioo_session')
}

// ══════════════════════════════════════════════════════════════
//  Metadatos de PostgREST
// ══════════════════════════════════════════════════════════════

// Para compatibilidad con código existente que usa supabase.from()
export const api = {
  from: (table) => ({
    select: (cols = '*') => ({
      // Cadena de métodos fluida
      _table: table,
      _select: cols,
      _filters: [],
      _order: null,
      _limit: null,
      _offset: null,
      _range: null,
      _single: false,
      _count: false,
      _head: false,

      or(filterStr) { this._filters.push(`or=(${filterStr})`); return this },
      eq(col, val) { this._filters.push(`${col}=eq.${encodeURIComponent(val)}`); return this },
      neq(col, val) { this._filters.push(`${col}=neq.${encodeURIComponent(val)}`); return this },
      gt(col, val) { this._filters.push(`${col}=gt.${encodeURIComponent(val)}`); return this },
      gte(col, val) { this._filters.push(`${col}=gte.${encodeURIComponent(val)}`); return this },
      lt(col, val) { this._filters.push(`${col}=lt.${encodeURIComponent(val)}`); return this },
      lte(col, val) { this._filters.push(`${col}=lte.${encodeURIComponent(val)}`); return this },
      in(col, vals) { this._filters.push(`${col}=in.(${vals.join(',')})`); return this },
      order(col, { ascending = true } = {}) {
        this._order = `${col}.${ascending ? 'asc' : 'desc'}`
        return this
      },
      limit(n) { this._limit = n; return this },
      offset(n) { this._offset = n; return this },
      range(a, b) { this._range = [a, b]; return this },
      single() { this._single = true; return this },
      maybeSingle() { this._single = true; return this },

      // Método count exacto
      async then(resolve) {
        const opts = {
          select: this._select,
          filters: this._filters,
          order: this._order,
          limit: this._limit,
          offset: this._offset,
          range: this._range,
          single: !this._head,
          count: this._count,
        }
        if (this._head) {
          // HEAD request para obtener solo count
          opts.limit = 1
          opts.headers = { Prefer: 'count=exact' }
        }
        const result = await query(this._table, opts)
        resolve(result)
      },
    }),

    insert: (rows) => insert(table, rows),
    update: (body) => ({
      eq(col, val) { return update(table, [`${col}=eq.${encodeURIComponent(val)}`], body) },
    }),
    delete: () => ({
      eq(col, val) { return remove(table, [`${col}=eq.${encodeURIComponent(val)}`]) },
    }),
  }),

  auth: {
    signInWithPassword: ({ email, password }) => loginWithPassword(email, password),
    getUser: async () => {
      const profile = getCurrentProfile()
      return profile ? { data: { user: { id: profile.id, email: profile.email } } } : { data: { user: null } }
    },
    signOut: () => signOut(),
  },
}

export default api
