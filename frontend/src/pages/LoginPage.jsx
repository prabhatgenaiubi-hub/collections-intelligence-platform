import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

/* ── decorative SVG blob for left panel ── */
function Blob({ className, opacity = 0.12 }) {
  return (
    <svg viewBox="0 0 200 200" className={className} style={{ opacity }}>
      <path
        fill="white"
        d="M44.7,-67.1C56.3,-57.3,62.8,-41.4,67.4,-25.3C72,-9.2,74.7,7.1,70.2,21.3C65.7,35.5,54,47.6,40.4,56.3C26.8,65,11.4,70.3,-4.3,71C-20,71.7,-40,68,-54.5,57.9C-69,47.8,-78,31.3,-79.5,14.4C-81,-2.5,-75,-19.8,-65.2,-33.3C-55.4,-46.8,-41.8,-56.5,-27.5,-64.8C-13.2,-73.1,1.8,-80,16.6,-79.3C31.4,-78.6,33.1,-76.9,44.7,-67.1Z"
        transform="translate(100 100)"
      />
    </svg>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();

  const [role,     setRole]     = useState('officer');
  const [userId,   setUserId]   = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.post('/auth/login', {
        user_id:  userId.trim(),
        password,
        role,
      });
      const { token, role: userRole, user_id, name } = res.data;
      localStorage.setItem('token',   token);
      localStorage.setItem('role',    userRole);
      localStorage.setItem('user_id', user_id);
      localStorage.setItem('name',    name);
      if (userRole === 'customer') navigate('/customer');
      else                         navigate('/officer');
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const features = [
    { icon: '🤖', text: 'AI-powered risk segmentation' },
    { icon: '📊', text: 'Real-time portfolio analytics' },
    { icon: '💬', text: 'Intelligent officer chat assistant' },
    { icon: '⚡', text: 'Automated recovery workflows' },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center p-4"
      style={{ background: 'linear-gradient(135deg, #0a1628 0%, #0f2351 50%, #1a1a2e 100%)' }}>

      {/* Card wrapper */}
      <div className="w-full max-w-5xl rounded-3xl overflow-hidden shadow-2xl flex"
        style={{ minHeight: '580px', boxShadow: '0 32px 80px rgba(0,0,0,0.5)' }}>

        {/* ── LEFT PANEL ─────────────────────────────────────────── */}
        {/* Color theory: Union Bank uses #003087 (blue) + #E31837 (red).
            Left panel uses deep navy as base, with red as accent — analogous
            harmony keeps it professional; red draws attention to key elements. */}
        <div className="relative hidden md:flex flex-col justify-between p-10 overflow-hidden"
          style={{
            width: '48%',
            background: 'linear-gradient(150deg, #003087 0%, #001a5c 60%, #0a0f2e 100%)',
          }}>

          {/* Decorative blobs */}
          <Blob className="absolute -top-16 -left-16 w-72 h-72" opacity={0.08} />
          <Blob className="absolute bottom-0 right-0 w-80 h-80 rotate-180" opacity={0.06} />

          {/* Red accent bar */}
          <div className="absolute top-0 left-0 w-1.5 h-full"
            style={{ background: 'linear-gradient(180deg, #E31837 0%, #ff6b35 100%)' }} />

          {/* Top — logo + bank name */}
          <div className="relative z-10">
            {/* Union Bank actual logo */}
            <div className="mb-8">
              <img
                src="/union_bank_logo.png"
                alt="Union Bank of India"
                style={{ height: '72px', width: 'auto', objectFit: 'contain',
                  filter: 'brightness(0) invert(1)',
                  dropShadow: '0 2px 8px rgba(0,0,0,0.3)' }}
              />
            </div>

            {/* App name */}
            <div className="mb-4">
              <div />
              <h1 className="text-white font-bold leading-tight" style={{ fontSize: '2rem' }}>
                Collections
              </h1>
              <h1 className="font-bold leading-tight" style={{ fontSize: '2rem',
                background: 'linear-gradient(90deg, #E31837, #ff6b35)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Intelligence
              </h1>
              <h1 className="text-white font-bold leading-tight" style={{ fontSize: '2rem' }}>
                Platform
              </h1>
            </div>

            <p className="text-blue-200 text-sm leading-relaxed mt-4" style={{ maxWidth: '280px' }}>
              Harness the power of AI to transform loan recovery — smarter segmentation,
              faster decisions, better outcomes.
            </p>
          </div>

          {/* Middle — feature pills */}
          <div className="relative z-10 space-y-3 my-6">
            {features.map((f, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-2.5 rounded-xl"
                style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.1)' }}>
                <span className="text-lg">{f.icon}</span>
                <span className="text-blue-100 text-sm">{f.text}</span>
              </div>
            ))}
          </div>

          {/* Bottom — tagline */}
          <div className="relative z-10 pt-4"
            style={{ borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <p className="text-blue-300 text-xs">
              Empowering collections officers with data-driven intelligence.
            </p>
          </div>
        </div>

        {/* ── RIGHT PANEL — Sign In Form ──────────────────────────── */}
        <div className="flex-1 bg-white flex flex-col justify-center px-10 py-12">

          {/* Mobile-only header */}
          <div className="md:hidden text-center mb-8">
            <h1 className="text-2xl font-bold text-gray-800">Collections Intelligence</h1>
            <p className="text-gray-500 text-sm mt-1">Union Bank of India</p>
          </div>

          <h2 className="text-2xl font-bold text-gray-800 mb-1">Welcome Back</h2>
          <p className="text-gray-400 text-sm mb-8">Sign in to your account to continue</p>

          {/* Role Toggle */}
          <div className="flex rounded-xl p-1 mb-6"
            style={{ background: '#f1f5f9' }}>
            {[
              { val: 'officer', label: '🏛️ Bank Officer' },
              { val: 'customer', label: '👤 Customer' },
            ].map(({ val, label }) => (
              <button key={val}
                onClick={() => { setRole(val); setUserId(''); setError(''); }}
                className="flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all"
                style={role === val
                  ? { background: 'white', color: '#003087',
                      boxShadow: '0 1px 6px rgba(0,48,135,0.15)' }
                  : { color: '#94a3b8' }}>
                {label}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-4">
            {/* ID Field */}
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">
                {role === 'customer' ? 'Customer ID' : 'Officer ID'}
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">
                  👤
                </span>
                <input
                  type="text"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder={role === 'customer' ? 'e.g. CUST001' : 'e.g. OFF001'}
                  required
                  className="w-full pl-10 pr-4 py-3 rounded-xl text-sm text-gray-700 outline-none transition-all"
                  style={{ border: '1.5px solid #e2e8f0',
                    background: '#f8fafc',
                    focusBorderColor: '#003087' }}
                  onFocus={e => e.target.style.borderColor = '#003087'}
                  onBlur={e  => e.target.style.borderColor = '#e2e8f0'}
                />
              </div>
            </div>

            {/* Password Field */}
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">
                Password
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔒</span>
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  className="w-full pl-10 pr-12 py-3 rounded-xl text-sm text-gray-700 outline-none transition-all"
                  style={{ border: '1.5px solid #e2e8f0', background: '#f8fafc' }}
                  onFocus={e => e.target.style.borderColor = '#003087'}
                  onBlur={e  => e.target.style.borderColor = '#e2e8f0'}
                />
                <button type="button"
                  onClick={() => setShowPass(v => !v)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs">
                  {showPass ? '🙈' : '👁️'}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
                style={{ background: '#fff1f2', border: '1px solid #fecdd3', color: '#be123c' }}>
                <span>⚠️</span> {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full text-white font-semibold py-3 rounded-xl text-sm transition-all mt-2"
              style={{
                background: loading
                  ? '#94a3b8'
                  : 'linear-gradient(90deg, #003087 0%, #0051c3 100%)',
                boxShadow: loading ? 'none' : '0 4px 16px rgba(0,48,135,0.35)',
              }}>
              {loading
                ? <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="3" strokeDasharray="31 11"/>
                    </svg>
                    Signing in...
                  </span>
                : 'Sign In →'}
            </button>
          </form>

          {/* Demo credentials */}
          <div className="mt-6 rounded-xl overflow-hidden"
            style={{ border: '1px solid #e2e8f0' }}>
            <div className="px-4 py-2 flex items-center gap-2"
              style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              <span className="text-xs font-bold tracking-wider uppercase"
                style={{ color: '#003087' }}>Demo Credentials</span>
            </div>
            <div className="px-4 py-3 space-y-1.5">
              {role === 'customer' ? (
                <>
                  <p className="text-xs text-gray-600">🟢 <strong>CUST001</strong> / password123 — Arun Mehta</p>
                  <p className="text-xs text-gray-600">🔴 <strong>CUST003</strong> / password123 — Vikram Nair</p>
                  <p className="text-xs text-gray-600">🔵 <strong>CUST006</strong> / password123 — Anjali Singh</p>
                </>
              ) : (
                <>
                  <p className="text-xs text-gray-600">🏛️ <strong>OFF001</strong> / officer123 — Rajesh Kumar</p>
                  <p className="text-xs text-gray-600">🏛️ <strong>OFF002</strong> / officer123 — Priya Sharma</p>
                </>
              )}
            </div>
          </div>

          {/* Footer */}
          <p className="text-center text-xs text-gray-300 mt-6">
            © 2026 Union Bank of India · Collections Intelligence Platform
          </p>
        </div>
      </div>
    </div>
  );
}