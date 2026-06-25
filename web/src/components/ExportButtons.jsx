import { useState } from 'react'
import { Download, Loader2 } from 'lucide-react'

export default function ExportButtons({ data }) {
  const [exporting, setExporting] = useState(false)

  const exportCSV = async () => {
    if (!data || data.length === 0) return
    setExporting(true)
    try {
      const headers = ['DNI', 'Nombre', 'CIMA', 'Renove Mixto', 'Variante', 'Línea', 'Paquete', 'Dirección', 'Fecha']
      const rows = data.map(c => {
        const ad = c.atributos_dinamicos || {}
        const bas = ad.datos_basicos || {}
        return [
          c.dni,
          bas.nombre || c.nombre || '',
          ad.cima === 'SI' ? 'SÍ' : 'NO',
          ad.tiene_renove_mixto ? 'SÍ' : 'NO',
          ad.renove_mixto_variante || 'N/A',
          c.linea || '',
          ad.paquete_principal || c.paquete || '',
          bas.direccion || '',
          ad.fecha_procesado || '',
        ]
      })

      const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))].join('\n')
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `clientes_oratioo_${new Date().toISOString().split('T')[0]}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Error exportando:', err)
    } finally {
      setExporting(false)
    }
  }

  const exportExcel = async () => {
    if (!data || data.length === 0) return
    setExporting(true)
    try {
      const ExcelJS = await import('exceljs')
      const wb = new ExcelJS.Workbook()
      const ws = wb.addWorksheet('Clientes')

      ws.columns = [
        { header: 'DNI', key: 'dni', width: 15 },
        { header: 'Nombre', key: 'nombre', width: 30 },
        { header: 'CIMA', key: 'cima', width: 8 },
        { header: 'Renove Mixto', key: 'renove', width: 14 },
        { header: 'Variante', key: 'variante', width: 40 },
        { header: 'Línea', key: 'linea', width: 15 },
        { header: 'Paquete', key: 'paquete', width: 20 },
        { header: 'Dirección', key: 'direccion', width: 40 },
        { header: 'Fecha', key: 'fecha', width: 12 },
      ]

      for (const c of data) {
        const ad = c.atributos_dinamicos || {}
        const bas = ad.datos_basicos || {}
        ws.addRow({
          dni: c.dni,
          nombre: bas.nombre || c.nombre || '',
          cima: ad.cima === 'SI' ? 'SÍ' : 'NO',
          renove: ad.tiene_renove_mixto ? 'SÍ' : 'NO',
          variante: ad.renove_mixto_variante || 'N/A',
          linea: c.linea || '',
          paquete: ad.paquete_principal || c.paquete || '',
          direccion: bas.direccion || '',
          fecha: ad.fecha_procesado || '',
        })
      }

      const buf = await wb.xlsx.writeBuffer()
      const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `clientes_oratioo_${new Date().toISOString().split('T')[0]}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Error exportando Excel:', err)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={exportCSV}
        disabled={exporting || !data || data.length === 0}
        className="text-xs px-2 py-1 rounded border border-[#e8dce6] hover:bg-[#f0f0f8] disabled:opacity-40 flex items-center gap-1"
      >
        {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
        CSV
      </button>
      <button
        onClick={exportExcel}
        disabled={exporting || !data || data.length === 0}
        className="text-xs px-2 py-1 rounded border border-[#e8dce6] hover:bg-[#f0f0f8] disabled:opacity-40 flex items-center gap-1"
      >
        {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
        Excel
      </button>
    </div>
  )
}
