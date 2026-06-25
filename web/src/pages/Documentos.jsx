import React, { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Upload, FileSpreadsheet, FileText, File, X, CheckCircle2, AlertCircle,
  Loader2, Clock, Eye, Database, Trash2, RefreshCw, ChevronDown, ChevronRight,
  List, AlertTriangle,
} from 'lucide-react'
import api, { TABLA_CLIENTES, TABLA_DOCUMENTOS } from '../api'

function utcToLocalDate(isoStr) {
  if (!isoStr) return 'sin_fecha'
  const d = new Date(isoStr)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}

function extractDNIs(text) {
  const dnis = new Set()
  const clean = text.replace(/^\uFEFF/, '')
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\u200B-\u200F\uFEFF]/g, '')
    .replace(/["'\u2018\u2019\u201C\u201D_]/g, '')
  const matches = clean.match(/\b(?:[A-Za-z]\d{8}|\d{7,8}[A-Za-z]|[A-Za-z]\d{7}[A-Za-z])\b/g)
  const nieGuiones = clean.match(/\b[A-Za-z]-\d{7}-[A-Za-z]\b/g)
  if (matches) matches.forEach(d => dnis.add(d.toUpperCase()))
  if (nieGuiones) nieGuiones.forEach(d => dnis.add(d.toUpperCase().replace(/-/g, '')))
  return Array.from(dnis)
}

function extractTelefonos(text) {
  const tels = new Set()
  const clean = text.replace(/[^\d]/g, ' ')
  const matches = clean.match(/\b[6-9]\d{8}\b/g)
  if (matches) matches.forEach(t => tels.add(t))
  return Array.from(tels)
}

function detectColumns(headers) {
  const dniKeywords = ['dni', 'documento', 'identidad', 'nrodocumento', 'num_doc', 'documento_identidad', 'cedula', 'id']
  const telKeywords = ['telefono', 'telefono_voz', 'movil', 'celular', 'fijo', 'fono', 'phone', 'tel']
  let dniCol = null, telCol = null
  for (const h of headers) {
    const hclean = h.toLowerCase().replace(/[^a-z0-9_]/g, '')
    if (!dniCol && dniKeywords.some(k => hclean.includes(k))) dniCol = h
    if (!telCol && telKeywords.some(k => hclean.includes(k))) telCol = h
  }
  return { dniCol, telCol }
}

export default function Documentos() {
  const [files, setFiles] = useState([])
  const [preview, setPreview] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploaded, setUploaded] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [error, setError] = useState('')
  const [deletingId, setDeletingId] = useState(null)
  const [expandedDay, setExpandedDay] = useState(null)
  const [dayDetails, setDayDetails] = useState({})
  const [queueStats, setQueueStats] = useState({ total: 0, pendientes: 0, completados: 0, errores: 0 })
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState({ status: '', text: '' })

  const fetchHistory = async () => {
    setLoadingHistory(true)
    try {
      const { data } = await api.from(TABLA_DOCUMENTOS).select('*').order('created_at', { ascending: false }).limit(100)
      setUploaded(data || [])
    } catch (err) {
      console.error('Error cargando historial:', err?.message || err)
    } finally { setLoadingHistory(false) }
  }

  useEffect(() => { fetchHistory() }, [])
  useEffect(() => {
    const interval = setInterval(fetchHistory, 300000)
    return () => clearInterval(interval)
  }, [])

  const loadQueueStats = async () => {
    try {
      const { data: docs } = await api.from(TABLA_DOCUMENTOS).select('id').order('created_at', { ascending: false }).limit(1)
      if (!docs || docs.length === 0) {
        setQueueStats({ total: 0, pendientes: 0, completados: 0, errores: 0 })
        return
      }
      const docId = String(docs[0].id)

      // Consultar lineas por documento_id en atributos_dinamicos
      const { data: allLineas } = await api.from(TABLA_CLIENTES).select('atributos_dinamicos').limit(5000)

      if (!allLineas) {
        setQueueStats({ total: 0, pendientes: 0, completados: 0, errores: 0 })
        return
      }

      const delDoc = allLineas.filter(l => {
        let ad = l.atributos_dinamicos || {}
        if (typeof ad === 'string') { try { ad = JSON.parse(ad) } catch { ad = {} } }
        return String(ad.documento_id) === docId
      })

      const total = delDoc.length
      const pendientes = delDoc.filter(l => {
        let ad = l.atributos_dinamicos || {}
        if (typeof ad === 'string') { try { ad = JSON.parse(ad) } catch { ad = {} } }
        return ad.estado === 'pendiente'
      }).length
      const completados = delDoc.filter(l => {
        let ad = l.atributos_dinamicos || {}
        if (typeof ad === 'string') { try { ad = JSON.parse(ad) } catch { ad = {} } }
        return ad.estado === 'completado'
      }).length
      const errores = delDoc.filter(l => {
        let ad = l.atributos_dinamicos || {}
        if (typeof ad === 'string') { try { ad = JSON.parse(ad) } catch { ad = {} } }
        return ad.estado === 'error' || ad.estado === 'no_cliente'
      }).length

      setQueueStats({ total, pendientes, completados, errores })
    } catch (err) {
      console.error('Error en loadQueueStats:', err)
    }
  }

  useEffect(() => {
    loadQueueStats()
    const interval = setInterval(loadQueueStats, 3000)
    return () => clearInterval(interval)
  }, [])

  const onDrop = useCallback((acceptedFiles) => {
    setError('')
    setFiles(prev => [...prev, ...acceptedFiles.map(f => ({
      id: `${f.name}-${Date.now()}`,
      file: f, name: f.name, size: f.size, type: f.type || f.name.split('.').pop(),
    }))])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    maxSize: 100 * 1024 * 1024,
  })

  const removeFile = (id) => {
    setFiles(prev => prev.filter(f => f.id !== id))
    if (preview?.id === id) setPreview(null)
  }

  const previewFile = async (fileData) => {
    setError('')
    try {
      const ext = fileData.name.split('.').pop().toLowerCase()
      let text = ''
      if (['xlsx', 'xls'].includes(ext)) {
        const ExcelJS = await import('exceljs')
        const wb = new ExcelJS.Workbook()
        const buf = await fileData.file.arrayBuffer()
        await wb.xlsx.load(buf)
        const ws = wb.worksheets[0]
        if (!ws) { setError('Sin hojas'); return }
        const rows = []
        ws.eachRow((row) => {
          const vals = []
          row.eachCell({ includeEmpty: true }, (cell, colNumber) => {
            while (vals.length < colNumber - 1) vals.push('')
            vals.push(String(cell.value ?? '').trim())
          })
          if (vals.some(v => v !== '')) rows.push(vals.join(';'))
        })
        text = rows.join('\n')
      } else {
        text = await fileData.file.text()
      }
      const lines = text.split('\n').filter(Boolean)
      const headers = (lines[0] || '').split(/[,;\t|]/).map(h => h.trim().replace(/^"|"$/g, ''))
      const cols = detectColumns(headers)
      const dnis = extractDNIs(text)
      const tels = extractTelefonos(text)
      setPreview({ id: fileData.id, name: fileData.name, headers, dniCol: cols.dniCol, telCol: cols.telCol,
        dnis, telefonos: tels, totalLines: lines.length, sample: lines.slice(0, 6) })
    } catch (err) {
      setError('No se pudo leer el archivo.')
    }
  }

  const handleUpload = async () => {
    if (files.length === 0) return
    setUploading(true)
    setError('')
    const errores = []
    let totalDNIsEncolados = 0
    const resultados = []

    try {
      for (const f of files) {
        const ext = f.name.split('.').pop().toLowerCase()
        let text = ''
        if (['xlsx', 'xls'].includes(ext)) {
          try {
            const ExcelJS = await import('exceljs')
            const wb = new ExcelJS.Workbook()
            const buf = await f.file.arrayBuffer()
            await wb.xlsx.load(buf)
            const ws = wb.worksheets[0]
            if (!ws) { errores.push(`${f.name}: sin hojas`); continue }
            const rows = []
            ws.eachRow((row) => {
              const vals = []
              row.eachCell({ includeEmpty: true }, (cell, colNumber) => {
                while (vals.length < colNumber - 1) vals.push('')
                vals.push(String(cell.value ?? '').trim())
              })
              if (vals.some(v => v !== '')) rows.push(vals.join(';'))
            })
            text = rows.join('\n')
          } catch (exErr) {
            errores.push(`${f.name}: error al leer Excel — ${exErr.message}`)
            continue
          }
        } else {
          text = await f.file.text()
        }

        const dnis = extractDNIs(text)
        if (dnis.length === 0) {
          errores.push(`${f.name}: sin DNIs detectados`)
          continue
        }

        // Crear documento en BD
        const { data: newDoc } = await api.from(TABLA_DOCUMENTOS).insert([{
          nombre_archivo: f.name,
          total_dnis: dnis.length,
          procesados: 0,
          estado: 'analizando',
        }])
        const docId = newDoc?.[0]?.id

        // Insertar DNIs en lineas
        const lote = dnis.map(dni => ({
          dni,
          linea: dni,
          atributos_dinamicos: {
            estado: 'pendiente',
            fecha_encolado: new Date().toISOString().split('T')[0],
            documento_id: String(docId || ''),
          },
        }))

        // Insertar en lotes de 500
        for (let i = 0; i < lote.length; i += 500) {
          const batch = lote.slice(i, i + 500)
          await api.from(TABLA_CLIENTES).insert(batch)
        }

        totalDNIsEncolados += dnis.length
        resultados.push({ name: f.name, dnis: dnis.length, docId })
      }

      if (errores.length > 0) {
        setError(errores.join('\n'))
      } else {
        setFiles([])
        setPreview(null)
        fetchHistory()
        loadQueueStats()
        alert(`✅ ${totalDNIsEncolados} DNIs encolados de ${resultados.length} archivos`)
      }
    } catch (err) {
      setError('Error al subir: ' + (err.message || 'Error desconocido'))
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteDocument = async (doc) => {
    if (!confirm(`¿Eliminar "${doc.nombre_archivo}" y todos sus DNIs?`)) return
    setDeletingId(doc.id)
    try {
      // Eliminar lineas asociadas
      const postgrestUrl = import.meta.env.VITE_POSTGREST_URL || 'http://localhost:3001'
      await fetch(`${postgrestUrl}/lineas?atributos_dinamicos->>documento_id=eq.${doc.id}`, { method: 'DELETE' })
      // Eliminar documento
      await fetch(`${postgrestUrl}/documentos?id=eq.${doc.id}`, { method: 'DELETE' })
      fetchHistory()
      loadQueueStats()
    } catch (err) {
      console.error('Error eliminando:', err)
    }
    setDeletingId(null)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1a1030]">Analizar Clientes</h1>
          <p className="text-xs text-[#7c757c] mt-0.5">Sube archivos con DNIs para analizar</p>
        </div>
      </div>

      {/* Dropzone */}
      <div {...getRootProps()} className={`card !p-8 border-2 border-dashed text-center cursor-pointer transition-all ${
        isDragActive ? 'border-[#0a6ea9] bg-[#f0f5ff]' : 'border-[#e8dce6] hover:border-[#0a6ea9]/50'
      }`}>
        <input {...getInputProps()} />
        <Upload size={36} className="mx-auto mb-3 text-[#b8b0b8]" />
        <p className="text-sm text-[#1a1030] font-medium">
          {isDragActive ? 'Suelta los archivos aquí' : 'Arrastra archivos o haz clic para seleccionar'}
        </p>
        <p className="text-[10px] text-[#7c757c] mt-1">CSV, TXT, XLSX, XLS — Máx 100MB</p>
      </div>

      {/* Files list */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map(f => (
            <div key={f.id} className="card !p-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileSpreadsheet size={18} className="text-[#0a6ea9]" />
                <div>
                  <p className="text-sm font-medium text-[#1a1030]">{f.name}</p>
                  <p className="text-[10px] text-[#7c757c]">{(f.size / 1024).toFixed(1)} KB</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => previewFile(f)} className="p-1.5 rounded hover:bg-[#f0f0f8] text-[#7c757c]">
                  <Eye size={14} />
                </button>
                <button onClick={() => removeFile(f.id)} className="p-1.5 rounded hover:bg-red-50 text-red-400">
                  <X size={14} />
                </button>
              </div>
            </div>
          ))}

          <button
            onClick={handleUpload}
            disabled={uploading}
            className="w-full bg-[#0a6ea9] hover:bg-[#085d8f] disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium flex items-center justify-center gap-2"
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {uploading ? 'Subiendo...' : `Subir y encolar ${files.length} archivo(s)`}
          </button>
        </div>
      )}

      {/* Preview */}
      {preview && (
        <div className="card !p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-[#1a1030]">Vista previa: {preview.name}</h3>
            <button onClick={() => setPreview(null)} className="p-1 rounded hover:bg-[#f0f0f8]"><X size={14} /></button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <div className="bg-[#f0f5ff] rounded-lg p-2 text-center">
              <p className="text-lg font-bold text-[#0a6ea9]">{preview.dnis.length}</p>
              <p className="text-[10px] text-[#7c757c]">DNIs</p>
            </div>
            <div className="bg-emerald-50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold text-emerald-600">{preview.telefonos.length}</p>
              <p className="text-[10px] text-[#7c757c]">Teléfonos</p>
            </div>
            <div className="bg-amber-50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold text-amber-600">{preview.dniCol || '—'}</p>
              <p className="text-[10px] text-[#7c757c]">Columna DNI</p>
            </div>
            <div className="bg-purple-50 rounded-lg p-2 text-center">
              <p className="text-lg font-bold text-purple-600">{preview.telCol || '—'}</p>
              <p className="text-[10px] text-[#7c757c]">Columna Tel</p>
            </div>
          </div>
          {preview.sample && (
            <div className="bg-[#faf8fa] rounded-lg p-3 overflow-x-auto">
              <pre className="text-[10px] text-[#7c757c]">{preview.sample.join('\n')}</pre>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-600 whitespace-pre-wrap">
          {error}
        </div>
      )}

      {/* Queue Stats */}
      {queueStats.total > 0 && (
        <div className="card !p-4">
          <h3 className="text-xs font-semibold text-[#7c757c] uppercase tracking-wider mb-3">Cola actual</h3>
          <div className="grid grid-cols-4 gap-2">
            {[
              { icon: Database, label: 'Total', value: queueStats.total, color: 'text-[#1a1030] bg-[#f5f5fa]' },
              { icon: Clock, label: 'Pendientes', value: queueStats.pendientes, color: 'text-amber-600 bg-amber-50' },
              { icon: CheckCircle2, label: 'Completados', value: queueStats.completados, color: 'text-emerald-600 bg-emerald-50' },
              { icon: AlertTriangle, label: 'Errores', value: queueStats.errores, color: 'text-red-500 bg-red-50' },
            ].map((s, i) => (
              <div key={i} className={`rounded-lg px-3 py-2 text-center ${s.color.split(' ').slice(1).join(' ')}`}>
                <p className={`text-lg font-bold ${s.color.split(' ')[0]}`}>{s.value.toLocaleString()}</p>
                <p className="text-[9px] text-[#7c757c]">{s.label}</p>
              </div>
            ))}
          </div>

          {/* Progress bar */}
          <div className="mt-3">
            <div className="h-1.5 bg-[#e8dce6] rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                style={{ width: `${queueStats.total > 0 ? (queueStats.completados / queueStats.total) * 100 : 0}%` }}
              />
            </div>
            <div className="flex justify-between mt-0.5">
              <span className="text-[9px] text-emerald-600">{queueStats.completados} completados</span>
              {queueStats.errores > 0 && <span className="text-[9px] text-red-500">{queueStats.errores} errores</span>}
            </div>
          </div>
        </div>
      )}

      {/* History */}
      <div className="card !p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-[#7c757c] uppercase tracking-wider">Últimas cargas</h3>
          <button onClick={fetchHistory} className="p-1 rounded hover:bg-[#f0f0f8]">
            <RefreshCw size={14} className={loadingHistory ? 'animate-spin' : ''} />
          </button>
        </div>
        {loadingHistory ? (
          <div className="flex items-center justify-center py-3">
            <Loader2 size={14} className="animate-spin text-[#b8b0b8]" />
          </div>
        ) : uploaded.length === 0 ? (
          <p className="text-[11px] text-[#7c757c] text-center py-2">Aún no hay cargas</p>
        ) : (
          <div className="space-y-1">
            {uploaded.slice(0, 10).map(d => {
              const completo = (d.procesados || 0) >= (d.total_dnis || 0) && (d.total_dnis || 0) > 0
              return (
                <div key={d.id} className="flex items-center justify-between bg-[#faf8fa] rounded-lg px-3 py-1.5 border border-[#e8dce6]">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${completo ? 'bg-emerald-400' : d.estado === 'analizando' ? 'bg-purple-400 animate-pulse' : 'bg-amber-400'}`} />
                    <span className="text-[11px] text-[#1a1030] truncate max-w-[200px]">{d.nombre_archivo}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-[#7c757c] flex-shrink-0">
                    <span>{d.procesados || 0}/{d.total_dnis || 0} DNIs</span>
                    <button onClick={() => handleDeleteDocument(d)}
                      className="p-0.5 rounded text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                      title="Eliminar">
                      <Trash2 size={10} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
