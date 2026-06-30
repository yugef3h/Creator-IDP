import { useChatStore } from './store'

export async function sendQuery(queryText: string, dateRange?: { start: string; end: string }, replaceLast = false) {
  const store = useChatStore.getState()
  const chatId = store.chatId

  if (replaceLast) {
    // 替换模式：就地更新最后一个 bot 消息，不增删任何消息
    useChatStore.getState().setStatus('parsing')
    useChatStore.getState().updateLastBot({
      parseInfo: undefined, result: undefined, summary: undefined,
      sql: undefined, ratio: undefined, recommendedDimensions: undefined, error: undefined,
    })
  } else {
    store.setStatus('parsing')
    store.addMessage({ id: '', role: 'user', content: queryText })
    store.addMessage({ id: '', role: 'bot', content: '' })
  }

  try {
    const response = await fetch('/api/chat/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ queryText, chatId, dateRange }),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let summaryBuf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          const st = useChatStore.getState()

          switch (event.type) {
            case 'parse_info':
              st.setStatus('executing')
              st.updateLastBot({ parseInfo: event.data })
              break

            case 'query_result':
              st.setStatus('streaming')
              st.updateLastBot({
                result: {
                  columns: event.data.columns,
                  rows: event.data.rows,
                  sql: event.data.sql,
                },
                sql: event.data.sql,
              })
              break

            case 'summary_chunk':
              summaryBuf += event.text
              st.updateLastBot({ summary: summaryBuf })
              break

            case 'done':
              st.setStatus('idle')
              st.updateLastBot({
                ratio: event.data?.ratio,
                recommendedDimensions: event.data?.recommendedDimensions,
                dateInfo: event.data?.dateInfo,
              })
              if (event.data?.chatId) {
                useChatStore.setState({ chatId: event.data.chatId })
              }
              break

            case 'error':
              st.setStatus('error')
              st.updateLastBot({ error: event.data?.message || '未知错误' })
              break
          }
        } catch {}
      }
    }
  } catch (e: any) {
    useChatStore.getState().setStatus('error')
    useChatStore.getState().updateLastBot({ error: `请求失败: ${e.message}` })
  }
}
