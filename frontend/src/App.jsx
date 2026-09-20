import { t } from "./i18n";
import { lazy, Suspense, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import DashboardLayout from './pages/DashboardLayout';
import DashboardHome from './pages/DashboardHome';
import UserManagement from './pages/UserManagement';
import NodeManagement from './pages/NodeManagement';
import AdminManagement from './pages/AdminManagement';
import ResellerNodes from './pages/ResellerNodes';
import MonitoringSettings from './pages/MonitoringSettings';
import FleetManagement from './pages/FleetManagement';
const SecuritySettings = lazy(() => import('./pages/SecuritySettings'));
import OperationsCenter from './pages/OperationsCenter';
import BandwidthControl from './pages/BandwidthControl';
import favicon from './assets/fav.webp';
function App() {
  const {
    isAuthenticated,
    userRole
  } = useAuth();
  useEffect(() => {
    const link = document.createElement('link');
    link.rel = 'icon';
    link.type = 'image/webp';
    link.href = favicon;
    document.head.appendChild(link);
    return () => {
      document.head.removeChild(link);
    };
  }, []);
  return <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" /> : <LoginPage />} />
      <Route path="/" element={isAuthenticated ? <DashboardLayout /> : <Navigate to="/login" />}>
        <Route index element={<DashboardHome />} />
        <Route path="users" element={<UserManagement />} />
        {userRole !== 'admin' && <Route path="nodes" element={<NodeManagement />} />}
        {userRole === 'admin' && <Route path="nodes" element={<ResellerNodes />} />}
        {userRole === 'main_admin' && <Route path="admins" element={<AdminManagement />} />}
        {userRole === 'main_admin' && <Route path="monitoring" element={<MonitoringSettings />} />}
        {userRole === 'main_admin' && <Route path="fleet" element={<FleetManagement />} />}
        {userRole === 'main_admin' && <Route path="security" element={<Suspense fallback={<div className="ov-page-loader">Loading...</div>}><SecuritySettings /></Suspense>} />}
        {userRole === 'main_admin' && <Route path="operations" element={<OperationsCenter />} />}
        {userRole === 'main_admin' && <Route path="bandwidth" element={<BandwidthControl />} />}
      </Route>
      <Route path="*" element={<Navigate to={isAuthenticated ? "/" : t("ui.c42c80aa0611")} />} />
    </Routes>;
}
export default App;
