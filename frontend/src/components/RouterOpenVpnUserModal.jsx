import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';

const RouterOpenVpnUserModal = ({ user, nodes = [], healthyNodeIds = [], onClose }) => {
  const { t } = useTranslation();
  const healthy = useMemo(() => new Set((healthyNodeIds || []).map(Number)), [healthyNodeIds]);
  const assigned = useMemo(() => {
    const ids = new Set((user?.node_ids || []).map(Number));
    return nodes.filter(node => ids.has(Number(node.id)) && healthy.has(Number(node.id)));
  }, [user, nodes, healthy]);
  const [nodeId, setNodeId] = useState('');
  const [status, setStatus] = useState(null);
  const [secret, setSecret] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const errorText = exception =>
    exception?.response?.data?.detail || exception?.response?.data?.msg ||
    exception?.message || t('routerOpenVpn.requestFailed', 'Request failed.');

  useEffect(() => {
    setNodeId(assigned.length ? String(assigned[0].id) : '');
  }, [assigned]);

  const loadStatus = async selected => {
    if (!user?.uuid || !selected) { setStatus(null); return; }
    setBusy(true); setError(''); setSecret(null);
    try {
      const response = await apiClient.get(`/router-openvpn/users/${user.uuid}/nodes/${selected}`);
      setStatus(response.data?.data || null);
    } catch (exception) {
      setStatus(null); setError(errorText(exception));
    } finally { setBusy(false); }
  };

  useEffect(() => { loadStatus(nodeId); }, [nodeId]); // eslint-disable-line react-hooks/exhaustive-deps

  const rotate = async () => {
    if (!nodeId) return;
    setBusy(true); setError(''); setSecret(null);
    try {
      const response = await apiClient.post(`/router-openvpn/users/${user.uuid}/nodes/${nodeId}/credential`);
      const data = response.data?.data || {};
      setSecret({ username: data.username || '', password: data.password || '' });
      setStatus(previous => ({ ...(previous || {}), ...data, password_available: false }));
    } catch (exception) { setError(errorText(exception)); }
    finally { setBusy(false); }
  };

  const disable = async () => {
    if (!nodeId) return;
    setBusy(true); setError(''); setSecret(null);
    try {
      await apiClient.put(`/router-openvpn/users/${user.uuid}/nodes/${nodeId}/credential/status`, { enabled: false });
      setStatus(previous => ({ ...(previous || {}), enabled: false }));
    } catch (exception) { setError(errorText(exception)); }
    finally { setBusy(false); }
  };

  const downloadProfile = async () => {
    if (!nodeId) return;
    setBusy(true); setError('');
    try {
      const response = await apiClient.get(
        `/router-openvpn/users/${user.uuid}/nodes/${nodeId}/profile`,
        { responseType: 'blob' }
      );
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${user.name}.router.ovpn`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (exception) { setError(errorText(exception)); }
    finally { setBusy(false); }
  };

  const routerOsText = secret ?
    `/interface/ovpn-client/import-ovpn-configuration file-name=${user.name}.router.ovpn ovpn-user=${secret.username} ovpn-password=${secret.password} skip-cert-import=no` : '';

  const copyRouterOs = async () => {
    if (!routerOsText) return;
    try {
      await navigator.clipboard.writeText(routerOsText);
    } catch {
      window.prompt(t('routerOpenVpn.copyCommand', 'Copy RouterOS command:'), routerOsText);
    }
  };

  if (!user) return null;
  return <div className="modal-overlay">
    <div className="modal router-openvpn-user-modal">
      <div className="modal-header">
        <h3>{t('routerOpenVpn.userTitle', 'Router / MikroTik')} — {user.name}</h3>
        <button onClick={onClose} className="close-modal-btn">&times;</button>
      </div>

      <p style={{ opacity: 0.9 }}>
        {t('routerOpenVpn.normalUnaffected', 'Normal OpenVPN remains certificate-only and does not need these credentials.')}
      </p>

      {assigned.length === 0 ? <p className="error-message">
        {t('routerOpenVpn.noHealthyAssignedNode', 'No assigned node has a healthy Router compatibility listener.')}
      </p> : <>
        <div className="input-group">
          <label>{t('routerOpenVpn.node', 'Node')}</label>
          <select value={nodeId} onChange={event => setNodeId(event.target.value)} disabled={busy}>
            {assigned.map(node => <option key={node.id} value={node.id}>{node.name}</option>)}
          </select>
        </div>

        <div className="input-group">
          <label>{t('routerOpenVpn.status', 'Credential status')}</label>
          <input readOnly value={status?.configured
            ? (status?.enabled ? t('enabled', 'Enabled') : t('disabled', 'Disabled'))
            : t('routerOpenVpn.notCreated', 'Not created')} />
        </div>

        {status?.username && <div className="input-group">
          <label>{t('routerOpenVpn.username', 'Router username')}</label>
          <input readOnly dir="ltr" value={status.username} />
        </div>}

        <div className="modal-footer" style={{ flexWrap: 'wrap' }}>
          <button type="button" className="btn" disabled={busy} onClick={rotate}>
            {status?.configured ? t('routerOpenVpn.rotate', 'Rotate credentials') : t('routerOpenVpn.generate', 'Generate credentials')}
          </button>
          <button type="button" className="btn btn-secondary" disabled={busy || !status?.configured}
            onClick={downloadProfile}>{t('routerOpenVpn.downloadProfile', 'Download Router profile')}</button>
          <button type="button" className="btn btn-secondary" disabled={busy || !status?.enabled}
            onClick={disable}>{t('routerOpenVpn.disableCredential', 'Disable credential')}</button>
        </div>

        {secret && <div className="router-openvpn-one-time-secret">
          <p><strong>{t('routerOpenVpn.oneTimeWarning', 'Save this password now. It will not be shown again.')}</strong></p>
          <div className="input-group">
            <label>{t('routerOpenVpn.username', 'Router username')}</label>
            <input readOnly dir="ltr" value={secret.username} />
          </div>
          <div className="input-group">
            <label>{t('routerOpenVpn.password', 'One-time password')}</label>
            <input readOnly dir="ltr" value={secret.password} />
          </div>
          <div className="input-group">
            <label>{t('routerOpenVpn.routerOsCommand', 'RouterOS import command')}</label>
            <textarea readOnly dir="ltr" rows="4" value={routerOsText} />
          </div>
          <button type="button" className="btn btn-secondary" onClick={copyRouterOs}>
            {t('routerOpenVpn.copyRouterOs', 'Copy RouterOS command')}
          </button>
        </div>}
      </>}

      {error && <p className="error-message">{error}</p>}
      <div className="modal-footer">
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          {t('close', 'Close')}
        </button>
      </div>
    </div>
  </div>;
};

export default RouterOpenVpnUserModal;
