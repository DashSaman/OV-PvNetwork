

const baseUrl = (process.env.PV_UI_BASE_URL || 'http://127.0.0.1:4173/panel').replace(/\/$/, '');
if(!/^http:\/\/127\.0\.0\.1:\d+\/panel$/.test(baseUrl))throw new Error('Documentation captures require owned loopback preview');
const routes = ['/', '/users', '/nodes', '/admins', '/operations', '/security', '/fleet', '/monitoring', '/bandwidth'];
const demoUser = {
  id: 1,
  uuid: 'demo-user-001',
  name: 'demo-user',
  owner: 'demo-admin',
  total: 0,
  used: 0,
  expiry_date: '2030-01-01',
  is_active: true,
  is_online: false,
  online_count: 0,
  device_limit: 1,
  anyconnect_enabled: false,
  node_ids: [1],
};

function responseFor(url) {
  const path = new URL(url).pathname.replace(/^\/api/, '');
  const ok = (data = {}) => ({ success: true, msg: 'ok', data });

  if (path === '/server/info') return ok({ cpu: 12, memory_percent: 24, memory_total: 100, memory_used: 24, uptime: 7200, disk_percent: 31, disk_total: 100, disk_used: 31 });
  if (path === '/server/dashboard-live') return ok({
    presence: { online_users: 0, central_online_users: 0, direct_fallback_users: 0 },
    nodes: [1,2].map(id => ({ id, available: true, rate_ready: true, rx_bytes: 9e9, tx_bytes: 11e9, download_bps: 12e6, upload_bps: 4e6, traffic_bytes: 20e9, cpu_usage: 18, memory_usage: 32, uptime: 7200, online_count: 0, online_sessions: 0 })),
  });
  if (path === '/nodes/health/' || path === '/nodes/health') return ok([]);
  if (/^\/nodes\/\d+\/status\/?$/.test(path)) return ok({node_info:{cpu_usage:12,memory_usage:24,uptime:7200}});
  if (path === '/nodes/' || path === '/nodes') return ok([
    { id: 1, name: 'Demo Europe', address: 'node.example.invalid', port: 9090, ovpn_port: 1194, protocol: 'udp', status: true, drain: false, maintenance: false },
    { id: 2, name: 'Demo USA', address: 'node.example.invalid', port: 9090, ovpn_port: 1194, protocol: 'udp', status: true, drain: false, maintenance: false },
  ]);
  if (path.includes('/users/online')) return ok({ total: 0, per_node: {} });
  if (path === '/users/' || path === '/users') return ok([demoUser]);
  if (path.endsWith('/domain-activity')) return ok({items:[{node_id:1,node_name:'Demo Europe',domain:'docs.example.invalid',hit_count:7,first_seen:1790000000,last_seen:1790000300}],total:1,total_hits:7,page:1,page_size:25});
  if (path.startsWith('/users')) return ok({});
  if (path === '/admin/' || path === '/admin') return ok([{id:7,username:'demo-reseller',is_active:true,quota_total:500,quota_used:100,unlimited_quota_total:5,unlimited_quota_used:1}]);
  if (path.startsWith('/admins')) return ok([]);
  if (path.startsWith('/backups')) return ok({ backups: [{id:'20300101-120000',created_at:'2030-01-01T12:00:00Z',size_bytes:1048576,verified:true}] });
  if (path === '/fleet/' || path === '/fleet') return ok([
    {id:1,name:'Demo Europe',version:'1.0.54',health_score:96,health:'healthy',drain:false,maintenance:false},
    {id:2,name:'Demo USA',version:'1.0.54',health_score:88,health:'healthy',drain:true,maintenance:false},
  ]);
  if (path.startsWith('/fleet/jobs/')) return ok({ id: 'demo', state: 'succeeded', stage: 'done' });
  if (path === '/operations/dashboard') return ok({ users: 1, nodes: 2, online: 0, traffic_bytes: 0 });
  if (path === '/operations/audit') return ok([]);
  if (path.includes('/operations/users/') && path.includes('/history')) return ok([]);
  if (path === '/security/panel-settings') return ok({username:'demo-admin',panel_path:'panel',panel_port:19000,redirect:null,active_change:null});
  if (path.startsWith('/security')) return ok({
    rate_limit_enabled: true,
    rate_limit_per_minute: 120,
    ip_allowlist_enabled: false,
    allowed_cidrs: [],
    totp_enabled: false,
    tokens: [],
  });
  if (path.startsWith('/server/monitoring')) return ok({
    enabled: false,
    telegram_configured: false,
    cpu_threshold: 90,
    memory_threshold: 90,
    disk_threshold: 90,
  });
  if (path === '/bandwidth/status') return ok([]);
  if (path === '/bandwidth/' || path === '/bandwidth') return ok({
    settings: { enabled: false, target_type: 'all', download_mbps: 1, node_ids: [] },
    nodes: [], users: [demoUser], owners: [], groups: [],
  });
  if (path.startsWith('/bandwidth')) return ok({});
  if (path === '/anyconnect/settings') return ok({ default_enabled: false });
  if (path === '/server/settings/' || path === '/server/settings') return ok({
    subscription_url_prefix: 'https://example.invalid/',
    subscription_path: 'sub',
  });
  if (path.includes('/settings') || path.includes('/setting')) return ok({});
  return ok({});
}

function demoToken() {
  const payload = Buffer.from(JSON.stringify({
    exp: Math.floor(Date.now() / 1000) + 3600,
    type: 'main_admin',
  })).toString('base64url');
  return `demo.${payload}.signature`;
}



export { baseUrl, routes, demoUser, responseFor, demoToken };
