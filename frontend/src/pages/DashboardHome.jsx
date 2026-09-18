import { useAuth } from '../context/AuthContext';
import BackupRestorePanel from '../components/BackupRestorePanel';
import ServerStats from './ServerStats';


export default function DashboardHome() {
  const { userRole } = useAuth();

  return (
    <>
      <ServerStats />
      {userRole === 'main_admin' && <BackupRestorePanel />}
    </>
  );
}
