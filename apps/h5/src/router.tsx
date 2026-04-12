import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login/Login';
import Home from './pages/Home/Home';
import Products from './pages/Products/Products';
import Chat from './pages/Chat/Chat';
import Profile from './pages/Profile/Profile';
import BottomNav from './components/BottomNav';
import { authStore } from './store/auth';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!authStore.isLoggedIn()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
        <Route path="/products" element={<ProtectedRoute><Products /></ProtectedRoute>} />
        <Route path="/chat" element={<ProtectedRoute><Chat /></ProtectedRoute>} />
        <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <BottomNav />
    </BrowserRouter>
  );
}
