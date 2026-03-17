import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import CustomerLayout from './pages/customer/CustomerLayout';
import CustomerDashboard from './pages/customer/CustomerDashboard';
import CustomerLoans from './pages/customer/CustomerLoans';
import LoanDetail from './pages/customer/LoanDetail';
import Preferences from './pages/customer/Preferences';
import OfficerLayout from './pages/officer/OfficerLayout';
import OfficerDashboard from './pages/officer/OfficerDashboard';
import CustomerSearch from './pages/officer/CustomerSearch';
import LoanIntelligence from './pages/officer/LoanIntelligence';
import GraceManagement from './pages/officer/GraceManagement';
import RestructureManagement from './pages/officer/RestructureManagement';
import OfficerChat from './pages/officer/OfficerChat';
import SentimentAnalysis from './pages/officer/SentimentAnalysis';

// Auth guard
function PrivateRoute({ children, role }) {
  const token = localStorage.getItem('token');
  const userRole = localStorage.getItem('role');
  if (!token) return <Navigate to="/" replace />;
  if (role && userRole !== role) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/" element={<LoginPage />} />

        {/* Customer Portal */}
        <Route
          path="/customer"
          element={
            <PrivateRoute role="customer">
              <CustomerLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<CustomerDashboard />} />
          <Route path="loans" element={<CustomerLoans />} />
          <Route path="loans/:loanId" element={<LoanDetail />} />
          <Route path="preferences" element={<Preferences />} />
        </Route>

        {/* Officer Portal */}
        <Route
          path="/officer"
          element={
            <PrivateRoute role="officer">
              <OfficerLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<OfficerDashboard />} />
          <Route path="search" element={<CustomerSearch />} />
          <Route path="loan-intelligence" element={<LoanIntelligence />} />
          <Route path="loan-intelligence/:loanId" element={<LoanIntelligence />} />
          <Route path="grace" element={<GraceManagement />} />
          <Route path="restructure" element={<RestructureManagement />} />
          <Route path="chat" element={<OfficerChat />} />
          <Route path="sentiment" element={<SentimentAnalysis />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}