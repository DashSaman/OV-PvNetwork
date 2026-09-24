import { t } from "../i18n";
import { useEffect, useMemo, useRef, useState } from 'react';
import apiClient from '../services/api';
import { FiActivity, FiClock, FiCpu, FiDownload, FiHardDrive, FiMoon, FiServer, FiSun, FiUpload, FiUsers } from 'react-icons/fi';
import { BsDeviceSsd } from 'react-icons/bs';
import { useTranslation } from 'react-i18next';

// PVNETWORK_DASHBOARD_REAL_OPENVPN_ONLINE_V1
const SAMPLE_INTERVAL = 1000;
const HISTORY_POINTS = 100;
const formatBytes = (value, decimals = 2) => {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const number = bytes / Math.pow(1024, index);
  return `${number.toFixed(index === 0 ? 0 : decimals)} ${units[index]}`;
};
const formatRate = bytesPerSecond => {
  const value = Math.max(0, Number(bytesPerSecond || 0)) * 8;
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)} Gbps`;
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)} Mbps`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)} Kbps`;
  }
  return `${Math.round(value)} bps`;
};
const formatUptime = seconds => {
  const value = Math.max(0, Number(seconds || 0));
  const days = Math.floor(value / 86400);
  const hours = Math.floor(value % 86400 / 3600);
  const minutes = Math.floor(value % 3600 / 60);
  if (days > 0) {
    return `${days}d ${hours}h`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
};
const clampPercent = value => Math.max(0, Math.min(100, Number(value || 0)));
const nodeVisual = (name = '') => {
  const key = name.toLowerCase();
  if (key.includes('finland')) {
    return {
      flag: '🇫🇮',
      accent: '#38bdf8'
    };
  }
  if (key.includes('usa')) {
    return {
      flag: '🇺🇸',
      accent: '#818cf8'
    };
  }
  if (key.includes('germany')) {
    return {
      flag: '🇩🇪',
      accent: '#facc15'
    };
  }
  if (key.includes('turkey')) {
    return {
      flag: '🇹🇷',
      accent: '#fb7185'
    };
  }
  return {
    flag: '🌐',
    accent: '#34d399'
  };
};
const MetricBox = ({
  icon,
  label,
  value,
  hint,
  accent
}) => <div className="ov-metric-box">
    <div className="ov-metric-icon" style={{
    color: accent,
    background: `${accent}18`
  }}>
      {icon}
    </div>

    <div className="ov-metric-content">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint && <small>{hint}</small>}
    </div>
  </div>;
const LiveChart = ({
  history
}) => {
  const width = 1000;
  const height = 190;
  const padding = 8;
  const points = history.length ? history : [{
    down: 0,
    up: 0
  }];
  const maxValue = Math.max(1, ...points.map(point => Math.max(point.down || 0, point.up || 0)));
  const buildPoints = key => points.map((point, index) => {
    const x = points.length <= 1 ? 0 : index / (points.length - 1) * width;
    const ratio = Number(point[key] || 0) / maxValue;
    const y = height - padding - ratio * (height - padding * 2);
    return `${x},${y}`;
  }).join(' ');
  return <div className="ov-chart-wrap">
      <svg className="ov-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={t("ui.3c303fbd4264")}>
        <defs>
          <linearGradient id="downloadGlow" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#22d3ee" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>

          <linearGradient id="uploadGlow" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#a78bfa" />
            <stop offset="100%" stopColor="#ec4899" />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75].map(ratio => <line key={ratio} x1="0" x2={width} y1={height * ratio} y2={height * ratio} className="ov-chart-grid" />)}

        <polyline points={buildPoints('down')} fill="none" stroke="url(#downloadGlow)" strokeWidth="5" vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" />

        <polyline points={buildPoints('up')} fill="none" stroke="url(#uploadGlow)" strokeWidth="4" vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" />
      </svg>

      <div className="ov-chart-caption">
        <span>
          <i className="ov-dot ov-dot-down" />{t("ui.a479c9c34e87")}</span>

        <span>
          <i className="ov-dot ov-dot-up" />{t("ui.8bdf057f91e7")}</span>

        <span className="ov-chart-window">{t("ui.1f58be29707f")}</span>
      </div>
    </div>;
};
const ProgressLine = ({
  label,
  value,
  accent
}) => {
  const percent = clampPercent(value);
  return <div className="ov-progress-line">
      <div className="ov-progress-title">
        <span>{label}</span>
        <strong>
          {percent.toFixed(1)}%
        </strong>
      </div>

      <div className="ov-progress-track">
        <div className="ov-progress-fill" style={{
        width: `${percent}%`,
        background: accent
      }} />
      </div>
    </div>;
};
const NodeCard = ({
  node,
  metric,
  online
}) => {
  const visual = nodeVisual(node.name);
  const available = Boolean(metric?.available);
  const sampled = Boolean(metric?.ready);
  return <div className="ov-node-card" style={{
    borderTopColor: visual.accent
  }}>
      <div className="ov-node-header">
        <div className="ov-node-name">
          <span className="ov-node-flag">
            {visual.flag}
          </span>

          <div>
            <strong>{node.name}</strong>
            <small>
              {metric?.network_interface || 'Waiting for metrics'}
            </small>
          </div>
        </div>

        <div className={available ? t("ui.e64c423d3392") : t("ui.c87a9101a464")}>
          <span />
          {available ? t("ui.c3e839df6084") : t("ui.e01fa717bacc")}
        </div>
      </div>

      <div className="ov-node-speed-grid">
        <div>
          <span className="download">{t("ui.a8acf221de4c")}</span>
          <strong>
            {sampled ? formatRate(metric.download) : t("ui.f536b5eaf524")}
          </strong>
        </div>

        <div>
          <span className="upload">{t("ui.71887a34a9be")}</span>
          <strong>
            {sampled ? formatRate(metric.upload) : t("ui.f536b5eaf524")}
          </strong>
        </div>
      </div>

      <div className="ov-node-facts">
        <div>
          <span>{t("ui.c3e839df6084")}</span>
          <strong>{online}</strong>
        </div>

        <div>
          <span>{t("ui.3d139ce07b92")}</span>
          <strong>
            {formatBytes(metric?.traffic_bytes)}
          </strong>
        </div>

        <div>
          <span>{t("ui.6aafa80cab6f")}</span>
          <strong>
            {formatUptime(metric?.uptime)}
          </strong>
        </div>
      </div>

      <div className="ov-node-progress">
        <ProgressLine label="CPU" value={metric?.cpu_usage} accent={visual.accent} />

        <ProgressLine label="RAM" value={metric?.memory_usage} accent={visual.accent} />
      </div>
    </div>;
};
const ServerStats = () => {
  const {
    t
  } = useTranslation();
  const [stats, setStats] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [dashboardError, setDashboardError] = useState('');
  const [nodeMetrics, setNodeMetrics] = useState({});
  const [presence, setPresence] = useState({ online_users: null });
  const [history, setHistory] = useState([]);
  const [panelVersion, setPanelVersion] = useState('');
  const [themeMode, setThemeMode] = useState(() => {
    if (typeof window === 'undefined') {
      return 'dark';
    }
    const saved = window.localStorage.getItem('ov-dashboard-theme');
    if (saved === 'dark' || saved === 'light') {
      return saved;
    }
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  });
  const metricsRef = useRef({});
  const pollBusy = useRef(false);
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('ov-dashboard-theme', themeMode);

      // PVNETWORK_GLOBAL_THEME_SYNC_V2
      document.documentElement.setAttribute('data-ov-theme', themeMode);
      document.body.setAttribute('data-ov-theme', themeMode);
    }
  }, [themeMode]);
  useEffect(() => {
    let active = true;
    // PVNETWORK_PANEL_VERSION_BADGE_V1
    fetch('/healthz', { cache: 'no-store' })
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        if (active && data && typeof data.version === 'string' && data.version) {
          setPanelVersion(data.version);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    const fetchServer = async () => {
      try {
        const response = await apiClient.get('/server/info', {
          timeout: 10000
        });
        if (active && response.data?.success) {
          setStats(response.data.data);
        }
      } catch (error) {
        if (active) setDashboardError(error?.response?.data?.detail || error.message || 'Unable to load server information.');
      }
    };
    const fetchNodes = async () => {
      try {
        const response = await apiClient.get('/nodes/', {
          timeout: 10000
        });
        if (active && response.data?.success) {
          setNodes(response.data.data || []);
        }
      } catch (error) {
        if (active) setDashboardError(error?.response?.data?.detail || error.message || 'Unable to load nodes.');
      }
    };
    fetchServer();
    fetchNodes();
    const serverTimer = setInterval(fetchServer, 15000);
    const onlineTimer = null;
    return () => {
      active = false;
      clearInterval(serverTimer);
      clearInterval(onlineTimer);
    };
  }, []);
  useEffect(() => {
    if (!nodes.length) {
      return undefined;
    }
    let active = true;

    // PVNETWORK_DASHBOARD_AGGREGATED_POLL_V1
    const pollNodes = async () => {
      if (
        !active ||
        pollBusy.current ||
        (
          typeof document !== 'undefined' &&
          document.hidden
        )
      ) {
        return;
      }
      pollBusy.current = true;
      try {
        const response = await apiClient.get('/server/dashboard-live', {
          timeout: 10000
        });
        const payload =
          response.data?.data || {};

        const rows =
          payload.nodes || [];
        if (active && payload.presence) {
          setPresence(payload.presence);
        }

        /*
         * PVNETWORK_RATE_SAMPLE_TIME_V1
         *
         * Rate is calculated only from a genuinely
         * new backend counter sample.
         *
         * Cached/repeated responses never generate
         * fake zero or spike values.
         */

        const next = {
          ...metricsRef.current
        };

        rows.forEach(info => {

          const nodeId =
            Number(info.id);

          if (
            !nodeId ||
            !info.available
          ) {

            next[nodeId] = {
              ...(next[nodeId] || {}),
              available: false,
              ready: false,
              download: 0,
              upload: 0,
              online_count: 0,
              online_sessions: 0
            };

            return;
          }


          /*
           * PVNETWORK_FRONTEND_SERVER_RATE_V2
           *
           * Rate is calculated by the backend with
           * per-node timestamps and a rolling window.
           * Browser timing is NOT used anymore.
           */
          const rx =
            Number(
              info.rx_bytes || 0
            );
          
          const tx =
            Number(
              info.tx_bytes || 0
            );
          
          const download =
            Number(
              info.download_bps || 0
            );
          
          const upload =
            Number(
              info.upload_bps || 0
            );
          
          const ready =
            Boolean(
              info.rate_ready
            );
          
          next[nodeId] = {
            available: true,
            ready,

            download:
              Math.max(
                0,
                download
              ),

            upload:
              Math.max(
                0,
                upload
              ),

            rx_bytes: rx,
            tx_bytes: tx,

            traffic_bytes:
              Number(
                info.traffic_bytes
                ?? rx + tx
              ),

            cpu_usage:
              Number(
                info.cpu_usage || 0
              ),

            memory_usage:
              Number(
                info.memory_usage || 0
              ),

            uptime:
              Number(
                info.uptime || 0
              ),

            boot_time:
              Number(
                info.boot_time || 0
              ),

            network_interface:
              info.network_interface || '',

            online_count:
              Number(
                info.online_count || 0
              ),

            online_sessions:
              Number(
                info.online_sessions || 0
              )
          };
        });

        metricsRef.current = next;
        if (active) {
          setNodeMetrics(next);
          const liveTotals = Object.values(next).filter(metric => metric.available && metric.ready).reduce((acc, metric) => {
            acc.down += metric.download || 0;
            acc.up += metric.upload || 0;
            return acc;
          }, {
            down: 0,
            up: 0
          });
          setHistory(old => [...old, liveTotals].slice(-HISTORY_POINTS));
        }
      } catch (error) {
        /*
         * PVNETWORK_DASHBOARD_TRANSIENT_FAILOPEN_V1
         *
         * A temporary slow/offline node must not break
         * the whole admin dashboard.
         *
         * Keep the last valid metrics and retry on the
         * next poll automatically.
         */
        if (active) {
          console.warn(
            'Dashboard live metrics transient failure:',
            error?.message || error
          );
        }
      } finally {
        pollBusy.current = false;
      }
    };
    pollNodes();
    const timer = setInterval(pollNodes, SAMPLE_INTERVAL);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [nodes]);
  const totals = useMemo(() => {
    let download = 0;
    let upload = 0;
    let traffic = 0;
    let activeNodes = 0;
    let sampledNodes = 0;
    let nodeOnline = 0;
    let onlineSessions = 0;
    nodes.forEach(node => {
      const metric = nodeMetrics[node.id];
      if (!metric || !metric.available) {
        return;
      }
      activeNodes += 1;
      nodeOnline += Number(metric.online_count || 0);
      onlineSessions += Number(metric.online_sessions || 0);
      traffic += Number(metric.traffic_bytes || 0);
      if (metric.ready) {
        sampledNodes += 1;
        download += Number(metric.download || 0);
        upload += Number(metric.upload || 0);
      }
    });
    return {
      download,
      upload,
      live: download + upload,
      traffic,
      activeNodes,
      sampledNodes,
      online: presence.online_users !== null
        && presence.online_users !== undefined
        && Number.isFinite(Number(presence.online_users))
        ? Number(presence.online_users)
        : nodeOnline,
      onlineSessions
    };
  }, [nodes, nodeMetrics, presence]);
  const liveReady = totals.sampledNodes > 0;
  return <div id="dashboard-view" className="view ovdash" data-theme={themeMode}>
      {dashboardError && <div className="monitor-form">
        <p className="error-message">{dashboardError}</p>
        <button className="btn" onClick={() => window.location.reload()}>
          {t('retry', 'Retry')}
        </button>
      </div>}
      <style>{`
        .ovdash {
          --ov-accent-cyan: #22d3ee;
          --ov-accent-blue: #3b82f6;
          --ov-accent-purple: #c084fc;
          --ov-accent-green: #34d399;
          --ov-accent-orange: #fb923c;
          --ov-accent-pink: #f472b6;
          --ov-radius: 18px;
          color: var(--ov-text);
          background: var(--ov-page-bg);
          border-radius: 20px;
          transition:
            background .25s ease,
            color .25s ease;
        }

        .ovdash[data-theme="dark"] {
          --ov-page-bg:
            linear-gradient(
              180deg,
              rgba(10, 14, 24, .35),
              rgba(15, 23, 42, .12)
            );
          --ov-bg:
            linear-gradient(
              145deg,
              rgba(12, 21, 39, .96),
              rgba(9, 18, 34, .88)
            );
          --ov-surface-soft:
            rgba(10, 18, 32, .52);
          --ov-chip-bg:
            rgba(148, 163, 184, .06);
          --ov-chart-bg:
            rgba(2, 6, 23, .32);
          --ov-border:
            rgba(148, 163, 184, .14);
          --ov-border-soft:
            rgba(148, 163, 184, .10);
          --ov-grid:
            rgba(148, 163, 184, .11);
          --ov-text:
            #e5eefb;
          --ov-muted:
            #94a3b8;
          --ov-subtle:
            #64748b;
          --ov-hero-bg:
            radial-gradient(
              circle at 15% 15%,
              rgba(34, 211, 238, .15),
              transparent 34%
            ),
            radial-gradient(
              circle at 85% 15%,
              rgba(168, 85, 247, .16),
              transparent 38%
            ),
            linear-gradient(
              145deg,
              rgba(9, 20, 41, .98),
              rgba(25, 22, 58, .94)
            );
          --ov-hero-border:
            rgba(99, 102, 241, .20);
          --ov-hero-label:
            #a5b4fc;
          --ov-hero-value:
            #f8fafc;
          --ov-hero-shadow:
            0 0 35px rgba(56, 189, 248, .18);
          --ov-hero-orb:
            rgba(59, 130, 246, .14);
          --ov-card-shadow:
            0 12px 35px rgba(0, 0, 0, .15);
          --ov-toggle-bg:
            rgba(15, 23, 42, .72);
        }

        .ovdash[data-theme="light"] {
          --ov-page-bg:
            linear-gradient(
              180deg,
              rgba(248, 250, 252, .92),
              rgba(241, 245, 249, .96)
            );
          --ov-bg:
            linear-gradient(
              145deg,
              rgba(255, 255, 255, .97),
              rgba(247, 250, 252, .98)
            );
          --ov-surface-soft:
            rgba(241, 245, 249, .92);
          --ov-chip-bg:
            rgba(226, 232, 240, .58);
          --ov-chart-bg:
            rgba(248, 250, 252, .92);
          --ov-border:
            rgba(148, 163, 184, .22);
          --ov-border-soft:
            rgba(148, 163, 184, .18);
          --ov-grid:
            rgba(148, 163, 184, .20);
          --ov-text:
            #0f172a;
          --ov-muted:
            #475569;
          --ov-subtle:
            #64748b;
          --ov-hero-bg:
            radial-gradient(
              circle at 15% 15%,
              rgba(34, 211, 238, .12),
              transparent 34%
            ),
            radial-gradient(
              circle at 85% 15%,
              rgba(168, 85, 247, .10),
              transparent 38%
            ),
            linear-gradient(
              145deg,
              rgba(255, 255, 255, .98),
              rgba(240, 249, 255, .96)
            );
          --ov-hero-border:
            rgba(99, 102, 241, .18);
          --ov-hero-label:
            #4338ca;
          --ov-hero-value:
            #0f172a;
          --ov-hero-shadow:
            none;
          --ov-hero-orb:
            rgba(99, 102, 241, .10);
          --ov-card-shadow:
            0 10px 26px rgba(15, 23, 42, .07);
          --ov-toggle-bg:
            rgba(255, 255, 255, .82);
        }

        .ovdash * {
          box-sizing: border-box;
        }

        .ov-dashboard-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 18px;
        }

        .ov-dashboard-header h2 {
          margin: 0;
          color: var(--ov-text);
        }

        .ov-dashboard-header-tools {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
          justify-content: flex-end;
        }

        .ov-theme-toggle {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 9px 14px;
          border-radius: 999px;
          border: 1px solid var(--ov-border);
          background: var(--ov-toggle-bg);
          color: var(--ov-text);
          cursor: pointer;
          font-size: 12px;
          font-weight: 700;
          transition:
            all .2s ease;
          box-shadow: var(--ov-card-shadow);
        }

        .ov-theme-toggle:hover {
          transform: translateY(-1px);
          border-color: var(--ov-accent-blue);
        }

        .ov-live-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 7px 12px;
          border-radius: 999px;
          background:
            rgba(34, 197, 94, .10);
          border:
            1px solid
            rgba(34, 197, 94, .22);
          color: #16a34a;
          font-size: 12px;
          font-weight: 700;
        }

        .ov-live-badge i {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #22c55e;
          box-shadow:
            0 0 16px #22c55e;
        }

        .ov-version-badge {
          display: inline-flex;
          align-items: center;
          padding: 7px 12px;
          border-radius: 999px;
          border: 1px solid var(--ov-border);
          background: var(--ov-toggle-bg);
          color: var(--ov-text);
          opacity: .75;
          font-size: 12px;
          font-weight: 700;
          letter-spacing: .02em;
          font-variant-numeric: tabular-nums;
        }

        .ov-hero {
          position: relative;
          overflow: hidden;
          padding: 30px;
          border-radius: 24px;
          border:
            1px solid
            var(--ov-hero-border);
          background: var(--ov-hero-bg);
          box-shadow: var(--ov-card-shadow);
          margin-bottom: 18px;
        }

        .ov-hero::after {
          content: "";
          position: absolute;
          width: 260px;
          height: 260px;
          right: -110px;
          top: -140px;
          border-radius: 50%;
          background: var(--ov-hero-orb);
          filter: blur(8px);
          pointer-events: none;
        }

        .ov-hero-label {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          color: var(--ov-hero-label);
          font-size: 13px;
          letter-spacing: 1.7px;
          font-weight: 800;
          text-transform: uppercase;
        }

        .ov-hero-value {
          position: relative;
          z-index: 1;
          text-align: center;
          margin:
            12px 0 22px;
          font-size:
            clamp(
              44px,
              7vw,
              84px
            );
          line-height: 1;
          font-weight: 850;
          letter-spacing: -3px;
          color: var(--ov-hero-value);
          text-shadow: var(--ov-hero-shadow);
        }

        .ov-hero-rates {
          display: grid;
          grid-template-columns:
            repeat(2, minmax(0, 1fr));
          gap: 12px;
          max-width: 740px;
          margin:
            0 auto 18px;
        }

        .ov-hero-rate {
          padding: 15px 18px;
          border-radius: 16px;
          background: var(--ov-surface-soft);
          border:
            1px solid
            var(--ov-border);
          text-align: center;
        }

        .ov-hero-rate span {
          display: block;
          color: var(--ov-muted);
          font-size: 12px;
          margin-bottom: 5px;
        }

        .ov-hero-rate strong {
          color: #f8fafc;
          font-size: 22px;
        }

        .ov-hero-rate.download strong {
          color: #22d3ee;
        }

        .ov-hero-rate.upload strong {
          color: #c084fc;
        }

        .ov-chart-wrap {
          position: relative;
          z-index: 1;
          margin-top: 8px;
          padding:
            14px 14px 10px;
          border-radius: 17px;
          background: var(--ov-chart-bg);
          border:
            1px solid
            var(--ov-border-soft);
        }

        .ov-chart {
          display: block;
          width: 100%;
          height: 190px;
        }

        .ov-chart-grid {
          stroke: var(--ov-grid);
          stroke-width: 1;
        }

        .ov-chart-caption {
          display: flex;
          align-items: center;
          gap: 18px;
          margin-top: 8px;
          color: var(--ov-muted);
          font-size: 11px;
        }

        .ov-chart-caption span {
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }

        .ov-chart-window {
          margin-left: auto;
        }

        .ov-dot {
          display: inline-block;
          width: 7px;
          height: 7px;
          border-radius: 50%;
        }

        .ov-dot-down {
          background: #22d3ee;
          box-shadow:
            0 0 9px #22d3ee;
        }

        .ov-dot-up {
          background: #c084fc;
          box-shadow:
            0 0 9px #c084fc;
        }

        .ov-summary-grid {
          display: grid;
          grid-template-columns:
            repeat(4, minmax(0, 1fr));
          gap: 14px;
          margin-bottom: 24px;
        }

        .ov-metric-box {
          min-height: 104px;
          display: flex;
          align-items: center;
          gap: 13px;
          padding: 17px;
          border:
            1px solid var(--ov-border);
          border-radius: 18px;
          background: var(--ov-bg);
          box-shadow: var(--ov-card-shadow);
        }

        .ov-metric-icon {
          width: 46px;
          height: 46px;
          flex: 0 0 46px;
          display: grid;
          place-items: center;
          border-radius: 14px;
          font-size: 21px;
        }

        .ov-metric-content {
          min-width: 0;
        }

        .ov-metric-content span {
          display: block;
          color: var(--ov-muted);
          font-size: 11px;
          margin-bottom: 4px;
        }

        .ov-metric-content strong {
          display: block;
          color: var(--ov-text);
          font-size: 20px;
          white-space: nowrap;
        }

        .ov-metric-content small {
          display: block;
          color: #64748b;
          font-size: 10px;
          margin-top: 3px;
        }

        .ov-section-title {
          margin:
            26px 0 12px;
          display: flex;
          align-items: center;
          gap: 9px;
          font-size: 15px;
          font-weight: 750;
        }

        .ov-node-grid {
          display: grid;
          grid-template-columns:
            repeat(2, minmax(0, 1fr));
          gap: 15px;
        }

        .ov-node-card {
          border:
            1px solid var(--ov-border);
          border-top:
            3px solid #38bdf8;
          border-radius: 19px;
          padding: 18px;
          background: var(--ov-bg);
          box-shadow: var(--ov-card-shadow);
        }

        .ov-node-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 17px;
        }

        .ov-node-name {
          display: flex;
          align-items: center;
          gap: 11px;
        }

        .ov-node-flag {
          font-size: 27px;
        }

        .ov-node-name strong {
          display: block;
          color: var(--ov-text);
          font-size: 17px;
        }

        .ov-node-name small {
          display: block;
          color: var(--ov-muted);
          margin-top: 2px;
          font-size: 10px;
        }

        .ov-status-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 9px;
          border-radius: 999px;
          font-size: 10px;
          font-weight: 750;
        }

        .ov-status-pill span {
          width: 7px;
          height: 7px;
          border-radius: 50%;
        }

        .ov-status-pill.online {
          color: #4ade80;
          background:
            rgba(34, 197, 94, .10);
        }

        .ov-status-pill.online span {
          background: #22c55e;
          box-shadow:
            0 0 9px #22c55e;
        }

        .ov-status-pill.offline {
          color: #fb7185;
          background:
            rgba(244, 63, 94, .10);
        }

        .ov-status-pill.offline span {
          background: #f43f5e;
        }

        .ov-node-speed-grid {
          display: grid;
          grid-template-columns:
            repeat(2, minmax(0, 1fr));
          gap: 10px;
          margin-bottom: 14px;
        }

        .ov-node-speed-grid > div {
          padding: 12px;
          border-radius: 13px;
          background: var(--ov-surface-soft);
          border:
            1px solid
            var(--ov-border-soft);
        }

        .ov-node-speed-grid span {
          display: block;
          font-size: 10px;
          margin-bottom: 5px;
        }

        .ov-node-speed-grid .download {
          color: #22d3ee;
        }

        .ov-node-speed-grid .upload {
          color: #c084fc;
        }

        .ov-node-speed-grid strong {
          display: block;
          color: var(--ov-text);
          font-size: 17px;
        }

        .ov-node-facts {
          display: grid;
          grid-template-columns:
            repeat(3, minmax(0, 1fr));
          gap: 9px;
          margin-bottom: 16px;
        }

        .ov-node-facts > div {
          padding: 10px;
          text-align: center;
          border-radius: 12px;
          background: var(--ov-chip-bg);
        }

        .ov-node-facts span {
          display: block;
          color: var(--ov-muted);
          font-size: 9px;
          margin-bottom: 4px;
        }

        .ov-node-facts strong {
          color: var(--ov-text);
          font-size: 13px;
        }

        .ov-node-progress {
          display: grid;
          gap: 10px;
        }

        .ov-progress-title {
          display: flex;
          justify-content: space-between;
          color: var(--ov-muted);
          font-size: 10px;
          margin-bottom: 5px;
        }

        .ov-progress-title strong {
          color: var(--ov-text);
        }

        .ov-progress-track {
          height: 6px;
          overflow: hidden;
          border-radius: 999px;
          background:
            rgba(148, 163, 184, .12);
        }

        .ov-progress-fill {
          height: 100%;
          border-radius: inherit;
          transition:
            width .35s ease;
        }

        .pvnetwork-panel-grid {
          display: grid;
          grid-template-columns:
            repeat(4, minmax(0, 1fr));
          gap: 12px;
        }

        .ov-footnote {
          margin-top: 16px;
          color: var(--ov-subtle);
          font-size: 10px;
          text-align: center;
        }

        @media (max-width: 1050px) {
          .ov-summary-grid,
          .pvnetwork-panel-grid {
            grid-template-columns:
              repeat(2, minmax(0, 1fr));
          }
        }

        @media (max-width: 760px) {
          .ov-hero {
            padding: 20px 14px;
            border-radius: 18px;
          }

          .ov-hero-value {
            letter-spacing: -2px;
          }

          .ov-hero-rates,
          .ov-summary-grid,
          .pvnetwork-panel-grid,
          .ov-node-grid {
            grid-template-columns: 1fr;
          }

          .ov-chart {
            height: 150px;
          }

          .ov-node-speed-grid {
            grid-template-columns: 1fr 1fr;
          }
        }
      `}</style>


      <div className="ov-dashboard-header">
        <h2>{t('dashboard')}</h2>

        <div className="ov-dashboard-header-tools">
          <button type="button" className="ov-theme-toggle" onClick={() => setThemeMode(prev => prev === 'dark' ? t("ui.dfccc06f1441") : t("ui.3d09ba44760d"))} title={themeMode === 'dark' ? t("ui.fc4509124987") : t("ui.c29220f9585c")}>
            {themeMode === 'dark' ? <>
                <FiSun />
                <span>{t("ui.a36ef8aba229")}</span>
              </> : <>
                <FiMoon />
                <span>{t("ui.ae1ef0143294")}</span>
              </>}
          </button>

          <div className="ov-live-badge">
            <i />{t("ui.2efef14fa30b")}</div>
          {panelVersion && <div className="ov-version-badge">v{panelVersion}</div>}
        </div>
      </div>


      <section className="ov-hero">
        <div className="ov-hero-label">
          <FiActivity />{t("ui.4c6882a75164")}</div>

        <div className="ov-hero-value">
          {liveReady ? formatRate(totals.live) : t("ui.f536b5eaf524")}
        </div>

        <div className="ov-hero-rates">
          <div className="ov-hero-rate download">
            <span>{t("ui.e2ff93e8b816")}</span>

            <strong>
              {liveReady ? formatRate(totals.download) : '—'}
            </strong>
          </div>

          <div className="ov-hero-rate upload">
            <span>{t("ui.92dcf820e9f9")}</span>

            <strong>
              {liveReady ? formatRate(totals.upload) : '—'}
            </strong>
          </div>
        </div>

        <LiveChart history={history} />
      </section>


      <div className="ov-summary-grid">
        <MetricBox icon={<FiUsers />} label="Online Users" value={Number(totals.online || 0).toLocaleString()} hint={`${Number(totals.onlineSessions || 0)} active OpenVPN session${Number(totals.onlineSessions || 0) === 1 ? '' : t("ui.a0f1490a20d0")}`} accent="#34d399" />

        <MetricBox icon={<FiServer />} label="Active Nodes" value={`${totals.activeNodes} / ${nodes.length}`} hint="Realtime node health" accent="#60a5fa" />

        <MetricBox icon={<FiDownload />} label="Traffic Since Boot" value={formatBytes(totals.traffic)} hint="Combined RX + TX" accent="#22d3ee" />

        <MetricBox icon={<FiClock />} label="Sample Interval" value="Realtime" hint="No per-user polling" accent="#c084fc" />
      </div>


      <h3 className="ov-section-title">
        <FiServer />{t("ui.092505a4182e")}</h3>

      <div className="ov-node-grid">
        {nodes.map(node => <NodeCard
          key={node.id}
          node={node}
          metric={nodeMetrics[node.id]}
          online={Number(
            presence.managed_online_by_node?.[node.id]
            ?? nodeMetrics[node.id]?.online_count
            ?? 0
          )}
        />)}
      </div>


      {stats && <>
          <h3 className="ov-section-title">
            <FiCpu />{t("ui.88a55778015f")}</h3>

          <div className="pvnetwork-panel-grid">
            <MetricBox icon={<FiCpu />} label="Panel CPU" value={`${Number(stats.cpu || 0).toFixed(1)}%`} accent="#fb923c" />

            <MetricBox icon={<BsDeviceSsd />} label="Panel RAM" value={`${Number(stats.memory_percent || 0).toFixed(1)}%`} hint={`${formatBytes(stats.memory_used)} / ${formatBytes(stats.memory_total)}`} accent="#34d399" />

            <MetricBox icon={<FiHardDrive />} label="Panel Disk" value={`${Number(stats.disk_percent || 0).toFixed(1)}%`} hint={`${formatBytes(stats.disk_used)} / ${formatBytes(stats.disk_total)}`} accent="#60a5fa" />

            <MetricBox icon={<FiClock />} label="Panel Uptime" value={formatUptime(stats.uptime)} accent="#a78bfa" />
          </div>
        </>}


      <div className="ov-footnote">{t("ui.47ada210814e")}</div>
    </div>;
};
export default ServerStats;
