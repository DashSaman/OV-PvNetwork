import { useEffect, useMemo, useState, useCallback } from 'react';
import { FiServer, FiCheckCircle, FiXCircle, FiSearch } from 'react-icons/fi';
import apiClient from '../services/api';
import AddNodeModal from '../components/AddNodeModal';
import EditNodeModal from '../components/EditNodeModal';
import NodeTable from '../components/NodeTable';
import NodeHealthPanel from '../components/NodeHealthPanel';
import UserStatCard from '../components/UserStatCard';
import Pagination from '../components/Pagination';
import { useTranslation } from 'react-i18next';
const ITEMS_PER_PAGE = 10;
const NodeManagement = () => {
  const [nodes, setNodes] = useState([]);
  const [nodeInfo, setNodeInfo] = useState({});
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [nodesError, setNodesError] = useState('');
  const [nodeStatusError, setNodeStatusError] = useState('');
  const [nodeHealth, setNodeHealth] = useState([]);
  const [isHealthLoading, setIsHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState('');

  const errorText = error =>
    error?.response?.data?.detail ||
    error?.response?.data?.msg ||
    error?.message ||
    'The request failed. Please try again.';
  const {
    t
  } = useTranslation();
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const fetchNodes = useCallback(async () => {
    setIsLoading(true);
    setNodesError('');
    try {
      const response = await apiClient.get('/nodes/');
      if (!response.data.success) {
        throw new Error(response.data.msg || 'Unable to load nodes.');
      }
      setNodes(response.data.data || []);
    } catch (error) {
      setNodesError(errorText(error));
    } finally {
      setIsLoading(false);
    }
  }, []);
  useEffect(() => {
    fetchNodes();
  }, [fetchNodes]);
  useEffect(() => {
    let intervalId;
    const fetchAllNodeStatus = async () => {
      if (!nodes || nodes.length === 0) {
        setNodeStatusError('');
        return;
      }
      setNodeStatusError('');
      const info = {};
      await Promise.all(nodes.map(async node => {
        try {
          const res = await apiClient.get(`/nodes/${node.id}/status/`);
          if (res.data.success && res.data.data && res.data.data.node_info) {
            info[node.id] = res.data.data.node_info;
          }
        } catch (error) {
          setNodeStatusError(errorText(error));
        }
      }));
      setNodeInfo(info);
    };
    fetchAllNodeStatus();
    intervalId = setInterval(fetchAllNodeStatus, 10000);
    return () => clearInterval(intervalId);
  }, [nodes]);
  const fetchNodeHealth = useCallback(async () => {
    setIsHealthLoading(true);
    setHealthError('');
    try {
      const response = await apiClient.get('/nodes/health/');
      if (!response.data.success || !Array.isArray(response.data.data)) {
        throw new Error(response.data.msg || 'Unable to load node health.');
      }
      setNodeHealth(response.data.data);
    } catch (error) {
      setHealthError(errorText(error));
    } finally {
      setIsHealthLoading(false);
    }
  }, []);
  useEffect(() => {
    fetchNodeHealth();
    const intervalId = setInterval(fetchNodeHealth, 10000);
    return () => clearInterval(intervalId);
  }, [fetchNodeHealth]);
  const handleNodeControl = useCallback(async (nodeId, patch) => {
    const response = await apiClient.put(`/nodes/${nodeId}/control`, patch);
    if (!response.data.success) {
      throw new Error(response.data.msg || 'Node control update failed.');
    }
    await Promise.all([fetchNodeHealth(), fetchNodes()]);
    return response.data.data;
  }, [fetchNodeHealth, fetchNodes]);
  const nodeStats = useMemo(() => {
    const activeCount = nodes.filter(node => node.status).length;
    return {
      total: nodes.length,
      active: activeCount,
      inactive: nodes.length - activeCount
    };
  }, [nodes]);
  const filteredNodes = useMemo(() => {
    return nodes.filter(node => node.name.toLowerCase().includes(searchTerm.toLowerCase()));
  }, [nodes, searchTerm]);
  const totalPages = Math.ceil(filteredNodes.length / ITEMS_PER_PAGE);
  const paginatedNodes = useMemo(() => {
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredNodes.slice(startIndex, startIndex + ITEMS_PER_PAGE);
  }, [filteredNodes, currentPage]);
  const handleSearchChange = event => {
    setSearchTerm(event.target.value);
    setCurrentPage(1);
  };
  const handleDelete = async (nodeId, nodeName) => {
    if (!window.confirm(`${t('deleteNodeConfirm')} ${nodeName}?`)) {
      return;
    }
    try {
      const response = await apiClient.delete(`/nodes/${nodeId}`);
      if (response.data.success) {
        alert(t("ui.123e8dfc7d0a"));
        fetchNodes();
      } else {
        alert(response.data.msg || 'Unable to delete node.');
      }
    } catch (error) {
      alert(
        error?.response?.data?.detail ||
        error?.response?.data?.msg ||
        error?.message ||
        t("ui.c9397e09b983")
      );
    }
  };
  const handleCheckStatus = async nodeId => {
    try {
      const response = await apiClient.get(`/nodes/${nodeId}/status/`);
      alert(response.data.msg || 'Status check complete.');
      fetchNodes();
    } catch {
      alert(t("ui.88fed087db4c"));
    }
  };
  const handleNodeCreated = () => {
    setIsAddModalOpen(false);
    fetchNodes();
  };
  const handleOpenEditModal = node => {
    setSelectedNode(node);
    setIsEditModalOpen(true);
  };
  const handleNodeUpdated = () => {
    setIsEditModalOpen(false);
    setSelectedNode(null);
    fetchNodes();
  };
  return <div id="nodes-view" className="view">
      <div className="view-header">
        <h2>{t('nodeManagement')}</h2>
        <button type="button" onClick={() => setIsAddModalOpen(true)} className="btn" aria-haspopup="dialog">
          {t('addNewNode')}
        </button>
      </div>

      {nodesError && <div className="monitor-form">
        <p className="error-message">{nodesError}</p>
        <button className="btn" disabled={isLoading} onClick={fetchNodes}>
          {t('retry', 'Retry')}
        </button>
      </div>}

      {nodeStatusError && <div className="monitor-form">
        <p className="error-message">{nodeStatusError}</p>
      </div>}

      <div className="stats-grid" style={{
      marginBottom: '30px'
    }}>
        <UserStatCard icon={<FiServer className="icon" />} label={t('nodesTotal')} value={nodeStats.total} color="var(--accent-color)" className="card-orange" />
        <UserStatCard icon={<FiCheckCircle className="icon" />} label={t('nodesActive')} value={nodeStats.active} color="var(--success-color)" className="card-green" />
        <UserStatCard icon={<FiXCircle className="icon" />} label={t('nodesInactive')} value={nodeStats.inactive} color="var(--danger-color)" className="card-red" />
      </div>

      {healthError && <div className="monitor-form">
        <p className="error-message">{healthError}</p>
        <button className="btn" disabled={isHealthLoading} onClick={fetchNodeHealth}>
          {t('retry', 'Retry')}
        </button>
      </div>}

      <NodeHealthPanel nodes={nodeHealth} isLoading={isHealthLoading} onRefresh={fetchNodeHealth} onControl={handleNodeControl} />

      <div className="search-pagination-controls">
        <div className="search-container">
          <FiSearch className="search-icon" />
          <input type="text" placeholder={t("ui.98dad3bbdc48")} value={searchTerm} onChange={handleSearchChange} className="search-input" />
        </div>
        <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} />
      </div>

      <NodeTable nodes={paginatedNodes} isLoading={isLoading} nodeInfo={nodeInfo} onDelete={handleDelete} onCheckStatus={handleCheckStatus} onEdit={handleOpenEditModal} />

      {isAddModalOpen && <AddNodeModal onClose={() => setIsAddModalOpen(false)} onNodeCreated={handleNodeCreated} />}

      {isEditModalOpen && <EditNodeModal node={selectedNode} onClose={() => setIsEditModalOpen(false)} onNodeUpdated={handleNodeUpdated} />}

    </div>;
};
export default NodeManagement;
