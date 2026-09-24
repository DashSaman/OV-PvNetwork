import { useEffect, useState } from 'react';
import apiClient from '../services/api';
import { useTranslation } from 'react-i18next';

// PVNETWORK_ANYCONNECT_USER_TOGGLE_V1
const AnyConnectUserModal = ({ user, onClose, onChanged }) => {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null);
  const [customPassword, setCustomPassword] = useState('');
  const [shownPassword, setShownPassword] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  const errorText = exception =>
    exception?.response?.data?.detail ||
    exception?.response?.data?.msg ||
    exception?.message ||
    t('anyConnect.opFailed', 'خطا در انجام عملیات AnyConnect');

  const loadStatus = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await apiClient.get(`/anyconnect/users/${user.uuid}`);
      setStatus(response.data?.data || null);
    } catch (exception) {
      setError(errorText(exception));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (user?.uuid) loadStatus();
    // Reload only when the selected user changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.uuid]);

  const rotatePassword = async () => {
    setIsSaving(true);
    setError('');
    setShownPassword('');
    try {
      const payload = customPassword.trim()
        ? { password: customPassword }
        : {};
      const response = await apiClient.post(
        `/anyconnect/users/${user.uuid}/password`,
        payload
      );
      const data = response.data?.data || {};
      setShownPassword(data.password || '');
      setCustomPassword('');
      setStatus(previous => ({
        ...(previous || {}),
        configured: true,
        enabled: Boolean(data.enabled),
        password_available: true,
        server: data.server || previous?.server,
        password_changed_at: Math.floor(Date.now() / 1000)
      }));
      if (onChanged) onChanged();
    } catch (exception) {
      setError(errorText(exception));
    } finally {
      setIsSaving(false);
    }
  };

  const revealPassword = async () => {
    setIsSaving(true);
    setError('');
    try {
      const response = await apiClient.get(
        `/anyconnect/users/${user.uuid}/password`
      );
      setShownPassword(response.data?.data?.password || '');
    } catch (exception) {
      setError(errorText(exception));
    } finally {
      setIsSaving(false);
    }
  };

  const toggleStatus = async () => {
    setIsSaving(true);
    setError('');
    try {
      const enabled = !status?.enabled;
      const response = await apiClient.put(
        `/anyconnect/users/${user.uuid}/status`,
        { enabled }
      );
      const data = response.data?.data || {};
      if (data.password) setShownPassword(data.password);
      setStatus(previous => ({
        ...(previous || {}),
        configured: Boolean(data.configured),
        enabled,
        password_available: Boolean(data.password_available)
      }));
      if (onChanged) onChanged();
    } catch (exception) {
      setError(errorText(exception));
    } finally {
      setIsSaving(false);
    }
  };

  const copyPassword = async () => {
    if (!shownPassword) return;
    try {
      await navigator.clipboard.writeText(shownPassword);
      window.alert(t('anyConnect.passwordCopied', 'رمز AnyConnect کپی شد.'));
    } catch {
      window.prompt(t('anyConnect.copyPasswordPrompt', 'رمز را کپی کنید:'), shownPassword);
    }
  };

  const copyConnection = async () => {
    if (!shownPassword) return;
    const value = [
      `Server: ${status?.server || 'vpn.example.com:9443'}`,
      `Username: ${user.name}`,
      `Password: ${shownPassword}`
    ].join('\n');
    try {
      await navigator.clipboard.writeText(value);
      window.alert(t('anyConnect.detailsCopied', 'اطلاعات اتصال کپی شد.'));
    } catch {
      window.prompt(t('anyConnect.copyDetailsPrompt', 'اطلاعات اتصال را کپی کنید:'), value);
    }
  };

  if (!user) return null;

  return <div className="modal-overlay">
    <div className="modal" dir="rtl">
      <div className="modal-header">
        <h3>AnyConnect — {user.name}</h3>
        <button onClick={onClose} className="close-modal-btn">&times;</button>
      </div>

      {isLoading ? <p>{t('anyConnect.loadingStatus', 'در حال دریافت وضعیت...')}</p> : <>
        <div className="input-group">
          <label>{t('anyConnect.accountStatus', 'وضعیت حساب AnyConnect')}</label>
          <input
            type="text"
            disabled
            value={status?.configured
              ? (status?.enabled ? t('anyConnect.stateEnabled', 'فعال') : t('anyConnect.stateDisabled', 'غیرفعال'))
              : t('anyConnect.noPasswordYet', 'هنوز رمز ساخته نشده')}
          />
        </div>

        <div className="input-group">
          <label>{t('anyConnect.serverAddress', 'آدرس سرور')}</label>
          <input
            type="text"
            readOnly
            dir="ltr"
            value={status?.server || 'vpn.example.com:9443'}
          />
        </div>

        <div className="input-group">
          <label>{t('anyConnect.finlandGatewayStatus', 'وضعیت درگاه فنلاند')}</label>
          <input
            type="text"
            disabled
            value={status?.gateway_ready
              ? t('anyConnect.gatewayReady', 'درگاه آماده اتصال است')
              : t('anyConnect.gatewayTesting', 'درگاه عمومی هنوز در مرحله تست است')}
          />
        </div>

        <div className="input-group">
          <label htmlFor="anyconnect-custom-password">
            {t('anyConnect.customPasswordOptional', 'رمز دلخواه (اختیاری)')}
          </label>
          <input
            id="anyconnect-custom-password"
            type="password"
            minLength="12"
            maxLength="64"
            autoComplete="new-password"
            value={customPassword}
            onChange={event => setCustomPassword(event.target.value)}
            placeholder={t('anyConnect.customPasswordPlaceholder', 'خالی بماند تا رمز قوی خودکار ساخته شود')}
          />
          <small>{t('anyConnect.passwordLengthHint', 'رمز باید ۱۲ تا ۶۴ کاراکتر باشد.')}</small>
        </div>

        <div className="modal-footer" style={{ flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn"
            disabled={isSaving}
            onClick={rotatePassword}
          >
            {status?.configured ? t('anyConnect.changePassword', 'تغییر رمز AnyConnect') : t('anyConnect.generatePassword', 'ساخت رمز AnyConnect')}
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            disabled={isSaving}
            onClick={toggleStatus}
          >
            {status?.enabled ? t('anyConnect.disableAction', 'غیرفعال‌کردن') : t('anyConnect.enableAction', 'فعال‌کردن')}
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            disabled={isSaving || !status?.password_available}
            onClick={revealPassword}
          >
            {t('anyConnect.showCurrentPassword', 'نمایش رمز فعلی')}
          </button>
        </div>

        {shownPassword && <div className="input-group" style={{ marginTop: 18 }}>
          <label>{t('anyConnect.currentPassword', 'رمز فعلی AnyConnect')}</label>
          <input type="text" readOnly value={shownPassword} dir="ltr" />
          <div className="modal-footer" style={{ flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={copyPassword}
            >
              {t('anyConnect.copyPassword', 'کپی رمز')}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={copyConnection}
            >
              {t('anyConnect.copyDetails', 'کپی اطلاعات اتصال')}
            </button>
          </div>
        </div>}
      </>}

      {error && <p className="error-message">{error}</p>}

      <div className="modal-footer">
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          {t('close', 'بستن')}
        </button>
      </div>
    </div>
  </div>;
};

export default AnyConnectUserModal;
