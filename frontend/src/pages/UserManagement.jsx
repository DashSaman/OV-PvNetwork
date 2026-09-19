import { useState, useEffect, useMemo } from 'react';
import apiClient from '../services/api';
import UserTable from '../components/UserTable';
import AddUserModal from '../components/AddUserModal';
import EditUserModal from '../components/EditUserModal';
import RenewUserModal from '../components/RenewUserModal';
import AnyConnectUserModal from '../components/AnyConnectUserModal';
import SelectNodeForDownloadModal from '../components/SelectNodeForDownloadModal';
import DomainHistoryModal from '../components/DomainHistoryModal';
import UserStatCard from '../components/UserStatCard';
import Pagination from '../components/Pagination';
import { FiSearch } from 'react-icons/fi';
import { BsPersonFill, BsPersonCheckFill, BsPersonXFill } from 'react-icons/bs';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
const ITEMS_PER_PAGE = 10;
const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const [presenceOnline, setPresenceOnline] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [subscriptionSettings, setSubscriptionSettings] = useState(null);
  const [anyConnectSettings, setAnyConnectSettings] = useState({
    default_enabled: false
  });
  const [anyConnectBusy, setAnyConnectBusy] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const errorText = exception =>
    exception?.response?.data?.detail ||
    exception?.response?.data?.msg ||
    exception?.message ||
    'Unable to complete the request.';
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isRenewModalOpen, setIsRenewModalOpen] = useState(false);
  const [isDownloadModalOpen, setIsDownloadModalOpen] = useState(false);
  const [isDomainHistoryOpen, setIsDomainHistoryOpen] = useState(false);
  const [isAnyConnectModalOpen, setIsAnyConnectModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const {
    t
  } = useTranslation();
  const {
    userRole
  } = useAuth();
  const [reseller, setReseller] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // PVNETWORK_USER_SORTING_V2
  const [sortMode, setSortMode] = useState(() =>
    localStorage.getItem('ov-users-sort-mode') || 'newest'
  );
  const refreshResellerProfile = async () => {
    if (userRole !== 'admin') return;
    try {
      const response = await apiClient.get('/admin/me');
      setReseller(response.data.data || null);
    } catch {
      setReseller(null);
    }
  };
  const fetchUsers = async (showLoading = true) => {
    if (showLoading) setIsLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/users/');
      if (!response.data.success || !Array.isArray(response.data.data)) {
        throw new Error(response.data.msg || 'Unable to load users.');
      }
      setUsers(response.data.data);
    } catch (exception) {
      setError(errorText(exception));
      setUsers([]);
    } finally {
      if (showLoading) setIsLoading(false);
    }
  };
  const fetchPresence = async () => {
    try {
      const response = await apiClient.get('/users/presence');
      if (!response.data?.success) return;
      const payload = response.data.data || {};
      const counts = payload.counts_by_uuid || {};
      setPresenceOnline(Number(payload.online_users || 0));
      setUsers(previous => previous.map(item => {
        const count = Number(counts[item.uuid] || 0);
        return { ...item, online_count: count, is_online: count > 0 };
      }));
    } catch {
      // Keep the last good presence snapshot on transient polling failures.
    }
  };
  const fetchNodes = async () => {
    try {
      const response = await apiClient.get('/nodes/');
      if (!response.data?.success || !Array.isArray(response.data?.data)) {
        throw new Error(response.data?.msg || 'Unable to load nodes.');
      }
      setNodes(response.data.data);
    } catch (exception) {
      setError(errorText(exception));
      setNodes([]);
    }
  };

  const fetchSubscriptionSettings = async () => {
    try {
      const response = await apiClient.get('/server/settings/');
      if (response.data.success && response.data.data) {
        setSubscriptionSettings(response.data.data);
      }
    } catch (exception) {
      setError(errorText(exception));
    }
  };
  const fetchAnyConnectSettings = async () => {
    try {
      const response = await apiClient.get('/anyconnect/settings');
      if (response.data?.success && response.data?.data) {
        setAnyConnectSettings(response.data.data);
      }
    } catch (exception) {
      setError(errorText(exception));
    }
  };
  useEffect(() => {
    fetchUsers();
    fetchNodes();
    fetchSubscriptionSettings();
    fetchAnyConnectSettings();
    refreshResellerProfile();

    fetchPresence();
    // Lightweight shared presence refresh keeps Dashboard and Users on the same snapshot.
    const liveStatusTimer = setInterval(fetchPresence, 1000);
    // Keep non-presence user fields eventually fresh without polling the full list every second.
    const userRefreshTimer = setInterval(() => fetchUsers(false), 30000);
    return () => {
      clearInterval(liveStatusTimer);
      clearInterval(userRefreshTimer);
    };
    // Polling callbacks intentionally use the mount-time function set; state updates are functional/server-derived.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const userStats = useMemo(() => {
    const activeUsersCount = users.filter(user => user.is_active).length;
    const inactiveUsersCount = users.length - activeUsersCount;
    const rowOnlineUsersCount = users.filter(user => user.is_online).length;
    const onlineUsersCount = Number.isFinite(presenceOnline) ? presenceOnline : rowOnlineUsersCount;
    return {
      total: users.length,
      online: onlineUsersCount,
      active: activeUsersCount,
      inactive: inactiveUsersCount
    };
  }, [users, presenceOnline]);

  // Filter, sort and then paginate users.
  const filteredUsers = useMemo(() => {
    const filtered = users.filter(user =>
      String(user.name || '')
        .toLowerCase()
        .includes(searchTerm.toLowerCase())
    );

    const creationId = user => {
      const value = Number(user.id);
      return Number.isFinite(value) ? value : 0;
    };

    const onlineCount = user => {
      const value = Number(user.online_count);
      return Number.isFinite(value) ? value : 0;
    };

    const usedTraffic = user => {
      const value = Number(user.used);
      return Number.isFinite(value) ? value : 0;
    };

    const remainingTraffic = user => {
      const total = Number(user.total || 0);
      const used = Number(user.used || 0);

      if (total === 0) {
        return Number.POSITIVE_INFINITY;
      }

      return Math.max(total - used, 0);
    };

    const expiryValue = user => {
      const value = Date.parse(
        `${user.expiry_date || ''}T00:00:00Z`
      );

      return Number.isFinite(value) ? value : 0;
    };

    const compareNames = (left, right) =>
      String(left.name || '').localeCompare(
        String(right.name || ''),
        undefined,
        {
          numeric: true,
          sensitivity: 'base'
        }
      );

    const newestFallback = (left, right) =>
      creationId(right) - creationId(left) ||
      compareNames(left, right);

    return [...filtered].sort((left, right) => {
      switch (sortMode) {
        case 'oldest':
          return (
            creationId(left) - creationId(right) ||
            compareNames(left, right)
          );

        case 'online_first':
          return (
            Number(Boolean(right.is_online)) -
              Number(Boolean(left.is_online)) ||
            onlineCount(right) -
              onlineCount(left) ||
            newestFallback(left, right)
          );

        case 'name_asc':
          return (
            compareNames(left, right) ||
            newestFallback(left, right)
          );

        case 'name_desc':
          return (
            compareNames(right, left) ||
            newestFallback(left, right)
          );

        case 'traffic_desc':
          return (
            usedTraffic(right) -
              usedTraffic(left) ||
            newestFallback(left, right)
          );

        case 'remaining_desc': {
          const leftRemaining =
            remainingTraffic(left);

          const rightRemaining =
            remainingTraffic(right);

          if (
            leftRemaining ===
            rightRemaining
          ) {
            return newestFallback(
              left,
              right
            );
          }

          if (
            rightRemaining ===
            Number.POSITIVE_INFINITY
          ) {
            return 1;
          }

          if (
            leftRemaining ===
            Number.POSITIVE_INFINITY
          ) {
            return -1;
          }

          return (
            rightRemaining -
            leftRemaining
          );
        }

        case 'expiry_soon':
          return (
            expiryValue(left) -
              expiryValue(right) ||
            newestFallback(left, right)
          );

        case 'expiry_late':
          return (
            expiryValue(right) -
              expiryValue(left) ||
            newestFallback(left, right)
          );

        case 'newest':
        default:
          return newestFallback(
            left,
            right
          );
      }
    });
  }, [users, searchTerm, sortMode]);

  const totalPages = Math.ceil(
    filteredUsers.length /
    ITEMS_PER_PAGE
  );

  const paginatedUsers = useMemo(() => {
    const startIndex =
      (currentPage - 1) *
      ITEMS_PER_PAGE;

    return filteredUsers.slice(
      startIndex,
      startIndex + ITEMS_PER_PAGE
    );
  }, [filteredUsers, currentPage]);

  const handleSearchChange = event => {
    setSearchTerm(event.target.value);
    setCurrentPage(1);
  };

  const handleSortChange = event => {
    const value = event.target.value;

    setSortMode(value);

    localStorage.setItem(
      'ov-users-sort-mode',
      value
    );

    setCurrentPage(1);
  };
  const handleDelete = async (uuid, name) => {
    // PVNETWORK_USERNAME_REUSE_V7
    if (!window.confirm(`Are you sure you want to delete user ${name}?`)) return;
    try {
      const response = await apiClient.delete(`/users/${uuid}`);
      if (!response.data?.success) {
        throw new Error(response.data?.msg || 'Unable to delete user.');
      }
      alert(response.data.msg || `User ${name} deleted successfully.`);
      fetchUsers();
      refreshResellerProfile();
    } catch (exception) {
      alert(
        exception?.response?.data?.detail ||
        exception?.response?.data?.msg ||
        exception?.message ||
        t("ui.220fb63dddff")
      );
    }
  };
  const handleToggleStatus = async user => {
    const newStatus = !user.is_active;
    const statusLabel = newStatus ? 'activate' : 'deactivate';
    if (!window.confirm(`Are you sure you want to ${statusLabel} user ${user.name}?`)) return;
    try {
      const response = await apiClient.put(`/users/${user.uuid}/status`, {
        name: user.name,
        status: !user.is_active,
        expiry_date: null
      });
      if (response.data.success) {
        alert(`User ${statusLabel}d successfully.`);
        fetchUsers();
      } else {
        alert(`Failed to ${statusLabel} user.`);
      }
    } catch {
      alert(`Error ${statusLabel}ing user.`);
    }
  };
  const handleResetUsage = async user => {
    if (!window.confirm(`Are you sure you want to reset usage for user ${user.name}?`)) return;
    try {
      const response = await apiClient.get(`/users/${user.uuid}`);
      if (response.data.success) {
        alert(`Usage for ${user.name} has been reset.`);
        fetchUsers();
      } else {
        alert(`Failed to reset usage for ${user.name}.`);
      }
    } catch {
      alert(t("ui.82be20060add"));
    }
  };
  const handleOpenDownloadModal = user => {
    setSelectedUser(user);
    setIsDownloadModalOpen(true);
  };
  const handleOpenDomainHistory = user => {
    setSelectedUser(user);
    setIsDomainHistoryOpen(true);
  };

  const handleToggleAnyConnect = async user => {
    const enabled = !user.anyconnect_enabled;
    setAnyConnectBusy(user.uuid);
    setError('');
    try {
      const response = await apiClient.put(
        `/anyconnect/users/${user.uuid}/status`,
        { enabled }
      );
      const data = response.data?.data || {};
      setUsers(previous => previous.map(item =>
        item.uuid === user.uuid
          ? {
              ...item,
              anyconnect_configured: Boolean(data.configured),
              anyconnect_enabled: enabled,
              anyconnect_password_available: Boolean(data.password_available)
            }
          : item
      ));
      if (data.password_generated) {
        window.alert(
          t('anyConnectEnabledGenerated', 'AnyConnect was enabled for {{name}}. The generated password is available in the subscription page and AnyConnect management.', { name: user.name })
        );
      }
    } catch (exception) {
      setError(errorText(exception));
      await fetchUsers();
    } finally {
      setAnyConnectBusy('');
    }
  };

  const handleAnyConnectDefaultChange = async event => {
    const defaultEnabled = Boolean(event.target.checked);
    setAnyConnectSettings(previous => ({
      ...previous,
      default_enabled: defaultEnabled
    }));
    try {
      const response = await apiClient.put('/anyconnect/settings', {
        default_enabled: defaultEnabled
      });
      setAnyConnectSettings(response.data?.data || {
        default_enabled: defaultEnabled
      });
    } catch (exception) {
      setAnyConnectSettings(previous => ({
        ...previous,
        default_enabled: !defaultEnabled
      }));
      setError(errorText(exception));
    }
  };

  const handleOpenAnyConnect = user => {
    setSelectedUser(user);
    setIsAnyConnectModalOpen(true);
  };
  const handleUserAdded = () => {
    setIsAddModalOpen(false);
    fetchUsers();
    refreshResellerProfile();
  };
  const handleEdit = user => {
    setSelectedUser(user);
    setIsEditModalOpen(true);
  };
  const handleRenew = user => {
    setSelectedUser(user);
    setIsRenewModalOpen(true);
  };
  const handleUserRenewed = () => {
    setIsRenewModalOpen(false);
    setSelectedUser(null);
    fetchUsers();
    refreshResellerProfile();
  };
  const handleUserUpdated = () => {
    setIsEditModalOpen(false);
    setSelectedUser(null);
    fetchUsers();
    refreshResellerProfile();
  };

  const handleQuickSave = async (user, draft) => {
    const GB = 1024 * 1024 * 1024;
    const total = Math.round(Number(draft.totalTrafficGb) * GB);
    const desiredNodeIds = [...draft.nodeIds].map(Number).sort((a, b) => a - b);
    const currentNodeIds = [...(user.node_ids || [])].map(Number).sort((a, b) => a - b);
    const assignmentsChanged =
      desiredNodeIds.length !== currentNodeIds.length ||
      desiredNodeIds.some((value, index) => value !== currentNodeIds[index]);

    try {
      // Reset first. For unlimited users this starts the existing fresh 30-day
      // cycle; the normal update below preserves that new unlimited expiry.
      if (draft.resetUsage) {
        const resetResponse = await apiClient.get(`/users/${user.uuid}`);
        if (!resetResponse.data?.success) {
          throw new Error(resetResponse.data?.msg || 'Usage reset failed.');
        }
      }

      const updateResponse = await apiClient.put(`/users/${user.uuid}/`, {
        name: user.name,
        expiry_date: draft.expiryDate || user.expiry_date,
        total,
        device_limit: Number(draft.deviceLimit),
        status: Boolean(draft.isActive)
      });
      if (!updateResponse.data?.success) {
        throw new Error(updateResponse.data?.msg || 'User update failed.');
      }

      // Explicit deactivation comes after the edit because the normal update
      // recalculates active state from expiry/quota. Activation is left to that
      // server-side validity rule so expired/exhausted users are not forced on.
      if (!draft.isActive) {
        const statusResponse = await apiClient.put(`/users/${user.uuid}/status`, {
          name: user.name,
          status: false,
          expiry_date: null
        });
        if (!statusResponse.data?.success) {
          throw new Error(statusResponse.data?.msg || 'Unable to deactivate user.');
        }
      }

      let assignmentData = null;
      if (assignmentsChanged) {
        const assignmentResponse = await apiClient.put(`/users/${user.uuid}/nodes`, {
          node_ids: desiredNodeIds
        });
        if (!assignmentResponse.data?.success) {
          throw new Error(assignmentResponse.data?.msg || 'Node assignment failed.');
        }
        assignmentData = assignmentResponse.data?.data || null;
      }

      await fetchUsers();
      await refreshResellerProfile();
      if (assignmentData?.pending_node_ids?.length) {
        window.alert(
          t('quickEditSavedPendingNodes', 'Changes saved. Some newly assigned nodes are pending reconciliation.')
        );
      }
      return assignmentData;
    } catch (exception) {
      const message = errorText(exception);
      setError(message);
      await fetchUsers();
      throw new Error(message);
    }
  };

  // Generate subscription link for each user
  const getSubscriptionLink = user => {
    if (!subscriptionSettings || !user || !user.uuid) return '';
    let prefix = subscriptionSettings.subscription_url_prefix;
    let path = subscriptionSettings.subscription_path || '';
    if (!prefix.endsWith('/')) prefix += '/';
    if (path.startsWith('/')) path = path.slice(1);
    if (path && !path.endsWith('/')) path += '/';
    return `${prefix}${path}${user.uuid}`;
  };
  return <div id="users-view" className="view">
      <div className="view-header">
        <h2>{t('userManagement')}</h2>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '14px',
          flexWrap: 'wrap'
        }}>
          {userRole === 'main_admin' && <label style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            fontSize: '13px'
          }}>
            <input
              type="checkbox"
              checked={Boolean(anyConnectSettings.default_enabled)}
              onChange={handleAnyConnectDefaultChange}
            />
            <span>{t('anyConnectDefaultNewUsers', 'AnyConnect default for new users')}</span>
          </label>}
          <button onClick={() => setIsAddModalOpen(true)} className="btn">{t('addNewUser')}</button>
        </div>
      </div>

      {error && <div className="monitor-form">
        <p className="error-message">{error}</p>
        <button className="btn" disabled={isLoading} onClick={() => {
          fetchUsers();
          fetchNodes();
          fetchSubscriptionSettings();
          fetchAnyConnectSettings();
        }}>
          {t('retry', 'Retry')}
        </button>
      </div>}

      <div className="stats-grid" style={{
      marginBottom: '30px',
      display: 'flex',
      gap: '18px',
      flexWrap: 'wrap'
    }}>
        {reseller && <UserStatCard icon={<BsPersonFill style={{
        fontSize: 28
      }} />} label={t('reseller.remainingCredit')} value={`${(Number(reseller.quota_remaining) / 1024 / 1024 / 1024).toFixed(2)} GB`} color="#f59e0b" className="card-dark" />}
        {reseller && <UserStatCard icon={<BsPersonFill style={{
        fontSize: 28
      }} />} label={t('resellerUnlimitedRemaining', 'اکانت نامحدود باقی‌مانده')} value={Number(reseller.unlimited_quota_remaining || 0)} color="#a78bfa" className="card-dark" />}
        <UserStatCard icon={<BsPersonFill style={{
        fontSize: 28
      }} />} label={t('totalUsers')} value={userStats.total} color="#90caf9" className="card-dark" />
        <UserStatCard icon={<BsPersonCheckFill style={{
        fontSize: 28
      }} />} label={t('onlineUsers', 'Online Users')} value={userStats.online} color="#00e5ff" className="card-dark" />
        <UserStatCard icon={<BsPersonCheckFill style={{
        fontSize: 28
      }} />} label={t('activeUsers')} value={userStats.active} color="#43a047" className="card-dark" />
        <UserStatCard icon={<BsPersonXFill style={{
        fontSize: 28
      }} />} label={t('inactiveUsers')} value={userStats.inactive} color="#e53935" className="card-dark" />
      </div>

      <div className="search-pagination-controls">
        <div className="search-container">
          <FiSearch className="search-icon" />
          <input type="text" placeholder={t("ui.5fffed8775b0")} value={searchTerm} onChange={handleSearchChange} className="search-input" />
        </div>

        <div style={{
          minWidth: '230px',
          flex: '0 1 260px'
        }}>
          {/* PVNETWORK_USER_SORT_I18N_V1 */}
          <select
            value={sortMode}
            onChange={handleSortChange}
            aria-label={t('userSort.label', 'Sort users')}
            title={t('userSort.label', 'Sort users')}
            dir="rtl"
            style={{
              width: '100%',
              height: '46px',
              padding: '0 14px',
              borderRadius: '12px',
              border: '1px solid rgba(0, 229, 255, 0.60)',
              background: '#09182a',
              color: '#e7f4ff',
              outline: 'none',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: '14px'
            }}
          >
            <option value="newest">{t('userSort.newest', 'Newest accounts')}</option>

            <option value="oldest">{t('userSort.oldest', 'Oldest accounts')}</option>

            <option value="online_first">{t('userSort.onlineFirst', 'Online users first')}</option>

            <option value="name_asc">{t('userSort.nameAsc', 'Username A to Z')}</option>

            <option value="name_desc">{t('userSort.nameDesc', 'Username Z to A')}</option>

            <option value="traffic_desc">{t('userSort.trafficDesc', 'Highest traffic usage')}</option>

            <option value="remaining_desc">{t('userSort.remainingDesc', 'Highest remaining traffic')}</option>

            <option value="expiry_soon">{t('userSort.expirySoon', 'Nearest expiry date')}</option>

            <option value="expiry_late">{t('userSort.expiryLate', 'Latest expiry date')}</option>
          </select>
        </div>

        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
      </div>

      <UserTable users={paginatedUsers} isLoading={isLoading} onDelete={handleDelete} onDownload={handleOpenDownloadModal} onAnyConnect={handleOpenAnyConnect} onToggleAnyConnect={handleToggleAnyConnect} anyConnectBusy={anyConnectBusy} onEdit={handleEdit} onRenew={handleRenew} onToggleStatus={handleToggleStatus} onResetUsage={handleResetUsage} onViewDomainHistory={handleOpenDomainHistory} canViewDomainHistory={userRole === 'main_admin'} canDeleteUnlimited={userRole === 'main_admin'} getSubscriptionLink={getSubscriptionLink} availableNodes={nodes} userRole={userRole} onQuickSave={handleQuickSave} />
      {isAddModalOpen && <AddUserModal onClose={() => setIsAddModalOpen(false)} onUserAdded={handleUserAdded} userRole={userRole} anyConnectDefaultEnabled={Boolean(anyConnectSettings.default_enabled)} nodes={nodes} />}
      {isEditModalOpen && <EditUserModal user={selectedUser} onClose={() => setIsEditModalOpen(false)} onUserUpdated={handleUserUpdated} userRole={userRole} />}
      {isRenewModalOpen && <RenewUserModal user={selectedUser} onClose={() => setIsRenewModalOpen(false)} onRenewed={handleUserRenewed} />}
      {isDownloadModalOpen && <SelectNodeForDownloadModal user={selectedUser} onClose={() => setIsDownloadModalOpen(false)} />}
      {isAnyConnectModalOpen && selectedUser && <AnyConnectUserModal user={selectedUser} onChanged={fetchUsers} onClose={() => {
        setIsAnyConnectModalOpen(false);
        setSelectedUser(null);
      }} />}
      {isDomainHistoryOpen && selectedUser && <DomainHistoryModal user={selectedUser} onClose={() => {
      setIsDomainHistoryOpen(false);
      setSelectedUser(null);
    }} />}
    </div>;
};
export default UserManagement;
