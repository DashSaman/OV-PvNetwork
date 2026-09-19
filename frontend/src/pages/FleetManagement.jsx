import { t } from "../i18n";
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';
export default function FleetManagement() {
  const { t: translate, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || 'en';
  const tr = useCallback(key => translate(`feature.${key}`), [translate]);
  const [nodes, setNodes] = useState([]);
  const [selected, setSelected] = useState([]);
  const [sshUsername, setSshUsername] = useState('root');
  const [sshPassword, setSshPassword] = useState('');
  const [sshFingerprints, setSshFingerprints] = useState('');
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);
  const [error, setError] = useState('');
  const mounted = useRef(true);
  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const response = await apiClient.get('/fleet/', {
        timeout: 15000
      });
      if (mounted.current) {
        setNodes(response.data.data || []);
        setError('');
      }
    } catch (requestError) {
      if (mounted.current && !silent) {
        setError(requestError.response?.data?.detail || requestError.response?.data?.msg || tr('loadFailed'));
      }
    } finally {
      if (mounted.current && !silent) setLoading(false);
    }
  }, [tr]);
  useEffect(() => {
    mounted.current = true;
    load();
    const timer = window.setInterval(() => {
      load(true);
    }, 10000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [load]);
  useEffect(() => {
    if (!job?.id || !['queued', 'running'].includes(job.state)) return;
    let stopped = false;
    const poll = async () => {
      try {
        const response = await apiClient.get(`/fleet/jobs/${job.id}`, {
          timeout: 12000
        });
        if (!stopped) {
          setJob(response.data.data);
          if (response.data.data?.state === 'succeeded') load(true);
        }
      } catch {
        if (!stopped) setError(tr('loadFailed'));
      }
    };
    poll();
    const timer = window.setInterval(poll, 2500);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.state, load, tr]);
  const updateControl = async (nodeId, payload) => {
    try {
      setError('');
      await apiClient.put(`/fleet/${nodeId}/control`, payload, {
        timeout: 12000
      });
      await load(true);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.response?.data?.msg || tr('loadFailed'));
    }
  };
  const parsedFingerprints = useMemo(() => {
    const result = {};
    for (const rawLine of sshFingerprints.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line) continue;
      const splitAt = line.indexOf('=');
      if (splitAt <= 0) continue;
      const nodeId = Number(line.slice(0, splitAt).trim());
      const fingerprint = line.slice(splitAt + 1).trim();
      if (Number.isInteger(nodeId) && nodeId > 0 && fingerprint) {
        result[nodeId] = fingerprint;
      }
    }
    return result;
  }, [sshFingerprints]);
  const startUpgrade = async () => {
    if (!selected.length || !sshPassword) {
      window.alert(tr('selectNodes'));
      return;
    }
    setUpgrading(true);
    setError('');
    try {
      const response = await apiClient.post('/fleet/upgrade', {
        node_ids: selected,
        ssh_username: sshUsername,
        ssh_password: sshPassword,
        ssh_port: 22,
        canary_node_id: selected[0],
        ssh_fingerprints: parsedFingerprints
      }, {
        timeout: 15000
      });
      setSshPassword('');
      setJob({
        id: response.data.data.job_id,
        state: 'queued',
        stage: 'queued'
      });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.response?.data?.msg || tr('loadFailed'));
    } finally {
      setUpgrading(false);
    }
  };
  const retryJob = async () => {
    if (!job?.id || !sshPassword) {
      window.alert(tr('selectNodes'));
      return;
    }
    setUpgrading(true);
    setError('');
    try {
      await apiClient.post(`/fleet/jobs/${job.id}/retry`, {
        ssh_password: sshPassword
      }, {
        timeout: 15000
      });
      setSshPassword('');
      setJob(current => ({
        ...current,
        state: 'queued',
        stage: 'queued',
        error: null
      }));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.response?.data?.msg || tr('loadFailed'));
    } finally {
      setUpgrading(false);
    }
  };
  const displayState = useCallback(node => {
    if (node.maintenance) return tr('maintenance');
    if (node.drain) return tr('drain');
    return tr(node.health || 'offline');
  }, [tr]);
  const sortedNodes = useMemo(() => [...nodes].sort((a, b) => Number(a.id) - Number(b.id)), [nodes]);
  return <div className="view" data-no-translate="true" dir={['fa', 'ar'].includes(language) ? t("ui.dbc9052979a4") : t("ui.61ac44aaabb6")}>
      <div className="view-header">
        <h2>{tr('fleetTitle')}</h2>
      </div>

      <section className="monitor-form">
        <div className="monitor-grid">
          <label>
            {tr('sshUsername')}
            <input value={sshUsername} onChange={event => setSshUsername(event.target.value)} autoComplete="username" />
          </label>

          <label>
            {tr('sshPassword')}
            <input type="password" value={sshPassword} onChange={event => setSshPassword(event.target.value)} autoComplete="current-password" />
          </label>

          <label>
            SSH host fingerprints (optional if already pinned)
            <textarea
              value={sshFingerprints}
              onChange={event => setSshFingerprints(event.target.value)}
              placeholder={'12=SHA256:...\n13=SHA256:...'}
              rows={3}
              dir="ltr"
            />
          </label>
        </div>

        <div className="ov-action-row">
          <button type="button" className="btn" disabled={upgrading || !selected.length} onClick={startUpgrade}>
            {upgrading ? tr('loading') : tr('canaryUpgrade')}
          </button>

          {job?.state === 'failed' && <button type="button" className="btn" disabled={upgrading} onClick={retryJob}>
              {tr('smartRetry')}
            </button>}
        </div>

        {job && <div className={`ov-status-box ${job.state || ''}`}>
            <strong>{tr('job')}:</strong> <span dir="ltr">{job.id}</span>
            <span>{tr('jobStatus')}: {tr(job.state || 'queued')}</span>
            <span>{tr('stage')}: {tr(job.stage || 'queued')}</span>
            {job.error && <span className="ov-error">{job.error}</span>}
          </div>}
      </section>

      {error && <div className="ov-error-panel">
          <span>{error}</span>
          <button type="button" className="btn" onClick={() => load()}>
            {tr('retry')}
          </button>
        </div>}

      {loading ? <div className="ov-page-loader">{tr('loading')}</div> : <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>{tr('select')}</th>
                <th>{tr('node')}</th>
                <th>{tr('version')}</th>
                <th>{tr('healthScore')}</th>
                <th>{tr('state')}</th>
                <th>{tr('actions')}</th>
              </tr>
            </thead>
            <tbody>
              {sortedNodes.map(node => <tr key={node.id}>
                  <td>
                    <input type="checkbox" checked={selected.includes(node.id)} onChange={event => {
                setSelected(current => event.target.checked ? [...new Set([...current, node.id])] : current.filter(id => id !== node.id));
              }} />
                  </td>
                  <td>{node.name}</td>
                  <td>{node.version || tr('unknown')}</td>
                  <td>{node.health_score ?? 0}</td>
                  <td>
                    <span className={`ov-health-pill ${node.health || 'offline'}`}>
                      {displayState(node)}
                    </span>
                  </td>
                  <td>
                    <div className="ov-table-actions">
                      <button type="button" className="btn" onClick={() => updateControl(node.id, {
                  maintenance: !node.maintenance
                })}>
                        {node.maintenance ? tr('leaveMaintenance') : tr('maintenance')}
                      </button>

                      <button type="button" className="btn" onClick={() => updateControl(node.id, {
                  drain: !node.drain
                })}>
                        {node.drain ? tr('resume') : tr('drain')}
                      </button>
                    </div>
                  </td>
                </tr>)}

              {!sortedNodes.length && <tr>
                  <td colSpan="6">{tr('loadFailed')}</td>
                </tr>}
            </tbody>
          </table>
        </div>}
    </div>;
}
