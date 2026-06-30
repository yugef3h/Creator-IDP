import { useState, useRef, useEffect, useCallback } from 'react'
import { Input, Button, Spin, Tag, Modal } from 'antd'
import { SendOutlined, PlusOutlined, EditOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useChatStore, type Message } from './store'
import { sendQuery } from './api'
import { getChartType } from './chart-utils'

const EXAMPLES = [
  '最近7天播放量趋势',
  '各分区播放量排名',
  '点赞最多的5个视频',
  '互动率是多少',
  '最近30天新增粉丝的城市分布',
  '深圳的粉丝有多少',
  '帮我预测下周播放量',
]

export default function App() {
  const { messages, status, addMessage, resetChat } = useChatStore()
  const [input, setInput] = useState('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const isBusy = status !== 'idle' && status !== 'error'

  const handleSend = useCallback(() => {
    const q = input.trim()
    if (!q || isBusy) return
    setInput('')
    sendQuery(q)
  }, [input, isBusy])

  const handleExample = (ex: string) => {
    if (isBusy) return
    sendQuery(ex)
  }

  const handleNewChat = () => {
    if (messages.length === 0 || isBusy) return
    setConfirmOpen(true)
  }

  const confirmNewChat = () => {
    setConfirmOpen(false)
    setInput('')
    resetChat()
  }

  const handleEditMessage = (text: string) => {
    if (isBusy) return
    setInput(text)
    // focus the input
    const ta = document.querySelector('.chat-footer textarea') as HTMLTextAreaElement
    ta?.focus()
  }

  const statusLabel: Record<string, string> = {
    idle: '就绪',
    parsing: '解析中...',
    executing: '执行查询...',
    streaming: '生成解读...',
    done: '就绪',
    error: '出错了',
  }

  return (
    <div className="app-layout">
      {/* ============================================================
          左侧面板 — 查询输入 + 推荐问句 + 数据概览
          ============================================================ */}
      <aside className="left-panel">
        <div className="left-panel-header">
          <h1>📊 B站创作数据中心</h1>
          <p>自然语言查询你的视频数据</p>
        </div>

        <div className="left-panel-body">

          <Button
            icon={<PlusOutlined />}
            onClick={handleNewChat}
            className="new-chat-btn"
            disabled={isBusy || messages.length === 0}
          >
            新对话
          </Button>

          {/* 推荐问句 */}
          <div>
            <div className="section-title">💡 试试这些</div>
            <div className="example-list">
              {EXAMPLES.map(ex => (
                <button
                  key={ex}
                  className="example-btn"
                  onClick={() => handleExample(ex)}
                  disabled={isBusy}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>

          {/* 数据概览 */}
          <div>
            <div className="section-title">📋 数据概览</div>
            <div className="data-overview">
              <div className="overview-item">
                <span className="dot" />
                50 个视频，8 个分区
              </div>
              <div className="overview-item">
                <span className="dot" />
                9 个指标，7 个维度
              </div>
              <div className="overview-item">
                <span className="dot" />
                数据范围：最近 90 天
              </div>
            </div>
          </div>

        </div>

        <div className="left-panel-footer">
          <span className="footer-dot" />
          Powered by DeepSeek V3 | SQLite | React
        </div>
      </aside>

      {/* ============================================================
          右侧面板 — 对话消息 + 图表结果
          ============================================================ */}
      <main className="right-panel">
        {/* 顶部状态栏 */}
        <div className="right-panel-header">
          <div className="status-badge">
            <span className={`status-dot ${status === 'parsing' ? 'parsing' : ''} ${status === 'error' ? 'error' : ''}`} />
            {statusLabel[status] || '就绪'}
          </div>
          <span style={{ fontSize: 12, color: 'var(--text-color-fourth)' }}>
            {messages.length > 0 ? `${messages.filter(m => m.role === 'user').length} 轮对话` : ''}
          </span>
        </div>

        {/* 消息区域 */}
        <div className="messages">
          {messages.length === 0 ? (
            // 空状态欢迎页
            <div className="welcome-state">
              <div className="welcome-icon">📊</div>
              <h2>欢迎使用创作数据中心</h2>
              <p>
                用自然语言查询你的B站视频数据——播放量、点赞数、粉丝增长，
                所有指标一目了然。在下方输入问题或点击左侧推荐问句开始 👈
              </p>
            </div>
          ) : (
            messages.map(msg => (
              <div key={msg.id} className={msg.role === 'user' ? 'user-bubble' : 'bot-bubble'}>
                {msg.role === 'user' ? (
                  <span
                    className="user-msg-text"
                    onClick={() => handleEditMessage(msg.content)}
                    title="点击重新编辑"
                  >
                    {msg.content}
                    <EditOutlined className="edit-hint" />
                  </span>
                ) : msg.error ? (
                  <div style={{ color: 'var(--error-color)' }}>{msg.error}</div>
                ) : (
                  <BotMessage msg={msg} status={status} />
                )}
              </div>
            ))
          )}

          {status === 'parsing' && (
            <div className="bot-bubble">
              <Spin size="small" /> 解析中...
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* 底部输入区 — 始终可见 */}
        <div className="chat-footer">
          <div className="input-row">
            <Input.TextArea
              value={input}
              onChange={e => setInput(e.target.value)}
              onPressEnter={e => {
                if (!e.shiftKey) { e.preventDefault(); handleSend() }
              }}
              placeholder="输入你的问题，如：最近7天播放量趋势"
              autoSize={{ minRows: 1, maxRows: 3 }}
              disabled={isBusy}
              style={{ borderRadius: 8 }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!input.trim() || isBusy}
              className="send-btn"
            />
          </div>
        </div>
      </main>

      {/* 新对话确认弹窗 */}
      <Modal
        title="新对话"
        open={confirmOpen}
        onOk={confirmNewChat}
        onCancel={() => setConfirmOpen(false)}
        okText="确认"
        cancelText="取消"
        centered
      >
        <p>开启新对话将清空当前全部聊天记录，确定继续？</p>
      </Modal>
    </div>
  )
}

/* ============================================================
   BotMessage — 助手回复卡片
   ============================================================ */
function BotMessage({ msg, status }: { msg: Message; status: string }) {
  const { parseInfo, result, summary } = msg
  const [showSql, setShowSql] = useState(false)

  const modeLabel: Record<string, string> = {
    RULE: '规则匹配',
    LLM: 'AI 理解',
    METRIC_TREND: '趋势分析',
    METRIC_GROUPBY: '分组查询',
    METRIC_ORDERBY: 'TopN排序',
    METRIC_FILTER: '条件过滤',
    METRIC_CARD: '单值查询',
  }

  // 尚无 parseInfo 时显示骨架状态
  if (!parseInfo) {
    return (
      <div className="loading-row">
        <Spin size="small" /> 正在理解问题...
      </div>
    )
  }

  return (
    <div>
      {/* 解析信息条 */}
      <div className="parse-tip">
        <Tag color="green">
          ✅ {modeLabel[parseInfo.queryMode] || parseInfo.queryMode}
        </Tag>
        {parseInfo.metrics.map(m => (
          <span key={m} className="tag">📊 {m}</span>
        ))}
        {parseInfo.dimensions.map(d => (
          <span key={d} className="tag">📏 {d}</span>
        ))}
        {parseInfo.dateInfo?.start && (
          <span className="tag">
            📅 {parseInfo.dateInfo.start} ~ {parseInfo.dateInfo.end}
          </span>
        )}
      </div>

      {/* 图表 */}
      {result && result.rows.length > 0 && <ChartView msg={msg} />}

      {result && result.rows.length === 0 && (
        <div style={{ color: 'var(--text-color-fourth)', padding: 12 }}>
          📭 查询结果为空
        </div>
      )}

      {/* AI 解读 */}
      {summary && (
        <div className="summary-text">
          {summary}
          {status === 'streaming' && <span className="cursor-blink">|</span>}
        </div>
      )}
      {status === 'executing' && !summary && (
        <div className="loading-row"><Spin size="small" /> 正在执行查询...</div>
      )}

      {/* SQL 折叠 */}
      {msg.sql && (
        <>
          <div className="sql-toggle" onClick={() => setShowSql(!showSql)}>
            {showSql ? '收起 SQL ▲' : '查看 SQL ▼'}
          </div>
          {showSql && (
            <pre className="sql-block">{msg.sql}</pre>
          )}
        </>
      )}
    </div>
  )
}

/* ============================================================
   ChartView — 图表渲染
   ============================================================ */
function ChartView({ msg }: { msg: Message }) {
  const { result } = msg
  if (!result) return null

  const { columns, rows } = result
  const chartType = getChartType(columns, rows)

  // 单值卡片
  if (chartType === 'METRIC_CARD') {
    const val = rows[0][0]
    return (
      <div style={{ textAlign: 'center', padding: '20px 16px' }}>
        <div style={{ fontSize: 44, fontWeight: 700, color: 'var(--chat-blue)', lineHeight: 1.2 }}>
          {typeof val === 'number' ? val.toLocaleString() : String(val)}
        </div>
        <div style={{ color: 'var(--text-color-fourth)', marginTop: 4 }}>
          {columns[0]?.name}
        </div>
      </div>
    )
  }

  const numIdx = columns.findIndex(c => c.showType === 'NUMERIC')
  const dateIdx = columns.findIndex(c => c.showType === 'DATE')
  const catIdx = columns.findIndex(c => c.showType === 'CATEGORY')

  // 趋势线图
  if (chartType === 'METRIC_TREND' && dateIdx >= 0) {
    const option = {
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: rows.map(r => r[dateIdx]),
        axisLabel: { fontSize: 11 },
      },
      yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
      series: [{
        data: rows.map(r => r[numIdx >= 0 ? numIdx : 1]),
        type: 'line',
        smooth: true,
        itemStyle: { color: '#1b4aef' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(27,74,239,0.15)' }, { offset: 1, color: 'rgba(27,74,239,0.02)' }] } },
      }],
    }
    return <div className="chart-area"><ReactECharts option={option} style={{ height: 300 }} /></div>
  }

  // 柱状图 / 饼图
  if ((chartType === 'METRIC_BAR' || chartType === 'METRIC_PIE') && catIdx >= 0 && numIdx >= 0) {
    const option = {
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 20, bottom: rows.length > 5 ? 60 : 30 },
      xAxis: {
        type: 'category',
        data: rows.map(r => String(r[catIdx])),
        axisLabel: { rotate: rows.length > 5 ? 45 : 0, fontSize: 11 },
      },
      yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
      series: [{
        data: rows.map(r => r[numIdx]),
        type: 'bar',
        itemStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [{ offset: 0, color: '#4e86f5' }, { offset: 1, color: '#1b4aef' }],
          },
          borderRadius: [4, 4, 0, 0],
        },
      }],
    }
    return <div className="chart-area"><ReactECharts option={option} style={{ height: 300 }} /></div>
  }

  // 表格兜底
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map(c => (
              <th key={c.name}>{c.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 50).map((row, i) => (
            <tr key={i}>
              {row.map((cell: any, j: number) => (
                <td key={j}>
                  {typeof cell === 'number' ? cell.toLocaleString() : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
