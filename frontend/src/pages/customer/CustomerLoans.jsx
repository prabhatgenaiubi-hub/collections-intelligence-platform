import { useEffect, useState } from 'react';
import api from '../../api';
import LoanChat from '../../components/LoanChat';

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

export default function CustomerLoans() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState({});
  const [message, setMessage] = useState('');
  const [selectedLoan, setSelectedLoan] = useState(null); // for modal
  const [chatLoan,     setChatLoan]     = useState(null); // for inline loan chat

  useEffect(() => {
    api.get('/customer/loans')
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const submitRequest = async (loanId, type) => {
    setSubmitting(s => ({ ...s, [loanId + type]: true }));
    setMessage('');
    try {
      const endpoint = type === 'grace' ? '/grace/request' : '/restructure/request';
      await api.post(endpoint, { loan_id: loanId });
      setMessage(`✅ ${type === 'grace' ? 'Grace' : 'Restructure'} request submitted successfully!`);
      // Refresh
      const r = await api.get('/customer/loans');
      setData(r.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'object' ? detail.message : detail;
      setMessage(`❌ ${msg || 'Request failed.'}`);
    } finally {
      setSubmitting(s => ({ ...s, [loanId + type]: false }));
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Your Loans</h1>
        <span className="text-sm text-gray-500">{data?.total || 0} loan(s)</span>
      </div>

      {message && (
        <div className={`px-4 py-3 rounded-xl text-sm font-medium ${
          message.startsWith('✅') ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message}
        </div>
      )}

      {data?.loans?.length === 0 && (
        <div className="bg-white rounded-2xl shadow p-8 text-center text-gray-400">
          No loans found.
        </div>
      )}

      <div className="space-y-4">
        {data?.loans?.map((loan) => (
          <div key={loan.loan_id} className="bg-white rounded-2xl shadow hover:shadow-md transition-shadow">
            <div className="p-5">
              {/* Top row */}
              <div className="flex items-start justify-between mb-4">
                <div>
                  <button
                    onClick={() => setSelectedLoan(loan)}
                    className="text-blue-600 font-bold text-lg hover:underline"
                  >
                    {loan.loan_id}
                  </button>
                  <span className="ml-3 text-sm text-gray-500">{loan.loan_type}</span>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${riskBadge(loan.risk_segment)}`}>
                  {loan.risk_segment} Risk
                </span>
              </div>

              {/* Details grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <Detail label="Outstanding"   value={`₹${loan.outstanding_balance?.toLocaleString('en-IN')}`} />
                <Detail label="EMI Amount"    value={`₹${loan.emi_amount?.toLocaleString('en-IN')}`} />
                <Detail label="Next EMI Due"  value={loan.emi_due_date} />
                <Detail label="Days Past Due" value={loan.days_past_due} highlight={loan.days_past_due > 0} />
              </div>

              {/* Status + Actions */}
              <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-gray-100">
                <StatusPill label="Grace"       status={loan.grace_status} />
                <StatusPill label="Restructure" status={loan.restructure_status} />

                <div className="ml-auto flex gap-2">
                  <button
                    onClick={() => submitRequest(loan.loan_id, 'grace')}
                    disabled={submitting[loan.loan_id + 'grace'] || loan.grace_status === 'Pending'}
                    className="px-4 py-2 bg-yellow-500 hover:bg-yellow-600 disabled:bg-gray-300 text-white text-xs font-semibold rounded-xl transition-colors"
                  >
                    {submitting[loan.loan_id + 'grace'] ? '...' : '⏱ Grace Request'}
                  </button>
                  <button
                    onClick={() => submitRequest(loan.loan_id, 'restructure')}
                    disabled={submitting[loan.loan_id + 'restructure'] || loan.restructure_status === 'Pending'}
                    className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white text-xs font-semibold rounded-xl transition-colors"
                  >
                    {submitting[loan.loan_id + 'restructure'] ? '...' : '🔄 Restructure'}
                  </button>
                  <button
                    onClick={() => setSelectedLoan(loan)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl transition-colors"
                  >
                    View Details →
                  </button>
                  <button
                    onClick={() => setChatLoan(loan)}
                    className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded-xl transition-colors"
                  >
                    💬 Chat
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Loan Detail Modal */}
      {selectedLoan && (
        <LoanDetailModal loan={selectedLoan} onClose={() => setSelectedLoan(null)} />
      )}

      {/* Loan-scoped AI Chat slide-over */}
      {chatLoan && (
        <LoanChat loan={chatLoan} onClose={() => setChatLoan(null)} />
      )}
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

function LoanDetailModal({ loan, onClose }) {
  const [payments, setPayments] = useState([]);
  const [loadingPay, setLoadingPay] = useState(true);

  useEffect(() => {
    api.get(`/customer/loans/${loan.loan_id}/payments`)
      .then(r => setPayments(r.data.payments || []))
      .catch(console.error)
      .finally(() => setLoadingPay(false));
  }, [loan.loan_id]);

  const riskMap = {
    High:   'bg-red-100 text-red-700',
    Medium: 'bg-yellow-100 text-yellow-700',
    Low:    'bg-green-100 text-green-700',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-gray-800">Loan Details</h2>
            <span className="font-bold text-blue-600">{loan.loan_id}</span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${riskMap[loan.risk_segment] || 'bg-gray-100 text-gray-500'}`}>
              {loan.risk_segment} Risk
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">✕</button>
        </div>

        {/* Scrollable Body */}
        <div className="overflow-y-auto p-6 space-y-6">
          {/* Loan Summary */}
          <div className="bg-gray-50 rounded-xl p-4">
            <p className="text-xs text-gray-500 mb-3 font-semibold uppercase tracking-wide">Loan Summary</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Detail label="Loan Type"      value={loan.loan_type} />
              <Detail label="Loan Amount"    value={`₹${loan.loan_amount?.toLocaleString('en-IN')}`} />
              <Detail label="Outstanding"    value={`₹${loan.outstanding_balance?.toLocaleString('en-IN')}`} />
              <Detail label="EMI Amount"     value={`₹${loan.emi_amount?.toLocaleString('en-IN')}`} />
              <Detail label="Next EMI Due"   value={loan.emi_due_date} />
              <Detail label="Days Past Due"  value={loan.days_past_due} highlight={loan.days_past_due > 0} />
              <Detail label="Interest Rate"  value={`${loan.interest_rate}%`} />
              <Detail label="Loan Status"    value={loan.loan_status} />
            </div>
          </div>

          {/* Status Pills */}
          <div className="flex flex-wrap gap-2">
            <StatusPill label="Grace"       status={loan.grace_status} />
            <StatusPill label="Restructure" status={loan.restructure_status} />
          </div>

          {/* Payment History */}
          <div>
            <p className="text-xs text-gray-500 mb-3 font-semibold uppercase tracking-wide">Payment History</p>
            {loadingPay ? (
              <div className="flex justify-center py-6">
                <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent"></div>
              </div>
            ) : payments.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">No payment records found.</p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-gray-100">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      {['Date', 'Amount', 'Status', 'Method', 'Late Fees'].map(h => (
                        <th key={h} className="px-4 py-2 text-left text-xs font-semibold text-gray-500">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {payments.map((p, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-600">{p.payment_date}</td>
                        <td className="px-4 py-2 font-semibold text-gray-800">₹{p.payment_amount?.toLocaleString('en-IN')}</td>
                        <td className="px-4 py-2">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                            p.payment_status === 'On Time' ? 'bg-green-100 text-green-700'
                            : p.payment_status === 'Late' ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-500'
                          }`}>{p.payment_status}</span>
                        </td>
                        <td className="px-4 py-2 text-gray-600">{p.payment_method || '—'}</td>
                        <td className="px-4 py-2 text-gray-600">₹{p.late_fee?.toLocaleString('en-IN') || '0'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-sm font-semibold"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}