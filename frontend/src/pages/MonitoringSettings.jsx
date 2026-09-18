import { t } from "../i18n";
import { useCallback, useEffect, useRef, useState } from 'react';
import { FiBell, FiSave, FiSend } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';
const defaults = {
  enabled: false,
  telegram_token: '',
  telegram_configured: false,
  telegram_chat_id: '',
  cpu_limit: 85,
  ram_limit: 85,
  disk_limit: 85,
  ssl_host: '',
  ssl_port: 443,
  ssl_warning_days: 14
};
export default function MonitoringSettings() {
  const { t: translate, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || 'en';
  const tr = useCallback(key => translate(`feature.${key}`), [translate]);
  const [form, setForm] = useState(defaults);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const mounted = useRef(true);
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/server/monitoring', {
        timeout: 12000
      });
      if (mounted.current) {
        setForm({
          ...defaults,
          ...(response.data.data || {}),
          telegram_token: ''
        });
      }
    } catch (requestError) {
      if (mounted.current) {
        setError(requestError.response?.data?.detail || requestError.response?.data?.msg || tr('loadFailed'));
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [tr]);
  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
    };
  }, [load]);
  const set = (key, value) => {
    setForm(current => ({
      ...current,
      [key]: value
    }));
  };
  const save = async event => {
    event.preventDefault();
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const payload = {
        enabled: Boolean(form.enabled),
        telegram_chat_id: form.telegram_chat_id || null,
        cpu_limit: Number(form.cpu_limit),
        ram_limit: Number(form.ram_limit),
        disk_limit: Number(form.disk_limit),
        ssl_host: form.ssl_host || null,
        ssl_port: Number(form.ssl_port),
        ssl_warning_days: Number(form.ssl_warning_days)
      };
      if (form.telegram_token) {
        payload.telegram_token = form.telegram_token;
      }
      const response = await apiClient.put('/server/monitoring', payload, {
        timeout: 15000
      });
      setForm(current => ({
        ...current,
        ...(response.data.data || {}),
        telegram_token: ''
      }));
      setMessage(tr('saved'));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.response?.data?.msg || tr('loadFailed'));
    } finally {
      setSaving(false);
    }
  };
  const testTelegram = async () => {
    setTesting(true);
    setMessage('');
    setError('');
    try {
      await apiClient.post('/server/monitoring/test', {}, {
        timeout: 15000
      });
      setMessage(tr('testSent'));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || requestError.response?.data?.msg || tr('testFailed'));
    } finally {
      setTesting(false);
    }
  };
  if (loading) {
    return <div className="view" data-no-translate="true" dir={['fa', 'ar'].includes(language) ? t("ui.dbc9052979a4") : t("ui.61ac44aaabb6")}>
        <div className="ov-page-loader">
          <span>{tr('loading')}</span>
          <button type="button" className="btn" onClick={load}>
            {tr('retry')}
          </button>
        </div>
      </div>;
  }
  return <div className="view" data-no-translate="true" dir={['fa', 'ar'].includes(language) ? t("ui.dbc9052979a4") : t("ui.61ac44aaabb6")}>
      <div className="view-header">
        <h2><FiBell /> {tr('monitoringTitle')}</h2>
      </div>

      <form className="monitor-form" onSubmit={save}>
        <label className="ov-switch-row">
          <input type="checkbox" checked={Boolean(form.enabled)} onChange={event => set('enabled', event.target.checked)} />
          <span>{tr('enableAlerts')}</span>
        </label>

        <div className="monitor-grid">
          <label>
            {tr('telegramToken')}
            <input type="password" value={form.telegram_token} placeholder={form.telegram_configured ? tr('telegramTokenHint') : tr('telegramToken')} onChange={event => set('telegram_token', event.target.value)} autoComplete="new-password" />
          </label>

          <label>
            {tr('telegramChat')}
            <input value={form.telegram_chat_id || ''} onChange={event => set('telegram_chat_id', event.target.value)} />
          </label>

          <label>
            {tr('cpuLimit')}
            <input type="number" min="1" max="100" value={form.cpu_limit} onChange={event => set('cpu_limit', event.target.value)} />
          </label>

          <label>
            {tr('ramLimit')}
            <input type="number" min="1" max="100" value={form.ram_limit} onChange={event => set('ram_limit', event.target.value)} />
          </label>

          <label>
            {tr('diskLimit')}
            <input type="number" min="1" max="100" value={form.disk_limit} onChange={event => set('disk_limit', event.target.value)} />
          </label>

          <label>
            {tr('sslHost')}
            <input value={form.ssl_host || ''} onChange={event => set('ssl_host', event.target.value)} />
          </label>

          <label>
            {tr('sslPort')}
            <input type="number" min="1" max="65535" value={form.ssl_port} onChange={event => set('ssl_port', event.target.value)} />
          </label>

          <label>
            {tr('sslDays')}
            <input type="number" min="1" max="365" value={form.ssl_warning_days} onChange={event => set('ssl_warning_days', event.target.value)} />
          </label>
        </div>

        {error && <div className="ov-error-panel">{error}</div>}
        {message && <div className="ov-success-panel">{message}</div>}

        <div className="ov-action-row">
          <button type="submit" className="btn" disabled={saving}>
            <FiSave />
            {saving ? tr('saving') : tr('save')}
          </button>

          <button type="button" className="btn" disabled={testing || !form.telegram_configured} onClick={testTelegram}>
            <FiSend />
            {testing ? tr('testing') : tr('testTelegram')}
          </button>

          <button type="button" className="btn" onClick={load}>
            {tr('retry')}
          </button>
        </div>
      </form>
    </div>;
}
