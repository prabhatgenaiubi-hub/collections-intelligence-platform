import { useEffect, useState } from 'react';
import api from '../../api';

const statusColors = {
  Approved: 'bg-green-100 text-green-700 border-green-200',
  Rejected: 'bg-red-100 text-red-700 border-red-200',
  Pending:  'bg-yellow-100 text-yellow-700 border-yellow-200',
};

export default function RestructureManagement() {
  const [allRequests, setAllRequests] = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [filter,     setFilter]     = useState('Pending');
  const [deciding,   setDeciding]   = useState({});
  const [comments,   setComments]   = useState({});
  const [message,    setMessage]    = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [loanModal,  setLoanModal]  = useState(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const r = await api.get('/restructure/all');
      setAllRequests(r.data.requests || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  // Client-side filter
  const requests = filter === 'All'
    ? allRequests
    : allRequests.filter(r => r.request_status === filter);

  const handleDecide = async (requestId, decision) => {
    const comment = comments[requestId]?.trim();
    if (!comment) {
      setMessage('❌ Please enter a decision comment before submitting.');
      return;
    }
    setDeciding(d => ({ ...d, [requestId]: true }));
    setMessage('');
    try {
      await api.post(`/restructure/${requestId}/decide`, {
        decision,
        decision_comment: comment,
      });
      setMessage(`✅ Restructure request ${decision} successfully.`);
      setComments(c => ({ ...c, [requestId]: '' }));
      setExpandedId(null);
      loadAll();
    } catch (err) {
      setMessage(`❌ ${err.response?.data?.detail || 'Decision failed.'}`);
    } finally {
      setDeciding(d => ({ ...d, [requestId]: false }));
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">🔄 Restructure Request Management</h1>
          <p className="text-sm text-gray-500 mt-1">Review and decide on loan restructuring requests</p>
        </div>
        <div className="flex gap-2">
          {['Pending', 'Approved', 'Rejected', 'All'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                filter === f
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {message && (
        <div className={`px-4 py-3 rounded-xl text-sm font-medium ${
          message.startsWith('✅')
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message}
        </div>
      )}

      {loading ? (
        <LoadingSpinner />
      ) : requests.length === 0 ? (
        <div className="bg-white rounded-2xl shadow p-10 text-center text-gray-400">
          <p className="text-4xl mb-3">📭</p>
          <p className="font-medium">No {filter.toLowerCase()} restructure requests found.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {requests.map((req) => (
            <div key={req.request_id} className="bg-white rounded-2xl shadow overflow-hidden">
              {/* Request Header */}
              <div
                className="p-5 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => setExpandedId(expandedId === req.request_id ? null : req.request_id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); setLoanModal(req.loan_id); }}
                          className="font-bold text-blue-600 hover:underline"
                        >
                          {req.loan_id}
                        </button>
                        <span className="text-gray-400">•</span>
                        <span className="text-sm text-gray-600">{req.loan_type}</span>
                      </div>
                      <p className="text-sm font-semibold text-gray-800 mt-0.5">{req.customer_name}</p>
                      <p className="text-xs text-gray-400">Requested: {req.request_date}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="text-right text-sm">
                      <p className="text-gray-400 text-xs">Outstanding</p>
                      <p className="font-bold text-gray-800">₹{req.outstanding?.toLocaleString('en-IN')}</p>
                    </div>
                    <div className="text-right text-sm">
                      <p className="text-gray-400 text-xs">Loan Amount</p>
                      <p className="font-bold text-gray-700">₹{req.loan_amount?.toLocaleString('en-IN')}</p>
                    </div>
                    <div className="text-right text-sm">
                      <p className="text-gray-400 text-xs">DPD</p>
                      <p className={`font-bold ${req.days_past_due > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {req.days_past_due}
                      </p>
                    </div>
                    <div className="text-right text-sm">
                      <p className="text-gray-400 text-xs">Risk</p>
                      <p className={`font-bold text-xs ${
                        req.risk_segment === 'High' ? 'text-red-600'
                        : req.risk_segment === 'Medium' ? 'text-yellow-600'
                        : 'text-green-600'
                      }`}>{req.risk_segment}</p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${statusColors[req.request_status]}`}>
                      {req.request_status}
                    </span>
                    <span className="text-gray-400 text-sm">
                      {expandedId === req.request_id ? '▲' : '▼'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Expanded Panel */}
              {expandedId === req.request_id && (
                <div className="border-t border-gray-100 p-5 bg-gray-50">
                  {/* Details */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
                    <Detail label="Customer ID"  value={req.customer_id} />
                    <Detail label="EMI Amount"   value={`₹${req.emi_amount?.toLocaleString('en-IN')}`} />
                    <Detail label="EMI Due Date" value={req.emi_due_date} />
                    <Detail label="Request ID"   value={req.request_id} />
                  </div>

                  {/* Restructure options info box */}
                  {req.request_status === 'Pending' && (
                    <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-800">
                      <p className="font-semibold mb-1">📋 Restructuring Options to Consider:</p>
                      <ul className="list-disc list-inside space-y-0.5 text-xs">
                        <li>Extend loan tenure by 12–24 months</li>
                        <li>Reduce EMI through interest rate adjustment</li>
                        <li>Partial payment deferral for 1–3 months</li>
                        <li>Step-up repayment plan based on income</li>
                      </ul>
                    </div>
                  )}

                  {/* Existing decision */}
                  {req.decision_comment && (
                    <div className={`mb-4 p-3 rounded-xl border text-sm ${statusColors[req.request_status]}`}>
                      <strong>Decision Comment:</strong> {req.decision_comment}
                      {req.approved_by && (
                        <p className="text-xs mt-1 opacity-70">
                          By {req.approved_by} on {req.decision_date}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Decision Panel — only for Pending */}
                  {req.request_status === 'Pending' && (
                    <div className="bg-white rounded-xl p-4 border border-gray-200">
                      <h3 className="text-sm font-semibold text-gray-700 mb-3">Make Decision</h3>
                      <textarea
                        rows={3}
                        value={comments[req.request_id] || ''}
                        onChange={e => setComments(c => ({ ...c, [req.request_id]: e.target.value }))}
                        placeholder="Enter restructure decision details (e.g. Tenure extended by 18 months, new EMI ₹8,500)..."
                        className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none mb-3"
                      />
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleDecide(req.request_id, 'Approved')}
                          disabled={deciding[req.request_id]}
                          className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white font-semibold py-2.5 rounded-xl text-sm transition-colors"
                        >
                          {deciding[req.request_id] ? 'Processing...' : '✅ Approve Restructure'}
                        </button>
                        <button
                          onClick={() => handleDecide(req.request_id, 'Rejected')}
                          disabled={deciding[req.request_id]}
                          className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-gray-300 text-white font-semibold py-2.5 rounded-xl text-sm transition-colors"
                        >
                          {deciding[req.request_id] ? 'Processing...' : '❌ Reject'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Loan Detail Modal */}
      {loanModal && <LoanDetailModal loanId={loanModal} onClose={() => setLoanModal(null)} />}
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div className="bg-white rounded-xl p-3">
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm font-semibold text-gray-800 mt-0.5">{value ?? '—'}</p>
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

function LoanDetailModal({ loanId, onClose }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  useEffect(() => {
    api.get(`/officer/loan-intelligence/${loanId}`)
      .then(r => setData(r.data))
      .catch(err => {
        console.error(err);
        setError(err.response?.data?.detail || 'Failed to load loan details.');
      })
      .finally(() => setLoading(false));
  }, [loanId]);

  const riskMap = { High: 'bg-red-100 text-red-700', Medium: 'bg-yellow-100 text-yellow-700', Low: 'bg-green-100 text-green-700' };

  const loan      = data?.loan || {};
  const customer  = data?.customer || {};
  const analytics = data?.analytics || {};
  const risk      = analytics.risk_segment;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-gray-800">Loan Details</h2>
            <span className="font-bold text-blue-600">{loanId}</span>
            {risk && <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${riskMap[risk] || 'bg-gray-100'}`}>{risk} Risk</span>}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">✕</button>
        </div>
        <div className="overflow-y-auto p-6 space-y-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <div className="animate-spin rounded-full h-10 w-10 border-4 border-blue-500 border-t-transparent"></div>
            </div>
          ) : error ? (
            <p className="text-red-500 text-center py-4">⚠️ {error}</p>
          ) : !data ? (
            <p className="text-gray-400 text-center">No data available.</p>
          ) : (
            <>
              <div className="bg-gray-50 rounded-xl p-4 grid grid-cols-2 md:grid-cols-3 gap-4">
                <MiniDetail label="Customer"      value={customer.customer_name} />
                <MiniDetail label="Loan Type"     value={loan.loan_type} />
                <MiniDetail label="Loan Amount"   value={loan.loan_amount != null ? `₹${loan.loan_amount.toLocaleString('en-IN')}` : '—'} />
                <MiniDetail label="Outstanding"   value={loan.outstanding_balance != null ? `₹${loan.outstanding_balance.toLocaleString('en-IN')}` : '—'} />
                <MiniDetail label="EMI Amount"    value={loan.emi_amount != null ? `₹${loan.emi_amount.toLocaleString('en-IN')}` : '—'} />
                <MiniDetail label="Days Past Due" value={loan.days_past_due} highlight={(loan.days_past_due ?? 0) > 0} />
                <MiniDetail label="Interest Rate" value={loan.interest_rate != null ? `${loan.interest_rate}%` : '—'} />
                <MiniDetail label="EMI Due Date"  value={loan.emi_due_date} />
                <MiniDetail label="Credit Score"  value={customer.credit_score} />
              </div>
              {data.analytics && (
                <div className="bg-purple-50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-purple-700 mb-2 uppercase tracking-wide">Analytics</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <MiniDetail
                      label="Self-Cure Prob."
                      value={analytics.self_cure_probability != null ? `${(analytics.self_cure_probability * 100).toFixed(0)}%` : '—'}
                    />
                    <MiniDetail label="Recovery Strategy" value={analytics.recovery_strategy?.strategy ?? analytics.recovery_strategy ?? '—'} />
                    <MiniDetail label="Rec. Channel"      value={analytics.recommended_channel} />
                  </div>
                </div>
              )}
              {data.llm_recommendation && (
                <div className="bg-green-50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-green-700 mb-1 uppercase tracking-wide">AI Recommendation</p>
                  <p className="text-sm text-gray-700 whitespace-pre-line">{data.llm_recommendation}</p>
                </div>
              )}
            </>
          )}
        </div>
        <div className="px-6 py-4 border-t flex justify-end">
          <button onClick={onClose} className="px-5 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-sm font-semibold">Close</button>
        </div>
      </div>
    </div>
  );
}

function MiniDetail({ label, value, highlight }) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`text-sm font-semibold ${highlight ? 'text-red-600' : 'text-gray-800'}`}>{value ?? '—'}</p>
    </div>
  );
}