import { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Users,
  UserCheck,
  RefreshCw,
  TrendingUp,
  Loader2,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import api, { TABLA_CLIENTES, TABLA_DOCUMENTOS } from "../api";
import StatCard from "../components/StatCard";

function utcToLocalDate(isoStr) {
  if (!isoStr) return "sin_fecha";
  const d = new Date(isoStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function localDateStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(true);
  const [stats, setStats] = useState({
    total: 0, cima: 0, renoveMixto: 0, cimaRenove: 0, tasaExtraccion: 0,
    maxDescuento: 0, conDescuento: 0, mejorPrecio: 0, renoveBasico: 0,
    multidispositivo: 0, otros: 0, noCliente: 0, porTelefono: 0,
  });
  const [chartData, setChartData] = useState([]);
  const [periodo, setPeriodo] = useState("hoy");

  function getDateFilter(periodo) {
    const now = new Date();
    if (periodo === "hoy") return new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if (periodo === "semana") { const s = new Date(now); s.setDate(s.getDate() - 7); return s; }
    if (periodo === "mes") return new Date(now.getFullYear(), now.getMonth(), 1);
    if (periodo === "trimestre") { const s = new Date(now); s.setMonth(s.getMonth() - 3); return s; }
    if (periodo === "6m") { const s = new Date(now); s.setMonth(s.getMonth() - 6); return s; }
    return null;
  }

  const fetchData = async (periodoActual) => {
    const p = periodoActual || periodo;
    setLoading(true);
    try {
      let todosLosDatos = [];
      const PAGE_SIZE = 1000;
      let offset = 0;
      let hayMas = true;
      const fechaCorte = getDateFilter(p);

      while (hayMas) {
        const q = api
          .from(TABLA_CLIENTES)
          .select("dni, atributos_dinamicos, created_at")
          .order("created_at", { ascending: false })
          .limit(PAGE_SIZE);

        // Filtros server-side via alias ad_ (API los traduce a atributos_dinamicos->>)
        q.in('ad_estado', ['completado', 'no_cliente']);
        if (fechaCorte) {
          const fStr = `${fechaCorte.getFullYear()}-${String(fechaCorte.getMonth() + 1).padStart(2, "0")}-${String(fechaCorte.getDate()).padStart(2, "0")}`;
          q.gte('ad_fecha_procesado', fStr);
        }

        const { data } = await q.offset(offset);

        if (data && data.length > 0) {
          todosLosDatos = [...todosLosDatos, ...data];
          offset += PAGE_SIZE;
          if (data.length < PAGE_SIZE) hayMas = false;
        } else {
          hayMas = false;
        }
      }

      // Agrupar por DNI
      const unicos = {};
      const variantesPorCliente = {};
      for (const c of todosLosDatos) {
        let ad = c.atributos_dinamicos || {};
        if (typeof ad === "string") { try { ad = JSON.parse(ad); } catch { ad = {}; } }
        const d = c.dni || "sin_dni";
        const tipoPrev = unicos[d]?.tipo_busqueda;
        if (!unicos[d] || (ad.estado === "completado" && unicos[d].estado !== "completado")) {
          unicos[d] = ad;
          if (tipoPrev && !ad.tipo_busqueda) unicos[d].tipo_busqueda = tipoPrev;
        }
        if (!variantesPorCliente[d]) variantesPorCliente[d] = new Set();
        if (ad.renove_mixto_variante && ad.renove_mixto_variante !== "N/A") {
          variantesPorCliente[d].add(ad.renove_mixto_variante);
        }
        if (ad.cima === "SI") unicos[d]._cima = true;
        if (ad.tipo_busqueda && !unicos[d].tipo_busqueda) unicos[d].tipo_busqueda = ad.tipo_busqueda;
      }

      const todos = Object.values(unicos);
      const completados = todos.filter((c) => c.estado === "completado");
      const noClientesArr = todos.filter((c) => c.estado === "no_cliente");

      const dnisCompletados = new Set(
        completados.map((c) => {
          for (const [dni, attr] of Object.entries(unicos)) { if (attr === c) return dni; }
          return "";
        }).filter(Boolean),
      );

      const clientesConVariante = (variante) => {
        let count = 0;
        for (const dni of dnisCompletados) {
          if (variantesPorCliente[dni]?.has(variante)) count++;
        }
        return count;
      };

      const VARIANTES_MIXTO = [
        "Renove mixto al mejor precio con máximo descuento",
        "Renove mixto al mejor precio con descuento",
        "Renove mixto al mejor precio",
        "Renove mixto",
      ];

      const total = todos.length;
      const noCliente = noClientesArr.length;
      const cima = completados.filter((c) => c.cima === "SI" || c._cima).length;
      const renoveMixto = completados.filter((c) => {
        const d = Object.keys(unicos).find((k) => unicos[k] === c);
        if (!d) return false;
        const vars = variantesPorCliente[d];
        return vars && VARIANTES_MIXTO.some((v) => vars.has(v));
      }).length;
      const maxDescuento = clientesConVariante("Renove mixto al mejor precio con máximo descuento");
      const conDescuento = clientesConVariante("Renove mixto al mejor precio con descuento");
      const mejorPrecio = clientesConVariante("Renove mixto al mejor precio");
      const renoveBasico = clientesConVariante("Renove mixto");
      const multidispositivo = clientesConVariante("Renove Multidispositivo");
      const otros = completados.filter((c) => {
        const d = Object.keys(unicos).find((k) => unicos[k] === c);
        if (!d) return false;
        const vars = variantesPorCliente[d];
        return vars && [...vars].some((v) => v !== "N/A" && !VARIANTES_MIXTO.includes(v) && v !== "Renove Multidispositivo");
      }).length;
      const cimaRenove = completados.filter((c) => {
        const d = Object.keys(unicos).find((k) => unicos[k] === c);
        if (!d) return false;
        const vars = variantesPorCliente[d];
        return (c.cima === "SI" || c._cima) && vars && VARIANTES_MIXTO.some((v) => vars.has(v));
      }).length;
      const tasaExtraccion = total > 0 ? Math.round((cimaRenove / total) * 100) : 0;
      const porTelefono = completados.filter((c) => c.tipo_busqueda === "telefono").length;

      setStats({ total, cima, renoveMixto, cimaRenove, tasaExtraccion, maxDescuento, conDescuento, mejorPrecio, renoveBasico, multidispositivo, otros, noCliente, porTelefono });
    } catch (err) {
      console.error("Error fetching dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [periodo]);

  // Monitoreo chart
  const fetchChartData = async () => {
    setChartLoading(true);
    try {
      // Documentos
      const { data: docs } = await api
        .from(TABLA_DOCUMENTOS)
        .select("created_at, total_dnis")
        .order("created_at", { ascending: false })
        .limit(1000);

      // Lineas
      // Solo últimos 7 días — una query por día con filtro server-side
      const last7 = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const dateStr = localDateStr(d);
        const nextStr = localDateStr(new Date(d.getTime() + 86400000));
        const label = d.toLocaleDateString("es", { weekday: "short", day: "numeric" });

        const subidos = (docs || [])
          .filter((doc) => utcToLocalDate(doc.created_at) === dateStr)
          .reduce((sum, doc) => sum + (doc.total_dnis || 0), 0);
        
        const delDiaResp = await api
          .from(TABLA_CLIENTES)
          .select("atributos_dinamicos")
          .gte('ad_fecha_procesado', dateStr)
          .lt('ad_fecha_procesado', nextStr)
          .limit(50000);
        const lineasRows = delDiaResp?.data || [];
        
        const lineas = lineasRows.filter((c) => {
          const a = c.atributos_dinamicos || {};
          return a.estado === "completado";
        }).length;
        const noCliente = lineasRows.filter((c) => {
          const a = c.atributos_dinamicos || {};
          return a.estado === "no_cliente";
        }).length;
        const errores = lineasRows.filter((c) => {
          const a = c.atributos_dinamicos || {};
          return a.estado === "error";
        }).length;

        last7.push({ day: label, Subidos: subidos, Líneas: lineas, "No Cliente": noCliente, Error: errores });
      }
      setChartData(last7);
    } catch (err) {
      console.error("Chart error:", err);
    } finally {
      setChartLoading(false);
    }
  };

  useEffect(() => { fetchChartData(); }, []);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border border-[#e8dce6] rounded-lg px-3 py-2 text-xs shadow-lg">
          <p className="text-[#7c757c] font-medium mb-1">{label}</p>
          {payload.map((p, i) => (
            <p key={i} style={{ color: p.color }}>{p.name}: {p.value}</p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#1a1030]">Dashboard</h1>
          <p className="text-xs text-[#7c757c] mt-0.5">Resumen general de extracción</p>
        </div>
        <select
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
          className="text-xs border border-[#e8dce6] rounded-lg px-3 py-1.5 bg-white text-[#1a1030]"
        >
          <option value="hoy">Hoy</option>
          <option value="semana">Última semana</option>
          <option value="mes">Este mes</option>
          <option value="trimestre">Último trimestre</option>
          <option value="6m">Últimos 6 meses</option>
        </select>
      </div>

      {/* Stats cards */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={24} className="animate-spin text-[#b8b0b8]" />
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <StatCard icon={Users} label="Total procesados" value={stats.total.toLocaleString()} color="purple" />
          <StatCard icon={RefreshCw} label="CIMA" value={stats.cima.toLocaleString()} color="emerald" />
          <StatCard icon={TrendingUp} label="Renove Mixto" value={stats.renoveMixto.toLocaleString()} color="blue" />
          <StatCard icon={UserCheck} label="CIMA + Renove" value={stats.cimaRenove.toLocaleString()} color="amber" />
          <StatCard icon={LayoutDashboard} label="Tasa extracción" value={`${stats.tasaExtraccion}%`} color="slate" />
        </div>
      )}

      {/* Variantes breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
        {[
          { label: "Máx descuento", value: stats.maxDescuento, color: "emerald" },
          { label: "Con descuento", value: stats.conDescuento, color: "blue" },
          { label: "Mejor precio", value: stats.mejorPrecio, color: "amber" },
          { label: "Renove mixto", value: stats.renoveBasico, color: "slate" },
          { label: "Multidispositivo", value: stats.multidispositivo, color: "purple" },
          { label: "Otros", value: stats.otros, color: "slate" },
        ].map((v, i) => (
          <div key={i} className="bg-white border border-[#e8dce6] rounded-lg px-3 py-2">
            <p className="text-[10px] text-[#7c757c]">{v.label}</p>
            <p className="text-lg font-bold text-[#1a1030]">{v.value}</p>
          </div>
        ))}
      </div>

      {/* Monitoreo Chart */}
      <div className="card !p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-[#7c757c] uppercase tracking-wider">
            Subidos vs Procesados por día
          </h3>
          <span className="text-[10px] text-[#7c757c]">
            Últimos 7 días{chartLoading ? " (cargando...)" : ""}
          </span>
        </div>
        {chartLoading ? (
          <div className="h-32 flex items-center justify-center">
            <Loader2 size={20} className="animate-spin text-[#b8b0b8]" />
          </div>
        ) : (
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barCategoryGap="20%">
                <CartesianGrid strokeDasharray="3 3" stroke="#e8dce6" />
                <XAxis dataKey="day" tick={{ fill: "#7c757c", fontSize: 10 }} axisLine={{ stroke: "#e8dce6" }} tickLine={false} />
                <YAxis tick={{ fill: "#7c757c", fontSize: 10 }} axisLine={{ stroke: "#e8dce6" }} tickLine={false} allowDecimals={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(72,17,100,0.06)" }} />
                <Bar dataKey="Subidos" fill="#0a6ea9" radius={[4, 4, 0, 0]} maxBarSize={20} />
                <Bar dataKey="Líneas" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={20} />
                <Bar dataKey="No Cliente" fill="#ef4444" radius={[4, 4, 0, 0]} maxBarSize={20} />
                <Bar dataKey="Error" fill="#9ca3af" radius={[4, 4, 0, 0]} maxBarSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
