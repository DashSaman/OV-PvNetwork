import { NavLink } from 'react-router-dom';
import { FiGrid, FiUsers, FiServer, FiSettings, FiShield, FiActivity, FiSliders } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
const SidebarLink = ({
  to,
  end,
  icon,
  children
}) => <li>
    <NavLink to={to} end={end} className="nav-link">
      <div className="icon-wrapper">{icon}</div>
      <span>{children}</span>
    </NavLink>
  </li>;
const Sidebar = () => {
  const {
    t
  } = useTranslation();
  const {
    userRole
  } = useAuth();
  return <aside className="sidebar">
      <div className="sidebar-header">
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

      <nav>
        <ul>
          <SidebarLink to="/" end icon={<FiGrid size={22} />}>
            {t('dashboard')}
          </SidebarLink>

          <SidebarLink to="/users" icon={<FiUsers size={22} />}>
            {t('userManagement')}
          </SidebarLink>

          <SidebarLink to="/nodes" icon={<FiServer size={22} />}>
            {t('nodeManagement')}
          </SidebarLink>

          {userRole === 'main_admin' && <>
              <SidebarLink to="/admins" icon={<FiUsers size={22} />}>
                {t('adminManagement')}
              </SidebarLink>

              <SidebarLink to="/operations" icon={<FiActivity size={22} />}>
                {t('operationsCenter')}
              </SidebarLink>

              <SidebarLink to="/security" icon={<FiShield size={22} />}>
                {t('panelSecurity')}
              </SidebarLink>

              <SidebarLink to="/fleet" icon={<FiServer size={22} />}>
                {t('fleetManagement')}
              </SidebarLink>

              <SidebarLink to="/monitoring" icon={<FiSettings size={22} />}>
                {t('monitoringSettings')}
              </SidebarLink>

              <SidebarLink to="/bandwidth" icon={<FiSliders size={22} />}>
                {t('bandwidthControl')}
              </SidebarLink>
            </>}
        </ul>
      </nav>
    </aside>;
};
export default Sidebar;
