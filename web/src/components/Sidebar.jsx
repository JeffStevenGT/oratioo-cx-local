import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Settings,
  Upload,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Shield,
  ChevronDown,
  Globe,
  Loader2,
  KeyRound,
  X,
} from "lucide-react";

// Grupos del sidebar
const GROUPS = [
  {
    label: "Infraestructura",
    items: [
      { to: "/clientes", icon: Users, label: "Clientes", badge: null },
      { to: "/configurar-bot", icon: Settings, label: "Configurar App", badge: null },
      { to: "/documentos", icon: Upload, label: "Analizar Clientes", badge: null },
    ],
  },
  {
    label: "Administración",
    items: [
      { to: "/admin/users", icon: Shield, label: "Usuarios", badge: null },
    ],
  },
];

export default function Sidebar({ onLogout }) {
  const [collapsed, setCollapsed] = useState(false);
  const [showPassModal, setShowPassModal] = useState(false);
  const [passForm, setPassForm] = useState({ current: '', newPass: '', confirm: '' });
  const [passSaving, setPassSaving] = useState(false);
  const [passError, setPassError] = useState('');
  const [passSuccess, setPassSuccess] = useState('');

  const [gruposAbiertos, setGruposAbiertos] = useState(() => {
    const saved = localStorage.getItem("sidebar_grupos");
    return saved
      ? JSON.parse(saved)
      : { Infraestructura: true, Administración: false };
  });

  const session = JSON.parse(localStorage.getItem("oratioo_session") || "{}");
  const userRol = session.rol || "jefe_area";

  // Permisos por rol para cada item del sidebar
  const ITEM_PERMISSIONS = {
    '/dashboard': { asesor: false, supervisor: true, back_office: true, it: true, jefe_area: true, desarrollador: true },
    '/clientes': { asesor: true, supervisor: true, back_office: true, it: true, jefe_area: true, desarrollador: true },
    '/configurar-bot': { asesor: false, supervisor: false, back_office: false, it: true, jefe_area: true, desarrollador: true },
    '/documentos': { asesor: false, supervisor: true, back_office: true, it: true, jefe_area: true, desarrollador: true },
    '/admin/users': { asesor: false, supervisor: false, back_office: false, it: false, jefe_area: true, desarrollador: true },
  }

  const canSee = (item) => {
    const perms = ITEM_PERMISSIONS[item.to]
    return perms ? perms[userRol] : true
  }

  const toggleGrupo = (label) => {
    setGruposAbiertos((prev) => {
      const next = { ...prev, [label]: !prev[label] };
      localStorage.setItem("sidebar_grupos", JSON.stringify(next));
      return next;
    });
  };

  const handleChangePassword = async () => {
    if (!passForm.current || !passForm.newPass) {
      setPassError('Completa todos los campos');
      return;
    }
    if (passForm.newPass.length < 8) {
      setPassError('Mínimo 8 caracteres');
      return;
    }
    if (passForm.newPass !== passForm.confirm) {
      setPassError('Las contraseñas no coinciden');
      return;
    }
    setPassSaving(true);
    setPassError('');

    try {
      const bcrypt = await import('bcryptjs');
      
      // Verificar contraseña actual
      const postgrestUrl = import.meta.env.VITE_POSTGREST_URL || 'http://localhost:3001';
      const { data: users } = await (await fetch(
        `${postgrestUrl}/usuarios?email=eq.${encodeURIComponent(session.email)}&select=id,password_hash`
      )).json();
      
      const user = users?.[0];
      if (!user) { setPassError('Usuario no encontrado'); setPassSaving(false); return; }
      
      const valid = await bcrypt.default.compare(passForm.current, user.password_hash);
      if (!valid) { setPassError('Contraseña actual incorrecta'); setPassSaving(false); return; }
      
      // Generar nuevo hash
      const newHash = await bcrypt.default.hash(passForm.newPass, 10);
      
      // Actualizar en BD
      await fetch(`${postgrestUrl}/usuarios?id=eq.${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password_hash: newHash }),
      });
      
      setPassSuccess('Contraseña actualizada correctamente');
      setPassForm({ current: '', newPass: '', confirm: '' });
    } catch (e) {
      setPassError('Error de conexión: ' + e.message);
    } finally {
      setPassSaving(false);
    }
  };

  return (
    <aside
      className={`${collapsed ? "w-16" : "w-60"} bg-[#481163] border-r border-[#5d1a7a] flex flex-col transition-all duration-300 h-screen sticky top-0`}
    >
      <div className="flex items-center justify-between h-16 px-4 border-b border-[#5d1a7a]">
        {!collapsed && (
          <svg viewBox="0 0 123 19" className="h-5 w-auto" style={{ filter: "brightness(0) invert(1)" }}>
            <path d="M26.511 7.841C26.369 6.9 26.072 5.922 25.552 4.988C25.423 4.759 25.263 4.512 25.089 4.237C25.003 4.1 24.892 3.969 24.785 3.825C24.675 3.685 24.564 3.532 24.437 3.386C23.919 2.801 23.252 2.168 22.363 1.585C21.474 1.009 20.353 0.496 19.011 0.212" fill="currentColor" />
          </svg>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded hover:bg-[#5d1a7a] text-white/60 hover:text-white transition-colors"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {GROUPS.map((group) => {
          const visibleItems = group.items.filter(canSee);
          if (visibleItems.length === 0) return null;

          return (
            <div key={group.label}>
              {!collapsed && (
                <button
                  onClick={() => toggleGrupo(group.label)}
                  className="flex items-center justify-between w-full px-3 py-1.5 text-[10px] text-[#11ddde]/60 uppercase tracking-wider font-semibold hover:text-[#11ddde] transition-colors"
                >
                  <span>{group.label}</span>
                  <ChevronDown
                    size={12}
                    className={`transition-transform ${gruposAbiertos[group.label] ? "rotate-0" : "-rotate-90"}`}
                  />
                </button>
              )}
              {(!collapsed ? gruposAbiertos[group.label] : true) && (
                <div className="space-y-0.5">
                  {visibleItems.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200 ${
                          isActive
                            ? "bg-white/10 text-white font-medium"
                            : "text-white/50 hover:text-white hover:bg-white/5"
                        } ${collapsed ? "justify-center" : ""}`
                      }
                      title={collapsed ? item.label : undefined}
                    >
                      <item.icon size={18} />
                      {!collapsed && <span>{item.label}</span>}
                    </NavLink>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-[#5d1a7a] p-3 space-y-1">
        <button
          onClick={() => setShowPassModal(true)}
          className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-white/50 hover:text-white hover:bg-white/5 transition-all ${collapsed ? "justify-center" : ""}`}
          title={collapsed ? "Cambiar contraseña" : undefined}
        >
          <KeyRound size={16} />
          {!collapsed && <span>Cambiar contraseña</span>}
        </button>

        <button
          onClick={onLogout}
          className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-red-400/70 hover:text-red-400 hover:bg-red-500/10 transition-all ${collapsed ? "justify-center" : ""}`}
          title={collapsed ? "Cerrar sesión" : undefined}
        >
          <LogOut size={16} />
          {!collapsed && <span>Cerrar sesión</span>}
        </button>
      </div>

      {/* Modal cambiar contraseña */}
      {showPassModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowPassModal(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-base font-semibold text-[#1a1030]">Cambiar contraseña</h2>
              <button onClick={() => setShowPassModal(false)} className="p-1 rounded hover:bg-[#f0f0f8]"><X size={18} /></button>
            </div>
            {passSuccess ? (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3 text-sm text-emerald-700 mb-4">{passSuccess}</div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-[#7c757c] mb-1">Contraseña actual</label>
                  <input type="password" value={passForm.current} onChange={(e) => setPassForm({ ...passForm, current: e.target.value })}
                    className="w-full border border-[#e8dce6] rounded-lg px-3 py-2 text-sm" placeholder="********" />
                </div>
                <div>
                  <label className="block text-xs text-[#7c757c] mb-1">Nueva contraseña</label>
                  <input type="password" value={passForm.newPass} onChange={(e) => setPassForm({ ...passForm, newPass: e.target.value })}
                    className="w-full border border-[#e8dce6] rounded-lg px-3 py-2 text-sm" placeholder="Mínimo 8 caracteres" />
                </div>
                <div>
                  <label className="block text-xs text-[#7c757c] mb-1">Confirmar nueva contraseña</label>
                  <input type="password" value={passForm.confirm} onChange={(e) => setPassForm({ ...passForm, confirm: e.target.value })}
                    className="w-full border border-[#e8dce6] rounded-lg px-3 py-2 text-sm" placeholder="Repite la contraseña" />
                </div>
                {passError && <p className="text-sm text-red-500">{passError}</p>}
                <button onClick={handleChangePassword} disabled={passSaving}
                  className="w-full bg-[#0a6ea9] hover:bg-[#085d8f] text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-50 mt-2">
                  {passSaving ? <Loader2 size={16} className="animate-spin mx-auto" /> : 'Guardar contraseña'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
