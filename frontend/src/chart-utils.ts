import type { ColumnInfo, ChartType } from './store'

export function getChartType(columns: ColumnInfo[], rows: any[][]): ChartType {
  const dateCols = columns.filter(c => c.showType === 'DATE')
  const numCols = columns.filter(c => c.showType === 'NUMERIC')
  const catCols = columns.filter(c => c.showType === 'CATEGORY')
  const n = rows.length

  if (n === 1 && numCols.length === 1 && catCols.length === 0) return 'METRIC_CARD'
  if (dateCols.length > 0 && numCols.length >= 1) return 'METRIC_TREND'
  if (catCols.length >= 1 && numCols.length === 1 && n <= 10) {
    const idx = columns.findIndex(c => c.showType === 'NUMERIC')
    if (idx >= 0 && rows.every(r => Number(r[idx]) >= 0)) return 'METRIC_PIE'
    return 'METRIC_BAR'
  }
  if (catCols.length >= 1 && numCols.length >= 1 && n <= 50) return 'METRIC_BAR'
  return 'TABLE'
}
