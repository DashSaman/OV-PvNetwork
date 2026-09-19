import { useTranslation } from 'react-i18next';
import ActionsDropdown from './ActionsDropdown';
function getUsageColor(value) {
  if (value === undefined || value === null) return '';
  if (value <= 50) return 'usage-green';
  if (value <= 80) return 'usage-yellow';
  return 'usage-red';
}
const NodeTable = ({
  nodes,
  isLoading,
  nodeInfo = {},
  onDelete,
  onCheckStatus,
  onEdit,
  onRouterOpenVpn
}) => {
  const {
    t
  } = useTranslation();
  return <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>{t('th_nodeName')}</th>
            <th>{t('th_address')}</th>
            <th>{t('th_protocol')}</th>
            <th>{t('th_status')}</th>
            <th>{t('cpuUsage', 'CPU')}</th>
            <th>{t('memoryUsage', 'RAM')}</th>
            <th>{t('th_actions')}</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? <tr>
              <td colSpan="7" style={{
            textAlign: 'center'
          }}>{t("ui.b04ba49f8486")}</td>
            </tr> : nodes.length === 0 ? <tr>
              <td colSpan="7" style={{
            textAlign: 'center'
          }}>{t('noNodesFound')}</td>
            </tr> : nodes.map(node => {
          const info = nodeInfo[node.id] || {};
          return <tr key={node.id}>
                  <td>{node.name}</td>
                  <td>{node.address}</td>
                  <td>{node.protocol}</td>
                  <td>
                    <span className={`status-${node.status ? t("ui.2bb6b986c5d6") : t("ui.d436a3f40e3e")}`}>
                      {node.status ? t('status_active') : t('status_inactive')}
                    </span>
                  </td>
                  <td>
                    {info.cpu_usage !== undefined ? <span className={getUsageColor(info.cpu_usage)}>{info.cpu_usage + '%'}</span> : '-'}
                  </td>
                  <td>
                    {info.memory_usage !== undefined ? <span className={getUsageColor(info.memory_usage)}>{info.memory_usage + '%'}</span> : '-'}
                  </td>
                  <td>
                    <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: '8px'
              }}>
                      <button type="button" onClick={() => onDelete(node.id, node.name)} title={`Delete ${node.name}`} style={{
                  padding: '7px 12px',
                  border: '1px solid #ef4444',
                  borderRadius: '7px',
                  background: '#dc2626',
                  color: '#ffffff',
                  fontWeight: '600',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap'
                }}>{t("ui.8ad2d5218211")}</button>

                      <ActionsDropdown actions={[{
                  label: t('editButton'),
                  onClick: () => onEdit(node)
                }, {
                  label: t('checkStatus'),
                  onClick: () => onCheckStatus(node.id)
                }, {
                  label: t('routerOpenVpn.action', 'Router / MikroTik'),
                  onClick: () => onRouterOpenVpn && onRouterOpenVpn(node)
                }]} />
                    </div>
                  </td>
                </tr>;
        })}
        </tbody>
      </table>
    </div>;
};
export default NodeTable;
