import { useEffect, useState } from 'react';
import {
  PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer
} from 'recharts';
import api from '../../api';

export default function OfficerDashboard() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/officer/dashboard')
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (!data)   return <div className="text-red-500">Failed to load dashboard.</div>;

  const { summary, charts } = data;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Portfolio Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Collections Intelligence Overview</p>
        </div>
        <span className="text-xs text-gray-400">
          {new Date().toLocaleDateString('en-IN', { dateStyle: 'long' })}
        </span>
      </div>

      {/* KPI Cards Row 1 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Total Borrowers"
          value={summary.total_borrowers}
          icon="👥"
          color="blue"
        />
        <KPICard
          label="High Risk Accounts"
          value={summary.high_risk_accounts}
          icon="🔴"
          color="red"
          sub={`of ${summary.total_loans} loans`}
        />
        <KPICard
          label="Expected Recovery"
          value={`₹${(summary.expected_recovery / 100000).toFixed(1)}L`}
          icon="💰"
          color="green"
        />
        <KPICard
          label="Self Cure Rate"
          value={`${summary.self_cure_rate}%`}
          icon="📈"
          color="purple"
        />
      </div>

      {/* KPI Cards Row 2 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Total Outstanding"
          value={`₹${(summary.total_outstanding / 100000).toFixed(1)}L`}
          icon="🏦"
          color="blue"
        />
        <KPICard
          label="Portfolio NPV"
          value={`₹${(summary.total_npv / 100000).toFixed(1)}L`}
          icon="📊"
          color="green"
        />
        <KPICard
          label="Grace Requests"
          value={summary.pending_grace_requests}
          icon="⏱"
          color="yellow"
          sub="Pending"
          href="/officer/grace"
        />
        <KPICard
          label="Restructure Requests"
          value={summary.pending_restructure_requests}
          icon="🔄"
          color="purple"
          sub="Pending"
          href="/officer/restructure"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Risk Distribution Pie */}
        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Risk Distribution</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={charts.risk_distribution}
                dataKey="count"
                nameKey="segment"
                cx="50%"
                cy="50%"
                outerRadius={90}
                label={({ segment, count }) => `${segment}: ${count}`}
              >
                {charts.risk_distribution.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Recovery Strategy Bar */}
        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Recovery Strategy Mix</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart
              data={charts.recovery_strategy_mix}
              layout="vertical"
              margin={{ left: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="strategy" tick={{ fontSize: 10 }} width={140} />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-4">Portfolio Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Stat label="Overall Recovery Rate" value={`${summary.overall_recovery_rate}%`} />
          <Stat label="Overdue Loans"         value={summary.overdue_loans} />
          <Stat label="Medium Risk Accounts"  value={summary.medium_risk_accounts} />
          <Stat label="Low Risk Accounts"     value={summary.low_risk_accounts} />
        </div>
      </div>
    </div>
  );
}

function KPICard({ label, value, icon, color, sub, href }) {
  const colors = {
    blue:   'bg-blue-50 text-blue-700 border-blue-100',
    red:    'bg-red-50 text-red-700 border-red-100',
    green:  'bg-green-50 text-green-700 border-green-100',
    purple: 'bg-purple-50 text-purple-700 border-purple-100',
    yellow: 'bg-yellow-50 text-yellow-700 border-yellow-100',
  };
  const Tag = href ? 'a' : 'div';
  return (
    <Tag
      href={href}
      className={`rounded-2xl border p-5 ${colors[color]} ${href ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
    >
      <div className="flex items-start justify-between">
        <span className="text-2xl">{icon}</span>
      </div>
      <p className="text-2xl font-bold mt-2">{value}</p>
      <p className="text-xs font-medium mt-1 opacity-80">{label}</p>
      {sub && <p className="text-xs opacity-60 mt-0.5">{sub}</p>}
    </Tag>
  );
}

function Stat({ label, value }) {
  return (
    <div className="text-center">
      <p className="text-2xl font-bold text-gray-800">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
    </div>
  );
}