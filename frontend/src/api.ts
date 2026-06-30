import { useChatStore } from './store'

export async function sendQuery(queryText: string) {
  const store = useChatStore.getState()
  const chatId = store.chatId

  store.setStatus('parsing')
  store.addMessage({ id: '', role: 'user', content: queryText })
  store.addMessage({ id: '', role: 'bot', content: '' })

  try {
    const response = await fetch('/api/chat/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ queryText, chatId }),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let summaryBuf = ''  // 本地累积，不依赖 store 快照

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
