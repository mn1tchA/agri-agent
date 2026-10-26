import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

import { Header } from './components/Header';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { FarmsPage } from './pages/FarmsPage';
import { useAuthStore } from './store/useAuthStore';

function AppLayout() {
  return (
    <div className="min-h-screen p-4 md:p-8 overflow-x-hidden relative bg-slate-950 text-slate-100">
      <div className="max-w-7xl mx-auto relative z-10">
        <Header />
        <main className="animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function App() {
  const { initialize } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <BrowserRouter>
      <ToastContainer
        theme="dark"
        position="bottom-right"
        toastStyle={{
          backgroundColor: '#0f172a',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '12px',
          color: '#f1f5f9',
          fontFamily: 'Inter, sans-serif',
          fontSize: '13px',
        }}
      />
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        {/* Protected Application Routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/farms" element={<FarmsPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;