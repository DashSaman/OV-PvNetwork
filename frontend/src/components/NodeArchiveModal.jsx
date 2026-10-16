import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import apiClient from '../services/api';
import './NodeArchiveModal.css';

const emptyCredentials = { ssh_username: 'root', ssh_port: 22, ssh_password: '', ssh_private_key: '', ssh_key_passphrase: '', ssh_fingerprint: '' };
const NodeArchiveModal = ({ node, onClose, onChanged }) => {
  const { t } = useTranslation();
  const [credentials, setCredentials] = useState(emptyCredentials);
  const [auth, setAuth] = useState('password');
  const [operation, setOperation] = useState('backup');
  const [file, setFile] = useState(null);
  const [archive, setArchive] = useState(null);
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [offline, setOffline] = useState(false);
  const [startRecovered, setStartRecovered] = useState(false);
  const [confirmDowntime, setConfirmDowntime] = useState(false);
  const dialog = useRef(null);
  const alive = useRef(true);
  const active = job && ['queued', 'running'].includes(job.state);
  const base = `/nodes/${node.id}/archives`;
  const message = exception => {
    const detail = exception?.response?.data?.detail;
    return typeof detail === 'string' ? detail : t('nodeArchive.failed');
  };
  useEffect(() => {
    alive.current = true;
    const previous = document.activeElement;
    dialog.current?.focus();
    const saved = sessionStorage.getItem(`pvnNodeArchive-${node.id}`);
    if (saved && /^[a-f0-9]{24}$/.test(saved)) { setArchive({ archive_id: saved }); setJob({ state: 'queued', progress: 0 }); }
    return () => { alive.current = false; previous?.focus(); };
  }, [node.id]);
  useEffect(() => {
    const escape = event => {
      if (event.key === 'Escape') { event.preventDefault(); setCredentials(emptyCredentials); setFile(null); onClose(); }
    };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [onClose]);
  useEffect(() => {
    if (!active || !archive?.archive_id) return undefined;
    let stopped = false;
    let timer;
    const poll = async () => {
      try {
        const response = await apiClient.get(`${base}/${archive.archive_id}/status`);
        if (stopped) return;
        const value = response.data.data;
        setJob(value); setError('');
        if (value.state === 'succeeded') {
          if (value.result?.sha256) setArchive(value.result);
          onChanged?.();
        }
        if (['queued', 'running'].includes(value.state)) timer = setTimeout(poll, 1500);
      } catch (exception) {
        if (!stopped) {
          setError(message(exception));
          if ([403, 404].includes(exception?.response?.status)) { setJob({ state: 'failed', progress: 0 }); sessionStorage.removeItem(`pvnNodeArchive-${node.id}`); }
          else timer = setTimeout(poll, 5000);
        }
      }
    };
    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [active, archive?.archive_id, base]); // eslint-disable-line react-hooks/exhaustive-deps
  const change = event => setCredentials(value => ({ ...value, [event.target.name]: event.target.value }));
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      let selected = archive;
      if (operation === 'restore' && file) {
        if (file.size > 60 * 1024 ** 2 || file.size === 0) throw new Error(t('nodeArchive.uploadLimit'));
        const response = await apiClient.post(`${base}/upload`, file, { headers: { 'Content-Type': 'application/octet-stream' }, timeout: 120000 });
        selected = response.data.data;
        if (alive.current) { setArchive(selected); setFile(null); }
      }
      if (operation === 'restore' && !selected?.archive_id) throw new Error(t('nodeArchive.chooseFile'));
      const payload = { ...credentials, ssh_port: Number(credentials.ssh_port) };
      if (auth === 'key') payload.ssh_password = ''; else { payload.ssh_private_key = ''; payload.ssh_key_passphrase = ''; }
      if (operation === 'restore') Object.assign(payload, { archive_id: selected.archive_id, offline, start_recovered: startRecovered, confirm_downtime: confirmDowntime });
      const response = await apiClient.post(`${base}/${operation}`, payload);
      sessionStorage.setItem(`pvnNodeArchive-${node.id}`, response.data.data.archive_id);
      if (alive.current) {
        setArchive(operation === 'restore' ? { ...selected, ...response.data.data } : response.data.data);
        setJob({ state: 'queued', progress: 0, stage: 'queued' });
      }
    } catch (exception) {
      if (alive.current) setError(exception.response ? message(exception) : exception.message || t('nodeArchive.failed'));
    } finally {
      if (alive.current) { setCredentials(value => ({ ...value, ssh_password: '', ssh_private_key: '', ssh_key_passphrase: '' })); setBusy(false); }
    }
  };
  const download = async () => {
    setBusy(true); setError('');
    try {
      const response = await apiClient.get(`${base}/${archive.archive_id}/download`, { responseType: 'blob', timeout: 120000 });
      const url = URL.createObjectURL(response.data); const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `pvnetwork-node-${node.id}-${archive.archive_id}.tar.gz`; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (exception) { if (alive.current) setError(message(exception)); }
    finally { if (alive.current) setBusy(false); }
  };
  const discard = async () => {
    setBusy(true); setError('');
    try {
      await apiClient.delete(`${base}/${archive.archive_id}`);
      sessionStorage.removeItem(`pvnNodeArchive-${node.id}`);
      if (alive.current) { setArchive(null); setJob(null); }
    } catch (exception) { if (alive.current) setError(message(exception)); }
    finally { if (alive.current) setBusy(false); }
  };
  const close = () => { setCredentials(emptyCredentials); setFile(null); onClose(); };
  const trap = event => {
    if (event.key !== 'Tab') return;
    const fields = [...dialog.current.querySelectorAll('button,input,select,textarea,a[href]')].filter(item => !item.disabled && item.offsetParent !== null);
    const first = fields[0]; const last = fields.at(-1);
    if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  };
  return <div className="modal-overlay">
    <div ref={dialog} className="modal node-archive-modal" role="dialog" aria-modal="true" aria-labelledby="node-archive-title" tabIndex={-1} onKeyDown={trap}>
      <div className="modal-header"><h3 id="node-archive-title">{t('nodeArchive.title')} — {node.name}</h3><button type="button" className="close-modal-btn" onClick={close} aria-label={t('nodeArchive.close')}>×</button></div>
      <p className="node-archive-warning">{t('nodeArchive.privateWarning')}</p>
      <p>{t('nodeArchive.scope')}</p>
      {error && <p role="alert" className="error-message">{error}</p>}
      {job && <div aria-live="polite"><progress max="100" value={job.progress || 0} aria-label={t('nodeArchive.progress')} /><p>{job.state === 'failed' ? t('nodeArchive.failed') : job.state === 'succeeded' ? t('nodeArchive.complete') : t('nodeArchive.running')} ({job.progress || 0}%)</p>{job.error && <p role="alert">{job.error}</p>}</div>}
      {job?.result?.private_staging_retained && <p role="alert">{t('nodeArchive.stagingRetained')}</p>}
      {archive?.sha256 && <div className="node-archive-receipt"><p>{t('nodeArchive.expires')}: {new Date(archive.expires_at * 1000).toLocaleString()}</p><p>SHA256: <code dir="ltr">{archive.sha256}</code></p><button type="button" data-action="download" disabled={busy || active} onClick={download}>{t('nodeArchive.download')}</button><button type="button" data-action="discard" disabled={busy || active} onClick={discard}>{t('nodeArchive.discard')}</button></div>}
      <form onSubmit={submit} autoComplete="off">
        <fieldset disabled={busy || active}>
          <label>{t('nodeArchive.operation')}<select name="operation" value={operation} onChange={event => setOperation(event.target.value)}><option value="backup">{t('nodeArchive.backup')}</option><option value="restore">{t('nodeArchive.restore')}</option><option value="recover">{t('nodeArchive.recover')}</option></select></label>
          {operation === 'restore' && <>
            <label>{t('nodeArchive.file')}<input name="archive_file" type="file" accept=".tar.gz,.tgz,application/gzip" onChange={event => { setFile(event.target.files?.[0] || null); }} /></label><p>{t('nodeArchive.uploadLimit')}</p>
            <label className="node-archive-check"><input name="offline" type="checkbox" checked={offline} onChange={event => { setOffline(event.target.checked); setStartRecovered(false); setConfirmDowntime(false); }} />{t('nodeArchive.offline')}</label>
            {offline && <><label className="node-archive-check"><input name="confirm_downtime" type="checkbox" required checked={confirmDowntime} onChange={event => setConfirmDowntime(event.target.checked)} />{t('nodeArchive.confirm')}</label><label className="node-archive-check"><input name="start_recovered" type="checkbox" checked={startRecovered} onChange={event => setStartRecovered(event.target.checked)} />{t('nodeArchive.start')}</label></>}
          </>}
          <div className="node-archive-fields"><label>{t('nodeArchive.username')}<input name="ssh_username" value={credentials.ssh_username} onChange={change} required autoComplete="off" /></label><label>{t('nodeArchive.port')}<input name="ssh_port" type="number" min="1" max="65535" value={credentials.ssh_port} onChange={change} required /></label></div>
          <label>{t('nodeArchive.auth')}<select name="auth" value={auth} onChange={event => { setAuth(event.target.value); setCredentials(value => ({ ...value, ssh_password: '', ssh_private_key: '', ssh_key_passphrase: '' })); }}><option value="password">{t('nodeArchive.password')}</option><option value="key">{t('nodeArchive.key')}</option></select></label>
          {auth === 'password' ? <label>{t('nodeArchive.password')}<input type="password" name="ssh_password" value={credentials.ssh_password} onChange={change} required autoComplete="new-password" /></label> : <><label>{t('nodeArchive.key')}<textarea name="ssh_private_key" value={credentials.ssh_private_key} onChange={change} required rows="4" spellCheck="false" /></label><label>{t('nodeArchive.passphrase')}<input type="password" name="ssh_key_passphrase" value={credentials.ssh_key_passphrase} onChange={change} autoComplete="new-password" /></label></>}
          <label>{t('nodeArchive.fingerprint')}<input name="ssh_fingerprint" value={credentials.ssh_fingerprint} onChange={change} dir="ltr" placeholder="SHA256:…" /></label>
          <p>{t('nodeArchive.trust')}</p>
          <button type="submit" className="btn btn-primary">{t('nodeArchive.run')}</button>
        </fieldset>
      </form>
      {active && <p>{t('nodeArchive.background')}</p>}
    </div>
  </div>;
};
export default NodeArchiveModal;
