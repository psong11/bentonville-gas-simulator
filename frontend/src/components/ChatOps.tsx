/**
 * ChatOps Component
 * Claude-powered operations chat pinned above the dashboard. Streams SSE from
 * POST /api/agent; tool calls render as chips and highlight locations on the
 * map via onHighlight.
 */

import { useEffect, useRef, useState } from 'react';
import { Sparkles, Send, ChevronDown, Wrench } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface AgentHighlight {
  node_ids?: number[];
  pipe_ids?: number[];
}

interface ToolEvent {
  name: string;
  done: boolean;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  tools?: ToolEvent[];
}

interface ChatOpsProps {
  onHighlight: (h: AgentHighlight | null) => void;
}

const SUGGESTIONS = [
  'How does gas pressure look today, and where should we run quality tests?',
  'What natural hazards could affect this network?',
  'Place 8 sensors optimally — how much of the network do they cover?',
  'Simulate peak winter demand. Where does pressure get critical?',
];

const TOOL_LABELS: Record<string, string> = {
  get_network_status: 'Reading network status',
  list_inspection_candidates: 'Ranking inspection candidates',
  run_scenario: 'Running scenario',
  inject_leaks: 'Injecting test leaks',
  clear_leaks: 'Clearing leaks',
  place_sensors: 'Optimizing sensor placement',
  detect_leaks: 'Running leak detection',
  get_hazard_context: 'Checking hazard exposure',
};

export function ChatOps({ onHighlight }: ChatOpsProps) {
  const [expanded, setExpanded] = useState(true);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight });
  }, [messages]);

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || streaming) return;
    setInput('');
    onHighlight(null);

    const history = [...messages, { role: 'user' as const, content: q }];
    setMessages([...history, { role: 'assistant', content: '', tools: [] }]);
    setStreaming(true);

    const appendToLast = (fn: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => [...prev.slice(0, -1), fn(prev[prev.length - 1])]);

    try {
      const resp = await fetch('/api/agent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          // send text-only history (tool traces stay server-side per request)
          messages: history.map(({ role, content }) => ({ role, content })),
        }),
      });
      if (!resp.ok || !resp.body) {
        const detail = await resp.json().catch(() => null);
        throw new Error(detail?.detail ?? `Agent request failed (${resp.status})`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === 'text') {
            appendToLast((m) => ({ ...m, content: m.content + event.text }));
          } else if (event.type === 'tool_start') {
            appendToLast((m) => ({
              ...m,
              tools: [...(m.tools ?? []), { name: event.name, done: false }],
            }));
          } else if (event.type === 'tool_result') {
            appendToLast((m) => ({
              ...m,
              tools: (m.tools ?? []).map((t) =>
                t.name === event.name ? { ...t, done: true } : t,
              ),
            }));
            const h = event.highlight as AgentHighlight | null;
            if (h && ((h.node_ids?.length ?? 0) > 0 || (h.pipe_ids?.length ?? 0) > 0)) {
              onHighlight(h);
            }
          } else if (event.type === 'error') {
            appendToLast((m) => ({
              ...m,
              content: m.content + `\n\n⚠️ ${event.message}`,
            }));
          }
        }
      }
    } catch (err) {
      appendToLast((m) => ({
        ...m,
        content: m.content + `\n\n⚠️ ${err instanceof Error ? err.message : 'Request failed'}`,
      }));
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="bg-slate-900 text-slate-100 border-b border-slate-700">
      <div className="px-6 py-2.5 flex items-center gap-3">
        <Sparkles className="w-5 h-5 text-teal-300 flex-none" />
        <span className="text-sm font-semibold">Ask the network</span>
        <span className="text-xs text-slate-400 hidden md:inline">
          Claude-powered ops assistant — answers with live simulator data and highlights the map
        </span>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="ml-auto p-1 rounded hover:bg-slate-700"
          aria-label={expanded ? 'Collapse chat' : 'Expand chat'}
        >
          <ChevronDown className={`w-4 h-4 transition-transform ${expanded ? '' : 'rotate-180'}`} />
        </button>
      </div>

      {expanded && (
        <div className="px-6 pb-4">
          {messages.length === 0 ? (
            <div className="flex flex-wrap gap-2 mb-3">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-xs px-3 py-1.5 rounded-full border border-slate-600 text-slate-300 hover:border-teal-400 hover:text-teal-200 transition-colors text-left"
                >
                  {s}
                </button>
              ))}
            </div>
          ) : (
            <div
              ref={threadRef}
              className="max-h-72 overflow-y-auto mb-3 space-y-3 pr-2"
            >
              {messages.map((m, i) => (
                <div key={i} className={m.role === 'user' ? 'text-right' : ''}>
                  {m.role === 'user' ? (
                    <span className="inline-block bg-teal-600/30 border border-teal-500/40 rounded-lg px-3 py-1.5 text-sm">
                      {m.content}
                    </span>
                  ) : (
                    <div className="text-sm leading-relaxed">
                      {(m.tools ?? []).length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mb-1.5">
                          {(m.tools ?? []).map((t, j) => (
                            <span
                              key={j}
                              className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border ${
                                t.done
                                  ? 'border-teal-500/50 text-teal-300'
                                  : 'border-amber-400/60 text-amber-300 animate-pulse'
                              }`}
                            >
                              <Wrench className="w-3 h-3" />
                              {TOOL_LABELS[t.name] ?? t.name}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="text-slate-200 chatops-md">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                        {streaming && i === messages.length - 1 && (
                          <span className="inline-block w-2 h-4 bg-teal-300 ml-0.5 animate-pulse align-text-bottom" />
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="flex gap-2"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder='Try: "How does gas pressure look today?"'
              disabled={streaming}
              className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm placeholder-slate-500 focus:outline-none focus:border-teal-400 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={streaming || !input.trim()}
              className="px-3 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Send"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
