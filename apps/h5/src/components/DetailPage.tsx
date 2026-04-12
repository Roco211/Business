import { useEffect, type ReactNode } from 'react';
import './DetailPage.css';

interface DetailPageProps {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
}

export default function DetailPage({ open, title, subtitle, onClose, children }: DetailPageProps) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  return (
    <div className={`detail-page ${open ? 'open' : ''}`}>
      <div className="detail-header">
        <button className="detail-back" onClick={onClose}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <span className="detail-title">{title}</span>
        {subtitle && <span className="detail-subtitle">{subtitle}</span>}
      </div>
      <div className="detail-body">
        {children}
      </div>
    </div>
  );
}
