import { useEffect, useMemo, useState } from 'react';
import { FiSearch } from 'react-icons/fi';

import apiClient from '../services/api';
import './DomainHistoryModal.css';


const PAGE_SIZE = 25;


const DomainHistoryModal = ({ user, onClose }) => {
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [days, setDays] = useState(7);
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setAppliedSearch(search.trim());
      setPage(1);
    }, 350);

    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();

    const load = async () => {
      setIsLoading(true);
      setError('');

      try {
        const response = await apiClient.get(
          `/users/${user.uuid}/domain-activity`,
          {
            params: {
              search: appliedSearch,
              days,
              page,
              page_size: PAGE_SIZE,
            },
            signal: controller.signal,
          },
        );

        if (!response.data?.success || !response.data?.data) {
          throw new Error(response.data?.msg || 'Unable to load domain history.');
        }

        setData(response.data.data);
      } catch (exception) {
        if (
          exception?.name === 'CanceledError' ||
          exception?.code === 'ERR_CANCELED'
        ) {
          return;
        }

        setError(
          exception?.response?.data?.detail ||
          exception?.response?.data?.msg ||
          exception?.message ||
          'Unable to load domain history.',
        );
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    };

    load();
    return () => controller.abort();
  }, [user.uuid, appliedSearch, days, page, retryVersion]);

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(Number(data?.total || 0) / PAGE_SIZE));
  }, [data?.total]);

  const formatTime = value => {
    const timestamp = Number(value);

    if (!Number.isFinite(timestamp) || timestamp <= 0) {
      return '-';
    }

    return new Date(timestamp * 1000).toLocaleString();
  };

  return <div className="modal-overlay domain-history-overlay">
    <div
      className="modal domain-history-modal"
      role="dialog"
      aria-modal="true"
      aria-label={`Domain history for ${user.name}`}
    >
      <div className="modal-header">
        <div>
          <h3>Domain History — {user.name}</h3>
          <p className="domain-history-subtitle">
            DNS domains observed on the VPN; full URLs and HTTPS content are not recorded.
          </p>
        </div>
        <button onClick={onClose} className="close-modal-btn" aria-label="Close">
          &times;
        </button>
      </div>

      <div className="domain-history-body">
        <div className="domain-history-controls">
          <label className="domain-history-search">
            <FiSearch aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Search domain..."
              autoComplete="off"
            />
          </label>

          <label className="domain-history-period">
            <span>Period</span>
            <select
              value={days}
              onChange={event => {
                setDays(Number(event.target.value));
                setPage(1);
              }}
            >
              <option value={1}>Last 24 hours</option>
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </label>
        </div>

        <div className="domain-history-summary">
          <span><strong>{Number(data?.total || 0).toLocaleString()}</strong> domains</span>
          <span><strong>{Number(data?.total_hits || 0).toLocaleString()}</strong> DNS queries</span>
        </div>

        <div className="domain-history-note">
          Encrypted DNS, DNS caching and browser prefetching can make this list incomplete
          or include a domain that was not opened directly.
        </div>

        {error && <div className="domain-history-error">
          <span>{error}</span>
          <button
            className="btn"
            onClick={() => setRetryVersion(value => value + 1)}
          >
            Retry
          </button>
        </div>}

        {isLoading ? <div className="domain-history-loading">
          <span className="spinner" />
          Loading domain history...
        </div> : !error && (!data?.items || data.items.length === 0) ?
          <div className="domain-history-empty">
            No observed domains match this filter.
          </div> : !error && <div className="domain-history-table-wrap">
            <table className="domain-history-table">
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Node</th>
                  <th>Queries</th>
                  <th>First seen</th>
                  <th>Last seen</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map(item => <tr key={`${item.node_id}:${item.domain}`}>
                  <td className="domain-history-domain">{item.domain}</td>
                  <td>{item.node_name || `#${item.node_id}`}</td>
                  <td>{Number(item.hit_count || 0).toLocaleString()}</td>
                  <td>{formatTime(item.first_seen)}</td>
                  <td>{formatTime(item.last_seen)}</td>
                </tr>)}
              </tbody>
            </table>
          </div>}
      </div>

      <div className="modal-footer domain-history-footer">
        <div className="domain-history-pagination">
          <button
            className="btn btn-secondary"
            disabled={page <= 1 || isLoading}
            onClick={() => setPage(value => Math.max(1, value - 1))}
          >
            Previous
          </button>
          <span>Page {page} of {totalPages}</span>
          <button
            className="btn btn-secondary"
            disabled={page >= totalPages || isLoading}
            onClick={() => setPage(value => Math.min(totalPages, value + 1))}
          >
            Next
          </button>
        </div>
        <button className="btn" onClick={onClose}>Close</button>
      </div>
    </div>
  </div>;
};


export default DomainHistoryModal;
