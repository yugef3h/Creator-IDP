import type { ColumnInfo, ChartType } from './store'

export interface ChartTypeOption {
  type: ChartType
  label: string
  icon: string
}

export const CHART_TYPE_CONFIG: Record<ChartType, { label: string; icon: string }> = {
  METRIC_TREND: { label: '趋势图', icon: '📈' },
  METRIC_BAR: { label: '柱状图', icon: '📊' },
  METRIC_PIE: { label: '饼图', icon: '🥧' },
  METRIC_CARD: { label: '数值卡', icon: '🃏' },
  TABLE: { label: '表格', icon: '📋' },
}

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

/** Return all chart types compatible with this data, excluding the current one. */
export function getAlternativeChartTypes(
  current: ChartType,
  columns: ColumnInfo[],
  rows: any[][],
): ChartTypeOption[] {
  const dateCols = columns.filter(c => c.showType === 'DATE')
  const numCols = columns.filter(c => c.showType === 'NUMERIC')
  const catCols = columns.filter(c => c.showType === 'CATEGORY')
  const n = rows.length

  const available = new Set<ChartType>()

  // METRIC_TREND: needs date + numeric
  if (dateCols.length > 0 && numCols.length >= 1) available.add('METRIC_TREND')

  // METRIC_BAR: needs category + numeric
  if (catCols.length >= 1 && numCols.length >= 1) available.add('METRIC_BAR')

  // METRIC_PIE: needs category + single numeric + <=10 rows + all non-negative
  if (catCols.length >= 1 && numCols.length === 1 && n <= 10) {
    const idx = columns.findIndex(c => c.showType === 'NUMERIC')
    if (idx >= 0 && rows.every(r => Number(r[idx]) >= 0)) available.add('METRIC_PIE')
  }

  // METRIC_CARD: single row, single numeric
  if (n === 1 && numCols.length === 1 && catCols.length === 0) available.add('METRIC_CARD')

  // TABLE: always available (as fallback to see raw data)
  available.add('TABLE')

  // Remove current type
  available.delete(current)

  return [...available].map(t => ({
    type: t,
    label: CHART_TYPE_CONFIG[t].label,
    icon: CHART_TYPE_CONFIG[t].icon,
  }))
}
