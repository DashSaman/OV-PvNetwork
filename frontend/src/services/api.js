import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

let handlingUnauthorized = false;

const hasActivePanelSettingsChange = () => {
  try {
    const raw = sessionStorage.getItem('pvnPanelSettingsChange');
    if (!raw) return false;
    const value = JSON.parse(raw);
    if (!value?.change_id || !value?.status_token || Number(value.expires_at || 0) <= Date.now()) {
      sessionStorage.removeItem('pvnPanelSettingsChange');
      return false;
    }
    return true;
  } catch {
    sessionStorage.removeItem('pvnPanelSettingsChange');
    return false;
  }
};

apiClient.interceptors.request.use(
  (config) => {
    if (!config.skipAuth) {
      const token = localStorage.getItem('authToken');
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url || '';
    const skipReload = Boolean(error?.config?.skipUnauthorizedReload);

    if (
      status === 401 &&
      url !== '/login' &&
      !skipReload &&
      !hasActivePanelSettingsChange() &&
      !handlingUnauthorized
    ) {
      handlingUnauthorized = true;
      localStorage.removeItem('authToken');
      localStorage.removeItem('userRole');
      window.location.reload();
    }

    return Promise.reject(error);
  }
);

export default apiClient;
