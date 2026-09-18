import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';

const scopes = ['users:read', 'users:write', 'nodes:read', 'nodes:write', 'settings:read', 'settings:write', 'audit:read'];
const messageFrom = (error, fallback) => error.response?.data?.detail || error.response?.data?.msg || fallback;

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
