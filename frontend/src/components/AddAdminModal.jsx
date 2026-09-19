import { useState } from 'react';
import apiClient from '../services/api';
import { useTranslation } from 'react-i18next';
import LoadingButton from './LoadingButton';


// PVNETWORK_ADD_ADMIN_ERROR_FIX_V2
const formatApiError = (error, fallback) => {
  const payload = error?.response?.data;
  const detail = payload?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map(item => {
        if (typeof item === 'string') {
          return item;
        }

        const field = Array.isArray(item?.loc)
          ? item.loc.filter(value => value !== 'body').join('.')
          : '';

        const message =
          typeof item?.msg === 'string'
            ? item.msg
            : 'مقدار واردشده معتبر نیست.';

        return field ? `${field}: ${message}` : message;
      })
      .filter(Boolean);

    if (messages.length) {
      return messages.join(' | ');
    }
  }

  if (detail && typeof detail === 'object') {
    if (typeof detail.msg === 'string') {
      return detail.msg;
    }

    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }

  return payload?.msg || error?.message || fallback;
};

const AddAdminModal = ({
  onClose,
  onAdminCreated
}) => {
  const {
    t
  } = useTranslation();
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    quota_total_gb: '',
    unlimited_quota_total: '0',
    is_active: true
  });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const handleChange = event => {
    const {
      name,
      value,
      type,
      checked
    } = event.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };
  const handleSubmit = async event => {
    event.preventDefault();
    setError('');
    if (!formData.username || !formData.password) {
      setError(t('fillAllFields'));
      return;
    }
    // PVNETWORK_ADD_ADMIN_VALIDATION_V2
    const username = formData.username.trim();

    if (username.length < 3 || username.length > 10) {
      setError('نام کاربری نماینده باید بین ۳ تا ۱۰ کاراکتر باشد.');
      return;
    }

    if (formData.password.length < 6 || formData.password.length > 20) {
      setError('رمز عبور نماینده باید بین ۶ تا ۲۰ کاراکتر باشد.');
      return;
    }

    setFormData(previous => ({
      ...previous,
      username
    }));

    setIsLoading(true);
    try {
      const quota = Number(formData.quota_total_gb);
      if (!Number.isFinite(quota) || quota < 0) {
        setError(t('validation.invalidQuota'));
        return;
      }
      const unlimitedQuota = Number(formData.unlimited_quota_total);
      if (!Number.isInteger(unlimitedQuota) || unlimitedQuota < 0) {
        setError(t('validation.invalidUnlimitedQuota', 'تعداد اکانت نامحدود باید عدد صحیح صفر یا بیشتر باشد.'));
        return;
      }
      const response = await apiClient.post('/admin/', {
        username: formData.username,
        password: formData.password,
        quota_total: Math.round(quota * 1024 * 1024 * 1024),
        unlimited_quota_total: unlimitedQuota,
        is_active: formData.is_active
      });
      if (response.data.success) {
        alert(t('adminCreatedSuccess'));
        onAdminCreated();
      } else {
        setError(response.data.msg || t('unableToCreateAdmin'));
      }
    } catch (err) {
      setError(formatApiError(err, t('errorCreatingAdmin')));
    } finally {
      setIsLoading(false);
    }
  };
  return <div className="modal-overlay">
            <div className="modal">
                <div className="modal-header">
                    <h3>{t('addNewAdmin')}</h3>
                    <button onClick={onClose} className="close-modal-btn">&times;</button>
                </div>
                <form onSubmit={handleSubmit}>
                    <div className="input-group">
                        <label htmlFor="username">{t('username')}</label>
                        <input type="text" id="username" name="username" value={formData.username} onChange={handleChange} minLength="3" maxLength="10" autoComplete="off" required />
                    </div>

                    <div className="input-group">
                        <label htmlFor="quota_total_gb">{t("ui.a5ed6b1206b7")}</label>
                        <input type="number" id="quota_total_gb" name="quota_total_gb" value={formData.quota_total_gb} onChange={handleChange} min="0" step="0.01" required />
                    </div>

                    <div className="input-group">
                        <label htmlFor="unlimited_quota_total">{t('resellerUnlimitedQuota', 'تعداد مجاز اکانت نامحدود')}</label>
                        <input type="number" id="unlimited_quota_total" name="unlimited_quota_total" value={formData.unlimited_quota_total} onChange={handleChange} min="0" step="1" required />
                        <small>{t('resellerUnlimitedQuotaHelp', 'هر اکانت نامحدود برای همیشه یک عدد از سهمیه مصرف می‌کند؛ حذف آن سهمیه را برنمی‌گرداند.')}</small>
                    </div>

                    <div className="input-group">
                        <label><input type="checkbox" name="is_active" checked={formData.is_active} onChange={handleChange} />{t("ui.adca744d9a15")}</label>
                    </div>

                    <div className="input-group">
                        <label htmlFor="password">{t('password')}</label>
                        <input type="password" id="password" name="password" value={formData.password} onChange={handleChange} minLength="6" maxLength="20" autoComplete="new-password" required />
                    </div>

                    <div className="modal-footer">
                        <button type="button" onClick={onClose} className="btn btn-secondary">
                            {t('cancelButton')}
                        </button>
                        <LoadingButton type="submit" className="btn" isLoading={isLoading}>
                            {t('createAdminButton')}
                        </LoadingButton>
                    </div>
                    {error && <p className="error-message">{error}</p>}
                </form>
            </div>
        </div>;
};
export default AddAdminModal;
