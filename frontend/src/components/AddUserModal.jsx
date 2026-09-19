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
        alert(t('userCreated', 'کاربر با موفقیت ساخته شد.'));
        onUserAdded();
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
          <input type="number" id="new-user-total" value={totalTraffic} onChange={e => setTotalTraffic(e.target.value)} min="0" step="0.01" placeholder="0 = نامحدود" />
        </div>

        <div className="input-group">
          <label>{t('accountDuration', 'مدت اعتبار حساب')}</label>

          {isUnlimited ? <>
            <select value="30" disabled aria-label="مدت اکانت نامحدود">
              <option value="30">۱ ماه (۳۰ روز)</option>
            </select>
            <small>{t('unlimitedFixedDuration', 'اکانت نامحدود فقط با اعتبار ۳۰ روز ساخته می‌شود.')}</small>
          </> : isReseller ? <>
            <select id="new-user-duration-months" value={durationMonths} onChange={e => setDurationMonths(e.target.value)} required>
              {monthOptions.map(month => <option key={month} value={month}>{month} ماه</option>)}
            </select>
            <small>{t('resellerMonthSelectHelp', 'نماینده فقط مدت را انتخاب می‌کند؛ تاریخ به‌صورت خودکار محاسبه می‌شود.')}</small>
          </> : <>
            <select value={expiryMode} onChange={e => setExpiryMode(e.target.value)}>
              <option value="date">انتخاب تاریخ دقیق</option>
              <option value="days">تعداد روز از امروز</option>
            </select>
            {expiryMode === 'date'
              ? <input type="date" id="new-user-expiry" value={expiryDate} onChange={e => setExpiryDate(e.target.value)} required />
              : <input type="number" id="new-user-duration-days" value={durationDays} onChange={e => setDurationDays(e.target.value)} min="1" max="3650" step="1" required placeholder="مثلاً 30 یا 60" />}
            <small>{expiryMode === 'date' ? 'تاریخ دقیق را انتخاب کنید.' : 'مثلاً ۳۰، ۶۰ یا هر تعداد روز دلخواه.'}</small>
          </>}
        </div>

        <div className="input-group">
          <label htmlFor="new-user-device-limit">{t('modal_deviceLimit', 'تعداد اتصال همزمان')}</label>
          <input type="number" id="new-user-device-limit" value={isResellerUnlimited ? '1' : deviceLimit} onChange={e => setDeviceLimit(e.target.value)} min={isResellerUnlimited ? '1' : '0'} step="1" required disabled={isResellerUnlimited} />
          <small className="device-limit-help">
            {isResellerUnlimited ? 'اکانت نامحدود نماینده فقط تک‌کاربره است.' : '۰ = بدون محدودیت اتصال، ۱ = تک‌کاربره'}
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
            <span>فعال‌سازی AnyConnect برای این کاربر</span>
          </label>
          <small>
            در صورت فعال‌بودن، همان نام کاربری OpenVPN با یک رمز تصادفی امن استفاده می‌شود.
          </small>
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
