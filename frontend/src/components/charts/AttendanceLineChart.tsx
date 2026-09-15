import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { BarPoint } from './AttendanceBarChart'
import { useChartColors } from './palette'

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: BarPoint }[] }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-lg border border-ink-200 bg-surface px-3 py-2 text-xs shadow-raised">
      <p className="font-semibold text-ink-800">{point.label}</p>
      <p className="mt-0.5 text-ink-600">Davomat: {point.rate}%</p>
      <p className="text-ink-600">
        {point.attended} / {point.total} dars
      </p>
    </div>
  )
}

export function AttendanceLineChart({ data, height = 260 }: { data: BarPoint[]; height?: number }) {
  // Read once per render: the theme can change between renders, and recharts
  // takes plain colour props that a CSS variable cannot reach.
  const colors = useChartColors()

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={colors.grid} />
        <XAxis
          dataKey="label"
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 12, fill: colors.axis }}
        />
        <YAxis
          domain={[0, 100]}
          tickCount={5}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 12, fill: colors.axis }}
          unit="%"
        />
        <Tooltip content={<ChartTooltip />} />
        <Line
          type="monotone"
          dataKey="rate"
          stroke={colors.brand}
          strokeWidth={2.5}
          dot={{ r: 3.5, fill: colors.brand, strokeWidth: 0 }}
          activeDot={{ r: 5.5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
