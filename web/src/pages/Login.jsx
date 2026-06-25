import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff, LogIn } from 'lucide-react'
import { loginWithPassword } from '../api'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const { profile } = await loginWithPassword(email, password)
      
      localStorage.setItem('oratioo_session', JSON.stringify(profile))
      
      // Redirigir según rol
      const rol = profile.rol || 'asesor'
      if (rol === 'asesor') {
        navigate('/clientes', { replace: true })
      } else {
        navigate('/dashboard', { replace: true })
      }
    } catch (err) {
      setError('Error al iniciar sesión: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#481163' }}>
      <div className="flex items-center justify-center min-h-screen p-4">
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-96 h-96 bg-[#0a6ea9]/10 rounded-full blur-3xl" />
          <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-[#0a6ea9]/10 rounded-full blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#0a6ea9]/5 rounded-full blur-[100px]" />
        </div>

        <div className="relative w-full max-w-md">
          <div className="bg-[#3a0e50]/80 backdrop-blur-xl rounded-2xl p-10 border border-[#5d1a7a] shadow-2xl">
            <div className="text-center mb-8">
              <svg viewBox="0 0 123 19" className="h-7 w-auto mx-auto" style={{ filter: 'brightness(0) invert(1)' }}>
                <path d="M26.511 7.841C26.369 6.9 26.072 5.922 25.552 4.988C25.423 4.759 25.263 4.512 25.089 4.237C25.003 4.1 24.892 3.969 24.785 3.825C24.675 3.685 24.564 3.532 24.437 3.386C23.919 2.801 23.252 2.168 22.363 1.585C21.474 1.009 20.353 0.496 19.011 0.212C18.677 0.146 18.326 0.1 17.969 0.05C17.788 0.039 17.607 0.031 17.422 0.02L17.141 0.007L17.001 0L15.033 0C13.859 0 12.213 0.002 10.86 0.004C10.521 0.004 10.202 0.007 9.913 0.009L9.696 0.009C9.608 0.013 9.522 0.017 9.438 0.02C9.273 0.028 9.119 0.037 8.979 0.044C8.698 0.052 8.474 0.1 8.321 0.118L8.081 0.155C8.081 0.155 7.979 0.17 7.796 0.199C7.615 0.236 7.357 0.301 7.038 0.382C6.878 0.417 6.708 0.476 6.527 0.539C6.346 0.605 6.152 0.672 5.948 0.744C5.559 0.926 5.118 1.105 4.702 1.364C3.854 1.856 3.008 2.521 2.366 3.261C2.192 3.436 2.054 3.635 1.909 3.816C1.764 3.999 1.626 4.178 1.515 4.366C1.4 4.549 1.291 4.724 1.187 4.89C1.095 5.06 1.015 5.226 0.941 5.377C0.403 6.481 0.156 7.529 0.047 8.446C0.034 8.677 0.023 8.9 0.011 9.114C0.007 9.219 0.002 9.321 0 9.424V10.216C0 10.262 0.005 10.306 0.007 10.352L0.02 10.614C0.029 10.784 0.041 10.95 0.05 11.107C0.066 11.264 0.095 11.415 0.115 11.559C0.163 11.849 0.201 12.116 0.274 12.353C0.339 12.594 0.396 12.816 0.459 13.017C0.534 13.216 0.604 13.397 0.667 13.565C1.07 14.552 1.631 15.405 2.268 16.126C2.922 16.835 3.655 17.405 4.415 17.855C5.959 18.719 7.615 19.086 9.155 18.983C9.345 18.968 9.537 18.955 9.725 18.94L10.193 18.868C10.505 18.815 10.815 18.763 11.125 18.71C11.747 18.601 12.367 18.479 13 18.35C14.262 18.09 15.565 17.789 16.98 17.449" fill="currentColor" />
              </svg>
              <p className="text-[#11ddde] text-sm mt-3 tracking-wide">Panel de gestión — Local</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-xs text-[#11ddde] font-medium mb-1.5 uppercase tracking-wider">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@oratioo.com"
                  className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-3 text-[#11ddde] placeholder-[#11ddde]/50 focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-white/20 transition-all text-sm"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs text-[#11ddde] font-medium mb-1.5 uppercase tracking-wider">Contraseña</label>
                <div className="relative">
                  <input
                    type={showPass ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-3 text-[#11ddde] placeholder-[#11ddde]/50 focus:outline-none focus:ring-2 focus:ring-white/20 focus:border-white/20 transition-all text-sm pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass(!showPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#11ddde] hover:text-white"
                  >
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {error && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-sm text-red-300">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading || !email || !password}
                className="w-full bg-[#1495e0] hover:bg-[#0f7cc0] disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-all duration-200 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <LogIn size={16} />
                )}
                {loading ? 'Ingresando...' : 'Iniciar sesión'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
