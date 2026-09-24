import { useState, useEffect } from 'react';
import apiClient from '../services/api';
import { useTranslation } from 'react-i18next';
import LoadingButton from './LoadingButton';

const EditUserModal = ({ user, onClose, onUserUpdated, userRole }) => {
  // PVNETWORK_DURATION_EDIT_UI_V8
  const effectiveRole = userRole || localStorage.getItem('userRole') || '';
  const isReseller = effectiveRole === 'admin';
  const [expiryDate, setExpiryDate] = useState('');
  const [totalTraffic, setTotalTraffic] = useState('');
  const [deviceLimit, setDeviceLimit] = useState('1');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { t } = useTranslation();

  const bytesFromGB = value => {
    const cleaned = value?.toString().trim();
    if (!cleaned) return null;
    const parsed = parseFloat(cleaned);
    return Number.isNaN(parsed) ? null : Math.round(parsed * 1024 * 1024 * 1024);
  };

  const gbFromBytes = bytes => {
    if (bytes === null || bytes === undefined) return '';
    const gb = Number(bytes) / 1024 / 1024 / 1024;
    return Number.isFinite(gb) ? parseFloat(gb.toFixed(2)).toString() : '';
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

  const displayedTraffic = totalTraffic === '' ? gbFromBytes(user?.total) : totalTraffic;
  const isUnlimited = Number(displayedTraffic || 0) <= 0;
  const isResellerUnlimited = isReseller && isUnlimited;

  useEffect(() => {
    if (user?.expiry_date) setExpiryDate(String(user.expiry_date).split('T')[0]);
    if (user) {
      setTotalTraffic(gbFromBytes(user.total));
      setDeviceLimit(String(user.device_limit ?? 1));
    }
  }, [user]);

  const handleSubmit = async event => {
    event.preventDefault();
    setError('');
    const parsedDeviceLimit = isResellerUnlimited ? 1 : Number(deviceLimit);
    if (!Number.isInteger(parsedDeviceLimit) || parsedDeviceLimit < 0) {
      setError(t('deviceLimitInvalid', 'تعداد اتصال باید صفر یا یک عدد صحیح مثبت باشد.'));
      return;
    }

    const oldUnlimited = Number(user?.total || 0) <= 0;
    const newUnlimited = Number(displayedTraffic || 0) <= 0;
    let payloadExpiry = expiryDate;
    if (!isReseller && !oldUnlimited && newUnlimited) payloadExpiry = addDaysToToday(30);

    setIsLoading(true);
    try {
      const response = await apiClient.put(`/users/${user.uuid}/`, {
        name: user.name,
        expiry_date: payloadExpiry,
        total: bytesFromGB(totalTraffic),
        device_limit: parsedDeviceLimit
      });
      if (response.data.success) {
        alert(t('userUpdated', 'کاربر با موفقیت بروزرسانی شد.'));
        onUserUpdated();
      } else {
        setError(response.data.msg || t('updateUserFailed', 'بروزرسانی انجام نشد.'));
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.msg || t('updateUserError', 'خطا در بروزرسانی کاربر.'));
    } finally {
      setIsLoading(false);
    }
  };

  if (!user) return null;

  return <div className="modal-overlay">
    <div className="modal">
      <div className="modal-header">
        <h3>{t('modal_editUserTitle', 'ویرایش کاربر')} - {user.name}</h3>
        <button onClick={onClose} className="close-modal-btn">&times;</button>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <label htmlFor="edit-user-name">{t('username', 'نام کاربری')}</label>
          <input type="text" id="edit-user-name" value={user.name} disabled />
        </div>

        <div className="input-group">
          <label htmlFor="edit-user-total">{t('modal_totalTraffic', 'کل ترافیک (گیگابایت)')}</label>
          <input type="number" id="edit-user-total" value={totalTraffic} onChange={e => setTotalTraffic(e.target.value)} min="0" step="0.01" />
        </div>

        {isReseller ? <div className="input-group">
          <label>{t('accountDuration', 'مدت اعتبار حساب')}</label>
          <small>{t('resellerExpiryHiddenLocked', 'مدت در زمان ساخت ثبت شده و بعد از ثبت برای نماینده قابل مشاهده یا تغییر نیست.')}</small>
        </div> : <div className="input-group">
          <label htmlFor="edit-user-expiry">{t('modal_expiryDate', 'تاریخ انقضا')}</label>
          {isUnlimited ? <>
            <input type="text" value={t('renewUnlimitedFixed30', 'اکانت نامحدود: دوره ثابت ۳۰ روزه')} disabled />
            <small>{t('renewUnlimitedNoEdit', 'تاریخ دوره نامحدود با ویرایش عادی تمدید نمی‌شود.')}</small>
          </> : <input type="date" id="edit-user-expiry" value={expiryDate} onChange={e => setExpiryDate(e.target.value)} required />}
        </div>}

        <div className="input-group">
          <label htmlFor="edit-user-device-limit">{t('modal_deviceLimit', 'تعداد اتصال همزمان')}</label>
          <input type="number" id="edit-user-device-limit" value={isResellerUnlimited ? '1' : deviceLimit} onChange={e => setDeviceLimit(e.target.value)} min={isResellerUnlimited ? '1' : '0'} step="1" required disabled={isResellerUnlimited} />
          <small>{isResellerUnlimited ? t('deviceLimitUnlimitedReseller', 'اکانت نامحدود نماینده فقط تک‌کاربره است.') : t('deviceLimitHint', '۰ = بدون محدودیت اتصال، ۱ = تک‌کاربره')}</small>
        </div>

        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">{t('cancelButton', 'انصراف')}</button>
          <LoadingButton isLoading={isLoading} type="submit" className="btn">{t('updateUserButton', 'بروزرسانی کاربر')}</LoadingButton>
        </div>
        {error && <p className="error-message">{error}</p>}
      </form>
    </div>
  </div>;
};

export default EditUserModal;
