import { t } from "../i18n";
import { useEffect, useState } from 'react';
import apiClient from '../services/api';
const ResellerNodes = () => {
  const [nodes, setNodes] = useState([]);
  useEffect(() => {
    const load = () => apiClient.get('/nodes/public-health/').then(r => setNodes(r.data.data || [])).catch(() => setNodes([]));
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);
  return <div className="view">
    <div className="view-header"><h2>{t("ui.ff3178cfe5f8")}</h2></div>
    <div className="admin-cards-container">
      {nodes.map(node => <div className="admin-card" key={node.id}>
        <div className="admin-card-header"><div className="admin-info">
          <h4 className="admin-username">{node.name}</h4>
          <div className="admin-stats"><span>{t("ui.372c3f95267f")}{node.health === 'healthy' ? t("ui.c3e839df6084") : node.health}</span></div>
          <div className="admin-stats"><span>{t("ui.56f91b9b56b4")}{node.online_users || 0}</span></div>
          <div className="admin-stats"><span>{node.eligible ? t("ui.2b068ac2d28d") : t("ui.a840afd3822c")}</span></div>
        </div></div>
      </div>)}
    </div>
  </div>;
};
export default ResellerNodes;
