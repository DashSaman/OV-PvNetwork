/* PVN-1017 — per-node mini sparkline (recharts, lazy chunk shared with
   the dashboard area chart). Receives per-node download/upload history. */
import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts';

const fmtBits = value => {
  const bits = Math.max(0, Number(value || 0));
  if (bits >= 1e9) return (bits / 1e9).toFixed(2) + ' Gbps';
  if (bits >= 1e6) return (bits / 1e6).toFixed(1) + ' Mbps';
  if (bits >= 1e3) return (bits / 1e3).toFixed(0) + ' Kbps';
  return Math.round(bits) + ' bps';
};

const NodeSparkline = ({ history = [], accent = '#22d3ee' }) => {
  const data = history.map((p, i) => ({ i, down: Number(p.down || 0), up: Number(p.up || 0) }));
  return (
    <div style={{ width: '100%', height: 56 }} aria-hidden="true">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={'sparkFill-' + accent.replace('#', '')} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={accent} stopOpacity={0.5} />
              <stop offset="100%" stopColor={accent} stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <Tooltip
            contentStyle={{
              background: 'rgba(13,16,23,.94)',
              border: '1px solid rgba(148,163,184,.25)',
              borderRadius: 10,
              fontSize: 11,
              color: '#f2f3f7',
            }}
            labelFormatter={() => ''}
            formatter={value => [fmtBits(value), '']}
            itemStyle={{ padding: 0 }}
          />
          <Area
            type="monotone"
            dataKey="down"
            stroke={accent}
            strokeWidth={1.6}
            fill={`url(#sparkFill-${accent.replace('#', '')})`}
            isAnimationActive={false}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default NodeSparkline;
