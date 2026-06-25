import { useState, useEffect } from 'react'
import {
  ChevronDown, ChevronRight, Phone, FileText, Tag, RefreshCw,
  DollarSign, Wifi, Save, UserPlus,
} from 'lucide-react'
import api, { TABLA_CLIENTES, TABLA_PERFILES } from '../api'

const PIPELINE_ESTADOS = [
  { value: 'pendiente', label: 'Pendiente', color: 'bg-gray-100 text-gray-700' },
  { value: 'contactado', label: 'Contactado', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'interesado', label: 'Interesado', color: 'bg-amber-100 text-amber-700' },
  { value: 'en_negociacion', label: 'En Negociación', color: 'bg-blue-100 text-blue-700' },
  { value: 'cerrado', label: 'Venta', color: 'bg-emerald-100 text-emerald-700' },
  { value: 'no_interesa', label: 'No Interesa', color: 'bg-red-100 text-red-700' },
]

export default function FilaExpandible({ cliente, abierto, onToggle }) {
  const attr = cliente.atributos_dinamicos || {}
  const bas = attr.datos_basicos || {}
  const linea = attr.linea || {}
  const pipeline = attr.pipeline || {}

  const session = JSON.parse(localStorage.getItem('oratioo_session') || '{}')
  const myRol = session.rol

  const [estado, setEstado] = useState(pipeline.estado || 'pendiente')
  const [asesorId, setAsesorId] = useState(pipeline.asesor_id || '')
  const [notas, setNotas] = useState(pipeline.notas || '')
  const [asesores, setAsesores] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (abierto) {
      api.from(TABLA_PERFILES).select('id, nombre').eq('rol', 'asesor').eq('activo', 'true')
        .then(({ data }) => { if (data) setAsesores(data) })
    }
  }, [abierto])

  const guardarPipeline = async (nuevoEstado) => {
    setSaving(true)
    const dni = cliente.dni
    const estadoFinal = nuevoEstado !== undefined ? nuevoEstado : estado
    const ad = { ...attr, pipeline: { estado: estadoFinal, asesor_id: asesorId, notas, ultimo_cambio: new Date().toISOString() } }

    const { error } = await api.from(TABLA_CLIENTES)
      .update({ atributos_dinamicos: ad })
      .eq('dni', dni)

    if (error) {
      console.error('Error al guardar pipeline:', error)
    }
    setSaving(false)
  }

  const estadoCfg = PIPELINE_ESTADOS.find(e => e.value === estado) || PIPELINE_ESTADOS[0]
  const canEdit = ['asesor', 'supervisor', 'jefe_area', 'desarrollador'].includes(myRol)

  // Datos de todas las líneas
  const todasLasLineas = (cliente._lineas || []).map(l => {
    const la = l.atributos_dinamicos || {}
    if (typeof la === 'string') { try { return JSON.parse(la) } catch { return {} } }
    const li = la.linea || {}
    return {
      numero: l.linea || li.numero || li.linea_principal || '-',
      paquete: l.paquete || li.paquete || '-',
      paquete_principal: la.paquete_principal || l.paquete || 'N/A',
      producto: li.producto || la.producto || 'N/A',
      estado_linea: li.estado_linea || la.estado_linea || [],
      permanencia: li.permanencia || la.permanencia || 'N/A',
      permanencia_fecha: li.permanencia_fecha || la.permanencia_fecha || '',
      consumo: li.consumo || la.consumo || 'N/A',
      venta_plazos: li.venta_plazos || la.venta_plazos || 'N/A',
      cima: la.cima || 'NO',
      tiene_renove: la.tiene_renove_mixto || false,
      variante_renove: la.renove_mixto_variante || 'N/A',
      etiquetas: li.etiquetas || la.etiquetas || [],
      activo_desde: li.activo_desde || la.activo_desde || 'N/A',
      tiene_tv: li.tiene_tv || false,
      es_principal: li.es_principal || la.es_principal || false,
      pestanas: la.pestanas || {},
      campanas_extra: la.campanas_extra || [],
      notificacion_pack: la.notificacion_pack || '',
    }
  })

  return (
    <>
      <tr onClick={onToggle}
        className="border-b border-[#e8dce6] hover:bg-[#f5ebf3]/50 cursor-pointer transition-colors">
        <td className="table-cell">
          <button className="p-0.5 rounded hover:bg-[#e8dce6] transition-colors">
            {abierto ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        </td>
        <td className="table-cell font-mono text-xs">{cliente.dni}</td>
        <td className="table-cell font-medium">
          {attr.tipo_busqueda === 'telefono' && (
            <Phone size={10} className="inline-block mr-1 text-[#7c757c] opacity-40" title="Encontrado por teléfono" />
          )}
          {cliente._isError ? <span className="text-red-600 font-semibold">{cliente.nombre || 'ERROR'}</span> : (bas.nombre || '-')}
        </td>
        <td className="table-cell">
          <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs border ${
            attr.cima === 'SI' ? 'bg-emerald-100 text-emerald-700 border-emerald-200' : 'bg-white text-[#1a1030] border-[#e8dce6]'
          }`}>
            {attr.cima === 'SI' ? 'CIMA' : 'NO'}
          </span>
        </td>
        <td className="table-cell text-xs font-mono">
          {(() => {
            const lns = todasLasLineas.map(l => l.numero).filter(Boolean)
            if (lns.length === 0) return linea.numero || linea.linea_principal || '-'
            if (lns.length === 1) return lns[0]
            return <span title={lns.join(', ')}>{lns[0]} <span className="text-[#7c757c]">+{lns.length - 1}</span></span>
          })()}
        </td>
        <td className="table-cell text-xs max-w-[180px] truncate" title={attr.paquete_principal || linea.paquete || ''}>
          {attr.paquete_principal || linea.paquete || '-'}
        </td>
        <td className="table-cell text-xs">
          {attr.renove_mixto_variante && attr.renove_mixto_variante !== 'N/A' ? (
            <span className="text-[#0a6ea9] font-medium text-xs">{attr.renove_mixto_variante}</span>
          ) : <span className="text-[#7c757c]">-</span>}
        </td>
        <td className="table-cell text-[#7c757c] text-xs">
          {(() => {
            const fp = cliente.atributos_dinamicos?.fecha_procesado || cliente.created_at
            if (!fp) return '-'
            if (fp.length === 10 && fp[4] === '-' && fp[7] === '-') {
              const d = new Date(fp + 'T12:00:00')
              return d.toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })
            }
            return new Date(fp).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' })
          })()}
        </td>
        <td className="table-cell text-[#7c757c] text-xs">
          {(() => {
            const fh = cliente.atributos_dinamicos?.fecha_hora
            if (fh) {
              const d = new Date(fh)
              return d.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })
            }
            return '-'
          })()}
        </td>
      </tr>

      {abierto && (
        <tr key={`${cliente.dni}-detail`} className="animate-slide-in">
          <td colSpan={9} className="p-0">
            <div className="bg-[#f5ebf3]/30 border-b border-[#e8dce6] px-6 py-4">
              {/* Datos generales */}
              <div className="card !bg-white/60 mb-4">
                <h4 className="text-sm font-semibold text-[#1a1030] mb-3 flex items-center gap-2">
                  <FileText size={14} className="text-[#0a6ea9]" /> Datos del cliente
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-2 text-xs">
                  <div><span className="text-[#7c757c]">Nombre:</span><p className="text-[#1a1030]">{bas.nombre || '-'}</p></div>
                  <div><span className="text-[#7c757c]">DNI:</span><p className="text-[#1a1030] font-mono">{cliente.dni}</p></div>
                  <div className="col-span-2"><span className="text-[#7c757c]">Dirección:</span><p className="text-[#1a1030]">{bas.direccion || '-'}</p></div>
                  <div><span className="text-[#7c757c]">Seg. Fijo:</span><p className="text-[#1a1030] font-mono">{bas.seg_fijo || 'N/A'}</p></div>
                  <div><span className="text-[#7c757c]">Seg. Móvil:</span><p className="text-[#1a1030] font-mono">{bas.seg_movil || 'N/A'}</p></div>
                  <div><span className="text-[#7c757c]">CIMA:</span>
                    <span className={attr.cima === 'SI' ? 'text-emerald-700 font-medium ml-1' : 'text-[#7c757c] ml-1'}>
                      {attr.cima === 'SI' ? 'SÍ' : 'NO'}
                    </span>
                  </div>
                  <div><span className="text-[#7c757c]">Renove:</span>
                    <span className={attr.tiene_renove_mixto ? 'text-emerald-700 font-medium ml-1' : 'text-[#7c757c] ml-1'}>
                      {attr.tiene_renove_mixto ? 'SÍ' : 'NO'}
                    </span>
                  </div>
                  {attr.renove_mixto_variante && attr.renove_mixto_variante !== 'N/A' && (
                    <div className="col-span-2"><span className="text-[#7c757c]">Variante:</span>
                      <p className="text-[#0a6ea9] font-medium">{attr.renove_mixto_variante}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Líneas */}
              {todasLasLineas.length > 0 && (
                <>
                  <h4 className="text-sm font-semibold text-[#1a1030] mb-3 flex items-center gap-2">
                    <Phone size={14} className="text-[#0a6ea9]" /> Líneas ({todasLasLineas.length})
                  </h4>
                  <div className="space-y-3">
                    {todasLasLineas.map((l, i) => (
                      <div key={i} className="card !p-3 border border-[#e8dce6]">
                        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs">
                          <div><span className="text-[#7c757c]">Número:</span> <span className="font-mono">{l.numero}</span></div>
                          <div><span className="text-[#7c757c]">Paquete:</span> <span>{l.paquete}</span></div>
                          <div><span className="text-[#7c757c]">Producto:</span> <span>{l.producto}</span></div>
                          <div><span className="text-[#7c757c]">CIMA:</span> <span className={l.cima === 'SI' ? 'text-emerald-600 font-medium' : ''}>{l.cima}</span></div>
                          <div><span className="text-[#7c757c]">TV:</span> <span>{l.tiene_tv ? 'SÍ' : 'NO'}</span></div>
                          <div><span className="text-[#7c757c]">Principal:</span> <span>{l.es_principal ? 'SÍ' : 'NO'}</span></div>
                          <div><span className="text-[#7c757c]">Activo desde:</span> <span>{l.activo_desde}</span></div>
                          <div><span className="text-[#7c757c]">Permanencia:</span> <span>{l.permanencia} {l.permanencia_fecha ? `(vence ${l.permanencia_fecha})` : ''}</span></div>
                          <div><span className="text-[#7c757c]">Consumo:</span> <span>{l.consumo}</span></div>
                          <div><span className="text-[#7c757c]">Venta Plazos:</span> <span>{l.venta_plazos}</span></div>
                        </div>
                        {l.variante_renove !== 'N/A' && (
                          <div className="pt-1"><span className="text-[#7c757c] text-xs">Renove:</span> <span className="text-[#0a6ea9] font-medium text-xs">{l.variante_renove}</span></div>
                        )}
                        {l.campanas_extra.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-[#e8dce6]">
                            <span className="text-[10px] text-[#7c757c] uppercase tracking-wider">Campañas</span>
                            <div className="mt-1 space-y-0.5">
                              {l.campanas_extra.map((c, ci) => (
                                <p key={ci} className="text-[10px] text-[#7c757c]">
                                  <strong className="text-[#481162]">{c.tipo || 'Info'}:</strong> {c.texto || c}
                                </p>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* Pipeline (si existe) */}
              {pipeline.estado && pipeline.estado !== 'pendiente' && (
                <div className="mt-4 pt-3 border-t border-[#e8dce6]">
                  <h4 className="text-xs font-semibold text-[#1a1030] mb-2">Pipeline</h4>
                  <div className="flex items-center gap-3 text-xs">
                    <span className={`px-2 py-0.5 rounded-full border ${PIPELINE_ESTADOS.find(e => e.value === pipeline.estado)?.color || 'bg-gray-100 text-gray-700'}`}>
                      {PIPELINE_ESTADOS.find(e => e.value === pipeline.estado)?.label || pipeline.estado}
                    </span>
                    {pipeline.notas && <span className="text-[#7c757c]">{pipeline.notas}</span>}
                  </div>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
