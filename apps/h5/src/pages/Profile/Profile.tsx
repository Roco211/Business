import { useNavigate } from 'react-router-dom';
import { authStore } from '../../store/auth';
import { authApi } from '../../api/auth';
import './Profile.css';

export default function Profile() {
  const navigate = useNavigate();
  const user = authStore.getUser();

  const handleLogout = async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    authStore.clear();
    navigate('/login', { replace: true });
  };

  return (
    <div className="profile-page">
      <div className="profile-header">
        <div className="profile-avatar">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
        </div>
        <div className="profile-info">
          <div className="profile-name">{user?.nickname || user?.username || '用户'}</div>
          <div className="profile-id">ID: {user?.username || '-'}</div>
        </div>
      </div>

      <div className="profile-menu">
        <div className="profile-menu-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4d6bfe" strokeWidth="2"><rect x="1" y="3" width="15" height="13" rx="2" /><path d="M16 8h4l3 3v5a1 1 0 01-1 1h-1M7 18a2 2 0 104 0M17 18a2 2 0 104 0" /></svg>
          <span>店铺设置</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
        </div>
        <div className="profile-menu-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00b96b" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
          <span>数据导出</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
        </div>
        <div className="profile-menu-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9c27b0" strokeWidth="2"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9" /></svg>
          <span>系统设置</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
        </div>
        <div className="profile-menu-item">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ff9500" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>
          <span>关于我们</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
        </div>
      </div>

      <button className="profile-logout" onClick={handleLogout}>退出登录</button>
    </div>
  );
}
