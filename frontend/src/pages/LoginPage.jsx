import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

export default function LoginPage() {
  const navigate = useNavigate();

  const [role,     setRole]     = useState('customer');
  const [userId,   setUserId]   = useState('');
  const [password, setPassword] = useState('');
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await api.post('/auth/login', {
        user_id:  userId.trim(),
        password: password,
        role:     role,
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-blue-800 to-blue-600 flex items-center justify-center p-4">
      <div className="w-full max-w-md">

        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white rounded-2xl shadow-lg mb-4">
            <span className="text-3xl">🏦</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Collections Intelligence</h1>
          <p className="text-blue-200 mt-1">AI-Powered Recovery Platform</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">

          {/* Role Toggle */}
          <div className="flex rounded-xl bg-gray-100 p-1 mb-6">
            <button
              onClick={() => { setRole('customer'); setUserId(''); setError(''); }}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                role === 'customer'
                  ? 'bg-white shadow text-blue-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              👤 Customer
            </button>
            <button
              onClick={() => { setRole('officer'); setUserId(''); setError(''); }}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                role === 'officer'
                  ? 'bg-white shadow text-blue-700'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              🏛️ Bank Officer
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {role === 'customer' ? 'Customer ID' : 'Officer ID'}
              </label>
              <input
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder={role === 'customer' ? 'e.g. CUST001' : 'e.g. OFF001'}
                required
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
                ⚠️ {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Demo credentials */}
          <div className="mt-6 p-4 bg-gray-50 rounded-xl">
            <p className="text-xs font-semibold text-gray-500 mb-2">DEMO CREDENTIALS</p>
            {role === 'customer' ? (
              <div className="space-y-1 text-xs text-gray-600">
                <p>🟢 <strong>CUST001</strong> / password123 — Arun Mehta (Medium Risk)</p>
                <p>🔴 <strong>CUST003</strong> / password123 — Vikram Nair (High Risk)</p>
                <p>🔵 <strong>CUST006</strong> / password123 — Anjali Singh (Low Risk)</p>
              </div>
            ) : (
              <div className="space-y-1 text-xs text-gray-600">
                <p>🏛️ <strong>OFF001</strong> / officer123 — Rajesh Kumar</p>
                <p>🏛️ <strong>OFF002</strong> / officer123 — Priya Sharma</p>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}