import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const {
    login
  } = useAuth();
  const navigate = useNavigate();
  const {
    t
  } = useTranslation();
  const handleSubmit = async e => {
    e.preventDefault();
    setError('');
    try {
      await login(username, password, otp);
      navigate('/');
    } catch {
      setError(t('loginError'));
    }
  };
  return <div id="login-container">
      <div className="login-box">
        <div className="pn-admin-brand">
  <img
    src="/sub-clients/private-network.webp"
    className="pn-admin-logo"
    alt="Private Network"
  />
  <div className="pn-admin-brand-copy">
    <span className="pn-admin-brand-title">PRIVATE NETWORK</span>
    <span className="pn-admin-brand-sub">PVNETWORK PANEL</span>
  </div>
</div>
        <h2>{t('loginTitle')}</h2>
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label htmlFor="username">{t('username')}</label>
            <input type="text" id="username" value={username} onChange={e => setUsername(e.target.value)} required />
          </div>
          <div className="input-group">
            <label htmlFor="password">{t('password')}</label>
            <input type="password" id="password" value={password} onChange={e => setPassword(e.target.value)} required />
          </div>
          <div className="input-group">
            <label htmlFor="otp">{t("ui.054600452d9c")}</label>
            <input type="text" inputMode="numeric" id="otp" value={otp} onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} autoComplete="one-time-code" />
          </div>
          <button type="submit" className="btn">{t('loginButton')}</button>
          {error && <p className="error-message">{error}</p>}
        </form>
      </div>
    </div>;
};
export default LoginPage;
