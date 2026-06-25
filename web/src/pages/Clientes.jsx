import { useState, useEffect, useMemo } from 'react'
import {
  Search,
  Loader2,
  RefreshCw,
  ArrowUpDown,
  Users,
  ChevronDown,
  ChevronUp,
  X,
  UserPlus,
  Send,
  Phone,
} from 'lucide-react'
import api, { TABLA_CLIENTES, TABLA_PERFILES, TABLA_USUARIOS } from '../api'
import FilaExpandible from '../components/FilaExpandible'
import ExportButtons from '../components/ExportButtons'

const VARIANTES_VALIOSAS = [
  { key: 'maximo', label: 'Máx descuento', bd: 'Renove mixto al mejor precio con máximo descuento', color: 'emerald' },
  { key: 'con_descuento', label: 'Con descuento', bd: 'Renove mixto al mejor precio con descuento', color: 'blue' },
  { key: 'mejor_precio', label: 'Mejor precio', bd: 'Renove mixto al mejor precio', color: 'amber' },
  { key: 'renove_mixto_basico', label: 'Renove mixto', bd: 'Renove mixto', color: 'slate' },
]

export default function Clientes() {
  const [clientes, setClientes] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sortConfig, setSortConfig] = useState({ key: null, dir: 'asc' })
  const [cimaFilter, setCimaFilter] = useState(null)
  const [renoveFilter, setRenoveFilter] = useState(null)
  const [variantesActivas, setVariantesActivas] = useState([])
  const [tagsActivas, setTagsActivas] = useState([])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [appliedFrom, setAppliedFrom] = useState('')
  const [appliedTo, setAppliedTo] = useState('')
  const [expandido, setExpandido] = useState(null)
  const [assignModal, setAssignModal] = useState(false)
  const [assignEquipoId, setAssignEquipoId] = useState('')
  const [assignAsesorId, setAssignAsesorId] = useState('')
  const [equipos, setEquipos] = useState([])
  const [asesoresEquipo, setAsesoresEquipo] = useState([])
  const [assigning, setAssigning] = useState(false)
  const [assignMsg, setAssignMsg] = useState('')
  const [assignCantidad, setAssignCantidad] = useState('')
  const [clientesPage, setClientesPage] = useState(1)
  const [clientesPageSize, setClientesPageSize] = useState(10)

  const fetchClientes = async () => {
    if (!appliedFrom && !appliedTo) {
      setClientes([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      let allData = []
      const PAGE = 500
      let offset = 0
      let hasMore = true

      while (hasMore) {
        const query = api
          .from(TABLA_CLIENTES)
          .select('*')
          .order('id', { ascending: true })
          .limit(PAGE)

        // Filtros de fecha server-side (usamos alias "ad_" para evitar encoding de ->> en URL)
        if (appliedFrom) query.gte('ad_fecha_procesado', appliedFrom)
        if (appliedTo) query.lte('ad_fecha_procesado', appliedTo)

        const { data } = await query.offset(offset)

        if (data && data.length > 0) {
          allData = [...allData, ...data]
          offset += PAGE
          if (data.length < PAGE) hasMore = false
        } else {
          hasMore = false
        }
      }

      setClientes(allData)
    } catch (err) {
      console.error('Error fetching clientes:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchClientes() }, [clientesPageSize, appliedFrom, appliedTo])
  useEffect(() => { setClientesPage(1) }, [cimaFilter, renoveFilter, variantesActivas, tagsActivas, dateFrom, dateTo, search])

  const handleFilter = () => {
    setClientesPage(1)
    setAppliedFrom(dateFrom)
    setAppliedTo(dateTo)
  }

  // Agrupar por DNI y filtrar
  const filtered = useMemo(() => {
    const grupos = {}
    for (const c of clientes) {
      const ad = c.atributos_dinamicos || {}
      const attr = typeof ad === 'string' ? JSON.parse(ad) : ad
      const isError = attr.estado === 'error'
      const dni = c.dni
      const displayName = c.nombre && c.nombre !== 'N/A' ? c.nombre : (isError ? 'ERROR' : (attr.datos_basicos?.nombre || 'PENDIENTE'))
      if (!grupos[dni]) {
        grupos[dni] = {
          dni, nombre: displayName, isError, created_at: c.created_at,
          fecha_analisis: attr.fecha_procesado || c.created_at,
          _lineas: [], _cima: false, _renove_mixto: false, _variantes: new Set(), _isError: isError, _isPending: attr.estado === 'pendiente',
        }
      }
      const g = grupos[dni]
      const numLinea = c.linea
      if (!g._lineas.some((l) => l.linea === numLinea)) {
        g._lineas.push(c)
      }
      if (attr.cima === 'SI') g._cima = true
      if (attr.tiene_renove_mixto) g._renove_mixto = true
      if (attr.renove_mixto_variante && attr.renove_mixto_variante !== 'N/A') {
        g._variantes.add(attr.renove_mixto_variante)
      }
      if (g._lineas.length === 1) {
        g.linea = c.linea
        g.paquete = c.paquete
        g.atributos_dinamicos = {
          tipo_busqueda: attr.tipo_busqueda || 'dni',
          telefono_buscado: attr.telefono_buscado || '',
          cima: attr.cima, tiene_renove_mixto: attr.tiene_renove_mixto,
          renove_mixto_variante: attr.renove_mixto_variante || 'N/A',
          datos_basicos: attr.datos_basicos,
          linea: attr.linea, pestanas: attr.pestanas,
          pipeline: attr.pipeline,
          estado: 'completado',
          fecha_procesado: attr.fecha_procesado || '',
          fecha_hora: attr.fecha_hora || '',
          paquete_principal: attr.paquete_principal || c.paquete || 'N/A',
          producto: attr.producto || 'N/A',
          estado_linea: attr.estado_linea || [],
          permanencia: attr.permanencia || 'N/A',
          permanencia_fecha: attr.permanencia_fecha || '',
          consumo: attr.consumo || 'N/A',
          venta_plazos: attr.venta_plazos || 'N/A',
          campanas_extra: attr.campanas_extra || [],
        }
      }
    }

    let result = Object.values(grupos)

    // Actualizar atributos con datos agregados
    for (const g of result) {
      const variantesArr = Array.from(g._variantes)
      g.atributos_dinamicos = g.atributos_dinamicos || {}
      g.atributos_dinamicos.cima = g._cima ? 'SI' : 'NO'
      g.atributos_dinamicos.tiene_renove_mixto = g._renove_mixto
      const PRIORIDAD_RENOVE = [
        'Renove mixto al mejor precio con máximo descuento',
        'Renove mixto al mejor precio con descuento',
        'Renove mixto al mejor precio',
        'Renove mixto',
        'Renove Multidispositivo',
      ]
      let mejorVariante = 'N/A'
      if (variantesArr.length > 0) {
        for (const p of PRIORIDAD_RENOVE) {
          if (variantesArr.some(v => v === p)) { mejorVariante = p; break }
        }
        if (mejorVariante === 'N/A') mejorVariante = variantesArr[0]
      }
      g.atributos_dinamicos.renove_mixto_variante = mejorVariante
      g.atributos_dinamicos.estado = g._isError ? 'error' : (g._isPending ? 'pendiente' : 'completado')
      if (!g.atributos_dinamicos.datos_basicos?.nombre && g.nombre) {
        g.atributos_dinamicos.datos_basicos = g.atributos_dinamicos.datos_basicos || {}
        g.atributos_dinamicos.datos_basicos.nombre = g.nombre
      }
    }

    // Filtros
    if (cimaFilter === 'SI') result = result.filter(g => g._cima)
    else if (cimaFilter === 'NO') result = result.filter(g => !g._cima)

    const VARIANTES_RENOVE_MIXTO = [
      'Renove mixto al mejor precio con máximo descuento',
      'Renove mixto al mejor precio con descuento',
      'Renove mixto al mejor precio',
      'Renove mixto',
    ]
    if (renoveFilter === 'SI') {
      result = result.filter(g => g._variantes.size > 0 && [...g._variantes].some(v => VARIANTES_RENOVE_MIXTO.includes(v)))
    } else if (renoveFilter === 'NO') {
      result = result.filter(g => !([...g._variantes].some(v => VARIANTES_RENOVE_MIXTO.includes(v))))
    }

    if (variantesActivas.length > 0) {
      result = result.filter(g =>
        variantesActivas.some(vk => {
          const vData = VARIANTES_VALIOSAS.find(x => x.key === vk)
          return vData && g._variantes.has(vData.bd)
        })
      )
    }

    if (tagsActivas.length > 0) {
      result = result.filter(g =>
        tagsActivas.some(tk => {
          if (tk === 'multidispositivo') return [...g._variantes].some(v => v.toLowerCase().includes('multidispositivo'))
          if (tk === 'otros') return [...g._variantes].some(v => !VARIANTES_RENOVE_MIXTO.includes(v) && !v.toLowerCase().includes('multidispositivo'))
          return false
        })
      )
    }

    // Búsqueda
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(g =>
        g.dni.toLowerCase().includes(q) ||
        g.nombre.toLowerCase().includes(q)
      )
    }

    // Sort
    if (sortConfig.key) {
      result.sort((a, b) => {
        const valA = a[sortConfig.key] || ''
        const valB = b[sortConfig.key] || ''
        return sortConfig.dir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA)
      })
    }

    return result
  }, [clientes, cimaFilter, renoveFilter, variantesActivas, tagsActivas, search, sortConfig])

  // Paginación
  const totalPages = Math.ceil(filtered.length / clientesPageSize)
  const paginated = filtered.slice((clientesPage - 1) * clientesPageSize, clientesPage * clientesPageSize)

  const handleSort = (key) => {
    setSortConfig(prev => ({
      key,
      dir: prev.key === key ? (prev.dir === 'asc' ? 'desc' : 'asc') : 'asc',
    }))
  }

  const toggleFiltro = (setter, valor) => {
    setter(prev => prev === valor ? null : valor)
  }

  const toggleVariante = (key) => {
    setVariantesActivas(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key])
  }

  const toggleTag = (key) => {
    setTagsActivas(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key])
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1a1030]">Clientes</h1>
          <p className="text-xs text-[#7c757c] mt-0.5">
            {filtered.length.toLocaleString()} resultados
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ExportButtons data={filtered} />
          <button onClick={fetchClientes} className="btn-secondary text-xs">
            <RefreshCw size={14} /> Actualizar
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="card !p-3 space-y-2">
        {/* Filtro de fechas */}
        <div className="flex items-center gap-2 flex-wrap">
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="text-xs border border-[#e8dce6] rounded-lg px-2 py-1.5" />
          <span className="text-xs text-[#7c757c]">hasta</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="text-xs border border-[#e8dce6] rounded-lg px-2 py-1.5" />
          <button onClick={handleFilter}
            className="text-xs bg-[#0a6ea9] text-white px-3 py-1.5 rounded-lg hover:bg-[#085d8f]">
            Filtrar
          </button>
          {(appliedFrom || appliedTo) && (
            <button onClick={() => { setDateFrom(''); setDateTo(''); setAppliedFrom(''); setAppliedTo(''); }}
              className="text-xs text-red-500 hover:underline">
              Limpiar fechas
            </button>
          )}
        </div>

        {/* Filtros de atributos */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] text-[#7c757c] uppercase tracking-wider mr-1">CIMA:</span>
          {['SI', 'NO'].map(v => (
            <button key={v} onClick={() => toggleFiltro(setCimaFilter, v)}
              className={`text-xs px-2 py-1 rounded-full border transition-all ${
                cimaFilter === v ? 'bg-emerald-100 text-emerald-700 border-emerald-300' : 'bg-white text-[#7c757c] border-[#e8dce6] hover:border-[#c8c0c8]'
              }`}>
              {v} {cimaFilter === v && <X size={10} className="inline ml-0.5" />}
            </button>
          ))}

          <span className="text-[10px] text-[#7c757c] uppercase tracking-wider ml-3 mr-1">Renove:</span>
          {['SI', 'NO'].map(v => (
            <button key={v} onClick={() => toggleFiltro(setRenoveFilter, v)}
              className={`text-xs px-2 py-1 rounded-full border transition-all ${
                renoveFilter === v ? 'bg-blue-100 text-blue-700 border-blue-300' : 'bg-white text-[#7c757c] border-[#e8dce6]'
              }`}>
              {v} {renoveFilter === v && <X size={10} className="inline ml-0.5" />}
            </button>
          ))}
        </div>

        {/* Variantes */}
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-[10px] text-[#7c757c] uppercase tracking-wider mr-1">Variantes:</span>
          {VARIANTES_VALIOSAS.map(v => (
            <button key={v.key} onClick={() => toggleVariante(v.key)}
              className={`text-[10px] px-2 py-1 rounded-full border transition-all ${
                variantesActivas.includes(v.key) ? `bg-${v.color}-100 text-${v.color}-700 border-${v.color}-300` : 'bg-white text-[#7c757c] border-[#e8dce6]'
              }`}>
              {v.label} {variantesActivas.includes(v.key) && <X size={9} className="inline ml-0.5" />}
            </button>
          ))}
        </div>

        {/* Búsqueda */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#b8b0b8]" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Buscar por DNI o nombre..."
            className="w-full pl-9 pr-4 py-2 text-xs border border-[#e8dce6] rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#0a6ea9]/20"
          />
        </div>
      </div>

      {/* Tabla */}
      <div className="card !p-0 overflow-x-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 size={24} className="animate-spin text-[#b8b0b8]" />
          </div>
        ) : paginated.length === 0 ? (
          <div className="text-center py-12 text-[#7c757c] text-sm">
            {!appliedFrom && !appliedTo ? 'Selecciona un rango de fechas para ver resultados' : 'Sin resultados'}
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#e8dce6] bg-[#faf8fa]">
                  <th className="table-header w-8"></th>
                  <th className="table-header cursor-pointer" onClick={() => handleSort('dni')}>
                    <div className="flex items-center gap-1">DNI <ArrowUpDown size={10} /></div>
                  </th>
                  <th className="table-header">Nombre</th>
                  <th className="table-header">CIMA</th>
                  <th className="table-header">Línea</th>
                  <th className="table-header">Paquete</th>
                  <th className="table-header">Renove</th>
                  <th className="table-header">Fecha</th>
                  <th className="table-header">Hora</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((c) => (
                  <FilaExpandible
                    key={c.dni}
                    cliente={c}
                    abierto={expandido === c.dni}
                    onToggle={() => setExpandido(expandido === c.dni ? null : c.dni)}
                  />
                ))}
              </tbody>
            </table>

            {/* Paginación */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-2 border-t border-[#e8dce6]">
                <span className="text-xs text-[#7c757c]">
                  Pág {clientesPage} de {totalPages}
                </span>
                <div className="flex gap-1">
                  <button onClick={() => setClientesPage(p => Math.max(1, p - 1))} disabled={clientesPage === 1}
                    className="text-xs px-2 py-1 rounded border border-[#e8dce6] disabled:opacity-30">Anterior</button>
                  <button onClick={() => setClientesPage(p => Math.min(totalPages, p + 1))} disabled={clientesPage === totalPages}
                    className="text-xs px-2 py-1 rounded border border-[#e8dce6] disabled:opacity-30">Siguiente</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
