import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';

export default function NodeReconcilePanel({ node, onClose }) {
  const { t } = useTranslation();
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const dialog = useRef(null);
  const active = busy || ['queued', 'running'].includes(job?.state);
  useEffect(() => {
    const previous = document.activeElement;
    dialog.current?.focus();
    const saved = sessionStorage.getItem(`pvnReconcile-${node.id}`);
    if (saved && /^[a-f0-9-]{36}$/.test(saved)) setJob({ id: saved, state: 'queued', progress: 0 });
    return () => previous?.focus();
  }, [node.id]);
  useEffect(() => {
    const escape = event => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [onClose]);
  useEffect(() => {
    if (!job?.id || !['queued', 'running'].includes(job.state)) return undefined;
    let stopped = false;
    let timer;
    const poll = async () => {
      try {
        const response = await apiClient.get(`/nodes/${node.id}/reconcile/${job.id}`);
        if (stopped) return;
        if (!response.data.success) throw new Error();
        setJob(response.data.data); setError('');
        if (['queued', 'running'].includes(response.data.data.state)) timer = setTimeout(poll, 1500);
      } catch (exception) {
        if (stopped) return;
        setError(t('nodeReconcile.failed'));
        if ([403, 404].includes(exception?.response?.status)) {
          setJob(null); sessionStorage.removeItem(`pvnReconcile-${node.id}`);
        } else timer = setTimeout(poll, 5000);
      }
    };
    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [job?.id, job?.state, node.id, t]);
  const submit = async () => {
    setBusy(true); setError('');
    try {
      const response = await apiClient.post(`/nodes/${node.id}/reconcile`, {});
      if (!response.data.success) throw new Error();
      const id = response.data.data.job_id;
      sessionStorage.setItem(`pvnReconcile-${node.id}`, id);
      setJob({ id, state: 'queued', progress: 0 });
    } catch { setError(t('nodeReconcile.failed')); }
    finally { setBusy(false); }
  };
  const keyboard = event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.current.querySelectorAll('button:not(:disabled)')];
    const first = controls[0]; const last = controls.at(-1);
    if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first?.focus(); }
  };
  return <div className="modal-overlay"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="node-reconcile-title" ref={dialog} tabIndex={-1} onKeyDown={keyboard}>
    <div className="modal-header"><h3 id="node-reconcile-title">{t('nodeReconcile.title')} — {node.name}</h3><button type="button" onClick={onClose} aria-label={t('close')}>×</button></div>
    <div className="modal-body">
      <p>{t('nodeReconcile.scope')}</p>
      {job && <div role="status" aria-live="polite"><p>{t(`nodeReconcile.${job.state}`, { defaultValue: job.state })}</p><progress max="100" value={job.progress || 0} /></div>}
      {error && <p className="error-message" role="alert">{error}</p>}
    </div>
    <div className="modal-footer"><button type="button" className="btn" onClick={onClose}>{t('close')}</button><button type="button" className="btn" disabled={active} onClick={submit}>{t('nodeReconcile.start')}</button></div>
  </section></div>;
}
