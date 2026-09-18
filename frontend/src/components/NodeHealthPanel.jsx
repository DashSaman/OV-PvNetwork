import { useEffect, useMemo, useState } from 'react';
import {
  FiActivity,
  FiPauseCircle,
  FiPlayCircle,
  FiRefreshCw,
  FiStar,
} from 'react-icons/fi';
import { useTranslation } from 'react-i18next';


const badgeStyle = (health) => {
  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '5px 10px',
    borderRadius: '999px',
    fontSize: '12px',
    fontWeight: 700,
    whiteSpace: 'nowrap',
  };

  if (health === 'healthy') {
    return {
      ...base,
      background: 'rgba(76, 175, 80, 0.15)',
      color: '#66bb6a',
    };
  }

  if (health === 'degraded') {
    return {
      ...base,
      background: 'rgba(255, 193, 7, 0.15)',
      color: '#ffca28',
    };
  }

  if (health === 'disabled') {
    return {
      ...base,
      background: 'rgba(158, 158, 158, 0.15)',
      color: '#bdbdbd',
    };
  }

  return {
    ...base,
    background: 'rgba(244, 67, 54, 0.15)',
    color: '#ef5350',
  };
};


const fmt = (value, suffix = '') => {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return '—';
  }

  return `${Number(value).toFixed(1)}${suffix}`;
};


