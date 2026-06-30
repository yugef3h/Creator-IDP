/** 前端独立开发用 Mock API，模拟后端 SSE 事件流。设置 USE_MOCK=true 启用。 */

import { useChatStore } from './store'

const USE_MOCK = false  // 改为 true 即可离线开发

// 查询关键词 → mock 数据文件名
const MOCK_MAP: Record<string, string> = {
  '趋势': '/mock/trend.json',
  '排名': '/mock/groupby.json',
  '播放量': '/mock/groupby.json',
  '分区': '/mock/groupby.json',
  '互动率': '/mock/card.json',
  '粉丝': '/mock/distribution.json',
  '城市': '/mock/distribution.json',
  '分布': '/mock/distribution.json',
  '点赞': '/mock/groupby.json',
}

function findMockFile(query: string): string {
  for (const [keyword, file] of Object.entries(MOCK_MAP)) {
    if (query.includes(keyword)) return file
  }
  return '/mock/trend.json' // default
}

export async function mockQuery(queryText: string, replaceLast = false) {
  const store = useChatStore.getState()

  if (replaceLast) {
    store.setStatus('parsing')
    store.updateLastBot({
      parseInfo: undefined, result: undefined, summary: undefined,
      sql: undefined, ratio: undefined, recommendedDimensions: undefined, error: undefined,
    })
  } else {
    store.setStatus('parsing')
    store.addMessage({ id: '', role: 'user', content: queryText })
    store.addMessage({ id: '', role: 'bot', content: '' })
  }

  const mockFile = findMockFile(queryText)
  const response = await fetch(mockFile)
  const events = await response.json()

  for (const event of events) {
    await new Promise(r => setTimeout(r, 200)) // 模拟网络延迟

    switch (event.type) {
      case 'parse_info':
        store.setStatus('executing')
        store.updateLastBot({ parseInfo: event.data })
        break
      case 'query_result':
        store.setStatus('streaming')
        store.updateLastBot({
          result: {
            columns: event.data.columns,
            rows: event.data.rows,
            sql: event.data.sql,
          },
          sql: event.data.sql,
        })
        break
      case 'summary_chunk':
        store.updateLastBot({
          summary: (useChatStore.getState().messages.slice(-1)[0]?.summary || '') + event.text,
        })
        break
      case 'done':
        store.setStatus('idle')
        store.updateLastBot({
          ratio: event.data?.ratio,
          recommendedDimensions: event.data?.recommendedDimensions,
          dateInfo: event.data?.dateInfo,
        })
        break
      case 'error':
        store.setStatus('error')
        store.updateLastBot({ error: event.data?.message || '未知错误' })
        break
    }
  }
}

export { USE_MOCK }
