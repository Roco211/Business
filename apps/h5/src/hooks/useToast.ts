import { useState, useCallback } from 'react';

interface ToastState {
  visible: boolean;
  message: string;
  type: 'success' | 'error';
}

export function useToast() {
  const [toast, setToast] = useState<ToastState>({ visible: false, message: '', type: 'success' });

  const showToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    setToast({ visible: true, message, type });
    setTimeout(() => setToast((t) => ({ ...t, visible: false })), 2500);
  }, []);

  return { toast, showToast };
}
