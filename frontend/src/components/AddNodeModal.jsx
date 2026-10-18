import ModalOverlay from './ModalOverlay';
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import apiClient from '../services/api';
import { useTranslation } from 'react-i18next';
import LoadingButton from './LoadingButton';
const AddNodeModal = ({
  onClose,
  onNodeCreated
}) => {
  const {
    t
  } = useTranslation();
  const [automatic, setAutomatic] = useState(true);
  const [sshAuthMethod, setSshAuthMethod] = useState('password');
  const [formData, setFormData] = useState({
    name: '',
    address: '',
    tunnel_address: '',
    protocol: 'udp',
    ovpn_port: 1194,
    port: 9090,
    key: '',
    status: true,
    set_new_setting: false,
    ssh_port: 22,
    ssh_username: 'root',
    ssh_password: '',
    ssh_fingerprint: '',
    panel_ip: '',
    ssh_private_key: '',
    ssh_key_passphrase: '',
    controller_url: window.location.origin,
    controller_ca_pem: '',
    mode: 'fresh',
    existing_node_id: ''
  });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [terminal, setTerminal] = useState(false);
  const [lines, setLines] = useState([]);
  const [seconds, setSeconds] = useState(0);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);
  const endRef = useRef(null);
  const pollRef = useRef(null);
  const startedAt = useRef(null);
  const titleId = useId();
  const formRef = useRef(null);
  const consoleRef = useRef(null);
  const previousTerminal = useRef(false);
  useLayoutEffect(() => {
    if (terminal) consoleRef.current?.focus();
    else if (previousTerminal.current) formRef.current?.querySelector('input,select,button')?.focus();
    previousTerminal.current = terminal;
  }, [terminal]);
  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: 'smooth'
    });
  }, [lines]);
  const log = (text, type = 'info') => setLines(p => [...p, {
    text,
    type,
    time: new Date().toLocaleTimeString('en-GB')
  }]);
  const startConsole = () => {
    setTerminal(true);
    setDone(false);
    setLines([]);
    setSeconds(0);
    setProgress(1);
    startedAt.current = Date.now();
  };
  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };
  const applyJob = job => {
    setProgress(Number(job.progress || 0));
    setSeconds(Math.max(0, Math.floor((Date.now() - (Number(job.created_at) || Math.floor(Date.now() / 1000)) * 1000) / 1000)));
    setLines((job.logs || []).map(x => ({
      text: x.message,
      type: x.level === 'error' ? 'bad' : x.level === 'ok' ? 'ok' : 'info',
      time: new Date(x.time * 1000).toLocaleTimeString('en-GB')
    })));
    if (job.state === 'succeeded') {
      stopPolling();
      localStorage.removeItem('ovNodeDeployJob');
      setError('');
      setDone(true);
      setIsLoading(false);
    }
    if (job.state === 'failed') {
      stopPolling();
      localStorage.removeItem('ovNodeDeployJob');
      setError(job.error || 'Deployment failed');
      setDone(true);
      setIsLoading(false);
    }
  };
  const pollJob = async jobId => {
    try {
      const r = await apiClient.get(`/nodes/deploy/${jobId}/`);
      if (!r.data.success) throw new Error(r.data.msg);
      applyJob(r.data.data);
    } catch (err) {
      stopPolling();
      setError(err.response?.data?.msg || err.message || 'Unable to read deployment status');
      setDone(true);
      setIsLoading(false);
    }
  };
  const watchJob = jobId => {
    localStorage.setItem('ovNodeDeployJob', jobId);
    pollJob(jobId);
    pollRef.current = setInterval(() => pollJob(jobId), 1200);
  };
  useEffect(() => {
    const existing = localStorage.getItem('ovNodeDeployJob');
    if (existing) {
      setTerminal(true);
      setIsLoading(true);
      watchJob(existing);
    }
    // Resume a persisted deployment only on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const handleChange = ({
    target
  }) => setFormData(p => ({
    ...p,
    [target.name]: target.type === 'checkbox' ? target.checked : target.value
  }));
  const field = (name, label, type = 'text', required = true) => <div className="input-group"><label htmlFor={name}>{label}</label><input id={name} name={name} type={type} value={formData[name]} onChange={handleChange} required={required} aria-describedby={name === 'ssh_fingerprint' ? `${titleId}-ssh-trust` : undefined} />{name === 'ssh_fingerprint' && <small id={`${titleId}-ssh-trust`}>{t('nodeArchive.trust')}</small>}</div>;
  const handleSubmit = async e => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    if (automatic) startConsole();
    try {
      let url = '/nodes/';
      let payload = {
        ...formData,
        ovpn_port: Number(formData.ovpn_port),
        port: Number(formData.port)
      };
      if (automatic) {
        url = '/nodes/deploy/';
        payload = {
          name: formData.name,
          address: formData.address,
          tunnel_address: formData.tunnel_address || null,
          protocol: formData.protocol,
          ovpn_port: Number(formData.ovpn_port),
          node_port: Number(formData.port),
          ssh_port: Number(formData.ssh_port),
          ssh_username: formData.ssh_username,
          ssh_password: sshAuthMethod === 'password' ? formData.ssh_password : null,
          ssh_private_key: sshAuthMethod === 'key' ? formData.ssh_private_key : null,
          ssh_key_passphrase: sshAuthMethod === 'key' ? formData.ssh_key_passphrase || null : null,
          controller_url: formData.controller_url,
          controller_ca_pem: formData.controller_ca_pem || null,
          mode: formData.mode,
          existing_node_id: formData.mode === 'adopt' ? Number(formData.existing_node_id) : null,
          ssh_fingerprint: formData.ssh_fingerprint || null,
          panel_ip: formData.panel_ip && formData.panel_ip.trim() ? formData.panel_ip.trim() : null
        };
      }
      const response = await apiClient.post(url, payload);
      if (!response.data.success) throw new Error(response.data.msg || 'Operation failed');
      if (automatic) {
        const jobId = response.data.data?.job_id;
        if (!jobId) throw new Error('Server did not return a deployment job ID');
        watchJob(jobId);
      } else {
        setIsLoading(false);
        onNodeCreated();
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.msg || err.message || 'Operation failed';
      setError(String(msg));
      if (automatic) {
        log('INSTALLATION FAILED', 'bad');
        log(String(msg), 'bad');
        setDone(true);
      }
      setIsLoading(false);
    } finally {
      setFormData(previous => ({ ...previous, ssh_password: '', ssh_private_key: '', ssh_key_passphrase: '' }));
    }
  };
  const leaveConsole = () => {
    if (!done) return;
    if (error) setTerminal(false); else onNodeCreated();
  };
  if (terminal) return <ModalOverlay onClose={leaveConsole} className="modal-overlay node-deployment-overlay"><div className="node-deployment-console" ref={consoleRef} tabIndex={-1} style={{
      width: 'min(1050px,100%)',
      height: 'min(720px,85dvh)',
      background: '#030806',
      border: '1px solid #194d32',
      borderRadius: 14,
      boxShadow: '0 0 60px rgba(0,255,128,.13)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'auto',
      fontFamily: 'Consolas,monospace'
    }}>
    <div style={{
        padding: '13px 18px',
        background: '#08110d',
        borderBottom: '1px solid #183426',
        display: 'flex',
        justifyContent: 'space-between',
        color: '#77ffac'
      }}><h3 id={titleId} style={{margin: 0, fontSize: 16}}>{t('addNodeDeploymentTitle', 'Node deployment')}</h3><span dir="ltr">{formData.address} · {String(Math.floor(seconds / 60)).padStart(2, '0')}:{String(seconds % 60).padStart(2, '0')}</span></div>
    <div role="progressbar" aria-label={t('nodeArchive.progress')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100, Math.max(0, progress))} style={{
        height: 4,
        background: '#102219'
      }}><div style={{
          height: '100%',
          width: `${progress}%`,
          background: done && error ? t("ui.eb4156f4a6ec") : t("ui.1ee3848386fd"),
          transition: 'width .5s'
        }} /></div>
    <div dir="ltr" style={{
        padding: '14px 18px',
        color: '#4fbd7b',
        fontSize: 12,
        borderBottom: '1px solid #11291c'
      }}>{t("ui.f2cb0a3aec62")}{formData.address}:{formData.ssh_port}{t("ui.c40f859cbc5b")}{formData.ssh_username}{t("ui.9530b0783061")}{formData.protocol.toUpperCase()}{t("ui.3a8b52048478")}{formData.ovpn_port}</div>
    <div role="log" aria-label={t('nodeArchive.progress')} aria-live="polite" aria-relevant="additions text" dir="ltr" style={{
        flex: 1,
        overflowY: 'auto',
        padding: 20,
        fontSize: 14,
        lineHeight: 1.8
      }}>{lines.map((x, i) => <div key={i} style={{
          color: x.type === 'ok' ? t("ui.741c0d690f42") : x.type === 'bad' ? t("ui.6684fdb6f2ae") : x.type === 'dim' ? t("ui.3cf51ada25e6") : t("ui.ed5856a76cfb")
        }}><span style={{
            color: '#8bb19b'
          }}>[{x.time}]</span> <span>{x.type === 'ok' ? t("ui.438ce7944d69") : x.type === 'bad' ? t("ui.ae30a087dc62") : '[ .... ]'}</span> {x.text}</div>)}{!done && <div style={{
          color: '#29e981'
        }}>{t("ui.e38679ccdcc2")}<span style={{
            animation: 'blink 1s step-end infinite'
          }}>█</span></div>}<div ref={endRef} /></div>
    <style>{`@keyframes blink{50%{opacity:0}}`}</style>
    <div style={{
        padding: 14,
        borderTop: '1px solid #183426',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        color: '#6e917d'
      }}><span role={error ? 'alert' : 'status'}>{error ? String(error) : done ? t('nodeArchive.complete') : t('nodeArchive.running')}</span>{done && <button className="btn" onClick={leaveConsole}>{error ? t("ui.234f624b2f7c") : t("ui.b74bdee9c34f")}</button>}</div>
  </div></ModalOverlay>;
  return <ModalOverlay onClose={onClose} className="modal-overlay"><div className="modal" style={{
      maxHeight: '85vh',
      overflowY: 'auto'
    }}><div className="modal-header"><h3 id={titleId}>{t("ui.1ade58681172")}</h3><button onClick={onClose} className="close-modal-btn">&times;</button></div><form ref={formRef} onSubmit={handleSubmit}>
    <div className="input-group"><label htmlFor="node-install-method">{t("ui.4831706c082f")}</label><select id="node-install-method" value={automatic ? t("ui.0d612c12d2ac") : t("ui.b363713a938a")} onChange={e => setAutomatic(e.target.value === 'auto')}><option value="auto">{t("ui.fabb8b43a5e0")}</option><option value="manual">{t("ui.99356529b772")}</option></select></div>
    {field('name', t('nodeName'))}{field('address', t('th_address'))}{automatic && <>{field('ssh_port', t('addNodeSshPort', 'SSH Port'), 'number')}{field('ssh_username', t('addNodeSshUsername', 'SSH Username'))}<div className="input-group"><label htmlFor="sshAuthMethod">{t('addNodeAuthMethod', 'SSH authentication')}</label><select id="sshAuthMethod" value={sshAuthMethod} onChange={event => setSshAuthMethod(event.target.value)}><option value="password">{t('password', 'Password')}</option><option value="key">{t('addNodePrivateKey', 'Private key')}</option></select></div>{sshAuthMethod === 'password' ? field('ssh_password', t('addNodeSshPassword', 'SSH Password'), 'password') : <><div className="input-group"><label htmlFor="ssh_private_key">{t('addNodePrivateKey', 'Private key')}</label><textarea id="ssh_private_key" name="ssh_private_key" value={formData.ssh_private_key} onChange={handleChange} required rows={5} autoComplete="off" spellCheck={false} /></div>{field('ssh_key_passphrase', t('addNodeKeyPassphrase', 'Key passphrase (optional)'), 'password', false)}</>}{field('controller_url', t('addNodeControllerUrl', 'Controller HTTPS origin'), 'url')}<small>{t('addNodeControllerTlsHelp', 'Remote nodes require a reachable HTTPS controller. Configure TLS before adding a remote node.')}</small><div className="input-group"><label htmlFor="mode">{t('addNodeMode', 'Installation mode')}</label><select id="mode" name="mode" value={formData.mode} onChange={handleChange}><option value="fresh">{t('addNodeFresh', 'Fresh server')}</option><option value="adopt">{t('addNodeAdopt', 'Adopt existing node')}</option></select></div>{formData.mode === 'adopt' && <>{field('existing_node_id', t('addNodeExistingId', 'Existing node ID'), 'number')}<small>{t('addNodeAdoptHelp', 'Keep its current name, address, VPN port and protocol. Select a free HTTPS API port. OpenVPN remains running.')}</small></>}{field('ssh_fingerprint', t('addNodeSshFingerprint', 'SSH Host Fingerprint (SHA256; first connection)'), 'text', false)}<div className="input-group"><label htmlFor="panel_ip">{t('addNodePanelIp', 'Panel source IP (optional)')}</label><input id="panel_ip" name="panel_ip" type="text" value={formData.panel_ip} onChange={handleChange} required={false} placeholder={t('addNodePanelIpPlaceholder', 'Auto-detected from the SSH connection')} /><small>{t('addNodePanelIpHelp', 'Leave empty to auto-detect. Fill only when the panel reaches the node from a different address than the SSH connection (for example behind a NAT or proxy).')}</small></div></>}{field('port', t('nodePort'), 'number')}
    <div className="input-group"><label htmlFor="node-protocol">{t('th_protocol')}</label><select id="node-protocol" name="protocol" value={formData.protocol} onChange={handleChange}><option value="udp">{t("ui.e9a6f622e340")}</option><option value="tcp">{t("ui.f544fb304c83")}</option></select></div>
    {field('ovpn_port', t('ovpnPort'), 'number')}{field('tunnel_address', t('tunnelAddress'), 'text', false)}{!automatic && field('key', t('key'))}
    <div className="modal-footer"><button type="button" onClick={onClose} className="btn btn-secondary">{t('cancelButton')}</button><LoadingButton isLoading={isLoading} type="submit" className="btn">{automatic ? t("ui.cb888a7010c5") : t("ui.1ade58681172")}</LoadingButton></div>
    {automatic && <p style={{
          fontSize: 12,
          color: 'var(--text-secondary)'
        }}>{t("ui.0f9fdb7c1c56")}</p>}{error && <p className="error-message" role="alert">{String(error)}</p>}
  </form></div></ModalOverlay>;
};
export default AddNodeModal;
