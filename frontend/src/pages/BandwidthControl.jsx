import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  FiActivity,
  FiAlertTriangle,
  FiCheckCircle,
  FiPlus,
  FiRefreshCw,
  FiSave,
  FiSliders,
  FiTrash2,
  FiXCircle,
} from 'react-icons/fi';
import apiClient from '../services/api';

const emptyForm = {
  target_type: 'all',
  download_mbps: 1,
  node_ids: [],
  group_id: '',
  owner: '',
  user_uuids: [],
  duration_minutes: 0,
  canary_node_id: '',
};

const errorText = (error, fallback) => (
  error?.response?.data?.detail
  || error?.response?.data?.msg
  || error?.message
  || fallback
);

const BandwidthControl = () => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [nodeStatus, setNodeStatus] = useState([]);
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [newGroup, setNewGroup] = useState('');
  const [groupDrafts, setGroupDrafts] = useState({});

  const loadConfiguration = async () => {
    const response = await apiClient.get('/bandwidth/');
    const payload = response.data.data;
    setData(payload);

    const settings = payload.settings || {};
    const defaultNodes = (settings.node_ids || []).length
      ? settings.node_ids
      : (payload.nodes || []).filter(item => item.enabled).map(item => item.id);

    setForm({
      target_type: settings.target_type || 'all',
      download_mbps: Number(settings.download_mbps || 1),
      node_ids: defaultNodes,
      group_id: settings.target_group_id || '',
      owner: settings.target_owner || '',
      user_uuids: settings.target_user_uuids || [],
      duration_minutes: 0,
      canary_node_id: defaultNodes[0] || '',
    });

    const drafts = {};
    (payload.groups || []).forEach(group => {
      drafts[group.id] = (payload.users || [])
        .filter(user => Number(user.group_id) === Number(group.id))
        .map(user => user.uuid);
    });
    setGroupDrafts(drafts);
  };

  const loadStatus = async () => {
    const response = await apiClient.get('/bandwidth/status');
    setNodeStatus(response.data.data || []);
  };

  const refreshAll = async () => {
    setBusy(true);
    setError('');
    try {
      await Promise.all([loadConfiguration(), loadStatus()]);
    } catch (requestError) {
      setError(errorText(requestError, t('bandwidth.loadFailed')));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    refreshAll();
    // Initial configuration/status fetch is mount-only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedUsers = useMemo(
    () => new Set(form.user_uuids || []),
    [form.user_uuids],
  );

  const requestPayload = () => ({
    target_type: form.target_type,
    download_mbps: Number(form.download_mbps),
    node_ids: form.node_ids.map(Number),
    group_id: form.group_id ? Number(form.group_id) : null,
    owner: form.owner || null,
    user_uuids: form.user_uuids,
    duration_minutes: Number(form.duration_minutes || 0),
    canary_node_id: form.canary_node_id ? Number(form.canary_node_id) : null,
  });

  const validateForm = () => {
    if (!form.node_ids.length) {
      throw new Error(t('bandwidth.selectNode'));
    }
    if (!Number.isFinite(Number(form.download_mbps)) || Number(form.download_mbps) < 0.064) {
      throw new Error(t('bandwidth.invalidRate'));
    }
    if (form.target_type === 'owner' && !form.owner) {
      throw new Error(t('bandwidth.selectOwner'));
    }
    if (form.target_type === 'group' && !form.group_id) {
      throw new Error(t('bandwidth.selectGroup'));
    }
    if (form.target_type === 'users' && !form.user_uuids.length) {
      throw new Error(t('bandwidth.selectUsers'));
    }
  };

  const runPolicyAction = async (mode) => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      validateForm();
      const payload = requestPayload();
      let response;

      if (mode === 'preview') {
        response = await apiClient.post('/bandwidth/preview', payload);
      } else {
        const confirmation = window.prompt(t('bandwidth.typeApply'));
        if (String(confirmation || '').trim().toUpperCase() !== 'APPLY') {
          setBusy(false);
          return;
        }
        response = await apiClient.post('/bandwidth/activate', {
          ...payload,
          confirmation: 'APPLY',
          canary_only: mode === 'canary',
        });
      }

      setResults(response.data.data || null);
      setMessage(response.data.msg || t('bandwidth.saved'));
      await Promise.all([loadConfiguration(), loadStatus()]);
    } catch (requestError) {
      setError(errorText(requestError, t('bandwidth.actionFailed')));
    } finally {
      setBusy(false);
    }
  };

  const emergencyOff = async () => {
    const confirmation = window.prompt(t('bandwidth.typeDisable'));
    if (String(confirmation || '').trim().toUpperCase() !== 'DISABLE') {
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const response = await apiClient.post('/bandwidth/disable', {
        confirmation: 'DISABLE',
      });
      setResults(response.data.data || null);
      setMessage(response.data.msg || t('bandwidth.disabled'));
      await Promise.all([loadConfiguration(), loadStatus()]);
    } catch (requestError) {
      setError(errorText(requestError, t('bandwidth.disableFailed')));
    } finally {
      setBusy(false);
    }
  };

  const toggleNode = (nodeId) => {
    setForm(current => {
      const selected = current.node_ids.includes(nodeId);
      const nodeIds = selected
        ? current.node_ids.filter(value => value !== nodeId)
        : [...current.node_ids, nodeId];
      const canary = nodeIds.includes(Number(current.canary_node_id))
        ? current.canary_node_id
        : (nodeIds[0] || '');
      return { ...current, node_ids: nodeIds, canary_node_id: canary };
    });
  };

  const toggleUser = (uuid) => {
    setForm(current => ({
      ...current,
      user_uuids: current.user_uuids.includes(uuid)
        ? current.user_uuids.filter(value => value !== uuid)
        : [...current.user_uuids, uuid],
    }));
  };

  const createGroup = async () => {
    const name = newGroup.trim();
    if (!name) return;
    setBusy(true);
    setError('');
    try {
      await apiClient.post('/bandwidth/groups', { name });
      setNewGroup('');
      await loadConfiguration();
      setMessage(t('bandwidth.groupCreated'));
    } catch (requestError) {
      setError(errorText(requestError, t('bandwidth.groupCreateFailed')));
    } finally {
      setBusy(false);
    }
  };

  const saveGroupMembers = async (groupId) => {
    setBusy(true);
    setError('');
    try {
      await apiClient.put(`/bandwidth/groups/${groupId}/users`, {
        user_uuids: groupDrafts[groupId] || [],
      });
      await loadConfiguration();
      setMessage(t('bandwidth.groupSaved'));
    } catch (requestError) {
      setError(errorText(requestError, t('bandwidth.groupSaveFailed')));
    } finally {
      setBusy(false);
    }
  };

  const deleteGroup = async (group) => {
    if (!window.confirm(`${t('bandwidth.deleteGroup')} ${group.name}?`)) return;
    setBusy(true);
    setError('');
    try {
      await apiClient.delete(`/bandwidth/groups/${group.id}`);
      await loadConfiguration();
      setMessage(t('bandwidth.groupDeleted'));
    } catch (requestError) {
      setError(errorText(requestError, t('bandwidth.groupDeleteFailed')));
    } finally {
      setBusy(false);
    }
  };

  if (!data) {
    return <div className="bandwidth-loading">{t('bandwidth.loading')}</div>;
  }

  const settings = data.settings || {};
  const active = Boolean(settings.enabled);

  return (
    <div className="bandwidth-page">
      <div className="view-header bandwidth-header">
        <div>
          <h2><FiSliders /> {t('bandwidth.title')}</h2>
          <p>{t('bandwidth.subtitle')}</p>
        </div>
        <button className="btn btn-secondary" onClick={refreshAll} disabled={busy}>
          <FiRefreshCw /> {t('bandwidth.refresh')}
        </button>
      </div>

      <div className={`bandwidth-state ${active ? 'is-active' : 'is-off'}`}>
        <div className="bandwidth-state-icon">
          {active ? <FiAlertTriangle /> : <FiCheckCircle />}
        </div>
        <div>
          <strong>{active ? t('bandwidth.active') : t('bandwidth.off')}</strong>
          <span>
            {active
              ? `${settings.download_mbps} Mbps — ${t(`bandwidth.target.${settings.target_type}`)}`
              : t('bandwidth.offDescription')}
          </span>
        </div>
        {active && (
          <button className="btn btn-danger" onClick={emergencyOff} disabled={busy}>
            <FiXCircle /> {t('bandwidth.emergencyOff')}
          </button>
        )}
      </div>

      <div className="bandwidth-safety-grid">
        <div><FiCheckCircle /> {t('bandwidth.safetyDisabledDefault')}</div>
        <div><FiCheckCircle /> {t('bandwidth.safetyTunOnly')}</div>
        <div><FiCheckCircle /> {t('bandwidth.safetyDownloadOnly')}</div>
        <div><FiCheckCircle /> {t('bandwidth.safetyFailOpen')}</div>
      </div>

      {error && <div className="bandwidth-alert error">{error}</div>}
      {message && <div className="bandwidth-alert success">{message}</div>}

      <section className="bandwidth-card">
        <h3><FiActivity /> {t('bandwidth.policy')}</h3>

        <div className="bandwidth-form-grid">
          <label>
            <span>{t('bandwidth.targetType')}</span>
            <select
              value={form.target_type}
              onChange={event => setForm({ ...form, target_type: event.target.value })}
              disabled={busy}
            >
              <option value="all">{t('bandwidth.target.all')}</option>
              <option value="owner">{t('bandwidth.target.owner')}</option>
              <option value="group">{t('bandwidth.target.group')}</option>
              <option value="users">{t('bandwidth.target.users')}</option>
            </select>
          </label>

          <label>
            <span>{t('bandwidth.downloadRate')}</span>
            <div className="bandwidth-rate-input">
              <input
                type="number"
                min="0.064"
                max="10000"
                step="0.1"
                value={form.download_mbps}
                onChange={event => setForm({ ...form, download_mbps: event.target.value })}
                disabled={busy}
              />
              <b>Mbps</b>
            </div>
            <small>{t('bandwidth.rateHint')}</small>
          </label>

          <label>
            <span>{t('bandwidth.duration')}</span>
            <select
              value={form.duration_minutes}
              onChange={event => setForm({ ...form, duration_minutes: Number(event.target.value) })}
              disabled={busy}
            >
              <option value="0">{t('bandwidth.untilManual')}</option>
              <option value="30">{t('bandwidth.minutes30')}</option>
              <option value="60">{t('bandwidth.hour1')}</option>
              <option value="360">{t('bandwidth.hours6')}</option>
              <option value="1440">{t('bandwidth.day1')}</option>
            </select>
          </label>

          <label>
            <span>{t('bandwidth.canaryNode')}</span>
            <select
              value={form.canary_node_id}
              onChange={event => setForm({ ...form, canary_node_id: event.target.value })}
              disabled={busy}
            >
              <option value="">{t('bandwidth.select')}</option>
              {(data.nodes || []).filter(node => form.node_ids.includes(node.id)).map(node => (
                <option key={node.id} value={node.id}>{node.name}</option>
              ))}
            </select>
          </label>
        </div>

        {form.target_type === 'owner' && (
          <div className="bandwidth-target-panel">
            <label>
              <span>{t('bandwidth.owner')}</span>
              <select value={form.owner} onChange={event => setForm({ ...form, owner: event.target.value })}>
                <option value="">{t('bandwidth.select')}</option>
                {(data.owners || []).map(owner => <option key={owner} value={owner}>{owner}</option>)}
              </select>
            </label>
          </div>
        )}

        {form.target_type === 'group' && (
          <div className="bandwidth-target-panel">
            <label>
              <span>{t('bandwidth.group')}</span>
              <select value={form.group_id} onChange={event => setForm({ ...form, group_id: event.target.value })}>
                <option value="">{t('bandwidth.select')}</option>
                {(data.groups || []).map(group => (
                  <option key={group.id} value={group.id}>{group.name} ({group.members_count})</option>
                ))}
              </select>
            </label>
          </div>
        )}

        {form.target_type === 'users' && (
          <div className="bandwidth-user-picker">
            <div className="bandwidth-picker-title">
              <span>{t('bandwidth.selectedUsers')}</span>
              <b>{selectedUsers.size}</b>
            </div>
            <div className="bandwidth-check-list">
              {(data.users || []).map(user => (
                <label key={user.uuid}>
                  <input
                    type="checkbox"
                    checked={selectedUsers.has(user.uuid)}
                    onChange={() => toggleUser(user.uuid)}
                  />
                  <span>{user.name}</span>
                  <small>{user.owner}</small>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="bandwidth-node-picker">
          <div className="bandwidth-picker-title">
            <span>{t('bandwidth.nodes')}</span>
            <b>{form.node_ids.length}</b>
          </div>
          <div className="bandwidth-node-grid">
            {(data.nodes || []).map(node => (
              <label key={node.id} className={form.node_ids.includes(node.id) ? 'selected' : ''}>
                <input
                  type="checkbox"
                  checked={form.node_ids.includes(node.id)}
                  onChange={() => toggleNode(node.id)}
                />
                <span>{node.name}</span>
                <small>{node.enabled ? t('bandwidth.nodeEnabled') : t('bandwidth.nodeDisabled')}</small>
              </label>
            ))}
          </div>
        </div>

        <div className="bandwidth-actions">
          <button className="btn btn-secondary" disabled={busy} onClick={() => runPolicyAction('preview')}>
            {t('bandwidth.preview')}
          </button>
          <button className="btn btn-secondary" disabled={busy || !form.canary_node_id} onClick={() => runPolicyAction('canary')}>
            {t('bandwidth.canary')}
          </button>
          <button className="btn" disabled={busy} onClick={() => runPolicyAction('activate')}>
            <FiAlertTriangle /> {t('bandwidth.activate')}
          </button>
        </div>
      </section>

      <section className="bandwidth-card">
        <h3>{t('bandwidth.nodeStatus')}</h3>
        <div className="bandwidth-status-grid">
          {nodeStatus.map(item => {
            const status = item.data || {};
            return (
              <div key={item.node_id} className={`bandwidth-node-status ${item.ok ? 'ok' : 'bad'}`}>
                <div>
                  <strong>{item.node_name}</strong>
                  {item.ok ? <FiCheckCircle /> : <FiXCircle />}
                </div>
                <span>{item.ok ? (status.message || item.msg) : (item.msg || t('bandwidth.agentUnavailable'))}</span>
                <small>
                  {t('bandwidth.qdisc')}: {status.current_qdisc?.kind || '-'} · {t('bandwidth.matched')}: {status.matched_users || 0}
                </small>
              </div>
            );
          })}
        </div>
      </section>

      {results && (
        <section className="bandwidth-card">
          <h3>{t('bandwidth.lastResult')}</h3>
          <pre className="bandwidth-result">{JSON.stringify(results, null, 2)}</pre>
        </section>
      )}

      <section className="bandwidth-card">
        <h3>{t('bandwidth.groups')}</h3>
        <div className="bandwidth-create-group">
          <input
            value={newGroup}
            onChange={event => setNewGroup(event.target.value)}
            placeholder={t('bandwidth.groupName')}
            maxLength={64}
          />
          <button className="btn" onClick={createGroup} disabled={busy || !newGroup.trim()}>
            <FiPlus /> {t('bandwidth.createGroup')}
          </button>
        </div>

        <div className="bandwidth-groups-grid">
          {(data.groups || []).map(group => (
            <div className="bandwidth-group-card" key={group.id}>
              <div className="bandwidth-group-head">
                <div>
                  <strong>{group.name}</strong>
                  <small>{group.members_count} {t('bandwidth.members')}</small>
                </div>
                <button className="bandwidth-icon-danger" onClick={() => deleteGroup(group)} disabled={busy}>
                  <FiTrash2 />
                </button>
              </div>
              <select
                multiple
                value={groupDrafts[group.id] || []}
                onChange={event => {
                  const values = Array.from(event.target.selectedOptions).map(option => option.value);
                  setGroupDrafts(current => ({ ...current, [group.id]: values }));
                }}
              >
                {(data.users || []).map(user => (
                  <option key={user.uuid} value={user.uuid}>{user.name} — {user.owner}</option>
                ))}
              </select>
              <button className="btn btn-secondary" onClick={() => saveGroupMembers(group.id)} disabled={busy}>
                <FiSave /> {t('bandwidth.saveMembers')}
              </button>
            </div>
          ))}
          {!data.groups?.length && <div className="bandwidth-empty">{t('bandwidth.noGroups')}</div>}
        </div>
      </section>
    </div>
  );
};

export default BandwidthControl;
