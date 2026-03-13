import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../api';

const statusBadge = (status) => {
  const map = {
    Approved: 'bg-green-100 text-green-700',
    Rejected: 'bg-red-100 text-red-700',
    Pending:  'bg-yellow-100 text-yellow-700',
    None:     'bg-gray-100 text-gray-500',
  };
  return map[status] || map['None'];
};

const riskBadge = (risk) => {
  const map = {
    High:   'bg-red-100 text-red-700',
    Medium: 'bg-yellow-100 text-yellow-700',
    Low:    'bg-green-100 text-green-700',
  };
  return map[risk] || 'bg-gray-100 text-gray-500';
};

export default function LoanDetail() {
  const { loanId }   = useParams();
  const navigate     = useNavigate();
  const [loan,    setLoan]    = useState(null);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState({});
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!loanId) return;
    Promise.all([
      api.get(`/customer/loans/${loanId}`),
      api.get(`/customer/loans/${loanId}/payments`),
    ])
      .then(([loanRes, payRes]) => {
        setLoan(loanRes.data);
        setPayments(payRes.data.payments || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [loanId]);

  const submitRequest = async (type) => {
    setSubmitting(s => ({ ...s, [type]: true }));
    setMessage('');
    try {
      const endpoint = type === 'grace' ? '/grace/request' : '/restructure/request';
      await api.post(endpoint, { loan_id: loanId });
      setMessage(`✅ ${type === 'grace' ? 'Grace' : 'Restructure'} request submitted successfully!`);
      const loanRes = await api.get(`/customer/loans/${loanId}`);
      setLoan(loanRes.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.message : detail;
      setMessage(`❌ ${msg || 'Request failed.'}`);
    } finally {
      setSubmitting(s => ({ ...s, [type]: false }));
    }
  };

  if (loading) return <LoadingSpinner />;
  if (!loan) return (
    <div className="text-center py-20 text-gray-400">
      <p className="text-4xl mb-3">❌</p>
      <p>Loan not found.</p>
      <button onClick={() => navigate('/customer/loans')} className="mt-4 text-blue-600 underline text-sm">← Back to Loans</button>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Back + Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/customer/loans')}
          className="text-gray-400 hover:text-gray-700 text-sm font-medium"
        >
          ← Back
        </button>
        <h1 className="text-2xl font-bold text-gray-800">Loan Details: {loan.loan_id}</h1>
        <span className={`ml-2 px-3 py-1 rounded-full text-xs font-semibold ${riskBadge(loan.risk_segment)}`}>
          {loan.risk_segment} Risk
        </span>
      </div>

      {message && (
        <div className={`px-4 py-3 rounded-xl text-sm font-medium ${
          message.startsWith('✅') ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message}
        </div>
      )}

      {/* Loan summary card */}
      <div className="bg-white rounded-2xl shadow p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="font-bold text-blue-600 text-lg">{loan.loan_id}</span>
          <span className="text-gray-400">•</span>
          <span className="text-gray-600">{loan.loan_type}</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <Detail label="Loan Amount"     value={`₹${loan.loan_amount?.toLocaleString('en-IN')}`} />
          <Detail label="Outstanding"     value={`₹${loan.outstanding_balance?.toLocaleString('en-IN')}`} />
          <Detail label="EMI Amount"      value={`₹${loan.emi_amount?.toLocaleString('en-IN')}`} />
          <Detail label="Next EMI Due"    value={loan.emi_due_date} />
          <Detail label="Loan Start"      value={loan.loan_start_date} />
          <Detail label="Loan End"        value={loan.loan_end_date} />
          <Detail label="Days Past Due"   value={loan.days_past_due} highlight={loan.days_past_due > 0} />
          <Detail label="Interest Rate"   value={`${loan.interest_rate}%`} />
        </div>

        {/* Status pills */}
        <div className="flex flex-wrap items-center gap-3 mt-5 pt-4 border-t border-gray-100">
          <StatusPill label="Loan Status"  status={loan.loan_status} />
          <StatusPill label="Grace"        status={loan.grace_status} />
          <StatusPill label="Restructure"  status={loan.restructure_status} />
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <button
          onClick={() => submitRequest('grace')}
          disabled={submitting['grace'] || loan.grace_status === 'Pending'}
          className="px-5 py-2.5 bg-yellow-500 hover:bg-yellow-600 disabled:bg-gray-300 text-white text-sm font-semibold rounded-xl transition-colors"
        >
          {submitting['grace'] ? 'Submitting...' : '⏱ Request Grace Period'}
        </button>
        <button
          onClick={() => submitRequest('restructure')}
          disabled={submitting['restructure'] || loan.restructure_status === 'Pending'}
          className="px-5 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white text-sm font-semibold rounded-xl transition-colors"
        >
          {submitting['restructure'] ? 'Submitting...' : '🔄 Request Restructure'}
        </button>
      </div>

      {/* Payment History */}
      <div className="bg-white rounded-2xl shadow">
        <div className="px-6 py-4 border-b">
          <h2 className="font-semibold text-gray-800">📋 Payment History</h2>
        </div>
        {payments.length === 0 ? (
          <div className="p-8 text-center text-gray-400">No payment records found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {['Date', 'Amount', 'Status', 'Method', 'Late Fees'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {payments.map((p, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-600">{p.payment_date}</td>
                    <td className="px-4 py-3 font-semibold text-gray-800">₹{p.payment_amount?.toLocaleString('en-IN')}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        p.payment_status === 'On Time' ? 'bg-green-100 text-green-700'
                        : p.payment_status === 'Late' ? 'bg-red-100 text-red-700'
                        : 'bg-gray-100 text-gray-500'
                      }`}>
                        {p.payment_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{p.payment_method || '—'}</td>
                    <td className="px-4 py-3 text-gray-600">₹{p.late_fee?.toLocaleString('en-IN') || '0'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Detail({ label, value, highlight }) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`font-semibold text-sm ${highlight ? 'text-red-600' : 'text-gray-800'}`}>{value ?? '—'}</p>
    </div>
  );
}

function StatusPill({ label, status }) {
  const map = {
    Approved: 'bg-green-100 text-green-700',
    Rejected: 'bg-red-100 text-red-700',
    Pending:  'bg-yellow-100 text-yellow-700',
    None:     'bg-gray-100 text-gray-400',
    Active:   'bg-blue-100 text-blue-700',
  };
  return (
    <span className={`text-xs px-3 py-1 rounded-full font-medium ${map[status] || map['None']}`}>
      {label}: {status}
    </span>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
    </div>
  );
}