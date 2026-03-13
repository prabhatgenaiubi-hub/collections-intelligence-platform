import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';
import api from '../../api';

const riskColors = {
  High:   'text-red-600 bg-red-50 border-red-200',
  Medium: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  Low:    'text-green-600 bg-green-50 border-green-200',
};

const toneColors = {
  Positive: 'text-green-600 bg-green-50',
  Negative: 'text-red-600 bg-red-50',
  Neutral:  'text-gray-600 bg-gray-50',
};

export default function LoanIntelligence() {
  const { loanId }    = useParams();
  const navigate      = useNavigate();
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/officer/loan-intelligence/${loanId}`)
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [loanId]);

  if (loading) return <LoadingSpinner />;
  if (!data)   return <div className="text-red-500 p-6">Loan not found.</div>;

  const { loan, customer, analytics, sentiment, interactions,
          payment_history, llm_recommendation, policy_validation,
          grace_history, restructure_history } = data;

  const chartData = [...(payment_history || [])].reverse().map(p => ({
    month: p.payment_date?.slice(0, 7),
    paid:  p.payment_amount,
    emi:   loan.emi_amount,
  }));

  const scoreColor = analytics.delinquency_score >= 70 ? 'text-red-600'
    : analytics.delinquency_score >= 40 ? 'text-yellow-600' : 'text-green-600';

  return (
    <div className="space-y-6">
      {/* Back */}
      <button onClick={() => navigate('/officer/search')}
        className="flex items-center gap-2 text-blue-600 hover:text-blue-800 text-sm font-medium">
        ← Back to Search
      </button>

      {/* Header */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-600 rounded-2xl p-6 text-white">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold">Loan Intelligence Panel</h1>
            <p className="text-slate-300 text-sm mt-1">{loan.loan_id} • {loan.loan_type}</p>
          </div>
          <span className={`px-4 py-1.5 rounded-full text-sm font-bold border ${riskColors[analytics.risk_segment]}`}>
            {analytics.risk_segment} Risk
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SBox label="Customer"       value={customer.customer_name} />
          <SBox label="Outstanding"    value={`₹${loan.outstanding_balance?.toLocaleString('en-IN')}`} />
          <SBox label="Days Past Due"  value={loan.days_past_due} />
          <SBox label="Credit Score"   value={customer.credit_score} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

        {/* Customer Details */}
        <div className="bg-white rounded-2xl shadow p-5">
          <h3 className="font-semibold text-gray-700 mb-3">👤 Customer Details</h3>
          <InfoRow label="Customer ID"  value={customer.customer_id} />
          <InfoRow label="Mobile"       value={customer.mobile_number} />
          <InfoRow label="Email"        value={customer.email_id} />
          <InfoRow label="Income"       value={`₹${customer.monthly_income?.toLocaleString('en-IN')}/mo`} />
          <InfoRow label="Pref. Channel" value={customer.preferred_channel} />
          <InfoRow label="Language"     value={customer.preferred_language} />
        </div>

        {/* Analytics */}
        <div className="bg-white rounded-2xl shadow p-5">
          <h3 className="font-semibold text-gray-700 mb-3">📊 Risk Analytics</h3>
          <div className="text-center mb-4">
            <p className={`text-4xl font-bold ${scoreColor}`}>{analytics.delinquency_score}</p>
            <p className="text-xs text-gray-400">Delinquency Score / 100</p>
            <div className="mt-2 w-full bg-gray-100 rounded-full h-2">
              <div
                className={`h-2 rounded-full ${analytics.delinquency_score >= 70 ? 'bg-red-500' : analytics.delinquency_score >= 40 ? 'bg-yellow-500' : 'bg-green-500'}`}
                style={{ width: `${analytics.delinquency_score}%` }}
              />
            </div>
          </div>
          <InfoRow label="Self Cure Prob"   value={`${((analytics.self_cure_probability || 0) * 100).toFixed(0)}%`} />
          <InfoRow label="Value at Risk"    value={`₹${analytics.value_at_risk?.toLocaleString('en-IN')}`} />
          <InfoRow label="Payment Trend"    value={analytics.payment_trend?.trend} />
          <InfoRow label="Missed Payments"  value={analytics.payment_trend?.missed_payments} />
          <InfoRow label="Rec. Channel"     value={analytics.recommended_channel} />
        </div>

        {/* Sentiment */}
        <div className="bg-white rounded-2xl shadow p-5">
          <h3 className="font-semibold text-gray-700 mb-3">💬 Sentiment Analysis</h3>
          <div className="text-center mb-4">
            <span className={`px-4 py-2 rounded-xl text-sm font-bold ${toneColors[sentiment.dominant_tonality] || 'bg-gray-50 text-gray-600'}`}>
              {sentiment.dominant_tonality}
            </span>
          </div>
          <InfoRow label="Avg Sentiment"  value={sentiment.average_sentiment} />
          <InfoRow label="Sentiment Trend" value={sentiment.sentiment_trend} />

          <h3 className="font-semibold text-gray-700 mt-4 mb-2">📞 Last Interactions</h3>
          <div className="space-y-2">
            {interactions.slice(0, 3).map((i, idx) => (
              <div key={idx} className="bg-gray-50 rounded-xl p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-gray-600">{i.interaction_type}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${toneColors[i.tonality_score] || 'bg-gray-100'}`}>
                    {i.tonality_score}
                  </span>
                </div>
                <p className="text-xs text-gray-600">{i.interaction_summary}</p>
                <p className="text-xs text-gray-400 mt-1">{i.interaction_time?.slice(0, 10)}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Payment Chart */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-4">📈 Payment Pattern</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${(v/1000).toFixed(0)}k`} />
              <Tooltip formatter={v => `₹${v?.toLocaleString('en-IN')}`} />
              <ReferenceLine y={loan.emi_amount} stroke="#3b82f6" strokeDasharray="4 4" label={{ value: 'EMI', fontSize: 11 }} />
              <Line type="monotone" dataKey="paid" stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} name="Amount Paid" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recovery Strategy + LLM Recommendation */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-3">🎯 Recovery Strategy</h2>
          <div className={`border rounded-xl p-4 mb-3 ${
            analytics.recovery_strategy?.priority === 'High'
              ? 'border-red-200 bg-red-50'
              : analytics.recovery_strategy?.priority === 'Medium'
              ? 'border-yellow-200 bg-yellow-50'
              : 'border-green-200 bg-green-50'
          }`}>
            <p className="font-semibold text-gray-800 text-sm">{analytics.recovery_strategy?.strategy}</p>
            <p className="text-sm text-gray-600 mt-1">{analytics.recovery_strategy?.action}</p>
            <div className="flex gap-2 mt-2">
              <Badge label={`Priority: ${analytics.recovery_strategy?.priority}`} />
              <Badge label={`Channel: ${analytics.recovery_strategy?.recommended_channel}`} />
            </div>
          </div>

          {/* NPV */}
          {analytics.npv_result && (
            <div className="bg-gray-50 rounded-xl p-3">
              <p className="text-xs font-semibold text-gray-500 mb-2">NPV Analysis</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-gray-400">Expected Recovery</span><p className="font-bold text-gray-800">₹{analytics.npv_result.expected_recovery?.toLocaleString('en-IN')}</p></div>
                <div><span className="text-gray-400">Collection Cost</span><p className="font-bold text-gray-800">₹{analytics.npv_result.collection_cost?.toLocaleString('en-IN')}</p></div>
                <div><span className="text-gray-400">NPV</span><p className="font-bold text-green-600">₹{analytics.npv_result.npv?.toLocaleString('en-IN')}</p></div>
                <div><span className="text-gray-400">Recovery Rate</span><p className="font-bold text-gray-800">{((analytics.npv_result.recovery_rate || 0) * 100).toFixed(0)}%</p></div>
              </div>
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-base font-semibold text-gray-800 mb-3">🧠 AI Recommendation</h2>
          <div className="bg-blue-50 border-l-4 border-blue-500 rounded-xl p-4 mb-3">
            <p className="text-sm text-gray-700 leading-relaxed">{llm_recommendation}</p>
          </div>

          {/* Policy Validation */}
          <div className={`rounded-xl p-3 border ${policy_validation.approved ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
            <p className="text-xs font-semibold mb-1">
              {policy_validation.approved ? '✅ Policy Validated' : '⚠️ Policy Violations'}
            </p>
            {policy_validation.violations?.map((v, i) => (
              <p key={i} className="text-xs text-red-600">• {v}</p>
            ))}
            {policy_validation.warnings?.map((w, i) => (
              <p key={i} className="text-xs text-yellow-600">• {w}</p>
            ))}
            <p className="text-xs text-gray-500 mt-1">{policy_validation.final_recommendation}</p>
          </div>
        </div>
      </div>

      {/* Request History */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <RequestHistory title="⏱ Grace Request History"       items={grace_history} />
        <RequestHistory title="🔄 Restructure Request History" items={restructure_history} />
      </div>
    </div>
  );
}

function RequestHistory({ title, items }) {
  const statusColors = {
    Approved: 'bg-green-100 text-green-700',
    Rejected: 'bg-red-100 text-red-700',
    Pending:  'bg-yellow-100 text-yellow-700',
  };
  return (
    <div className="bg-white rounded-2xl shadow p-5">
      <h3 className="font-semibold text-gray-700 mb-3">{title}</h3>
      {items?.length === 0 ? (
        <p className="text-xs text-gray-400">No requests found.</p>
      ) : (
        <div className="space-y-2">
          {items.map((item, i) => (
            <div key={i} className="bg-gray-50 rounded-xl p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-500">{item.request_date}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${statusColors[item.request_status] || 'bg-gray-100'}`}>
                  {item.request_status}
                </span>
              </div>
              {item.decision_comment && (
                <p className="text-xs text-gray-600">{item.decision_comment}</p>
              )}
              {item.approved_by && (
                <p className="text-xs text-gray-400 mt-1">By: {item.approved_by} on {item.decision_date}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SBox({ label, value }) {
  return (
    <div className="bg-white bg-opacity-10 rounded-xl p-3">
      <p className="text-slate-300 text-xs">{label}</p>
      <p className="text-white font-bold text-sm mt-0.5">{value}</p>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-xs font-semibold text-gray-700">{value}</span>
    </div>
  );
}

function Badge({ label }) {
  return <span className="text-xs px-2 py-0.5 bg-white rounded-full text-gray-600 border">{label}</span>;
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
    </div>
  );
}