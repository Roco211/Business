import './Toast.css';

interface ToastProps {
  visible: boolean;
  message: string;
  type: 'success' | 'error';
}

export default function Toast({ visible, message, type }: ToastProps) {
  if (!visible) return null;
  return (
    <div className={`toast ${type} ${visible ? 'show' : ''}`}>
      {message}
    </div>
  );
}
