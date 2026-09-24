import { useEffect, useState } from 'react';
import apiClient from '../services/api';
import { useTranslation } from 'react-i18next';
import LoadingButton from './LoadingButton';

const AddUserModal = ({
  onClose,
  onUserAdded,
  userRole,
  anyConnectDefaultEnabled = false,
  nodes = []
}) => {
  // PVNETWORK_DURATION_UI_V8
  // PVNETWORK_RESELLER_DURATION_MAX6_V8_1
  const effectiveRole = userRole || localStorage.getItem('userRole') || '';
  const isReseller = effectiveRole === 'admin';
  const isMainAdmin = effectiveRole === 'main_admin';
  const [name, setName] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [durationMonths, setDurationMonths] = useState('1');
  const [expiryMode, setExpiryMode] = useState('date');
  const [durationDays, setDurationDays] = useState('30');
  const [totalTraffic, setTotalTraffic] = useState('');
  const [deviceLimit, setDeviceLimit] = useState('1');
  const [anyConnectEnabled, setAnyConnectEnabled] = useState(
    Boolean(anyConnectDefaultEnabled)
  );
  const [routerDevicesEnabled, setRouterDevicesEnabled] = useState(false);
  // PVN-1011: live Router-capability probe for the selected nodes.
  const [routerReadiness, setRouterReadiness] = useState({ checking: false, ready: [], failed: [] });
  const [routerResults, setRouterResults] = useState(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState([]);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { t } = useTranslation();

  useEffect(() => {
    setAnyConnectEnabled(Boolean(anyConnectDefaultEnabled));
  }, [anyConnectDefaultEnabled]);

  useEffect(() => {
    setSelectedNodeIds(
      (nodes || [])
        .filter(node => node.status && !node.drain && !node.maintenance)
        .map(node => Number(node.id))
    );
  }, [nodes]);

  // PVNETWORK_CREATE_USER_ROUTER_CREDENTIALS_V1
  const provisionRouterCredentials = async (userUuid, nodeNameById) => {
    const results = [];
    for (const nodeId of selectedNodeIds) {
      try {
        const response = await apiClient.post(
          `/router-openvpn/users/${userUuid}/nodes/${nodeId}/credential`,
          null,
          { timeout: 60000 }
        );
        const data = response.data?.data || null;
        results.push({
          nodeId,
          nodeName: data?.node_name || nodeNameById[nodeId] || `Node ${nodeId}`,
          nodeAddress: String(nodeNameById['address_' + nodeId] || ''),
          ok: true,
          username: data?.username || '',
          password: data?.password || '',
        });
      } catch (err) {
        results.push({
          nodeId,
          nodeName: nodeNameById[nodeId] || `Node ${nodeId}`,
          nodeAddress: String(nodeNameById['address_' + nodeId] || ''),
          ok: false,
          detail: err?.response?.data?.detail || err?.response?.data?.msg || err.message || '',
        });
      }
    }
    return results;
  };

  const sortedNodes = [...(nodes || [])].sort((a, b) =>
    String(a.name || '').localeCompare(String(b.name || ''))
  );

  const toggleNode = node => {
    if (!node.status || node.drain || node.maintenance) return;
    const nodeId = Number(node.id);
    setSelectedNodeIds(current =>
      current.includes(nodeId)
        ? current.filter(item => item !== nodeId)
        : [...current, nodeId].sort((a, b) => a - b)
    );
  };

  const numericTraffic = Number(totalTraffic || 0);
  const isUnlimited = Number.isFinite(numericTraffic) && numericTraffic <= 0;
  const isResellerUnlimited = isReseller && isUnlimited;

  const bytesFromGB = value => {
    const cleaned = value?.toString().trim();
    if (!cleaned) return null;
    const parsed = parseFloat(cleaned);
    return Number.isNaN(parsed) ? null : Math.round(parsed * 1024 * 1024 * 1024);
  };

  const formatLocalDate = value => {
    const yyyy = value.getFullYear();
    const mm = String(value.getMonth() + 1).padStart(2, '0');
    const dd = String(value.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  };

  const addDaysToToday = days => {
    const now = new Date();
    now.setHours(12, 0, 0, 0);
    now.setDate(now.getDate() + Number(days));
    return formatLocalDate(now);
  };

  const addMonthsToToday = months => {
    const now = new Date();
    now.setHours(12, 0, 0, 0);
    const originalDay = now.getDate();
    const target = new Date(now.getFullYear(), now.getMonth() + Number(months), 1, 12);
    const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0, 12).getDate();
    target.setDate(Math.min(originalDay, lastDay));
    return formatLocalDate(target);
  };

  const handleSubmit = async event => {
    event.preventDefault();
    setError('');

    const total = bytesFromGB(totalTraffic);
    const parsedDeviceLimit = isResellerUnlimited ? 1 : Number(deviceLimit);
    if (!Number.isInteger(parsedDeviceLimit) || parsedDeviceLimit < 0) {
      setError(t('deviceLimitInvalid', 'تعداد اتصال باید صفر یا یک عدد صحیح مثبت باشد.'));
      return;
    }

    let computedExpiry = expiryDate;
    let payloadMonths = null;
    let payloadDays = null;

    if (isUnlimited) {
      // Every unlimited account created in this UI is fixed to 30 days.
      computedExpiry = addDaysToToday(30);
      payloadDays = 30;
      if (isReseller) payloadMonths = 1;
    } else if (isReseller) {
      const months = Number(durationMonths);
      if (!Number.isInteger(months) || months < 1 || months > 6) {
        setError(t('resellerDurationInvalid', 'مدت حساب را بین ۱ تا ۶ ماه انتخاب کنید.'));
        return;
      }
      computedExpiry = addMonthsToToday(months);
      payloadMonths = months;
    } else if (isMainAdmin && expiryMode === 'days') {
      const days = Number(durationDays);
      if (!Number.isInteger(days) || days < 1 || days > 3650) {
        setError(t('adminDurationDaysInvalid', 'تعداد روز باید بین ۱ تا ۳۶۵۰ باشد.'));
        return;
      }
      computedExpiry = addDaysToToday(days);
      payloadDays = days;
    } else if (!computedExpiry) {
      setError(t('expiryRequired', 'تاریخ انقضا را انتخاب کنید.'));
      return;
    }

    if (selectedNodeIds.length === 0) {
      setError(t('createUserNodeRequired', 'حداقل یک نود در دسترس را انتخاب کنید.'));
      return;
    }

    setIsLoading(true);
    try {
      const response = await apiClient.post('/users/', {
        name,
        expiry_date: computedExpiry,
        duration_months: payloadMonths,
        duration_days: payloadDays,
        total,
        device_limit: parsedDeviceLimit,
        anyconnect_enabled: anyConnectEnabled,
        node_ids: selectedNodeIds
      });
      if (response.data.success) {
        if (!routerDevicesEnabled) {
          alert(t('userCreated', 'کاربر با موفقیت ساخته شد.'));
          onUserAdded();
          return;
        }
        // PVN-1009: create returns {name, uuid}; older backends returned the
        // bare name — fall back to a name-based lookup before giving up.
        let userUuid = response.data?.data?.uuid || response.data?.data?.user?.uuid || '';
        if (!userUuid && typeof response.data?.data === 'string') {
          try {
            const listed = await apiClient.get('/users/', { timeout: 30000 });
            const found = (listed.data?.data || []).find(item => item && item.name === response.data.data);
            userUuid = found?.uuid || '';
          } catch { userUuid = ''; }
        }
        if (!userUuid) {
          alert(t('userCreated', 'کاربر با موفقیت ساخته شد.'));
          onUserAdded();
          return;
        }
        const nodeNameById = {};
        (nodes || []).forEach(node => { nodeNameById[Number(node.id)] = node.name; });
        const results = await provisionRouterCredentials(userUuid, nodeNameById);
        setRouterResults({ username: name, userUuid, results });
      } else {
        setError(response.data.msg || t('createUserFailed', 'ساخت کاربر انجام نشد.'));
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.msg || t('createUserError', 'خطا در ساخت کاربر.'));
    } finally {
      setIsLoading(false);
    }
  };

  const monthOptions = Array.from({ length: 6 }, (_, index) => index + 1);

  // PVN-1011: probe each selected node for a healthy Router listener so the
  // operator knows before submitting whether credentials can be generated.
  const probeRouterReadiness = async () => {
    if (!selectedNodeIds.length) return;
    setRouterReadiness({ checking: true, ready: [], failed: [] });
    const checks = await Promise.all(selectedNodeIds.map(async nodeId => {
      try {
        const r = await apiClient.get(`/router-openvpn/nodes/${nodeId}`, { timeout: 15000 });
        const d = r.data?.data || {};
        return { nodeId, ok: Boolean(d.enabled && d.healthy), upgrade: Boolean(d.upgrade_required) };
      } catch {
        return { nodeId, ok: false, upgrade: false };
      }
    }));
    setRouterReadiness({
      checking: false,
      ready: checks.filter(c => c.ok).map(c => c.nodeId),
      failed: checks.filter(c => !c.ok),
    });
  };

  const handleRouterToggle = event => {
    setRouterDevicesEnabled(event.target.checked);
    if (event.target.checked) probeRouterReadiness();
  };

  // PVN-1011: translate common credential failures into actionable text.
  const routerFriendlyError = detail => {
    const text = String(detail || '');
    if (text.includes('not enabled on this node')) {
      return t('routerErrNotEnabled', 'قابلیت Router روی این نود فعال نیست — از صفحه نودها → Router/MikroTik فعالش کن.');
    }
    if (text.includes('not healthy on this node')) {
      return t('routerErrNotHealthy', 'Listener روتر روی این نود سالم نیست — وضعیتش را در صفحه نودها بررسی کن.');
    }
    if (text.includes('upgrade')) {
      return t('routerErrUpgrade', 'این نود باید اول ارتقا پیدا کند تا Router پشتیبانی شود.');
    }
    return text.slice(0, 200);
  };

  // PVN-1009: authenticated Router profile download for the results panel.
  const downloadRouterProfile = async nodeId => {
    try {
      const response = await apiClient.get(
        `/router-openvpn/users/${routerResults.userUuid}/nodes/${nodeId}/profile`,
        { responseType: 'blob', timeout: 60000 }
      );
      const href = URL.createObjectURL(response.data);
      const anchor = document.createElement('a');
      anchor.href = href;
      anchor.download = `router-${routerResults.username}-${nodeId}.ovpn`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(href), 1000);
    } catch (err) {
      setError(String(err?.response?.data?.detail || err?.response?.data?.msg || err.message || 'Download failed'));
    }
  };
  if (routerResults) {
    const okResults = routerResults.results.filter(item => item.ok);
    const failedResults = routerResults.results.filter(item => !item.ok);
    return <div className="modal-overlay">
      <div className="modal">
        <div className="modal-header">
          <h3>{t('createUserRouterGenerated', 'کاربر ساخته شد — اعتبارنامه Router')}</h3>
          <button onClick={onClose} className="close-modal-btn">&times;</button>
        </div>
        <div className="input-group">
          <p style={{ fontWeight: 700 }}>{t('createUserRouterOnceWarning', 'این رمزها فقط یک بار نمایش داده می‌شوند؛ همین حالا ذخیره کنید.')}</p>
          {okResults.map(item => (
            <div key={item.nodeId} style={{ border: '1px solid rgba(148,163,184,.3)', borderRadius: 10, padding: 10, marginBottom: 8 }}>
              <strong>{item.nodeName}{item.nodeAddress ? ' · ' + item.nodeAddress : ''}</strong>
              <div dir="ltr" style={{ fontFamily: 'monospace' }}>user: {item.username}</div>
              <div dir="ltr" style={{ fontFamily: 'monospace' }}>pass: {item.password}</div>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ marginTop: 6 }}
                onClick={() => downloadRouterProfile(item.nodeId)}
              >
                {t('routerPanelDownloadProfile', 'دانلود پروفایل Router')}
              </button>
            </div>
          ))}
          {failedResults.map(item => (
            <div key={item.nodeId} className="error-message" style={{ marginBottom: 8 }}>
              {t('createUserRouterNodeFailed', 'تولید اعتبارنامه ناموفق:')} {item.nodeName} — {routerFriendlyError(item.detail)}
            </div>
          ))}
          <details style={{ marginTop: 10 }}>
            <summary style={{ cursor: 'pointer', fontWeight: 700 }}>{t('routerPanelGuideTitle', 'آموزش اتصال MikroTik / RouterOS')}</summary>
            <div style={{ fontSize: 12.5, lineHeight: 1.9, marginTop: 8, whiteSpace: 'pre-line' }}>{t('routerPanelGuide', "RouterOS → PPP → Add → OVPN Client: Connect to را روی آدرس سرور بالا بگذار؛ User/Password بالا را وارد کن؛ Mode: IP؛ پروفایل Router را دانلود و Certificate آن را import کن؛ Use Peer DNS در صورت نیاز.")}</div>
          </details>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={() => { setRouterResults(null); onUserAdded(); }}>
            {t('close', 'بستن')}
          </button>
        </div>
      </div>
    </div>;
  }

  return <div className="modal-overlay">
    <div className="modal">
      <div className="modal-header">
        <h3>{t('modal_createUserTitle', 'ایجاد کاربر جدید')}</h3>
        <button onClick={onClose} className="close-modal-btn">&times;</button>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <label htmlFor="new-user-name">{t('username', 'نام کاربری')}</label>
          <input type="text" id="new-user-name" value={name} onChange={e => setName(e.target.value)} required minLength="3" maxLength="10" />
        </div>

        <div className="input-group">
          <label htmlFor="new-user-total">{t('modal_totalTraffic', 'کل ترافیک (گیگابایت)')}</label>
          <input type="number" id="new-user-total" value={totalTraffic} onChange={e => setTotalTraffic(e.target.value)} min="0" step="0.01" placeholder={t('quickEditUnlimitedHint', '0 = نامحدود')} />
        </div>

        <div className="input-group">
          <label>{t('accountDuration', 'مدت اعتبار حساب')}</label>

          {isUnlimited ? <>
            <select value="30" disabled aria-label={t('unlimitedDurationLabel', 'مدت اکانت نامحدود')}>
              <option value="30">{t('oneMonth30Days', '۱ ماه (۳۰ روز)')}</option>
            </select>
            <small>{t('unlimitedFixedDuration', 'اکانت نامحدود فقط با اعتبار ۳۰ روز ساخته می‌شود.')}</small>
          </> : isReseller ? <>
            <select id="new-user-duration-months" value={durationMonths} onChange={e => setDurationMonths(e.target.value)} required>
              {monthOptions.map(month => <option key={month} value={month}>{month} {t('renewUnitMonths', 'ماه')}</option>)}
            </select>
            <small>{t('resellerMonthSelectHelp', 'نماینده فقط مدت را انتخاب می‌کند؛ تاریخ به‌صورت خودکار محاسبه می‌شود.')}</small>
          </> : <>
            <select value={expiryMode} onChange={e => setExpiryMode(e.target.value)}>
              <option value="date">{t('expiryModeDate', 'انتخاب تاریخ دقیق')}</option>
              <option value="days">{t('expiryModeDays', 'تعداد روز از امروز')}</option>
            </select>
            {expiryMode === 'date'
              ? <input type="date" id="new-user-expiry" value={expiryDate} onChange={e => setExpiryDate(e.target.value)} required />
              : <input type="number" id="new-user-duration-days" value={durationDays} onChange={e => setDurationDays(e.target.value)} min="1" max="3650" step="1" required placeholder={t('durationDaysPlaceholder', 'مثلاً 30 یا 60')} />}
            <small>{expiryMode === 'date' ? t('expiryDateHint', 'تاریخ دقیق را انتخاب کنید.') : t('expiryDaysHint', 'مثلاً ۳۰، ۶۰ یا هر تعداد روز دلخواه.')}</small>
          </>}
        </div>

        <div className="input-group">
          <label htmlFor="new-user-device-limit">{t('modal_deviceLimit', 'تعداد اتصال همزمان')}</label>
          <input type="number" id="new-user-device-limit" value={isResellerUnlimited ? '1' : deviceLimit} onChange={e => setDeviceLimit(e.target.value)} min={isResellerUnlimited ? '1' : '0'} step="1" required disabled={isResellerUnlimited} />
          <small className="device-limit-help">
            {isResellerUnlimited ? t('deviceLimitUnlimitedReseller', 'اکانت نامحدود نماینده فقط تک‌کاربره است.') : t('deviceLimitHint', '۰ = بدون محدودیت اتصال، ۱ = تک‌کاربره')}
          </small>
        </div>

        <fieldset className="create-user-nodes">
          <legend>{t('createUserNodes', 'نودهای مقصد')}</legend>
          <small className="create-user-nodes-help">
            {t('createUserNodesHelp', 'همه نودهای در دسترس به‌صورت پیش‌فرض انتخاب شده‌اند.')}
          </small>
          <div className="create-user-node-list">
            {sortedNodes.length === 0 ? (
              <p className="empty-message">{t('noNodesAvailable', 'هیچ نودی موجود نیست.')}</p>
            ) : sortedNodes.map(node => {
              const nodeId = Number(node.id);
              const unavailable = !node.status || node.drain || node.maintenance;
              const checked = selectedNodeIds.includes(nodeId);
              return (
                <label
                  key={nodeId}
                  className={`create-user-node ${checked ? 'selected' : ''} ${unavailable ? 'unavailable' : ''}`}
                >
                  <input
                    className="create-user-node-checkbox"
                    type="checkbox"
                    checked={checked}
                    disabled={unavailable}
                    onChange={() => toggleNode(node)}
                  />
                  <span>{node.name}</span>
                  {unavailable && (
                    <small>{t('createUserNodeUnavailable', 'غیردردسترس')}</small>
                  )}
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="input-group">
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            cursor: 'pointer'
          }}>
            <input
              type="checkbox"
              checked={anyConnectEnabled}
              onChange={event => setAnyConnectEnabled(event.target.checked)}
            />
            <span>{t('createUserAnyConnectToggle', 'فعال‌سازی AnyConnect برای این کاربر')}</span>
          </label>
          <small>
            {t('createUserAnyConnectHelp', 'در صورت فعال‌بودن، همان نام کاربری OpenVPN با یک رمز تصادفی امن استفاده می‌شود.')}
          </small>
        </div>

        <div className="input-group">
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            cursor: 'pointer'
          }}>
            <input
              type="checkbox"
              checked={routerDevicesEnabled}
              onChange={handleRouterToggle}
            />
            <span>{t('createUserRouterToggle', 'دستگاه‌های Router / MikroTik (نام کاربری و رمز)')}</span>
          </label>
          <small>
            {t('createUserRouterHelp', 'پس از ساخت کاربر، برای هر نود انتخابی دارای Listener سازگاری Router، نام کاربری و رمز یک‌بارمصرف ساخته و نمایش داده می‌شود. پروفایل عادی OpenVPN بدون تغییر و بدون رمز باقی می‌ماند.')}
          </small>
          {routerDevicesEnabled && routerReadiness.checking && (
            <small>{t('routerStatusChecking', 'در حال بررسی وضعیت Router نودهای انتخابی…')}</small>
          )}
          {routerDevicesEnabled && !routerReadiness.checking && routerReadiness.failed.length > 0 && (
            <small style={{ color: '#ff596d', display: 'block', marginTop: 4 }}>
              {t('routerStatusNone', 'قابلیت Router/MikroTik هنوز روی هیچ‌کدام از نودهای انتخابی فعال نیست؛ نام کاربری و رمز ساخته نمی‌شود. برای فعال‌سازی: صفحه «نودها» → روی نود دلخواه → Router / MikroTik → اجرای Preflight و Enable.')}
            </small>
          )}
          {routerDevicesEnabled && !routerReadiness.checking && routerReadiness.failed.length === 0 && routerReadiness.ready.length > 0 && (
            <small style={{ color: '#24dc8b', display: 'block', marginTop: 4 }}>
              {t('routerStatusReady', 'نودهای آماده Router:')} {routerReadiness.ready.length}/{selectedNodeIds.length}
            </small>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">{t('cancelButton', 'انصراف')}</button>
          <LoadingButton isLoading={isLoading} type="submit" className="btn">{t('createUserButton', 'ایجاد کاربر')}</LoadingButton>
        </div>
        {error && <p className="error-message">{error}</p>}
      </form>
    </div>
  </div>;
};

export default AddUserModal;
