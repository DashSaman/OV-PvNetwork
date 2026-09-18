import { useEffect, useMemo, useState, useCallback } from 'react';
import { FiUsers, FiSearch } from 'react-icons/fi';
import apiClient from '../services/api';
import AddAdminModal from '../components/AddAdminModal';
import EditAdminModal from '../components/EditAdminModal';
import AdminTable from '../components/AdminTable';
import UserStatCard from '../components/UserStatCard';
import Pagination from '../components/Pagination';
import { useTranslation } from 'react-i18next';

const ITEMS_PER_PAGE = 10;

const AdminManagement = () => {
    const [admins, setAdmins] = useState([]);
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [selectedAdmin, setSelectedAdmin] = useState(null);
    const [deleteAdminTarget, setDeleteAdminTarget] = useState(null);
    const [deleteMode, setDeleteMode] = useState('transfer_users');
    const [isDeleting, setIsDeleting] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const { t } = useTranslation();

    const errorText = exception =>
        exception?.response?.data?.detail ||
        exception?.response?.data?.msg ||
        exception?.message ||
        t('unableToLoadAdmins', 'Unable to load administrators.');

    const [searchTerm, setSearchTerm] = useState('');
    const [currentPage, setCurrentPage] = useState(1);

    const fetchAdmins = useCallback(async () => {
        setIsLoading(true);
        setError('');
        try {
            const response = await apiClient.get('/admin/');
            if (!response.data.success) {
                throw new Error(response.data.msg || 'Unable to load administrators.');
            }
            setAdmins(response.data.data || []);
        } catch (exception) {
            setError(errorText(exception));
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAdmins();
    }, [fetchAdmins]);

    const adminStats = useMemo(() => ({ total: admins.length }), [admins]);
    const filteredAdmins = useMemo(() => admins.filter(admin =>
        admin.username.toLowerCase().includes(searchTerm.toLowerCase())
    ), [admins, searchTerm]);
    const totalPages = Math.ceil(filteredAdmins.length / ITEMS_PER_PAGE);
    const paginatedAdmins = useMemo(() => {
        const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
        return filteredAdmins.slice(startIndex, startIndex + ITEMS_PER_PAGE);
    }, [filteredAdmins, currentPage]);

    const handleSearchChange = event => {
        setSearchTerm(event.target.value);
        setCurrentPage(1);
    };
    const handleAdminCreated = () => {
        setIsAddModalOpen(false);
        fetchAdmins();
    };
    const handleOpenEditModal = admin => {
        setSelectedAdmin(admin);
        setIsEditModalOpen(true);
    };
    const handleAdminUpdated = () => {
        setIsEditModalOpen(false);
        setSelectedAdmin(null);
        fetchAdmins();
    };
    const handleDelete = admin => {
        // OV_ADMIN_DELETE_OPTIONS_V7
        setDeleteAdminTarget(admin);
        setDeleteMode('transfer_users');
        setError('');
    };
    const handleConfirmDelete = async () => {
        if (!deleteAdminTarget || isDeleting) return;
        setIsDeleting(true);
        setError('');
        try {
            const response = await apiClient.post(
                `/admin/${encodeURIComponent(deleteAdminTarget.username)}/delete`,
                { mode: deleteMode, target_owner: 'owner' },
                { timeout: 600000 }
            );
            if (!response.data?.success) {
                throw new Error(response.data?.msg || t('unableToDeleteAdmin'));
            }
            const count = Number(response.data?.data?.affected_users || 0);
            alert(deleteMode === 'transfer_users'
                ? `نماینده حذف شد و ${count} کاربر به Owner منتقل شد.`
                : `نماینده و ${count} کاربر متعلق به او حذف شدند.`);
            setDeleteAdminTarget(null);
            fetchAdmins();
        } catch (exception) {
            const message = errorText(exception);
            setError(message);
            alert(message);
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div id="admins-view" className="view">
            <div className="view-header">
                <h2>{t('adminManagement')}</h2>
                <button onClick={() => setIsAddModalOpen(true)} className="btn">
                    {t('addNewAdmin')}
                </button>
            </div>
            {error && <div className="monitor-form">
                <p className="error-message">{error}</p>
                <button className="btn" disabled={isLoading} onClick={fetchAdmins}>
                    {t('retry', 'Retry')}
                </button>
            </div>}
            <div className="stats-grid" style={{ marginBottom: '30px' }}>
                <UserStatCard icon={<FiUsers className="icon" />} label={t('adminsTotal')}
                    value={adminStats.total} color="var(--accent-color)" className="card-orange" />
            </div>
            <div className="search-pagination-controls">
                <div className="search-container">
                    <FiSearch className="search-icon" />
                    <input type="text" placeholder={t('searchByUsername')} value={searchTerm}
                        onChange={handleSearchChange} className="search-input" />
                </div>
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
            </div>
            <AdminTable admins={paginatedAdmins} isLoading={isLoading}
                onEdit={handleOpenEditModal} onDelete={handleDelete} />
            {isAddModalOpen && <AddAdminModal onClose={() => setIsAddModalOpen(false)}
                onAdminCreated={handleAdminCreated} />}
            {isEditModalOpen && <EditAdminModal admin={selectedAdmin}
                onClose={() => setIsEditModalOpen(false)} onAdminUpdated={handleAdminUpdated} />}

            {deleteAdminTarget && (
                <div className="modal-overlay">
                    <div className="modal" style={{ maxWidth: '560px' }}>
                        <div className="modal-header">
                            <h3>حذف نماینده {deleteAdminTarget.username}</h3>
                            <button className="close-modal-btn" disabled={isDeleting}
                                onClick={() => setDeleteAdminTarget(null)}>&times;</button>
                        </div>
                        <div className="input-group">
                            <p style={{ marginTop: 0 }}>
                                این نماینده {Number(deleteAdminTarget.users_count || 0)} کاربر دارد. نحوه تعیین تکلیف کاربران را انتخاب کنید:
                            </p>
                            <label style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', cursor: 'pointer', marginBottom: '14px' }}>
                                <input type="radio" name="admin-delete-mode" value="transfer_users"
                                    checked={deleteMode === 'transfer_users'}
                                    onChange={() => setDeleteMode('transfer_users')} disabled={isDeleting} />
                                <span><strong>حذف نماینده و انتقال کاربران به Owner</strong><br />
                                    <small>حجم، مصرف، تاریخ، وضعیت، تعداد اتصال و نودهای کاربران بدون تغییر باقی می‌ماند.</small></span>
                            </label>
                            <label style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', cursor: 'pointer' }}>
                                <input type="radio" name="admin-delete-mode" value="delete_users"
                                    checked={deleteMode === 'delete_users'}
                                    onChange={() => setDeleteMode('delete_users')} disabled={isDeleting} />
                                <span><strong>حذف نماینده و تمام کاربران او</strong><br />
                                    <small style={{ color: '#ff9b9b' }}>این گزینه کاربران را از پنل و نودها حذف می‌کند و قابل بازگشت نیست.</small></span>
                            </label>
                        </div>
                        <div className="modal-footer">
                            <button type="button" className="btn btn-secondary" disabled={isDeleting}
                                onClick={() => setDeleteAdminTarget(null)}>انصراف</button>
                            <button type="button" className="btn" disabled={isDeleting}
                                onClick={handleConfirmDelete}>
                                {isDeleting ? 'در حال انجام...' : 'تأیید حذف نماینده'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AdminManagement;
