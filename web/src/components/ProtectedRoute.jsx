import { Navigate, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'

// Mapa de rutas protegidas por rol
const ROUTE_PERMISSIONS = {
  '/dashboard': ['supervisor', 'back_office', 'it', 'jefe_area', 'desarrollador'],
  '/clientes': ['supervisor', 'back_office', 'it', 'jefe_area', 'desarrollador', 'asesor'],
  '/configurar-bot': ['it', 'jefe_area', 'desarrollador'],
  '/documentos': ['supervisor', 'back_office', 'it', 'jefe_area', 'desarrollador'],
  '/admin/users': ['jefe_area', 'desarrollador'],
  '/usuarios': ['jefe_area', 'desarrollador'],
  '/proxies': ['it', 'jefe_area', 'desarrollador'],
}

// Destino por defecto según el rol
const DEFAULT_ROUTES = {
  asesor: '/clientes',
  supervisor: '/dashboard',
  back_office: '/dashboard',
  it: '/dashboard',
  jefe_area: '/dashboard',
  desarrollador: '/dashboard',
}

export default function ProtectedRoute({ children }) {
  const [checking, setChecking] = useState(true)
  const [authorized, setAuthorized] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const raw = localStorage.getItem('oratioo_session')
    if (!raw) {
      setAuthorized(false)
      setChecking(false)
      return
    }

    const parsed = JSON.parse(raw)
    const userRol = parsed.rol || 'asesor'
    const path = location.pathname
    const allowed = ROUTE_PERMISSIONS[path]

    if (allowed && !allowed.includes(userRol)) {
      // No tiene permiso -> redirigir
      const destino = DEFAULT_ROUTES[userRol] || '/dashboard'
      window.location.href = destino
      setAuthorized(false)
    } else {
      setAuthorized(true)
    }
    setChecking(false)
  }, [location.pathname])

  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#f5f5fa]">
        <div className="w-6 h-6 border-2 border-[#1495e0]/30 border-t-[#1495e0] rounded-full animate-spin" />
      </div>
    )
  }

  if (!authorized) {
    return <Navigate to="/login" replace />
  }

  return children
}
