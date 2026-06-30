import { create } from 'zustand'

export interface ColumnInfo {
  name: string
  showType: 'DATE' | 'NUMERIC' | 'CATEGORY'
}

export interface QueryResult {
  columns: ColumnInfo[]
  rows: any[][]
  sql: string
}

export interface Message {
  id: string
  role: 'user' | 'bot'
  content: string
  parseInfo?: { metrics: string[]; dimensions: string[]; dateInfo: any; queryMode: string }
  result?: QueryResult
  summary?: string
  sql?: string
  error?: string
  ratio?: Record<string, { current: number; previous: number; ratio: number; label: string }>
  recommendedDimensions?: { biz_name: string; score: number }[]
  dateInfo?: { start: string; end: string }
  chartTypeOverride?: ChartType
}

export type ChartType = 'METRIC_CARD' | 'METRIC_TREND' | 'METRIC_BAR' | 'METRIC_PIE' | 'TABLE'

interface ChatState {
  chatId: string
  messages: Message[]
  status: 'idle' | 'parsing' | 'executing' | 'streaming' | 'done' | 'error'
  currentChartType: ChartType

  setStatus: (s: ChatState['status']) => void
  addMessage: (msg: Message) => void
  updateLastBot: (updates: Partial<Message>) => void
  setChartType: (t: ChartType) => void
  resetChat: () => void
}

let msgId = 0
const nextId = () => `msg_${++msgId}`

export const useChatStore = create<ChatState>((set, get) => ({
  chatId: 'default',
  messages: [],
  status: 'idle',
  currentChartType: 'TABLE',

  setStatus: (status) => set({ status }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, { ...msg, id: nextId() }] })),

  updateLastBot: (updates) => set((s) => {
    const msgs = [...s.messages]
    const last = msgs.length > 0 ? { ...msgs[msgs.length - 1] } : null
    if (last && last.role === 'bot') {
      Object.assign(last, updates)
      msgs[msgs.length - 1] = last
    }
    return { messages: msgs }
  }),

  setChartType: (t) => set({ currentChartType: t }),

  resetChat: () => set({
    chatId: `chat_${Date.now()}`,
    messages: [],
    status: 'idle',
    currentChartType: 'TABLE',
  }),
}))
