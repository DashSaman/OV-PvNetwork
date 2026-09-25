import { Fragment, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FiCopy } from 'react-icons/fi';
import ActionsDropdown from './ActionsDropdown';
import InlineUserQuickEdit from './InlineUserQuickEdit';
import './UserTable.css';
const UserTable = ({ ratesByUuid = {},
  users,
  onDelete,
  onDownload,
  onAnyConnect,
  onRouterOpenVpn,
  routerOpenVpnNodeIds = [],
  onToggleAnyConnect,
  anyConnectBusy,
  onEdit,
  onRenew,
  onToggleStatus,
  onResetUsage,
  onViewDomainHistory,
  canViewDomainHistory,
  canDeleteUnlimited,
  getSubscriptionLink,
  availableNodes,
  userRole,
  onQuickSave,
  onRename,
  busyUserUuids = []
}) => {
  const {
    t
  } = useTranslation();
  const [expandedUserUuid, setExpandedUserUuid] = useState('');
  const [compactQuickEdit, setCompactQuickEdit] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia
      ? window.matchMedia('(max-width: 992px)').matches
      : false
  );

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const media = window.matchMedia('(max-width: 992px)');
    const sync = event => setCompactQuickEdit(event.matches);
    setCompactQuickEdit(media.matches);
    media.addEventListener?.('change', sync);
    return () => media.removeEventListener?.('change', sync);
  }, []);
  const formatTrafficGB = bytes => {
    if (bytes === null || bytes === undefined) {
      return '-';
    }
    const gb = Number(bytes) / 1024 / 1024 / 1024;
    if (!Number.isFinite(gb)) {
      return '-';
    }
    if (gb < 1) {
      return gb.toFixed(1);
    }
    return gb.toFixed(2).replace(/\.00$/, '').replace(/\.0$/, '');
  };
  const formatTrafficUsage = (used, total) => {
    const usedText = formatTrafficGB(used);
    const totalText = formatTrafficGB(total);
    if (Number(total) === 0) {
      return usedText === '-' ? '∞' : `${usedText} GB / ∞`;
    }
    if (usedText === '-' && totalText === '-') {
      return '-';
    }
    if (usedText === '-') {
      return `- / ${totalText} GB`;
    }
    if (totalText === '-') {
      return `${usedText} / -`;
    }
    return `${usedText} / ${totalText} GB`;
  };
  const handleCopyLink = user => {
    if (!getSubscriptionLink) {
      return;
    }
    const link = getSubscriptionLink(user) || '';
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(link).then(() => {
        window.alert(t('copied_subscription_link', 'Subscription link copied!'));
      }).catch(() => {
        fallbackCopyTextToClipboard(link);
      });
    } else {
      fallbackCopyTextToClipboard(link);
    }
  };
  function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.top = 0;
    textArea.style.left = 0;
    textArea.style.width = '2em';
    textArea.style.height = '2em';
    textArea.style.padding = 0;
    textArea.style.border = 'none';
    textArea.style.outline = 'none';
    textArea.style.boxShadow = 'none';
    textArea.style.background = 'transparent';
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand('copy');
      window.alert(t('copied_subscription_link', 'Subscription link copied!'));
    } catch {
      window.alert(t('copy_failed', 'Failed to copy link.'));
    }
    document.body.removeChild(textArea);
  }
  return <div className="table-container">

      <table className="pv-mobile-cards">

        <thead>
          <tr>

            <th>
              {t('th_username')}
            </th>

            <th>
              {t('th_liveStatus', 'Live Status')}
            </th>

            <th>
              {t('th_connections', 'Connections')}
            </th>

            <th>
              AnyConnect
            </th>

            <th>
              {t('th_expiryDate')}
            </th>

            <th>
              {t('th_totalTraffic')}
            </th>

            <th>
              {t('th_status')}
            </th>

            <th>
              {t('th_owner')}
            </th>

            <th>
              {t('th_actions')}
            </th>

          </tr>
        </thead>


        <tbody>

          {users.length === 0 ? <tr>
              <td colSpan="9" style={{
            textAlign: 'center'
          }}>
                {t('noUsersFound')}
              </td>
            </tr> : users.map(user => {
              const renameBusy = busyUserUuids.includes(user.uuid);
              return <Fragment key={user.uuid || user.name}><tr>

                <td>
                  <span style={{ fontWeight: 650 }}>{user.name}</span>
                  {(() => {
                    const bps = Number(ratesByUuid[user.uuid] || user.live_bps || 0);
                    if (!user.is_online || !bps || bps < 1024) return null;
                    const mbps = bps / 1e6;
                    const text = mbps >= 1 ? mbps.toFixed(1) + ' Mbps' : (bps / 1e3).toFixed(0) + ' Kbps';
                    return <span className="pv-live-speed" title={t('liveSpeedTitle', 'سرعت لحظه‌ای')}>{'⚡ ' + text}</span>;
                  })()}
                </td>


                <td>

                  <span className={`live-user-badge ${user.is_online ? t("ui.54abd7690046") : t("ui.979c6cdb7738")}`}>

                    <span className={`live-user-dot ${user.is_online ? t("ui.d54cb1751256") : t("ui.6edebfb387d5")}`} />

                    {user.is_online ? t('online', 'Online') : t('offline', 'Offline')}

                  </span>

                </td>


                <td>

                  <span className={`live-connection-count ${user.is_online ? t("ui.fb41c3496423") : ''}`}>

                    {Number(user.online_count || 0)}

                    {' / '}

                    {Number(user.device_limit) === 0 ? '∞' : Number(user.device_limit ?? 1)}

                  </span>

                </td>


                <td>
                  <label style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '7px',
                    cursor: anyConnectBusy === user.uuid ? 'wait' : 'pointer',
                    whiteSpace: 'nowrap'
                  }}>
                    <input
                      type="checkbox"
                      checked={Boolean(user.anyconnect_enabled)}
                      disabled={anyConnectBusy === user.uuid || renameBusy}
                      onChange={() => onToggleAnyConnect && onToggleAnyConnect(user)}
                      aria-label={`AnyConnect ${user.name}`}
                    />
                    <span style={{
                      fontSize: '11px',
                      color: user.anyconnect_enabled ? '#4ade80' : '#94a3b8'
                    }}>
                      {user.anyconnect_enabled ? t('enabled', 'Enabled') : t('disabled', 'Disabled')}
                    </span>
                  </label>
                </td>


                <td>
                  {new Date(user.expiry_date).toLocaleDateString('en-CA')}
                </td>


                <td>
                  {formatTrafficUsage(user.used, user.total)}
                </td>


                <td>

                  <span className={`status-${user.is_active ? t("ui.2bb6b986c5d6") : t("ui.d436a3f40e3e")}`}>

                    {user.is_active ? t('status_active') : t('status_inactive')}

                  </span>

                </td>


                <td>
                  {user.owner}
                </td>


                <td style={{
            textAlign: 'right',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>

                  <ActionsDropdown actions={[{
              label: t('quickEditButton', 'Quick Edit'),
              onClick: () => setExpandedUserUuid(current => current === user.uuid ? '' : user.uuid),
              className: 'secondary-action',
              disabled: renameBusy
            }, {
              label: t('renameUsername', 'Rename Username'),
              onClick: () => onRename && onRename(user),
              className: 'secondary-action'
            }, {
              label: t('editButton'),
              onClick: () => onEdit(user),
              disabled: renameBusy
            }, {
              label: t('renewButton', 'تمدید'),
              onClick: () => onRenew && onRenew(user),
              className: 'secondary-action',
              disabled: renameBusy
            }, {
              label: t('downloadButton'),
              onClick: () => onDownload(user)
            }, {
              label: 'AnyConnect',
              onClick: () => onAnyConnect && onAnyConnect(user),
              className: 'secondary-action'
            }, ...(((user.node_ids || []).some(id => routerOpenVpnNodeIds.map(Number).includes(Number(id)))) ? [{
              label: t('routerOpenVpn.action', 'Router / MikroTik'),
              onClick: () => onRouterOpenVpn && onRouterOpenVpn(user),
              className: 'secondary-action'
            }] : []), ...(canViewDomainHistory ? [{
              label: 'Domain History',
              onClick: () => onViewDomainHistory && onViewDomainHistory(user),
              className: 'secondary-action'
            }] : []), {
              label: t('resetUsageButton', 'Reset Usage'),
              onClick: () => onResetUsage && onResetUsage(user),
              className: 'secondary-action',
              disabled: renameBusy
            }, {
              label: user.is_active ? t('deactivateButton', 'Deactivate') : t('activateButton', 'Activate'),
              onClick: () => onToggleStatus(user),
              className: user.is_active ? t("ui.4ee369b40527") : t("ui.4834323b9a96"),
              disabled: renameBusy
            }, ...((Number(user.total || 0) > 0 || canDeleteUnlimited) ? [{
              label: t('deleteButton'),
              onClick: () => onDelete(user.uuid, user.name),
              className: 'danger-action',
              disabled: renameBusy
            }] : [])]} />


                  <button
                    type="button"
                    className="btn btn-secondary"
                    title={t('anyConnectManage', 'Manage AnyConnect')}
                    onClick={() => onAnyConnect && onAnyConnect(user)}
                    style={{
                      padding: '5px 9px',
                      fontSize: '11px',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    AnyConnect
                  </button>

                  <button className="icon-btn btn-copy" title={t('copySubscriptionLink', 'Copy Link')} onClick={() => handleCopyLink(user)} style={{
              background: 'none',
              border: 'none',
              padding: 0,
              marginLeft: 6,
              cursor: 'pointer'
            }}>

                    <FiCopy style={{
                fontSize: 20,
                color: '#90caf9'
              }} />

                  </button>

                </td>

              </tr>
              {expandedUserUuid === user.uuid && !compactQuickEdit && !renameBusy && <tr className="user-quick-edit-row desktop-user-quick-edit-row">
                <td colSpan="9">
                  <InlineUserQuickEdit
                    user={user}
                    nodes={availableNodes}
                    userRole={userRole}
                    onSave={onQuickSave}
                    onCancel={() => setExpandedUserUuid('')}
                  />
                </td>
              </tr>}
            </Fragment>;
            })}

        </tbody>

      </table>

      {expandedUserUuid && compactQuickEdit && (() => {
        const expandedUser = users.find(item => item.uuid === expandedUserUuid);
        return expandedUser ? (
          <div className="mobile-user-quick-edit-panel">
            <InlineUserQuickEdit
              user={expandedUser}
              nodes={availableNodes}
              userRole={userRole}
              onSave={onQuickSave}
              onCancel={() => setExpandedUserUuid('')}
            />
          </div>
        ) : null;
      })()}

    </div>;
};
export default UserTable;
