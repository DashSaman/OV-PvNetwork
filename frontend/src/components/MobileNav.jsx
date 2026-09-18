import { useEffect, useRef, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  FiActivity,
  FiGrid,
  FiMoreHorizontal,
  FiServer,
  FiSettings,
  FiShield,
  FiSliders,
  FiUsers,
} from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';

const MobileNav = () => {
  const { t } = useTranslation();
  const { userRole } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef(null);

  useEffect(() => {
    if (!moreOpen) return undefined;

    const onPointerDown = (event) => {
      if (!moreRef.current?.contains(event.target)) setMoreOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setMoreOpen(false);
    };

    document.addEventListener('mousedown', onPointerDown, true);
    document.addEventListener('keydown', onKeyDown, true);
    return () => {
      document.removeEventListener('mousedown', onPointerDown, true);
      document.removeEventListener('keydown', onKeyDown, true);
    };
  }, [moreOpen]);

  const closeMore = () => setMoreOpen(false);

  return (
    <nav className="mobile-nav" aria-label={t('navigation', 'Main navigation')}>
      <NavLink to="/" end className="mobile-nav-link" onClick={closeMore}>
        <FiGrid size={22} aria-hidden="true" />
        <span>{t('dashboard')}</span>
      </NavLink>

      <NavLink to="/users" className="mobile-nav-link" onClick={closeMore}>
        <FiUsers size={22} aria-hidden="true" />
        <span>{t('users')}</span>
      </NavLink>

      <NavLink to="/nodes" className="mobile-nav-link" onClick={closeMore}>
        <FiServer size={22} aria-hidden="true" />
        <span>{t('nodes')}</span>
      </NavLink>

      {userRole === 'main_admin' ? (
        <div className="mobile-more" ref={moreRef}>
          <button
            type="button"
            className="mobile-nav-link mobile-more-trigger"
            aria-haspopup="menu"
            aria-expanded={moreOpen}
            aria-controls="mobile-more-menu"
            onClick={() => setMoreOpen(value => !value)}
          >
            <FiMoreHorizontal size={22} aria-hidden="true" />
            <span>{t('more', 'More')}</span>
          </button>

          {moreOpen && (
            <div id="mobile-more-menu" className="mobile-more-menu" role="menu">
              <NavLink to="/admins" role="menuitem" onClick={closeMore}>
                <FiUsers aria-hidden="true" /> {t('admins')}
              </NavLink>
              <NavLink to="/operations" role="menuitem" onClick={closeMore}>
                <FiActivity aria-hidden="true" /> {t('operationsCenter')}
              </NavLink>
              <NavLink to="/security" role="menuitem" onClick={closeMore}>
                <FiShield aria-hidden="true" /> {t('panelSecurity')}
              </NavLink>
              <NavLink to="/fleet" role="menuitem" onClick={closeMore}>
                <FiServer aria-hidden="true" /> {t('fleetManagement')}
              </NavLink>
              <NavLink to="/monitoring" role="menuitem" onClick={closeMore}>
                <FiSettings aria-hidden="true" /> {t('monitoringSettings')}
              </NavLink>
              <NavLink to="/bandwidth" role="menuitem" onClick={closeMore}>
                <FiSliders aria-hidden="true" /> {t('bandwidthControl')}
              </NavLink>
            </div>
          )}
        </div>
      ) : null}
    </nav>
  );
};

export default MobileNav;
