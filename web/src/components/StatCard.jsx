export default function StatCard({ icon: Icon, label, value, color = 'purple' }) {
  const colorMap = {
    purple: 'bg-[#f5ebf3] text-[#481163]',
    emerald: 'bg-emerald-50 text-emerald-600',
    blue: 'bg-blue-50 text-blue-600',
    amber: 'bg-amber-50 text-amber-600',
    slate: 'bg-slate-50 text-slate-600',
  }

  return (
    <div className="card !p-4 flex items-center gap-3">
      <div className={`p-2 rounded-lg ${colorMap[color] || colorMap.purple}`}>
        <Icon size={18} />
      </div>
      <div>
        <p className="text-[10px] text-[#7c757c] uppercase tracking-wider">{label}</p>
        <p className="text-lg font-bold text-[#1a1030]">{value}</p>
      </div>
    </div>
  )
}
