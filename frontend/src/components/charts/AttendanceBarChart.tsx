import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { RATE_BAR_HEX, useChartColors } from './palette'

export interface BarPoint {
  label: string
  /** The plotted value: a percentage, or hours when `unit` says so. */
  rate: number
  /** Contextual counts shown in the tooltip (entries / exits, or days). */
  attended: number
  total: number
}

function ChartTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean
  payload?: { payload: BarPoint }[]
  unit: '%' | 'soat'
}) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-lg border border-ink-200 bg-surface px-3 py-2 text-xs shadow-raised">
      <p className="font-semibold text-ink-800">{point.label}</p>
      <p className="mt-0.5 text-ink-600">
        {point.attended} kirish · {point.total} chiqish
      </p>
      <p className="text-ink-600">
        {unit === '%' ? 'Davomat: ' : 'Maktabda: '}
        {point.rate}
        {unit === '%' ? '%' : ' soat'}
      </p>
    </div>
  )
}

export function AttendanceBarChart({
  data,
  height = 240,
  unit = '%',
}: {
  data: BarPoint[]
  height?: number
  /** Percentages are capped at 100; hours scale to the data. */
  unit?: '%' | 'soat'
}) {
  const colors = useChartColors()

  const isPercent = unit === '%'
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={colors.grid} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 12, fill: colors.axis }}
        />
        <YAxis
          domain={isPercent ? [0, 100] : [0, 'auto']}
          tickCount={5}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 12, fill: colors.axis }}
          unit={isPercent ? '%' : 's'}
        />
        <Tooltip content={<ChartTooltip unit={unit} />} cursor={{ fill: colors.grid }} />
        <Bar dataKey="rate" radius={[6, 6, 0, 0]} maxBarSize={44}>
          {data.map((point) => (
            // Hours have no "good/bad" band — colour them uniformly.
            <Cell key={point.label} fill={isPercent ? RATE_BAR_HEX(point.rate) : colors.brand} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
