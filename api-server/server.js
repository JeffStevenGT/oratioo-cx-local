/**
 * api-server/server.js
 * Reemplazo ligero de PostgREST para Oratioo CX Local
 * Traduce queries estilo PostgREST → SQL directo a PostgreSQL
 */
require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') })

const express = require('express')
const cors = require('cors')
const { Pool } = require('pg')

const app = express()
app.use(cors())
app.use(express.json({ limit: '10mb' }))

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10,
  idleTimeoutMillis: 30000,
})

// ═══════════════════════════════════════════════════════
//  Helpers
// ═══════════════════════════════════════════════════════

const VALID_IDENT = /^[a-zA-Z_][a-zA-Z0-9_]*$/
const OP_MAP = { eq: '=', neq: '!=', gt: '>', gte: '>=', lt: '<', lte: '<=', like: 'LIKE', ilike: 'ILIKE' }

function safeIdent(col) {
  // Alias ad_* = atributos_dinamicos->>* (evita problemas de encoding en URL)
  if (col.startsWith('ad_')) {
    return `atributos_dinamicos->>'${col.substring(3)}'`
  }
  // Si es una expresión JSON (contiene -> o ->>), no la quotear
  if (col.includes('->')) {
    return col.replace(/[^a-zA-Z0-9_>'-]/g, '')
  }
  // Columna normal: quotear con double quotes
  const cleaned = col.replace(/[^a-zA-Z0-9_]/g, '')
  return `"${cleaned}"`
}

function parseFilterValue(raw) {
  // "eq.value" → { op: "=", value: "value" }
  // "in.(a,b,c)" → { op: "IN", value: ["a","b","c"] }
  // Decodificar URL encoding que viene del frontend
  const decoded = decodeURIComponent(raw)
  const dot = decoded.indexOf('.')
  if (dot === -1) return { op: '=', value: decoded }

  const opName = decoded.substring(0, dot)
  let value = decoded.substring(dot + 1)

  if (opName === 'in') {
    const inner = value.replace(/^\(/, '').replace(/\)$/, '')
    return { op: 'IN', value: inner.split(',').map(v => v.trim()) }
  }

  if (OP_MAP[opName]) {
    return { op: OP_MAP[opName], value }
  }

  return { op: '=', value: decoded }
}

function buildQuery(req) {
  const { table } = req.params
  const select = req.query.select || '*'
  const params = []
  const whereParts = []
  let paramIdx = 1

  // Process filter params (everything except select, order, limit, offset)
  for (const [col, raw] of Object.entries(req.query)) {
    if (['select', 'order', 'limit', 'offset'].includes(col)) continue

    // Handle "or" special syntax: or=(col1.eq.val1,col2.eq.val2)
    if (col === 'or') {
      const inner = (Array.isArray(raw) ? raw[0] : raw).replace(/^\(/, '').replace(/\)$/, '')
      const orParts = inner.split(',').map(p => p.trim())
      const orClauses = []
      for (const part of orParts) {
        const m = part.match(/^(.+?)\.(eq|neq|gt|gte|lt|lte|like|ilike)\.(.+)$/)
        if (m) {
          params.push(m[3])
          orClauses.push(`${safeIdent(m[1])} ${OP_MAP[m[2]]} $${paramIdx++}`)
        }
      }
      if (orClauses.length > 0) whereParts.push(`(${orClauses.join(' OR ')})`)
      continue
    }

    // Handle array values (same param appears multiple times, e.g. gte + lte)
    const values = Array.isArray(raw) ? raw : [raw]
    for (const val of values) {
      const { op, value } = parseFilterValue(val)

      if (op === 'IN') {
        const placeholders = value.map(v => { params.push(v); return `$${paramIdx++}` }).join(', ')
        whereParts.push(`${safeIdent(col)} IN (${placeholders})`)
      } else {
        params.push(value)
        whereParts.push(`${safeIdent(col)} ${op} $${paramIdx++}`)
      }
    }
  }

  // Order
  let orderClause = ''
  if (req.query.order) {
    const parts = req.query.order.split('.')
    const col = parts[0]
    const dir = (parts[1] || 'asc').toUpperCase()
    orderClause = ` ORDER BY ${safeIdent(col)} ${dir === 'DESC' ? 'DESC' : 'ASC'} NULLS LAST`
  }

  // Limit / Offset (from query params OR Range header)
  let limitClause = ''
  let limit = parseInt(req.query.limit)
  let offset = parseInt(req.query.offset)
  
  // Support HTTP Range header: "0-999" → LIMIT 1000 OFFSET 0
  if (!limit && req.headers.range) {
    const m = req.headers.range.match(/^(\d+)-(\d+)$/)
    if (m) {
      offset = parseInt(m[1])
      limit = parseInt(m[2]) - offset + 1
    }
  }
  
  if (limit && limit > 0) {
    limitClause = ` LIMIT ${limit}`
    if (offset && offset > 0) limitClause += ` OFFSET ${offset}`
  }

  const whereClause = whereParts.length > 0 ? ' WHERE ' + whereParts.join(' AND ') : ''

  // Handle select with JSON paths (no quotear expresiones con ->)
  let selectClause = select
  if (select !== '*') {
    selectClause = select.split(',')
      .map(c => c.trim())
      .map(c => c.includes('->') ? c : (VALID_IDENT.test(c) ? `"${c}"` : c))
      .join(', ')
  }

  const sql = `SELECT ${selectClause} FROM "${table}"${whereClause}${orderClause}${limitClause}`
  const countSql = `SELECT COUNT(*) FROM "${table}"${whereClause}`

  return { sql, countSql, params }
}

function buildUpdateFilter(req) {
  // Build WHERE from query params for PATCH/DELETE
  const parts = []
  const values = []
  let idx = 1

  for (const [col, raw] of Object.entries(req.query)) {
    const { op, value } = parseFilterValue(raw)
    if (op === 'IN') {
      const ph = value.map(v => { values.push(v); return `$${idx++}` }).join(', ')
      parts.push(`${safeIdent(col)} IN (${ph})`)
    } else {
      values.push(value)
      parts.push(`${safeIdent(col)} ${op} $${idx++}`)
    }
  }

  return { where: parts.length > 0 ? ' WHERE ' + parts.join(' AND ') : '', values }
}

// ═══════════════════════════════════════════════════════
//  Routes
// ═══════════════════════════════════════════════════════

// GET /:table — SELECT
app.get('/:table', async (req, res) => {
  try {
    const { sql, countSql, params } = buildQuery(req)
    const result = await pool.query(sql, params)

    // Count if requested
    if (req.headers.prefer?.includes('count=exact')) {
      const countResult = await pool.query(countSql, params)
      const count = parseInt(countResult.rows[0].count)
      res.setHeader('Content-Range', `0-${result.rows.length - 1}/${count}`)
    }

    // Single object?
    if (req.headers.accept?.includes('vnd.pgrst.object+json')) {
      return res.json(result.rows[0] || null)
    }

    res.json(result.rows)
  } catch (err) {
    console.error('GET error:', err.message)
    res.status(400).json({ message: err.message })
  }
})

// POST /:table — INSERT
app.post('/:table', async (req, res) => {
  try {
    const { table } = req.params
    let rows = Array.isArray(req.body) ? req.body : [req.body]
    if (rows.length === 0) return res.status(400).json({ message: 'Empty body' })

    const cols = Object.keys(rows[0])
    const colNames = cols.map(c => `"${c}"`).join(', ')

    const allValues = []
    const placeholders = rows.map((_row, i) => {
      const ph = cols.map((_c, j) => {
        allValues.push(rows[i][cols[j]])
        return `$${allValues.length}`
      }).join(', ')
      return `(${ph})`
    }).join(', ')

    const sql = `INSERT INTO "${table}" (${colNames}) VALUES ${placeholders} RETURNING *`
    const result = await pool.query(sql, allValues)

    const prefer = req.headers.prefer || ''
    if (prefer.includes('return=representation')) {
      return res.status(201).json(rows.length === 1 ? result.rows[0] : result.rows)
    }

    res.status(201).json(null)
  } catch (err) {
    console.error('POST error:', err.message)
    res.status(400).json({ message: err.message })
  }
})

// PATCH /:table?col=eq.val — UPDATE
app.patch('/:table', async (req, res) => {
  try {
    const { table } = req.params
    const { where, values: filterVals } = buildUpdateFilter(req)
    if (!where) return res.status(400).json({ message: 'No filter provided' })

    const body = req.body
    const setParts = []
    const setVals = []

    for (const [col, val] of Object.entries(body)) {
      setParts.push(`"${col}" = $${filterVals.length + setVals.length + 1}`)
      setVals.push(val === null ? null : val)
    }

    const allVals = [...filterVals, ...setVals]
    const sql = `UPDATE "${table}" SET ${setParts.join(', ')}${where} RETURNING *`
    const result = await pool.query(sql, allVals)

    const prefer = req.headers.prefer || ''
    if (prefer.includes('return=representation')) {
      return res.json(result.rows)
    }

    res.status(204).send()
  } catch (err) {
    console.error('PATCH error:', err.message)
    res.status(400).json({ message: err.message })
  }
})

// DELETE /:table?col=eq.val
app.delete('/:table', async (req, res) => {
  try {
    const { table } = req.params
    const { where, values } = buildUpdateFilter(req)
    if (!where) return res.status(400).json({ message: 'No filter provided' })

    const sql = `DELETE FROM "${table}"${where} RETURNING *`
    const result = await pool.query(sql, values)

    res.json(result.rows)
  } catch (err) {
    console.error('DELETE error:', err.message)
    res.status(400).json({ message: err.message })
  }
})

// Health check
app.get('/', (_req, res) => {
  res.json({ status: 'ok', service: 'oratioo-cx-api' })
})

const PORT = process.env.API_PORT || 3001
app.listen(PORT, () => {
  console.log(`Oratioo API server running on http://localhost:${PORT}`)
})
