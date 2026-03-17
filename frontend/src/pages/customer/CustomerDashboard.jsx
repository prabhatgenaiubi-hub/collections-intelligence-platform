import { useEffect, useState } from 'react';
import api from '../../api';

export default function CustomerDashboard() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/customer/profile')
      .then(r => setProfile(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (!profile) return <div className="text-red-500">Failed to load profile.</div>;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="bg-gradient-to-r from-blue-700 to-blue-500 rounded-2xl p-6 text-white shadow">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{profile.customer_name}</h1>
            <p className="text-blue-100 text-sm mt-1">{profile.email_id} • {profile.mobile_number}</p>
          </div>
          <div className="text-right">
            <p className="text-blue-100 text-xs">Total Loan Exposure</p>
            <p className="text-2xl font-bold">₹{profile.total_loan_exposure?.toLocaleString('en-IN')}</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-6">
          <StatCard label="Total Loans"       value={profile.total_loans}    />
          <StatCard label="Credit Score"      value={profile.credit_score}   />
          <StatCard label="Preferred Channel" value={profile.preferred_channel} />
        </div>
      </div>

      {/* Relationship Assessment */}
      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
          🧠 Customer Relationship Assessment
        </h2>
        <div className="bg-blue-50 border-l-4 border-blue-500 rounded-xl p-4">
          <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-line">
            {profile.relationship_assessment}
          </p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <QuickAction
          icon="📋"
          title="View Your Loans"
          desc="Check outstanding balance, EMI schedule and payment history"
          href="/customer/loans"
          color="blue"
        />
        <QuickAction
          icon="💬"
          title="Loan AI Chat"
          desc="Go to Your Loans and tap 💬 Chat on any loan to ask AI questions about it"
          href="/customer/loans"
          color="purple"
        />
        <QuickAction
          icon="📡"
          title="Communication Preference"
          desc="Set your preferred channel for bank communications"
          href="/customer/preferences"
          color="green"
        />
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="bg-white bg-opacity-20 rounded-xl p-3 text-center">
      <p className="text-blue-100 text-xs">{label}</p>
      <p className="text-white font-bold text-lg">{value}</p>
    </div>
  );
}

function QuickAction({ icon, title, desc, href, color }) {
  const colors = {
    blue:   'border-blue-200 hover:border-blue-400 hover:bg-blue-50',
    purple: 'border-purple-200 hover:border-purple-400 hover:bg-purple-50',
    green:  'border-green-200 hover:border-green-400 hover:bg-green-50',
  };
  return (
    <a
      href={href}
      className={`block bg-white rounded-2xl shadow p-5 border-2 transition-all cursor-pointer ${colors[color]}`}
    >
      <div className="text-3xl mb-3">{icon}</div>
      <h3 className="font-semibold text-gray-800 mb-1">{title}</h3>
      <p className="text-gray-500 text-xs">{desc}</p>
    </a>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
    </div>
  );
}