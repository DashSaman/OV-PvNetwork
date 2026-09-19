import { useState, useEffect } from 'react';
import apiClient from '../services/api';
import { useTranslation } from 'react-i18next';
import LoadingButton from './LoadingButton';
const EditAdminModal = ({
  admin,
  onClose,
  onAdminUpdated
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
  useEffect(() => {
    if (admin) {
      setFormData({
        username: admin.username,
        password: '',
        quota_total_gb: (Number(admin.quota_total || 0) / 1024 / 1024 / 1024).toFixed(2),
        unlimited_quota_total: String(Number(admin.unlimited_quota_total || 0)),
        is_active: admin.is_active !== false
      });
    }
  }, [admin]);
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
    setIsLoading(true);
    try {
      const quota = Number(formData.quota_total_gb);
      const unlimitedQuota = Number(formData.unlimited_quota_total);
      if (!Number.isInteger(unlimitedQuota) || unlimitedQuota < 0) {
        setError(t('validation.invalidUnlimitedQuota', 'تعداد اکانت نامحدود باید عدد صحیح صفر یا بیشتر باشد.'));
        return;
      }
      const response = await apiClient.put('/admin/', {
        username: formData.username,
        password: formData.password || null,
        quota_total: Math.round(quota * 1024 * 1024 * 1024),
        unlimited_quota_total: unlimitedQuota,
        is_active: formData.is_active
      });
      if (response.data.success) {
        alert(t('adminUpdatedSuccess'));
        onAdminUpdated();
      } else {
        setError(response.data.msg || t('unableToUpdateAdmin'));
      }
    } catch (err) {
      setError(err.response?.data?.detail || t('errorUpdatingAdmin'));
    } finally {
      setIsLoading(false);
    }
  };
  return <div className="modal-overlay">
            <div className="modal">
                <div className="modal-header">
                    <h3>{t('editAdmin')}</h3>
                    <button onClick={onClose} className="close-modal-btn">&times;</button>
                </div>
                <form onSubmit={handleSubmit}>
                    <div className="input-group">
                        <label htmlFor="username">{t('username')}</label>
                        <input type="text" id="username" name="username" value={formData.username} disabled readOnly />
                    </div>

                    <div className="input-group">
                        <label htmlFor="password">{t('newPassword')}</label>
                        <input type="password" id="password" name="password" value={formData.password} onChange={handleChange} placeholder={t('enterNewPassword')} />
                    </div>

                    <div className="input-group">
                        <label htmlFor="quota_total_gb">{t("ui.ebee8cf050df")}</label>
                        <input type="number" id="quota_total_gb" name="quota_total_gb" value={formData.quota_total_gb} onChange={handleChange} min="0" step="0.01" required />
                        <small>{t("ui.3de0dfb4ec8e")}{(Number(admin.quota_used || 0) / 1024 / 1024 / 1024).toFixed(2)}{t("ui.505a44facaa3")}</small>
                    </div>

                    <div className="input-group">
                        <label htmlFor="unlimited_quota_total">{t('resellerUnlimitedQuota', 'تعداد مجاز اکانت نامحدود')}</label>
                        <input type="number" id="unlimited_quota_total" name="unlimited_quota_total" value={formData.unlimited_quota_total} onChange={handleChange} min="0" step="1" required />
                        <small>{t('resellerUnlimitedUsed', 'مصرف‌شده:')} {Number(admin.unlimited_quota_used || 0)} {t('accountUnit', 'اکانت')}</small>
                    </div>

                    <div className="input-group">
                        <label><input type="checkbox" name="is_active" checked={formData.is_active} onChange={handleChange} />{t("ui.adca744d9a15")}</label>
                    </div>

                    <div className="modal-footer">
                        <button type="button" onClick={onClose} className="btn btn-secondary">
                            {t('cancelButton')}
                        </button>
                        <LoadingButton type="submit" className="btn" isLoading={isLoading}>
                            {t('updateAdminButton')}
                        </LoadingButton>
                    </div>
                    {error && <p className="error-message">{error}</p>}
                </form>
            </div>
        </div>;
};
export default EditAdminModal;
