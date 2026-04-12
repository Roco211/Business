import { API_BASE } from './client';
import type { ChatResponse } from '../types';

export const chatApi = {
  // SSE流式聊天（主要调用方式）
  streamMessage(
    message: string,
    onToken: (token: string) => void,
    onDone: (data: ChatResponse) => void,
    onError: (error: Error) => void
  ): () => void {
    const token = localStorage.getItem('authToken');
    const url = `${API_BASE}/chat/stream?token=${token || ''}`;
    const controller = new AbortController();

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: 'default' }),
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.body) throw new Error('No response body');
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'token') {
                  onToken(data.content);
                } else if (data.type === 'done') {
                  onDone(data as ChatResponse);
                }
              } catch {
                // ignore parse errors
              }
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError(err);
        }
      });

    return () => controller.abort();
  },
};
