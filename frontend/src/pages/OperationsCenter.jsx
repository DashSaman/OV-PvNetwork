import { t } from "../i18n";
import { useEffect, useMemo, useState } from 'react';
import apiClient from '../services/api';
const gb = value => `${(Number(value || 0) / 1073741824).toFixed(2)} GB`;
function UsageChart({
  rows
}) {
  const points = useMemo(() => {
    if (!rows.length) return '';
    const maximum = Math.max(...rows.map(row => Number(row.total || row.used || 1)), 1);
    return rows.map((row, index) => {
      const x = rows.length === 1 ? 0 : index * 100 / (rows.length - 1);
      const y = 100 - Number(row.used || 0) * 100 / maximum;
      return `${x},${y}`;
    }).join(' ');
  }, [rows]);
  if (!rows.length) return <p>{t("ui.dbb117827368")}</p>;
  return <div style={{
    direction: 'ltr',
    width: '100%'
  }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{
      width: '100%',
      height: 260,
      overflow: 'visible'
    }}>
        {[0, 25, 50, 75, 100].map(y => <line key={y} x1="0" x2="100" y1={y} y2={y} stroke="rgba(255,255,255,.12)" strokeWidth=".4" />)}
        <polyline points={points} fill="none" stroke="#ff7a1a" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      <div style={{
      display: 'flex',
      justifyContent: 'space-between'
    }}>
        <span>
          {new Date(rows[0].sampled_at * 1000).toLocaleDateString()}
        </span>
        <span>{t("ui.b4e264030f2a")}{gb(rows.at(-1)?.used)}</span>
        <span>
          {new Date(rows.at(-1).sampled_at * 1000).toLocaleDateString()}
        </span>
      </div>
    </div>;
}
export default function OperationsCenter() {
  const [dashboard, setDashboard] = useState(null);
  const [audit, setAudit] = useState([]);
  const [uuids, setUuids] = useState('');
  const [source, setSource] = useState('');
  const [target, setTarget] = useState('');
  const [historyUuid, setHistoryUuid] = useState('');
  const [history, setHistory] = useState([]);
  const [rebalance, setRebalance] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const errorText = exception =>
    exception?.response?.data?.detail ||
    exception?.response?.data?.msg ||
    exception?.message ||
    'Operation failed. Please try again.';

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [dashboardResponse, auditResponse] = await Promise.all([
        apiClient.get('/operations/dashboard'),
        apiClient.get('/operations/audit')
      ]);
      setDashboard(dashboardResponse.data.data);
      setAudit(auditResponse.data.data || []);
    } catch (exception) {
      setError(errorText(exception));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const runAction = async request => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const response = await request();
      setMessage(
        response.data.msg ||
        JSON.stringify(response.data.data || {})
      );
      return response;
    } catch (exception) {
      setError(errorText(exception));
      return null;
    } finally {
      setBusy(false);
    }
  };
  const parsedUuids = () => uuids.split(/[\s,]+/).filter(Boolean);
  const bulk = action => runAction(() =>
    apiClient.post('/operations/users/bulk', {
      user_uuids: parsedUuids(),
      action
    })
  );

  const transfer = () => runAction(() =>
    apiClient.post('/operations/users/transfer', {
      source_node_id: Number(source),
      target_node_id: Number(target),
      user_uuids: uuids ? parsedUuids() : null
    })
  );

  const loadHistory = async () => {
    setBusy(true);
    setError('');
    try {
      const response = await apiClient.get(
        `/operations/users/${historyUuid}/history?days=30`
      );
      setHistory(response.data.data || []);
    } catch (exception) {
      setError(errorText(exception));
      setHistory([]);
    } finally {
      setBusy(false);
    }
  };
  const autoRebalance = async execute => {
    if (execute && !confirm(t("ui.1181737d4813"))) return;

    const response = await runAction(() =>
      apiClient.post('/operations/rebalance', {
        execute,
        source_node_id: source ? Number(source) : null,
        target_node_id: target ? Number(target) : null,
        limit: 25,
        source_score_max: 45,
        target_score_min: 70
      })
    );

    if (response) {
      setRebalance(response.data.data);
      await load();
    }
  };

  if (loading && !dashboard) {
    return <div className="view">{t("ui.b04ba49f8486")}</div>;
  }

  if (error && !dashboard) {
    return <div className="view">
      <div className="monitor-form">
        <p className="error-message">{error}</p>
        <button className="btn" onClick={load}>
          {t('retry', 'Retry')}
        </button>
      </div>
    </div>;
  }
  return <div className="view">
      <div className="view-header">
        <h2>{t("ui.b1cb39bcd857")}</h2>
        <button className="btn" disabled={loading || busy} onClick={load}>
          {t('retry', 'Refresh')}
        </button>
      </div>

      {error && <div className="monitor-form">
        <p className="error-message">{error}</p>
        <button className="btn" disabled={loading || busy} onClick={load}>
          {t('retry', 'Retry')}
        </button>
      </div>}

      <div className="stats-grid">
        {Object.entries(dashboard).map(([key, value]) => <div className="user-stat-card" key={key}>
            <b>{key}</b>
            <span>
              {key.includes('bytes') ? gb(value) : value}
            </span>
          </div>)}
      </div>

      <div className="monitor-form">
        <h3>{t("ui.034b82bdc12b")}</h3>
        <textarea placeholder={t("ui.bfe22ef374a6")} value={uuids} onChange={e => setUuids(e.target.value)} />
        <button className="btn" disabled={busy} onClick={() => bulk('activate')}>{t("ui.ef4d6437d48e")}</button>
        <button className="btn" disabled={busy} onClick={() => bulk('deactivate')}>{t("ui.0764958e2c62")}</button>
        <button className="btn" disabled={busy} onClick={() => bulk('reset_usage')}>{t("ui.dba0fc8f63c2")}</button>

        <div className="monitor-grid">
          <input placeholder={t("ui.60b232562abe")} value={source} onChange={e => setSource(e.target.value)} />
          <input placeholder={t("ui.1aacb73fc2d2")} value={target} onChange={e => setTarget(e.target.value)} />
        </div>

        <button className="btn" disabled={busy} onClick={transfer}>{t("ui.612914956f66")}</button>
        <button className="btn" disabled={busy} onClick={() => autoRebalance(false)}>{t("ui.00e1ef95fbbe")}</button>
        <button className="btn" disabled={busy} onClick={() => autoRebalance(true)}>{t("ui.4a743eafdae7")}</button>

        {rebalance && <pre style={{
        whiteSpace: 'pre-wrap'
      }}>
            {JSON.stringify(rebalance, null, 2)}
          </pre>}
        <p>{message}</p>
      </div>

      <div className="monitor-form">
        <h3>{t("ui.0afc9e620cbc")}</h3>
        <input placeholder={t("ui.9cb131d260a4")} value={historyUuid} onChange={e => setHistoryUuid(e.target.value)} />
        <button className="btn" disabled={!historyUuid || busy} onClick={loadHistory}>{t("ui.a95e811ee882")}</button>
        <UsageChart rows={history} />
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>{t("ui.6c82e6dd8680")}</th>
              <th>{t("ui.cbd19b5c397e")}</th>
              <th>{t("ui.a1fdaa6b2a84")}</th>
              <th>{t("ui.519e39132bb9")}</th>
              <th>{t("ui.5faa59d4bc37")}</th>
              <th>{t("ui.ea424d38af72")}</th>
            </tr>
          </thead>
          <tbody>
            {audit.map(row => <tr key={row.id}>
                <td>
                  {new Date(row.created_at * 1000).toLocaleString()}
                </td>
                <td>{row.actor}</td>
                <td>{row.action}</td>
                <td>{row.resource}</td>
                <td>{row.success ? t("ui.42a8f651d79f") : t("ui.09fef5d8d9a3")}</td>
                <td>{row.ip_address}</td>
              </tr>)}
          </tbody>
        </table>
      </div>
    </div>;
}
