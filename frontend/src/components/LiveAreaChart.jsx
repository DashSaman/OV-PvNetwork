/* PVN-1016 — professional live traffic chart (recharts, lazy-loaded chunk).
   Replaces the hand-rolled dashboard SVG with gradient areas, a live tooltip
   and smooth animation; receives the same `history` array the old chart used. */
import { useTranslation } from 'react-i18next';
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const fmtBits = value => {
  const bits = Math.max(0, Number(value || 0));
  if (bits >= 1e9) return (bits / 1e9).toFixed(2) + ' Gbps';
  if (bits >= 1e6) return (bits / 1e6).toFixed(1) + ' Mbps';
  if (bits >= 1e3) return (bits / 1e3).toFixed(0) + ' Kbps';
  return Math.round(bits) + ' bps';
};

const LiveAreaChart = ({ history = [] }) => {
  const { t } = useTranslation();
  const data = (history.length ? history : [{ down: 0, up: 0, at: 0 }]).map((p, i) => ({
    i,
    down: Number(p.down || 0),
    up: Number(p.up || 0),
  }));

  const tooltipStyle = {
    background: 'rgba(13, 16, 23, 0.94)',
    border: '1px solid rgba(148, 163, 184, 0.25)',
    borderRadius: 12,
    fontSize: 12,
    color: '#f2f3f7',
    boxShadow: '0 12px 32px rgba(0,0,0,.45)',
  };

  return (
    <div className="ov-chart-wrap" style={{ width: '100%', height: 200 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="pvDownFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.55} />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.04} />
            </linearGradient>
            <linearGradient id="pvUpFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ff8a2a" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#ff8a2a" stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <XAxis dataKey="i" hide />
          <YAxis
            width={64}
            tick={{ fill: '#9aa3b5', fontSize: 10 }}
            tickFormatter={fmtBits}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelFormatter={() => ''}
            formatter={(value, name) => [
              fmtBits(value),
              name === 'down' ? t('ui.e2ff93e8b816', 'Download') : t('ui.92dcf820e9f9', 'Upload'),
            ]}
          />
          <Area
            type="monotone"
            dataKey="down"
            stroke="#22d3ee"
            strokeWidth={2}
            fill="url(#pvDownFill)"
            isAnimationActive={false}
            dot={false}
          />
          <Area
            type="monotone"
            dataKey="up"
            stroke="#ff8a2a"
            strokeWidth={2}
            fill="url(#pvUpFill)"
            isAnimationActive={false}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default LiveAreaChart;
