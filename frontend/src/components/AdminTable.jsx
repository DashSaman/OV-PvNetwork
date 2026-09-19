import { FiEdit, FiTrash2, FiUser, FiUsers } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
const AdminTable = ({
  admins,
  isLoading,
  onEdit,
  onDelete
}) => {
  const {
    t
  } = useTranslation();
  const gb = bytes => (Number(bytes || 0) / 1024 / 1024 / 1024).toFixed(2);
  if (isLoading) {
    return <div className="table-container">
                <p>{t('loading')}</p>
            </div>;
  }
  if (!admins || admins.length === 0) {
    return <div className="table-container">
                <p>{t('noAdminsFound')}</p>
            </div>;
  }
  return <div className="admin-cards-container">
            {admins.map(admin => <div key={admin.id} className="admin-card">
                    <div className="admin-card-header">
                        <div className="admin-avatar">
                            <FiUser size={24} />
                        </div>
                        <div className="admin-info">
                            <h4 className="admin-username">{admin.username}</h4>
                            <div className="admin-stats">
                                <FiUsers size={14} />
                                <span>{admin.users_count || 0} {t('users')}</span>
                            </div>
                            <div className="admin-stats">
                                <span>{gb(admin.quota_used)} / {gb(admin.quota_total)}{t("ui.a2d57c527be1")}</span>
                            </div>
                            <div className="admin-stats">
                                <span>{t('unlimitedAccounts', 'نامحدود')}: {Number(admin.unlimited_quota_used || 0)} / {Number(admin.unlimited_quota_total || 0)} {t('accountUnit', 'اکانت')}</span>
                            </div>
                            <div className="admin-stats">
                                <span style={{
              color: admin.is_active ? t("ui.c1419dcb4d91") : t("ui.a293054a1e6e")
            }}>
                                    {admin.is_active ? t("ui.a733b809d2f1") : t("ui.24d58e184cd4")}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div className="admin-card-actions">
                        <button onClick={() => onEdit(admin)} className="btn-admin-edit" title={t('editButton')}>
                            <FiEdit size={16} />
                            <span>{t('editButton')}</span>
                        </button>
                        <button onClick={() => onDelete(admin)} className="btn-admin-delete" title={t('deleteButton')}>
                            <FiTrash2 size={16} />
                            <span>{t('deleteButton')}</span>
                        </button>
                    </div>
                </div>)}
        </div>;
};
export default AdminTable;
