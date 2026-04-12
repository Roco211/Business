import './Loading.css';

interface LoadingProps {
  text?: string;
}

export default function Loading({ text = '加载中' }: LoadingProps) {
  return (
    <div className="loading-container">
      <span>{text}</span>
      <div className="loading-spinner" />
    </div>
  );
}
