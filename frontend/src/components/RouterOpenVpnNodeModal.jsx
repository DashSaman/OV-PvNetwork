import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';

const RouterOpenVpnNodeModal = ({ node, onClose, onChanged }) => {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [port, setPort] = useState(1195);
  const [protocol, setProtocol] = useState('tcp');
  const [subnet, setSubnet] = useState('10.9.0.0/24');
  const [preflightOk, setPreflightOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const errorText = error =>
    error?.response?.data?.detail || error?.response?.data?.msg ||
    error?.message || t('routerOpenVpn.requestFailed', 'Request failed.');

  const load = async () => {
    if (!node?.id) return;
    setBusy(true);
    setError('');
    try {
      const response = await apiClient.get(`/router-openvpn/nodes/${node.id}`);
      const data = response.data?.data || {};
      setStatus(data);
      setPort(Number(data.port || 1195));
      setProtocol(data.protocol || 'tcp');
      setSubnet(data.subnet || '10.9.0.0/24');
    } catch (exception) {
      setError(errorText(exception));
    } finally { setBusy(false); }
  };

  useEffect(() => { load(); }, [node?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const settingsKey = useMemo(
    () => `${port}|${protocol}|${subnet}`,
    [port, protocol, subnet]
  );
  useEffect(() => { setPreflightOk(false); setNotice(''); }, [settingsKey]);

  const runPreflight = async () => {
    setBusy(true); setError(''); setNotice('');
    try {
      await apiClient.post(`/router-openvpn/nodes/${node.id}/preflight`, {
        enabled: true, port: Number(port), protocol, subnet
      });
      setPreflightOk(true);
      setNotice(t('routerOpenVpn.preflightPassed', 'Preflight passed.'));
    } catch (exception) {
      setPreflightOk(false);
      setError(errorText(exception));
    } finally { setBusy(false); }
  };

  const save = async enabled => {
    if (enabled && !preflightOk) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await apiClient.put(`/router-openvpn/nodes/${node.id}`, {
        enabled, port: Number(port), protocol, subnet
      });
      setStatus(response.data?.data || { enabled });
      setNotice(enabled
        ? t('routerOpenVpn.enabled', 'Router compatibility listener enabled.')
        : t('routerOpenVpn.disabled', 'Router compatibility listener disabled.'));
      onChanged?.();
    } catch (exception) {
      setError(errorText(exception));
    } finally { setBusy(false); }
  };

  if (!node) return null;
  return <div className="modal-overlay">
    <div className="modal router-openvpn-node-modal" dir={t('direction', 'rtl')}>
      <div className="modal-header">
        <h3>{t('routerOpenVpn.nodeTitle', 'Router / MikroTik OpenVPN')} — {node.name}</h3>
        <button onClick={onClose} className="close-modal-btn">&times;</button>
      </div>

      {status?.upgrade_required && <p className="error-message">
        {t('routerOpenVpn.upgradeRequired', 'This node must be upgraded before Router compatibility can be enabled.')}
      </p>}
      <p style={{ opacity: 0.85 }}>
        {t('routerOpenVpn.normalUnaffected', 'Normal OpenVPN remains certificate-only and is not changed by this feature.')}
      </p>

      <div className="input-group">
        <label>{t('routerOpenVpn.port', 'Secondary port')}</label>
        <input type="number" min="1" max="65535" value={port}
          onChange={event => setPort(event.target.value)} disabled={busy || status?.upgrade_required} />
      </div>
      <div className="input-group">
        <label>{t('routerOpenVpn.protocol', 'Protocol')}</label>
        <select value={protocol} onChange={event => setProtocol(event.target.value)} disabled={busy || status?.upgrade_required}>
          <option value="tcp">TCP</option><option value="udp">UDP</option>
        </select>
      </div>
      <div className="input-group">
        <label>{t('routerOpenVpn.subnet', 'Tunnel subnet')}</label>
        <input type="text" dir="ltr" value={subnet}
          onChange={event => setSubnet(event.target.value)} disabled={busy || status?.upgrade_required} />
      </div>

      <div className="modal-footer" style={{ flexWrap: 'wrap' }}>
        <button type="button" className="btn btn-secondary" disabled={busy || status?.upgrade_required}
          onClick={runPreflight}>{t('routerOpenVpn.preflight', 'Preflight')}</button>
        <button type="button" className="btn" disabled={busy || !preflightOk || status?.upgrade_required}
          onClick={() => save(true)}>{t('routerOpenVpn.enable', 'Enable')}</button>
        <button type="button" className="btn btn-secondary" disabled={busy || !status?.enabled}
          onClick={() => save(false)}>{t('routerOpenVpn.disable', 'Disable')}</button>
      </div>

      {notice && <p className="success-message">{notice}</p>}
      {error && <p className="error-message">{error}</p>}
      <div className="modal-footer">
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          {t('close', 'Close')}
        </button>
      </div>
    </div>
  </div>;
};

export default RouterOpenVpnNodeModal;
