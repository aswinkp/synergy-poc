import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Visualization } from './types'

const COLORS = ['#E8653B', '#1D8A7A', '#E7AF45', '#4E6AA8', '#A369A7', '#66A3C6', '#C66A78', '#6C8B5A']

const compactNumber = (value: number | string) =>
  typeof value === 'number' ? Intl.NumberFormat('en', { notation: value > 9999 ? 'compact' : 'standard' }).format(value) : value

function TableView({ visualization }: { visualization: Visualization }) {
  if (!visualization.data.length) return null
  const keys = Object.keys(visualization.data[0])
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{keys.map((key) => <th key={key}>{key.replaceAll('_', ' ')}</th>)}</tr>
        </thead>
        <tbody>
          {visualization.data.map((row, index) => (
            <tr key={index}>{keys.map((key) => <td key={key}>{row[key]?.toLocaleString() ?? '—'}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ChartView({ visualization }: { visualization: Visualization }) {
  if (visualization.type === 'table') return <TableView visualization={visualization} />

  const labelKey = visualization.labelKey || 'label'
  const valueKeys = visualization.valueKeys?.length ? visualization.valueKeys : ['value']
  const height = Math.max(300, visualization.data.length * 26)
  const tooltip = <Tooltip contentStyle={{ border: 0, borderRadius: 12, boxShadow: '0 10px 35px rgba(16,32,48,.14)' }} />

  return (
    <figure className="chart-card" aria-label={visualization.title}>
      <figcaption>{visualization.title}</figcaption>
      <div className="chart-canvas" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          {visualization.type === 'pie' ? (
            <PieChart>
              <Pie data={visualization.data} dataKey={valueKeys[0]} nameKey={labelKey} innerRadius="50%" outerRadius="78%" paddingAngle={2}>
                {visualization.data.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
              </Pie>
              {tooltip}
              <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          ) : visualization.type === 'line' ? (
            <LineChart data={visualization.data} margin={{ top: 10, right: 16, bottom: 42, left: 8 }}>
              <CartesianGrid stroke="#E8E8E2" vertical={false} />
              <XAxis dataKey={labelKey} angle={-24} textAnchor="end" interval={0} height={70} tick={{ fontSize: 11, fill: '#68717C' }} />
              <YAxis tickFormatter={compactNumber} tick={{ fontSize: 11, fill: '#68717C' }} />
              {tooltip}
              {valueKeys.map((key, index) => <Line key={key} dataKey={key} stroke={COLORS[index]} strokeWidth={3} dot={{ r: 3 }} />)}
            </LineChart>
          ) : visualization.type === 'area' ? (
            <AreaChart data={visualization.data} margin={{ top: 10, right: 16, bottom: 42, left: 8 }}>
              <defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#1D8A7A" stopOpacity={0.4}/><stop offset="95%" stopColor="#1D8A7A" stopOpacity={0.04}/></linearGradient></defs>
              <CartesianGrid stroke="#E8E8E2" vertical={false} />
              <XAxis dataKey={labelKey} angle={-24} textAnchor="end" interval={0} height={70} tick={{ fontSize: 11, fill: '#68717C' }} />
              <YAxis tickFormatter={compactNumber} tick={{ fontSize: 11, fill: '#68717C' }} />
              {tooltip}
              <Area dataKey={valueKeys[0]} stroke="#1D8A7A" strokeWidth={3} fill="url(#areaFill)" />
            </AreaChart>
          ) : (
            <BarChart data={visualization.data} layout={visualization.data.length > 8 ? 'vertical' : 'horizontal'} margin={{ top: 8, right: 18, bottom: visualization.data.length > 8 ? 8 : 52, left: visualization.data.length > 8 ? 115 : 8 }}>
              <CartesianGrid stroke="#E8E8E2" horizontal={visualization.data.length <= 8} vertical={visualization.data.length > 8} />
              {visualization.data.length > 8 ? (
                <><XAxis type="number" tickFormatter={compactNumber} tick={{ fontSize: 11, fill: '#68717C' }} /><YAxis type="category" dataKey={labelKey} width={110} tick={{ fontSize: 10, fill: '#68717C' }} /></>
              ) : (
                <><XAxis dataKey={labelKey} angle={-22} textAnchor="end" interval={0} height={72} tick={{ fontSize: 11, fill: '#68717C' }} /><YAxis tickFormatter={compactNumber} tick={{ fontSize: 11, fill: '#68717C' }} /></>
              )}
              {tooltip}
              {valueKeys.map((key, index) => <Bar key={key} dataKey={key} fill={COLORS[index]} radius={[5, 5, 0, 0]} maxBarSize={52} />)}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  )
}