const NodeHealthPanel = ({
  nodes,
  isLoading,
  onRefresh,
  onControl,
}) => {
  const { t } = useTranslation();

  const [weights, setWeights] = useState({});
  const [busyNode, setBusyNode] = useState(null);


  useEffect(() => {
    const next = {};

    for (const node of nodes || []) {
      next[node.id] = String(
        node.weight ?? 100
      );
    }

    setWeights(next);
  }, [nodes]);


  const summary = useMemo(() => {
    const list = nodes || [];

    return {
      healthy:
        list.filter(
          n => n.health === 'healthy'
        ).length,

      degraded:
        list.filter(
          n => n.health === 'degraded'
        ).length,

      draining:
        list.filter(
          n => n.drain
        ).length,

      offline:
        list.filter(
          n =>
            n.health === 'offline' ||
            n.health === 'disabled'
        ).length,
    };
  }, [nodes]);


  const updateDrain = async (node) => {
    const nextDrain = !node.drain;

    const message = nextDrain
      ? `${t(
          'drainNodeConfirm',
          'Stop new connections on'
        )} ${node.name}?`
      : `${t(
          'resumeNodeConfirm',
          'Resume new connections on'
        )} ${node.name}?`;

    if (!window.confirm(message)) {
      return;
    }

    setBusyNode(node.id);

    try {
      await onControl(
        node.id,
        {
          drain: nextDrain,
        }
      );
    } finally {
      setBusyNode(null);
    }
  };


  const saveWeight = async (node) => {
    const value = Number(
      weights[node.id]
    );

    if (
      !Number.isInteger(value) ||
      value < 0 ||
      value > 1000
    ) {
      alert(
        t(
          'invalidNodeWeight',
          'Weight must be an integer from 0 to 1000.'
        )
      );

      return;
    }

    setBusyNode(node.id);

    try {
      await onControl(
        node.id,
        {
          weight: value,
        }
      );
    } finally {
      setBusyNode(null);
    }
  };


  return (
    <div
      style={{
        marginBottom: '30px',
        background: 'var(--background-secondary)',
        border: '1px solid var(--border-color)',
        borderRadius: '14px',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '18px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '15px',
          flexWrap: 'wrap',
          borderBottom: '1px solid var(--border-color)',
        }}
      >
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '9px',
              fontWeight: 700,
              fontSize: '17px',
            }}
          >
            <FiActivity />

            {t(
              'nodeHealthRouting',
              'Node Health & Routing'
            )}
          </div>

          <div
            style={{
              opacity: 0.7,
              fontSize: '12px',
              marginTop: '6px',
            }}
          >
            {t(
              'nodeHealthHint',
              'Drain preserves existing sessions but blocks new connections.'
            )}
          </div>
        </div>

        <button
          type="button"
          className="btn"
          onClick={onRefresh}
          disabled={isLoading}
          style={{
            display: 'inline-flex',
            gap: '7px',
            alignItems: 'center',
          }}
        >
          <FiRefreshCw />

          {isLoading
            ? t('loading', 'Loading...')
            : t('refresh', 'Refresh')}
        </button>
      </div>


      <div
        style={{
          padding: '12px 20px',
          display: 'flex',
          gap: '18px',
          flexWrap: 'wrap',
          fontSize: '13px',
          borderBottom: '1px solid var(--border-color)',
        }}
      >
        <span>
          🟢 {t('healthy', 'Healthy')}:
          {' '}
          <strong>{summary.healthy}</strong>
        </span>

        <span>
          🟡 {t('degraded', 'Degraded')}:
          {' '}
          <strong>{summary.degraded}</strong>
        </span>

        <span>
          ⏸ {t('draining', 'Draining')}:
          {' '}
          <strong>{summary.draining}</strong>
        </span>

        <span>
          🔴 {t('offline', 'Offline')}:
          {' '}
          <strong>{summary.offline}</strong>
        </span>
      </div>


      <div
        style={{
          overflowX: 'auto',
        }}
      >
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            minWidth: '1180px',
          }}
        >
          <thead>
            <tr>
              {[
                t('node', 'Node'),
                t('health', 'Health'),
                t('mode', 'Mode'),
                'CPU',
                'RAM',
                t('apiLatency', 'API'),
                t('onlineUsers', 'Online Users'),
                t('sessions', 'Sessions'),
                t('weight', 'Weight'),
                t('score', 'Score'),
                t('actions', 'Actions'),
              ].map((title) => (
                <th
                  key={title}
                  style={{
                    padding: '12px',
                    textAlign: 'left',
                    fontSize: '12px',
                    opacity: 0.75,
                    borderBottom: '1px solid var(--border-color)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {title}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {(nodes || []).map((node) => {
              const busy =
                busyNode === node.id;

              return (
                <tr key={node.id}>
                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        gap: '7px',
                        alignItems: 'center',
                        fontWeight: 700,
                      }}
                    >
                      {node.recommended && (
                        <FiStar
                          title={t(
                            'recommended',
                            'Recommended'
                          )}
                        />
                      )}

                      {node.name}
                    </div>

                    <div
                      style={{
                        fontSize: '11px',
                        opacity: 0.6,
                        marginTop: '4px',
                      }}
                    >
                      {node.address}
                    </div>
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    <span
                      style={badgeStyle(
                        node.health
                      )}
                    >
                      {node.health || 'unknown'}
                    </span>
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {node.drain
                      ? `⏸ ${t(
                          'draining',
                          'Draining'
                        )}`
                      : `▶ ${t(
                          'enabled',
                          'Enabled'
                        )}`}
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    {fmt(
                      node.cpu_usage,
                      '%'
                    )}
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    {fmt(
                      node.memory_usage,
                      '%'
                    )}
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {fmt(
                      node.api_latency_ms,
                      ' ms'
                    )}
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    {node.central_online_users ?? 0}
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    {node.central_active_sessions ?? 0}
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        gap: '6px',
                        alignItems: 'center',
                      }}
                    >
                      <input
                        type="number"
                        min="0"
                        max="1000"
                        step="1"
                        value={
                          weights[node.id] ?? ''
                        }
                        onChange={(event) =>
                          setWeights(
                            current => ({
                              ...current,
                              [node.id]:
                                event.target.value,
                            })
                          )
                        }
                        style={{
                          width: '75px',
                          padding: '7px',
                          borderRadius: '7px',
                          border: '1px solid var(--border-color)',
                          background: 'var(--background-primary)',
                          color: 'var(--text-primary)',
                        }}
                      />

                      <button
                        type="button"
                        className="btn"
                        disabled={busy}
                        onClick={() =>
                          saveWeight(node)
                        }
                        style={{
                          padding: '7px 9px',
                          fontSize: '11px',
                        }}
                      >
                        {t('save', 'Save')}
                      </button>
                    </div>
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    {node.selection_score === null ||
                    node.selection_score === undefined
                      ? '—'
                      : Number(
                          node.selection_score
                        ).toFixed(2)}
                  </td>

                  <td
                    style={{
                      padding: '12px',
                      borderBottom: '1px solid var(--border-color)',
                    }}
                  >
                    <button
                      type="button"
                      className="btn"
                      disabled={busy}
                      onClick={() =>
                        updateDrain(node)
                      }
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {node.drain
                        ? <FiPlayCircle />
                        : <FiPauseCircle />}

                      {node.drain
                        ? t(
                            'resume',
                            'Resume'
                          )
                        : t(
                            'drain',
                            'Drain'
                          )}
                    </button>
                  </td>
                </tr>
              );
            })}

            {!isLoading &&
              (!nodes || nodes.length === 0) && (
                <tr>
                  <td
                    colSpan="11"
                    style={{
                      padding: '25px',
                      textAlign: 'center',
                      opacity: 0.7,
                    }}
                  >
                    {t(
                      'noHealthData',
                      'No health data available.'
                    )}
                  </td>
                </tr>
              )}
          </tbody>
        </table>
      </div>
    </div>
  );
};


export default NodeHealthPanel;
