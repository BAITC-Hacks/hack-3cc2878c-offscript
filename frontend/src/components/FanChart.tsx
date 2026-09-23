import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ForecastResult } from '../api/types'
import { localTime, percent } from './Shared'

const modelColors: Record<string, string> = { ecmwf_ifs025: '#a5b4fc', gfs_seamless: '#fbbf24', icon_seamless: '#f472b6' }

export function FanChart({ forecast, showModels, showActual }: { forecast: ForecastResult; showModels: boolean; showActual: boolean }) {
  const rows = forecast.rows.map(row => ({ ...row, band: [row.p10 * 100, row.p90 * 100], p50pct: row.p50 * 100, actualPct: row.actual == null ? null : row.actual * 100,
    label: `${new Date(row.target_time_local).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${row.target_time_local.slice(11, 16)}`,
    ecmwf: row.nwp_v_hub.ecmwf_ifs025, gfs: row.nwp_v_hub.gfs_seamless, icon: row.nwp_v_hub.icon_seamless }))
  return <div className="chart-wrap" role="img" aria-label="48 hour normalized farm power forecast as a percentage of installed capacity, with P10 to P90 interval and archived model wind speeds">
    <ResponsiveContainer width="100%" height={360}>
      <ComposedChart data={rows} margin={{ top: 14, right: 10, bottom: 4, left: -12 }}>
        <CartesianGrid stroke="#23344c" strokeDasharray="3 5" vertical={false} />
        <XAxis dataKey="lead_h" stroke="#8fa3bf" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} interval={5} label={{ value: 'Lead hour', position: 'insideBottomRight', offset: -3, fill: '#8fa3bf', fontSize: 11 }} />
        <YAxis yAxisId="power" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} stroke="#8fa3bf" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} tickFormatter={value => `${value}%`} />
        <YAxis yAxisId="wind" orientation="right" stroke="#8fa3bf" tickLine={false} axisLine={false} tick={{ fontSize: 11 }} hide={!showModels} unit=" m/s" />
        <Tooltip content={({ active, payload }) => {
          if (!active || !payload?.length) return null
          const row = payload[0]?.payload as (typeof rows)[number]
          return <div className="chart-tooltip"><strong>{row.label} · lead {row.lead_h}</strong><span>Median: {percent(row.p50)}</span><span>P10–P90: {percent(row.p10)} – {percent(row.p90)}</span>{row.actual != null ? <span>Actual: {percent(row.actual)}</span> : null}{showModels ? <span>Model wind: {Object.entries(row.nwp_v_hub).map(([name, value]) => `${name.split('_')[0].toUpperCase()} ${value.toFixed(1)}`).join(' · ')} m/s</span> : null}</div>
        }} />
        <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: 11 }} />
        <Area yAxisId="power" name="P10–P90 range" type="monotone" dataKey="band" stroke="none" fill="#38bdf8" fillOpacity={0.19} connectNulls={false} isAnimationActive={false} />
        <Line yAxisId="power" name="P50 forecast" type="monotone" dataKey="p50pct" stroke="#38bdf8" strokeWidth={3} dot={false} isAnimationActive={false} />
        {showActual ? <Line yAxisId="power" name="Actual" type="monotone" dataKey="actualPct" stroke="#f8fafc" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} /> : null}
        {showModels ? ([['ecmwf', 'ecmwf_ifs025'], ['gfs', 'gfs_seamless'], ['icon', 'icon_seamless']] as const).map(([key, model]) => <Line key={key} yAxisId="wind" name={`${key.toUpperCase()} wind`} dataKey={key} stroke={modelColors[model]} strokeDasharray="5 4" strokeWidth={1.5} dot={false} isAnimationActive={false} />) : null}
        <ReferenceLine yAxisId="power" x={24} stroke="#a1afc2" strokeDasharray="4 4" label={{ value: 'Day-ahead begins', position: 'insideTopRight', fill: '#cbd5e1', fontSize: 11 }} />
      </ComposedChart>
    </ResponsiveContainer>
    <div className="chart-foot">Left axis: normalized farm power (% of installed capacity; 100% = full rated output). Right axis, when shown: forecast wind speed (m/s). Issue: {localTime(forecast.issue_time)} · Day-ahead delivery is leads 24–47.</div>
  </div>
}
