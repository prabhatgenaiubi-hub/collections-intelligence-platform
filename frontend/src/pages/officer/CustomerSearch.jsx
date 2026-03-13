import { useState, useEffect } from 'react';
import api from '../../api';

const riskColors = {
  High:   'bg-red-100 text-red-700',
  Medium: 'bg-yellow-100 text-yellow-700',
  Low:    'bg-green-100 text-green-700',
};

export default function CustomerSearch() {
  const [filters, setFilters] = useState({
    loan_id: '', customer_id: '', name: '', loan_type: '', risk_segment: '',
  });
  const [results,   setResults]   = useState([]);
  const [loading,   setLoading]   = useState(false);
  const [searched,  setSearched]  = useState(false);
  const [error,     setError]     = useState('');
  const [loanModal, setLoanModal] = useState(null);

  // AND = multiple fields filled; OR = single field filled
  const filledCount = Object.values(filters).filter(v => v.trim() !== '').length;
  const searchMode  = filledCount > 1 ? 'AND' : 'OR';

  const handleSearch = async (e) => {
    e.preventDefault();
    setError('');

    const params = Object.fromEntries(
      Object.entries(filters).filter(([_, v]) => v.trim() !== '')
    );

    if (Object.keys(params).length === 0) {
      setError('Please enter at least one search filter.');
      return;
    }

    // Append the search mode so backend can use it (if supported),
    // and we also do client-side AND filtering when needed.
    setLoading(true);
    try {
      const r = await api.get('/officer/search', { params });
      let data = r.data.results || [];

      // If multiple fields → AND: keep only rows matching ALL filled fields
      if (filledCount > 1) {
        data = data.filter(row => {
          return Object.entries(params).every(([key, val]) => {
            const v = val.toLowerCase();
            switch (key) {
              case 'loan_id':       return row.loan_id?.toLowerCase().includes(v);
              case 'customer_id':   return row.customer_id?.toLowerCase().includes(v);
              case 'name':          return row.customer_name?.toLowerCase().includes(v);
              case 'loan_type':     return row.loan_type?.toLowerCase().includes(v);
              case 'risk_segment':  return row.risk_segment?.toLowerCase() === v;
              default:              return true;
            }
          });
        });
      }

      setResults(data);
      setSearched(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Search failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setFilters({ loan_id: '', customer_id: '', name: '', loan_type: '', risk_segment: '' });
    setResults([]);
    setSearched(false);
    setError('');
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">🔍 Customer Search</h1>

      {/* Search Form */}
      <div className="bg-white rounded-2xl shadow p-6">
        <p className="text-sm text-gray-500 mb-4">
          Fill <strong>one field</strong> → <span className="text-blue-600 font-semibold">OR</span> search &nbsp;|&nbsp;
          Fill <strong>multiple fields</strong> → <span className="text-green-600 font-semibold">AND</span> search
          {filledCount > 0 && (
            <span className={`ml-3 px-2 py-0.5 rounded-full text-xs font-bold ${filledCount > 1 ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
              Current: {searchMode}
            </span>
          )}
        </p>
        <form onSubmit={handleSearch}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <SearchInput label="Loan ID"       field="loan_id"      filters={filters} setFilters={setFilters} placeholder="e.g. LOAN001" />
            <SearchInput label="Customer ID"   field="customer_id"  filters={filters} setFilters={setFilters} placeholder="e.g. CUST001" />
            <SearchInput label="Customer Name" field="name"         filters={filters} setFilters={setFilters} placeholder="e.g. Arun" />
            <SearchInput label="Loan Type"     field="loan_type"    filters={filters} setFilters={setFilters} placeholder="e.g. Personal Loan" />
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Risk Segment</label>
              <select
                value={filters.risk_segment}
                onChange={e => setFilters(f => ({ ...f, risk_segment: e.target.value }))}
                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Segments</option>
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </select>
            </div>
          </div>

          {error && (
            <div className="mb-4 px-4 py-3 bg-red-50 text-red-700 border border-red-200 rounded-xl text-sm">
              ⚠️ {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-6 py-2.5 rounded-xl font-semibold text-sm"
            >
              {loading ? 'Searching...' : '🔍 Search'}
            </button>
            <button
              type="button"
              onClick={handleClear}
              className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-6 py-2.5 rounded-xl font-semibold text-sm"
            >
              Clear
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {searched && (
        <div className="bg-white rounded-2xl shadow">
          <div className="px-6 py-4 border-b flex items-center justify-between">
            <h2 className="font-semibold text-gray-800">Search Results</h2>
            <span className="text-sm text-gray-500">{results.length} result(s) found</span>
          </div>

          {results.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              No records found matching your search criteria.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    {['Loan ID', 'Customer ID', 'Name', 'Loan Type', 'Loan Amount', 'Outstanding', 'Risk', 'DPD', 'Rec. Channel', ''].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {results.map((row) => (
                    <tr key={row.loan_id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setLoanModal(row.loan_id)}
                          className="text-blue-600 font-semibold hover:underline"
                        >
                          {row.loan_id}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{row.customer_id}</td>
                      <td className="px-4 py-3 font-medium text-gray-800">{row.customer_name}</td>
                      <td className="px-4 py-3 text-gray-600">{row.loan_type}</td>
                      <td className="px-4 py-3 text-gray-700">₹{row.loan_amount?.toLocaleString('en-IN')}</td>
                      <td className="px-4 py-3 text-gray-700">₹{row.outstanding_balance?.toLocaleString('en-IN')}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${riskColors[row.risk_segment] || 'bg-gray-100 text-gray-500'}`}>
                          {row.risk_segment}
                        </span>
                      </td>
                      <td className={`px-4 py-3 font-semibold ${row.days_past_due > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {row.days_past_due}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{row.recommended_channel}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => setLoanModal(row.loan_id)}
                          className="bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1.5 rounded-xl font-medium"
                        >
                          View →
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Loan Detail Modal */}
      {loanModal && <LoanDetailModal loanId={loanModal} onClose={() => setLoanModal(null)} />}
    </div>
  );
}

function LoanDetailModal({ loanId, onClose }) {
  const [loan,    setLoan]    = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/officer/loan-intelligence/${loanId}`)
      .then(r => setLoan(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [loanId]);

  if (loading) return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-2xl p-8">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-blue-500 border-t-transparent mx-auto"></div>
      </div>
    </div>
  );

  const info = loan?.loan_info || {};
  const risk = info.risk_segment;
  const riskMap = { High: 'bg-red-100 text-red-700', Medium: 'bg-yellow-100 text-yellow-700', Low: 'bg-green-100 text-green-700' };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-gray-800">Loan Intelligence</h2>
            <span className="font-bold text-blue-600">{loanId}</span>
            {risk && <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${riskMap[risk] || 'bg-gray-100'}`}>{risk} Risk</span>}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-2xl leading-none">✕</button>
        </div>
        <div className="overflow-y-auto p-6 space-y-4">
          {!loan ? (
            <p className="text-gray-400 text-center">No data available.</p>
          ) : (
            <>
              <div className="bg-gray-50 rounded-xl p-4 grid grid-cols-2 md:grid-cols-3 gap-4">
                <MiniDetail label="Customer"      value={info.customer_name} />
                <MiniDetail label="Loan Type"     value={info.loan_type} />
                <MiniDetail label="Loan Amount"   value={`₹${info.loan_amount?.toLocaleString('en-IN')}`} />
                <MiniDetail label="Outstanding"   value={`₹${info.outstanding_balance?.toLocaleString('en-IN')}`} />
                <MiniDetail label="EMI Amount"    value={`₹${info.emi_amount?.toLocaleString('en-IN')}`} />
                <MiniDetail label="Days Past Due" value={info.days_past_due} highlight={info.days_past_due > 0} />
                <MiniDetail label="Interest Rate" value={`${info.interest_rate}%`} />
                <MiniDetail label="EMI Due Date"  value={info.emi_due_date} />
                <MiniDetail label="Loan Status"   value={info.loan_status} />
              </div>
              {loan.analytics && (
                <div className="bg-blue-50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-blue-700 mb-2 uppercase tracking-wide">Analytics</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <MiniDetail label="Self-Cure Prob."   value={`${(loan.analytics.self_cure_probability * 100).toFixed(0)}%`} />
                    <MiniDetail label="Recovery Strategy" value={loan.analytics.recovery_strategy} />
                    <MiniDetail label="Rec. Channel"      value={loan.analytics.recommended_channel} />
                  </div>
                </div>
              )}
              {loan.recommendation && (
                <div className="bg-green-50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-green-700 mb-1 uppercase tracking-wide">AI Recommendation</p>
                  <p className="text-sm text-gray-700">{loan.recommendation}</p>
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

function SearchInput({ label, field, filters, setFilters, placeholder }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        type="text"
        value={filters[field]}
        onChange={e => setFilters(f => ({ ...f, [field]: e.target.value }))}
        placeholder={placeholder}
        className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  );
}