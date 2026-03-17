import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import api from '../../api';

export default function OfficerLayout() {
  const navigate = useNavigate();
  const name     = localStorage.getItem('name') || 'Officer';

  const handleLogout = async () => {
    try { await api.post('/auth/logout'); } catch (_) {}
    localStorage.clear();
    navigate('/');
  };

  const navItems = [
    { to: '/officer',             label: '📊 Dashboard',         end: true },
    { to: '/officer/search',      label: '🔍 Customer Search' },
    { to: '/officer/grace',       label: '⏱ Grace Requests' },
    { to: '/officer/restructure', label: '🔄 Restructure Requests' },
    { to: '/officer/sentiment',   label: '🧠 Sentiment Analysis' },
    { to: '/officer/chat',        label: '💬 AI Chat Assistant' },
  ];

  return (
    <div className="min-h-screen flex bg-slate-100">

      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-white flex flex-col min-h-screen fixed top-0 left-0 z-30">
        <div className="px-6 py-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🏦</span>
            <div>
              <p className="font-bold text-sm leading-tight">Collections</p>
              <p className="font-bold text-sm leading-tight text-slate-400">Officer Portal</p>
            </div>
          </div>
        </div>

        <div className="px-6 py-4 border-b border-slate-800 bg-slate-800">
          <p className="text-xs text-slate-400">Logged in as</p>
          <p className="font-semibold text-sm truncate">{name}</p>
          <span className="inline-block mt-1 px-2 py-0.5 bg-blue-600 rounded-full text-xs">Bank Officer</span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-white text-slate-900'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 py-4 border-t border-slate-800">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-300 hover:bg-red-600 hover:text-white transition-all"
          >
            🚪 Logout
          </button>
        </div>
      </aside>

      <main className="flex-1 ml-64 p-6">
        <Outlet />
      </main>
    </div>
  );
}