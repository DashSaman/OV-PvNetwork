import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';
import { useAuth } from '../context/AuthContext';

const scopes = ['users:read', 'users:write', 'nodes:read', 'nodes:write', 'settings:read', 'settings:write', 'audit:read'];
const messageFrom = (error, fallback) => error.response?.data?.detail || error.response?.data?.msg || fallback;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

const readChangeEnvelope = () => {
  try {
    const raw = sessionStorage.getItem('pvnPanelSettingsChange');
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value?.change_id || !value?.status_token || Number(value.expires_at || 0) <= Date.now()) {
      sessionStorage.removeItem('pvnPanelSettingsChange');
      sessionStorage.removeItem('pvnPendingAuthToken');
      return null;
    }
    return value;
  } catch {
    sessionStorage.removeItem('pvnPanelSettingsChange');
    sessionStorage.removeItem('pvnPendingAuthToken');
    return null;
  }
};

function PanelRuntimeCard() {
  const { t } = useTranslation();
  const { stageReplacementToken, promoteReplacementToken, discardReplacementToken } = useAuth();
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({ currentPassword: '', newUsername: '', newPassword: '', confirmPassword: '', newPath: '' });
  const [confirming, setConfirming] = useState(false);
  const [applying, setApplying] = useState(false);
  const [progress, setProgress] = useState('');
  const [panelError, setPanelError] = useState('');
  const [panelMessage, setPanelMessage] = useState('');

  const loadPanel = useCallback(async () => {
    try {
      const response = await apiClient.get('/security/panel-settings', { timeout: 12000 });
      setInfo(response.data.data);
    } catch (error) {
      setPanelError(messageFrom(error, t('panelSettings.loadFailed')));
    }
  }, [t]);

  const pollChange = useCallback(async envelope => {
    setApplying(true);
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
      try {
        const response = await apiClient.get(`/security/panel-settings/jobs/${envelope.change_id}`, {
          headers: { 'X-PVNetwork-Change-Token': envelope.status_token },
          skipAuth: true,
          skipUnauthorizedReload: true,
          timeout: 4000,
        });
        const state = response.data.data || {};
        setProgress(state.status || 'verifying');
        if (state.status === 'complete') {
          promoteReplacementToken();
          sessionStorage.removeItem('pvnPanelSettingsChange');
          setApplying(false);
          setPanelMessage(t('panelSettings.complete'));
          if (envelope.target_path && envelope.target_path !== envelope.previous_path) {
            window.location.assign(`/${envelope.target_path}/security`);
          } else {
            await loadPanel();
          }
          return;
        }
        if (state.status === 'rolled_back') {
          discardReplacementToken();
          sessionStorage.removeItem('pvnPanelSettingsChange');
          setApplying(false);
          setPanelError(state.failure_reason || t('panelSettings.rollback'));
          return;
        }
      } catch {
        // The canonical panel may be briefly unavailable during its controlled restart.
      }
      await sleep(750);
    }
    setApplying(false);
    setPanelError(t('panelSettings.pollTimeout'));
  }, [discardReplacementToken, loadPanel, promoteReplacementToken, t]);

  useEffect(() => { loadPanel(); }, [loadPanel]);
  useEffect(() => {
    const envelope = readChangeEnvelope();
    if (envelope) pollChange(envelope);
  }, [pollChange]);

  const openConfirmation = () => {
    setPanelError(''); setPanelMessage('');
    if (!form.currentPassword) return setPanelError(t('panelSettings.currentRequired'));
    if (form.newPassword && form.newPassword !== form.confirmPassword) return setPanelError(t('panelSettings.passwordMismatch'));
    if (!form.newUsername.trim() && !form.newPassword && !form.newPath.trim()) return setPanelError(t('panelSettings.noChanges'));
    setConfirming(true);
  };

  const applyChanges = async () => {
    setConfirming(false); setApplying(true); setProgress('validating'); setPanelError('');
    try {
      const payload = { current_password: form.currentPassword };
      if (form.newUsername.trim()) payload.new_username = form.newUsername.trim();
      if (form.newPassword) payload.new_password = form.newPassword;
      if (form.newPath.trim()) payload.new_path = form.newPath.trim();
      const response = await apiClient.post('/security/panel-settings/apply', payload, { timeout: 15000 });
      const data = response.data.data;
      stageReplacementToken(data.pending_access_token || null);
      const envelope = {
        change_id: data.change_id,
        status_token: data.status_token,
        target_path: data.target_path,
        previous_path: info?.panel_path || '',
        started_at: Date.now(),
        expires_at: Date.now() + 5 * 60 * 1000,
      };
      sessionStorage.setItem('pvnPanelSettingsChange', JSON.stringify(envelope));
      setForm(current => ({ ...current, currentPassword: '', newPassword: '', confirmPassword: '' }));
      await pollChange(envelope);
    } catch (error) {
      discardReplacementToken();
      sessionStorage.removeItem('pvnPanelSettingsChange');
      setApplying(false);
      setPanelError(messageFrom(error, t('feature.loadFailed')));
    }
  };

  return <section className="monitor-form" aria-labelledby="panel-runtime-title">
    <h3 id="panel-runtime-title">{t('panelSettings.title')}</h3>
    {panelError && <div className="error-message" role="alert">{panelError}</div>}
    {panelMessage && <div className="success-message" role="status">{panelMessage}</div>}
    {progress && <p role="status">{t('panelSettings.progress')}: <strong>{progress}</strong></p>}
    {!info ? <p>{t('feature.loading')}</p> : <>
      <p>{t('panelSettings.currentUsername')}: <span className="ltr-number">{info.username}</span></p>
      <p>{t('panelSettings.currentPath')}: <span className="ltr-number">/{info.panel_path}</span></p>
      <div className="monitor-grid">
        <label htmlFor="pvn-new-username">{t('panelSettings.newUsername')}<input id="pvn-new-username" value={form.newUsername} onChange={e => setForm({...form, newUsername:e.target.value})}/></label>
        <label htmlFor="pvn-new-path">{t('panelSettings.panelPath')}<input id="pvn-new-path" value={form.newPath} onChange={e => setForm({...form, newPath:e.target.value})}/></label>
        <label htmlFor="pvn-new-password">{t('panelSettings.newPassword')}<input id="pvn-new-password" type="password" value={form.newPassword} onChange={e => setForm({...form, newPassword:e.target.value})}/></label>
        <label htmlFor="pvn-confirm-password">{t('panelSettings.confirmPassword')}<input id="pvn-confirm-password" type="password" value={form.confirmPassword} onChange={e => setForm({...form, confirmPassword:e.target.value})}/></label>
        <label htmlFor="pvn-current-password">{t('panelSettings.currentPassword')}<input id="pvn-current-password" type="password" autoComplete="current-password" value={form.currentPassword} onChange={e => setForm({...form, currentPassword:e.target.value})}/></label>
      </div>
      <div className="monitor-actions"><button type="button" className="btn" disabled={applying} onClick={openConfirmation}>{t('panelSettings.apply')}</button></div>
    </>}
    {confirming && <div className="modal-overlay"><div className="modal" role="dialog" aria-modal="true" aria-labelledby="panel-confirm-title">
      <div className="modal-header"><h3 id="panel-confirm-title">{t('panelSettings.confirmTitle')}</h3></div>
      <p>{t('panelSettings.summaryUser', { old: info?.username, next: form.newUsername || info?.username })}</p>
      <p>{t('panelSettings.summaryPath', { old: info?.panel_path, next: form.newPath || info?.panel_path })}</p>
      <div className="modal-footer"><button type="button" className="btn-secondary" onClick={() => setConfirming(false)}>{t('panelSettings.cancel')}</button><button type="button" className="btn" onClick={applyChanges}>{t('panelSettings.confirm')}</button></div>
    </div></div>}
  </section>;
}

