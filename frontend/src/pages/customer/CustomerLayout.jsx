import { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import api from '../../api';

export default function CustomerLayout() {
  const navigate  = useNavigate();
  const name      = localStorage.getItem('name') || 'Customer';
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = async () => {
    try { await api.post('/auth/logout'); } catch (_) {}
    localStorage.clear();
    navigate('/');
  };

  const navItems = [
    { to: '/customer',             label: '🏠 Dashboard',          end: true },
    { to: '/customer/loans',       label: '📋 Your Loans' },
    { to: '/customer/preferences', label: '📡 Preferred Channel' },
  ];

  return (
    <div className="min-h-screen flex bg-slate-100">

      {/* ── Sidebar ── */}
      <aside className="w-64 bg-blue-900 text-white flex flex-col min-h-screen fixed top-0 left-0 z-30">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-blue-800">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🏦</span>
            <div>
              <p className="font-bold text-sm leading-tight">Collections</p>
              <p className="font-bold text-sm leading-tight">Intelligence</p>
            </div>
          </div>
        </div>

        {/* User */}
        <div className="px-6 py-4 border-b border-blue-800 bg-blue-800">
          <p className="text-xs text-blue-300">Logged in as</p>
          <p className="font-semibold text-sm truncate">{name}</p>
          <span className="inline-block mt-1 px-2 py-0.5 bg-blue-600 rounded-full text-xs">Customer</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-white text-blue-900'
                    : 'text-blue-200 hover:bg-blue-800 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <div className="px-3 py-4 border-t border-blue-800">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-blue-200 hover:bg-red-600 hover:text-white transition-all"
          >
            🚪 Logout
          </button>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main className="flex-1 ml-64 p-6">
        <Outlet />
      </main>
    </div>
  );
}