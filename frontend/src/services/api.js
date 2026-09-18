import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

let handlingUnauthorized = false;

/*
 * Add JWT to every authenticated API request.
 */
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');

    if (token) {
      config.headers = config.headers || {};
      config.headers['Authorization'] = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

/*
 * If the JWT is expired/invalid, remove the stale session.
 *
 * Login itself is excluded so an incorrect username/password
 * can still display the normal login error.
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url || '';

    if (
      status === 401 &&
      url !== '/login' &&
      !handlingUnauthorized
    ) {
      handlingUnauthorized = true;

      localStorage.removeItem('authToken');
      localStorage.removeItem('userRole');

      // Reload current SPA location.
      // AuthContext will see that there is no valid token,
      // then React Router will send the user to login.
      window.location.reload();
    }

    return Promise.reject(error);
  }
);

export default apiClient;