export default function SecuritySettings() {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [cidr, setCidr] = useState('');
  const [code, setCode] = useState('');
  const [setup, setSetup] = useState(null);
  const [name, setName] = useState('');
  const [selectedScopes, setSelectedScopes] = useState([]);
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/security/', { timeout: 12000 });
      const next = response.data.data;
      setData(next);
      setCidr((next.allowed_cidrs || []).join('\n'));
    } catch (requestError) {
      setError(messageFrom(requestError, t('feature.loadFailed')));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { load(); }, [load]);

  const run = async (name, action, successMessage = '') => {
    setBusy(name);
    setError('');
    setMessage('');
    try {
      await action();
      if (successMessage) setMessage(successMessage);
      return true;
    } catch (requestError) {
      setError(messageFrom(requestError, t('feature.loadFailed')));
      return false;
    } finally {
      setBusy('');
    }
  };

  if (loading) return <div className="view"><div className="ov-page-loader">{t('feature.loading')}</div></div>;
  if (!data) return <div className="view"><div className="error-message">{error}</div><button className="btn" onClick={load}>{t('feature.retry')}</button></div>;

  const save = () => run('save', async () => {
    await apiClient.put('/security/', {
      ...data,
      allowed_cidrs: cidr.split(/[,\n]/).map(value => value.trim()).filter(Boolean),
    }, { timeout: 12000 });
    await load();
  }, t('feature.saved'));

  const beginTotp = () => run('totp-setup', async () => {
    const response = await apiClient.post('/security/totp/setup', {}, { timeout: 12000 });
    setSetup(response.data.data);
  });

  const confirmTotp = () => run('totp-confirm', async () => {
    await apiClient.post('/security/totp/confirm', { code }, { timeout: 12000 });
    setSetup(null); setCode(''); await load();
  }, t('feature.saved'));

  const disableTotp = () => run('totp-disable', async () => {
    await apiClient.delete('/security/totp', { data: { code }, timeout: 12000 });
    setCode(''); await load();
  }, t('feature.saved'));

  const createToken = () => run('token-create', async () => {
    const response = await apiClient.post('/security/tokens', {
      name, scopes: selectedScopes, expires_at: null,
    }, { timeout: 12000 });
    setToken(response.data.data.token); setName(''); await load();
  });

  const revokeToken = tokenId => run(`revoke-${tokenId}`, async () => {
    await apiClient.delete(`/security/tokens/${tokenId}`, { timeout: 12000 });
    await load();
  }, t('feature.saved'));

  return <div className="view">
    <div className="view-header"><h2>{t('ui.dbb6d4f17351')}</h2></div>
    {error && <div className="error-message" role="alert">{error}</div>}
    {message && <div className="success-message" role="status">{message}</div>}

    <PanelRuntimeCard />

    <section className="monitor-form">
      <label><input type="checkbox" checked={data.rate_limit_enabled} onChange={event => setData({...data, rate_limit_enabled: event.target.checked})}/>{t('ui.3ddc17b9f318')}</label>
      <input type="number" min="10" max="10000" value={data.rate_limit_per_minute} onChange={event => setData({...data, rate_limit_per_minute: Number(event.target.value)})}/>
      <label><input type="checkbox" checked={data.ip_allowlist_enabled} onChange={event => setData({...data, ip_allowlist_enabled: event.target.checked})}/>{t('ui.5922e4963c74')}</label>
      <textarea placeholder={t('ui.525163179b91')} value={cidr} onChange={event => setCidr(event.target.value)}/>
      <button type="button" className="btn" disabled={Boolean(busy)} onClick={save}>{busy === 'save' ? t('feature.saving') : t('ui.bc1ac6f5f5fd')}</button>
    </section>

    <section className="monitor-form">
      <h3>{t('ui.85ea9bd8fe04')} {data.totp_enabled ? t('ui.a733b809d2f1') : t('ui.09af574c7f20')}</h3>
      {!data.totp_enabled && <button type="button" className="btn" disabled={Boolean(busy)} onClick={beginTotp}>{t('ui.f0eed8dce439')}</button>}
      {setup && <><p className="ltr-number">{setup.secret}</p><input value={code} placeholder={t('ui.83e8f0bb6ae9')} onChange={event => setCode(event.target.value)}/><button type="button" className="btn" disabled={Boolean(busy) || code.length !== 6} onClick={confirmTotp}>{t('ui.a7b4c2d4a7f8')}</button></>}
      {data.totp_enabled && <><input value={code} placeholder={t('ui.83e8f0bb6ae9')} onChange={event => setCode(event.target.value)}/><button type="button" className="btn danger" disabled={Boolean(busy) || code.length !== 6} onClick={disableTotp}>{t('ui.e409bf474a5d')} 2FA</button></>}
    </section>

    <section className="monitor-form">
      <h3>{t('ui.731c458c5b55')}</h3>
      <input value={name} placeholder={t('ui.6e84ac10f830')} onChange={event => setName(event.target.value)}/>
      {scopes.map(scope => <label key={scope}><input type="checkbox" checked={selectedScopes.includes(scope)} onChange={event => setSelectedScopes(current => event.target.checked ? [...current, scope] : current.filter(value => value !== scope))}/>{scope}</label>)}
      <button type="button" className="btn" disabled={Boolean(busy) || !name || !selectedScopes.length} onClick={createToken}>{t('ui.2d2f4541d99c')}</button>
      {token && <textarea readOnly value={token} onFocus={event => event.target.select()}/>} 
      <div className="table-container"><table><tbody>{data.tokens.map(item => <tr key={item.id}><td>{item.name}</td><td>{item.prefix}</td><td>{item.revoked_at ? t('ui.57ab5550d820') : t('ui.a733b809d2f1')}</td><td><button type="button" disabled={Boolean(busy) || Boolean(item.revoked_at)} onClick={() => revokeToken(item.id)}>{t('ui.e409bf474a5d')}</button></td></tr>)}</tbody></table></div>
    </section>
  </div>;
}
