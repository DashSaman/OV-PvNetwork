import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import MobileNav from '../components/MobileNav';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { FiLogOut, FiRefreshCw, FiSend, FiGlobe } from 'react-icons/fi';
const languages = [['ar', '🇸🇦'], ['en', '🇬🇧'], ['fa', '🇮🇷'], ['zh_TW', '🇹🇼'], ['zh_CN', '🇨🇳'], ['ja', '🇯🇵'], ['ru', '🇷🇺'], ['vi', '🇻🇳'], ['es', '🇪🇸'], ['id', '🇮🇩'], ['uk', '🇺🇦'], ['tr', '🇹🇷'], ['pt_BR', '🇧🇷']];
const DashboardLayout = () => {
  const {
    logout
  } = useAuth();
  const {
    t,
    i18n
  } = useTranslation();
  return <div id="main-container">
      <Sidebar />

      <div className="content-wrapper">
        <header className="main-header">
          <div className="header-logo-container">
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
          </div>

          <div className="header-actions">
            <a href="https://t.me/pvnetwork_bot" target="_blank" rel="noopener noreferrer" className="action-btn" aria-label={t("ui.edbea9ff1a78")}>
              <FiSend size={18} />
            </a>

            <label className="language-picker" title={t('selectLanguage')}>
              <FiGlobe size={18} />
              <select value={i18n.language} onChange={event => i18n.changeLanguage(event.target.value)} aria-label={t('selectLanguage')}>
                {languages.map(([code, flag]) => <option key={code} value={code}>
                    {flag} {t(`language.${code}`)}
                  </option>)}
              </select>
            </label>

            <button onClick={() => window.location.reload()} className="action-btn" aria-label={t('refreshPanel')} title={t('refreshPanel')}>
              <FiRefreshCw size={18} />
            </button>

            <button onClick={logout} className="btn btn-danger logout-button">
              <FiLogOut />
              <span className="logout-text">
                {t('logout')}
              </span>
            </button>
          </div>
        </header>

        <main>
          <Outlet />
        </main>
      </div>

      <MobileNav />
    </div>;
};
export default DashboardLayout;
