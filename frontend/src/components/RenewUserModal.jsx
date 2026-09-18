import { useMemo, useState } from 'react';
import apiClient from '../services/api';
import { useTranslation } from 'react-i18next';
import LoadingButton from './LoadingButton';

const GB = 1024 * 1024 * 1024;

const RenewUserModal = ({ user, onClose, onRenewed }) => {
  const { t } = useTranslation();
  const [durationDays, setDurationDays] = useState('30');
  const [trafficAction, setTrafficAction] = useState('preserve');
  const [addTrafficGb, setAddTrafficGb] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const unlimited = Number(user?.total || 0) <= 0;
  const exhausted = !unlimited && Number(user?.used || 0) >= Number(user?.total || 0);
  const options = useMemo(() => [30, 60, 90], []);

  if (!user) return null;

  const submit = async event => {
    event.preventDefault();
    setError('');
    const days = Number(durationDays);
    const addBytes = Math.round(Number(addTrafficGb || 0) * GB);

    if (!Number.isInteger(days) || days < 1 || days > 3650) {
      setError(t('renewDaysInvalid', 'تعداد روز باید بین ۱ تا ۳۶۵۰ باشد.'));
      return;
    }
    if (trafficAction === 'add' && (!Number.isFinite(addBytes) || addBytes <= 0)) {
      setError(t('renewAddTrafficInvalid', 'حجم افزایشی باید بیشتر از صفر باشد.'));
      return;
    }

    setIsLoading(true);
    try {
      const response = await apiClient.post(`/users/${user.uuid}/renew`, {
        duration_days: days,
        traffic_action: unlimited ? 'preserve' : trafficAction,
        add_traffic: unlimited ? 0 : addBytes
      });
      if (!response.data?.success) throw new Error(response.data?.msg || 'Renew failed');
      onRenewed(response.data.data || {});
    } catch (exception) {
      setError(exception?.response?.data?.detail || exception?.response?.data?.msg || exception?.message || t('renewFailed', 'تمدید انجام نشد.'));
    } finally {
      setIsLoading(false);
    }
  };

  return <div className="modal-overlay">
    <div className="modal">
      <div className="modal-header">
        <h3>{t('renewUserTitle', 'تمدید کاربر')} - {user.name}</h3>
        <button onClick={onClose} className="close-modal-btn">&times;</button>
      </div>
      <form onSubmit={submit}>
        <div className="input-group">
          <label>{t('renewDuration', 'مدت تمدید')}</label>
          <select value={options.includes(Number(durationDays)) ? durationDays : 'custom'} onChange={e => {
            if (e.target.value !== 'custom') setDurationDays(e.target.value);
          }}>
            {options.map(value => <option key={value} value={value}>{value} روز</option>)}
            <option value="custom">دلخواه</option>
          </select>
          <input type="number" min="1" max="3650" step="1" value={durationDays} onChange={e => setDurationDays(e.target.value)} />
        </div>

        {unlimited ? <div className="input-group">
          <label>{t('renewTraffic', 'حجم')}</label>
          <input type="text" value="نامحدود — بدون تغییر" disabled />
        </div> : <div className="input-group">
          <label>{t('renewTrafficAction', 'رفتار حجم')}</label>
          <select value={trafficAction} onChange={e => setTrafficAction(e.target.value)}>
            {!exhausted && <option value="preserve">حفظ مصرف و حجم فعلی</option>}
            <option value="reset">ریست مصرف و شروع دوره جدید</option>
            <option value="add">افزودن حجم</option>
          </select>
          {trafficAction === 'add' && <input type="number" min="0.01" step="0.01" value={addTrafficGb} onChange={e => setAddTrafficGb(e.target.value)} placeholder="GB" />}
        </div>}

        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn btn-secondary">{t('cancelButton', 'انصراف')}</button>
          <LoadingButton isLoading={isLoading} type="submit" className="btn">{t('renewButton', 'تمدید')}</LoadingButton>
        </div>
        {error && <p className="error-message">{error}</p>}
      </form>
    </div>
  </div>;
};

export default RenewUserModal;
