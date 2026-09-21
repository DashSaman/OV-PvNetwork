import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';
import './RenameUserModal.css';

const TERMINAL = new Set(['completed', 'rolled_back', 'failed']);
const USERNAME_RE = /^[A-Za-z0-9_-]{3,64}$/;

const RenameUserModal = ({
  user,
  nodes = [],
  open,
  initialJob = null,
  onClose,
  onQueued,
  onCompleted,
}) => {
  const { t } = useTranslation();
  const [newUsername, setNewUsername] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [job, setJob] = useState(initialJob);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const completedRef = useRef('');

  const assignedNodes = useMemo(() => {
    const ids = new Set((user?.node_ids || []).map(Number));
    return nodes.filter(node => ids.has(Number(node.id)));
  }, [nodes, user?.node_ids]);

  useEffect(() => {
    if (!open) return;
    setNewUsername(initialJob?.new_name || '');
    setJob(initialJob || null);
    setAcknowledged(Boolean(initialJob));
    setError('');
    completedRef.current = '';
  }, [open, user?.uuid, initialJob]);

  useEffect(() => {
    if (!open || !user?.uuid || !job?.id || TERMINAL.has(job.state)) return undefined;
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await apiClient.get(`/users/${user.uuid}/rename/${job.id}`);
        if (!cancelled && response.data?.success) setJob(response.data.data || null);
      } catch (exception) {
        if (!cancelled) setError(exception?.response?.data?.detail || exception?.message || 'Unable to read rename status.');
      }
    };
    poll();
    const timer = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [open, user?.uuid, job?.id, job?.state]);

  useEffect(() => {
    if (job?.state !== 'completed' || completedRef.current === job.id) return;
    completedRef.current = job.id;
    onCompleted?.(job);
    onClose?.();
  }, [job, onCompleted, onClose]);

  if (!open || !user) return null;

  const valid = USERNAME_RE.test(newUsername) && newUsername !== user.name;
  const busy = Boolean(job?.id && !TERMINAL.has(job.state));
  const progressStates = ['preflight', 'staging', 'cutover', 'revoking_old', 'cleanup_pending', 'completed'];

  const submit = async event => {
    event.preventDefault();
    if (!valid || !acknowledged || busy) return;
    setSubmitting(true);
    setError('');
    try {
      const response = await apiClient.post(`/users/${user.uuid}/rename`, { new_username: newUsername });
      if (!response.data?.success) throw new Error(response.data?.msg || 'Unable to queue rename.');
      const queued = response.data.data;
      setJob(queued);
      onQueued?.(queued);
    } catch (exception) {
      const detail = exception?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : exception?.response?.data?.msg || exception?.message || 'Unable to queue rename.');
    } finally {
      setSubmitting(false);
    }
  };

  const retryCleanup = async () => {
    if (!job?.id || job.state !== 'cleanup_pending') return;
    setSubmitting(true);
    setError('');
    try {
      const response = await apiClient.post(`/users/${user.uuid}/rename/${job.id}/retry`);
      if (response.data?.success) setJob(response.data.data);
    } catch (exception) {
      setError(exception?.response?.data?.detail || exception?.message || 'Unable to retry cleanup.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rename-modal-backdrop" role="presentation">
      <section className="rename-modal" role="dialog" aria-modal="true" aria-labelledby="rename-user-title">
        <header className="rename-modal-header">
          <div>
            <h3 id="rename-user-title">{t('renameUsername')}</h3>
            <p><strong>{user.name}</strong>{newUsername ? ` → ${newUsername}` : ''}</p>
          </div>
          <button type="button" className="rename-modal-close" onClick={onClose} aria-label={t('cancelButton', 'Close')}>×</button>
        </header>

        <form onSubmit={submit} className="rename-modal-body">
          <label>
            <span>{t('renameNewUsername')}</span>
            <input value={newUsername} onChange={event => setNewUsername(event.target.value.trim())} disabled={busy || submitting} autoComplete="off" />
          </label>

          <div className="rename-node-list">
            <strong>{t('renameAffectedNodes')}</strong>
            {assignedNodes.map(node => <span key={node.id}>{node.name} <small>#{node.id}</small></span>)}
          </div>

          <div className="rename-warning" role="alert">
            <p>{t('renameOldProfilesWarning')}</p>
            <p>{t('renameSessionsWarning')}</p>
          </div>

          {!job?.id && <label className="rename-ack">
            <input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />
            <span>{t('renameAcknowledge')}</span>
          </label>}

          {job?.id && <div className="rename-progress" aria-live="polite">
            {progressStates.map(state => <span key={state} className={job.state === state ? 'current' : ''}>{t(`renameState.${state}`, state)}</span>)}
            <p>{t('renameCurrentState')}: <strong>{job.state}</strong></p>
            {job.state === 'cleanup_pending' && <p>{t('renameCleanupPending')}</p>}
          </div>}

          {error && <p className="error-message" role="alert">{String(error)}</p>}
          <footer className="rename-modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>{t('cancelButton', 'Close')}</button>
            {job?.state === 'cleanup_pending' ? (
              <button type="button" className="btn" onClick={retryCleanup} disabled={submitting}>{t('renameRetryCleanup')}</button>
            ) : !job?.id ? (
              <button type="submit" className="btn" disabled={!valid || !acknowledged || submitting}>{submitting ? t('saving', 'Saving…') : t('renameStart')}</button>
            ) : null}
          </footer>
        </form>
      </section>
    </div>
  );
};

export default RenameUserModal;
