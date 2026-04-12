import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import './BottomNav.css';

const tabs = [
  { path: '/', label: '首页', icon: 'home' },
  { path: '/products', label: '商品', icon: 'box' },
  { path: '/chat', label: '', icon: 'center', isCenter: true },
  { path: '/chat', label: 'AI助手', icon: 'robot' },
  { path: '/profile', label: '我的', icon: 'user' },
];

const icons: Record<string, React.ReactElement> = {
  home: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  ),
  box: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  ),
  robot: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="10" rx="2" />
      <circle cx="12" cy="5" r="2" />
      <path d="M12 7v4" />
      <line x1="8" y1="16" x2="8" y2="16" />
      <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
  ),
  user: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
};

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();

  // 登录页不显示底部导航
  if (location.pathname === '/login') return null;

  return (
    <nav className="bottom-nav">
      {tabs.map((tab, i) => {
        if (tab.isCenter) {
          return (
            <div key="center" className="nav-center" onClick={() => navigate(tab.path)}>
              <span className="nav-center-inner">+</span>
            </div>
          );
        }
        const active = location.pathname === tab.path;
        return (
          <div
            key={i}
            className={`nav-item ${active ? 'active' : ''}`}
            onClick={() => navigate(tab.path)}
          >
            <div className="nav-icon">{icons[tab.icon]}</div>
            <div className="nav-label">{tab.label}</div>
          </div>
        );
      })}
    </nav>
  );
}
