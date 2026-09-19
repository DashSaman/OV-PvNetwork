import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './InlineUserQuickEdit.css';

const GB = 1024 * 1024 * 1024;

const gbFromBytes = bytes => {
  const value = Number(bytes || 0) / GB;
  return Number.isFinite(value) ? Number(value.toFixed(2)).toString() : '0';
};

const InlineUserQuickEdit = ({ user, nodes, userRole, onSave, onCancel }) => {
  const { t } = useTranslation();
  const isReseller = userRole === 'admin';
  const [trafficGb, setTrafficGb] = useState('0');
  const [expiryDate, setExpiryDate] = useState('');
  const [deviceLimit, setDeviceLimit] = useState('1');
  const [active, setActive] = useState(true);
  const [nodeIds, setNodeIds] = useState([]);
  const [resetUsage, setResetUsage] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const unlimited = Number(trafficGb || 0) <= 0;
  const effectiveDeviceLimit = isReseller && unlimited ? '1' : deviceLimit;

  useEffect(() => {
    setTrafficGb(gbFromBytes(user?.total));
    setExpiryDate(String(user?.expiry_date || '').split('T')[0]);
    setDeviceLimit(String(user?.device_limit ?? 1));
    setActive(Boolean(user?.is_active));
    setNodeIds(Array.isArray(user?.node_ids) ? user.node_ids.map(Number) : []);
    setResetUsage(false);
    setError('');
  }, [user]);

  const sortedNodes = useMemo(
    () => [...(nodes || [])].sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''))),
    [nodes]
  );

  const toggleNode = node => {
    const nodeId = Number(node.id);
    const selected = nodeIds.includes(nodeId);
    const unavailableForChange = !node.status || node.drain || node.maintenance;
    if (unavailableForChange) return;
    setNodeIds(current => selected ? current.filter(id => id !== nodeId) : [...current, nodeId]);
  };

  const submit = async event => {
    event.preventDefault();
    setError('');
    const traffic = Number(trafficGb);
    const devices = Number(effectiveDeviceLimit);
    if (!Number.isFinite(traffic) || traffic < 0) {
      setError(t('quickEditTrafficInvalid', 'Traffic limit must be zero or greater.'));
      return;
    }
    if (!Number.isInteger(devices) || devices < 0) {
      setError(t('deviceLimitInvalid', 'Concurrent connections must be 0 or a positive integer.'));
      return;
    }
    if (!nodeIds.length) {
      setError(t('quickEditNodeRequired', 'Select at least one node.'));
      return;
    }
    if (!isReseller && !unlimited && !expiryDate) {
      setError(t('quickEditExpiryRequired', 'Expiry date is required.'));
      return;
    }

    setSaving(true);
    try {
      await onSave(user, {
        totalTrafficGb: traffic,
        expiryDate,
        deviceLimit: devices,
        isActive: active,
        nodeIds: [...nodeIds],
        resetUsage,
      });
      onCancel();
    } catch (exception) {
      setError(exception?.message || t('quickEditSaveFailed', 'Unable to apply quick edit.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="inline-user-quick-edit" onSubmit={submit} aria-label={t('quickEditTitle', 'Quick edit user')}>
      <div className="quick-edit-grid">
        <label className="quick-edit-field">
          <span>{t('username', 'Username')}</span>
          <input className="quick-edit-username" value={user.name} readOnly aria-readonly="true" />
          <small>{t('quickEditUsernameLocked', 'Username rename is locked here because it requires a safe multi-node profile migration.')}</small>
        </label>

        <label className="quick-edit-field">
          <span>{t('modal_totalTraffic', 'Traffic limit (GB)')}</span>
          <input className="quick-edit-traffic" type="number" min="0" step="0.01" value={trafficGb} onChange={event => setTrafficGb(event.target.value)} />
          <small>{t('quickEditUnlimitedHint', '0 = unlimited')}</small>
        </label>

        <label className="quick-edit-field">
          <span>{t('modal_expiryDate', 'Expiry date')}</span>
          <input
            className="quick-edit-expiry"
            type="date"
            value={expiryDate}
            onChange={event => setExpiryDate(event.target.value)}
            disabled={isReseller || unlimited}
          />
          {(isReseller || unlimited) && <small>{t('quickEditExpiryLocked', 'Expiry follows the existing reseller/unlimited policy.')}</small>}
        </label>

        <label className="quick-edit-field">
          <span>{t('modal_deviceLimit', 'Max devices')}</span>
          <input
            className="quick-edit-device-limit"
            type="number"
            min={isReseller && unlimited ? '1' : '0'}
            step="1"
            value={effectiveDeviceLimit}
            onChange={event => setDeviceLimit(event.target.value)}
            disabled={isReseller && unlimited}
          />
          <small>{t('quickEditDeviceHint', '0 = unlimited simultaneous connections')}</small>
        </label>

        <label className="quick-edit-toggle-field">
          <input className="quick-edit-active" type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} />
          <span>{t('status_active', 'Active')}</span>
          <small>{user.is_online ? t('online', 'Online') : t('offline', 'Offline')}</small>
        </label>
      </div>

      <fieldset className="quick-edit-nodes">
        <legend>{t('quickEditNodes', 'Assigned nodes')}</legend>
        <div className="quick-edit-node-list">
          {sortedNodes.map(node => {
            const nodeId = Number(node.id);
            const checked = nodeIds.includes(nodeId);
            const unavailable = !node.status || node.drain || node.maintenance;
            return (
              <label key={nodeId} className={`quick-edit-node ${checked ? 'selected' : ''} ${unavailable ? 'unavailable' : ''}`}>
                <input
                  className="quick-edit-node-checkbox"
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleNode(node)}
                  disabled={unavailable}
                />
                <span>{node.name}</span>
                {unavailable && <small>{t('quickEditNodeUnavailable', 'Unavailable')}</small>}
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="quick-edit-footer">
        <button
          type="button"
          className={`btn btn-secondary quick-edit-reset-usage ${resetUsage ? 'selected' : ''}`}
          onClick={() => setResetUsage(value => !value)}
          aria-pressed={resetUsage}
        >
          {resetUsage ? t('quickEditResetQueued', 'Reset Usage on Apply ✓') : t('resetUsageButton', 'Reset Usage')}
        </button>
        <div className="quick-edit-footer-actions">
          <button type="button" className="btn btn-secondary quick-edit-cancel" onClick={onCancel} disabled={saving}>
            {t('cancelButton', 'Cancel')}
          </button>
          <button type="submit" className="btn quick-edit-apply" disabled={saving}>
            {saving ? t('saving', 'Saving…') : t('quickEditApply', 'Apply')}
          </button>
        </div>
      </div>
      {error && <p className="error-message quick-edit-error" role="alert">{error}</p>}
    </form>
  );
};

export default InlineUserQuickEdit;
