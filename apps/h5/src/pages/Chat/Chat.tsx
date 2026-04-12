import { useState, useRef, useEffect, useCallback } from 'react';
import { chatApi } from '../../api/chat';
import './Chat.css';

interface Message {
  role: 'user' | 'assistant';
  text: string;
  roleName?: string;
  roleColor?: string;
  streaming?: boolean;
}

const ROLES: Record<string, { name: string; color: string }> = {
  xiaoya: { name: '小雅', color: '#ff9500' },
  data: { name: '营业数据员', color: '#3370ff' },
  sales: { name: '销售分析员', color: '#e91e63' },
  stock: { name: '库存守护员', color: '#00b96b' },
  ai: { name: 'AI参谋', color: '#9c27b0' },
};

const quickActions = [
  { label: '查营业额', text: '今天营业额怎么样？' },
  { label: '热销排行', text: '哪些商品卖得最好？' },
  { label: '库存预警', text: '有没有库存预警？' },
  { label: '进货建议', text: '给我一些进货建议' },
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', text: '你好！我是小雅，你的AI经营助手。\n\n我可以帮你查营业额、看热销排行、管库存、给进货建议。\n直接问我就好，我会安排对应的专业同事来回答你。' },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  };

  const detectRole = (intent: string) => {
    if (intent.includes('stock_in') || intent.includes('stock_out') || intent.includes('stock_query') || intent.includes('correction')) return ROLES.stock;
    if (intent.includes('list_items') || intent.includes('low_stock')) return ROLES.stock;
    if (intent.includes('item_create')) return ROLES.data;
    return ROLES.xiaoya;
  };

  const handleSend = useCallback((text?: string) => {
    const msg = text || input.trim();
    if (!msg || sending) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: msg }, { role: 'assistant', text: '', streaming: true }]);
    setSending(true);

    const abort = chatApi.streamMessage(
      msg,
      // onToken - 流式追加文字
      (token) => {
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'assistant' && last.streaming) {
            updated[updated.length - 1] = { ...last, text: last.text + token };
          }
          return updated;
        });
      },
      // onDone - 流式结束
      (data) => {
        const role = detectRole(data.intent || '');
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              streaming: false,
              roleName: role.name,
              roleColor: role.color,
              text: last.text || '操作完成',
            };
          }
          return updated;
        });
        setSending(false);
      },
      // onError
      (err) => {
        console.error('Stream error:', err);
        setMessages(prev => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last && last.role === 'assistant' && last.streaming) {
            updated[updated.length - 1] = { ...last, text: last.text || '网络错误，请重试', streaming: false };
          }
          return updated;
        });
        setSending(false);
      }
    );
    abortRef.current = abort;
  }, [input, sending]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-header">
        <div className="chat-title">
          <div className="chat-name">小雅 · AI经营助手</div>
          <div className="chat-sub">内容由 AI 生成</div>
        </div>
      </div>

      <div className="chat-body" ref={bodyRef}>
        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role === 'assistant' && msg.roleName && msg.roleName !== '小雅' && !msg.streaming && (
              <div className="chat-emp-tag">
                <span className="dot" style={{ background: msg.roleColor }} />
                {msg.roleName}
              </div>
            )}
            <div className={`chat-msg ${msg.role === 'user' ? 'self' : ''}`}>
              <div className="chat-bubble">
                {msg.text || (msg.streaming ? '' : '')}
                {msg.streaming && <span className="stream-cursor" />}
              </div>
            </div>
            {msg.role === 'assistant' && !msg.streaming && msg.text && (
              <div className="chat-actions">
                <button className="chat-act-btn" onClick={() => navigator.clipboard.writeText(msg.text)} title="复制">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4a90e2" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" /></svg>
                </button>
                <button className="chat-act-btn" title="朗读">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4a90e2" strokeWidth="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" /><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07" /></svg>
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="chat-func-bar">
        {quickActions.map((action) => (
          <div key={action.label} className="chat-func-chip" onClick={() => handleSend(action.text)}>
            {action.label}
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><polyline points="9 18 15 12 9 6" /></svg>
          </div>
        ))}
      </div>

      <div className="chat-bar">
        <div className="chat-input-wrap">
          <input
            className="chat-input"
            type="text"
            placeholder="发消息..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={500}
            disabled={sending}
          />
        </div>
        <button className="chat-send-btn" onClick={() => handleSend()} disabled={sending || !input.trim()}>
          {sending ? '生成中' : '发送'}
        </button>
      </div>
    </div>
  );
}
