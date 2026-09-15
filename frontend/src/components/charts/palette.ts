import { useMemo } from 'react'

import { useThemeStore } from '@/store/themeStore'

/** Chart colours mirror the status palette so the whole app reads as one system.
 *
 * Recharts takes colours as plain props on SVG attributes, so a CSS variable
 * cannot reach it the way a Tailwind class can. The two colours that must
 * follow the theme — the brand line and the chart's own gridlines — are read
 * back from the document instead; the status colours are deliberately fixed,
 * because green-means-good should not change meaning with the palette.
 */
const FALLBACK = {
  brand: '#35346f',
  grid: '#eef0f4',
  axis: '#98a1b3',
} as const

/** `--c-brand-600` holds `53 52 111`; charts need `rgb(53 52 111)`. */
function themeColor(variable: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const channels = getComputedStyle(document.documentElement)
    .getPropertyValue(variable)
    .trim()
  return channels ? `rgb(${channels})` : fallback
}

function chartColors() {
  return {
    brand: themeColor('--c-brand-600', FALLBACK.brand),
    grid: themeColor('--c-ink-200', FALLBACK.grid),
    axis: themeColor('--c-ink-400', FALLBACK.axis),
    good: '#16a34a',
    warn: '#d97706',
    bad: '#dc2626',
  }
}

/** Kept for callers that only need the fixed status colours. */
export const CHART_COLORS = {
  ...FALLBACK,
  good: '#16a34a',
  warn: '#d97706',
  bad: '#dc2626',
} as const

export function RATE_BAR_HEX(rate: number): string {
  if (rate >= 90) return CHART_COLORS.good
  if (rate >= 75) return CHART_COLORS.warn
  return CHART_COLORS.bad
}

/**
 * The chart palette, re-read whenever the theme changes.
 *
 * `getComputedStyle` is a snapshot: without subscribing, a chart would keep the
 * previous theme's gridlines until something else happened to re-render it.
 */
export function useChartColors() {
  const theme = useThemeStore((state) => state.theme)
  // The theme is not read inside chartColors() — it comes from the document —
  // but it is exactly what invalidates the snapshot, so it is the dependency.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => chartColors(), [theme])
}
