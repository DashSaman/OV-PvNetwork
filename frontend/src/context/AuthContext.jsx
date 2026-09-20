import React, { createContext, useState, useContext, useCallback } from 'react';
import apiClient from '../services/api';

const AuthContext = createContext(null);

const decodeJwtPayload = (token) => {
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Invalid JWT');
  let base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
  const padding = (4 - (base64.length % 4)) % 4;
  base64 += '='.repeat(padding);
  const binary = atob(base64);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
};

const loadValidToken = () => {
  const storedToken = localStorage.getItem('authToken');
  if (!storedToken) return null;
  try {
    const payload = decodeJwtPayload(storedToken);
    if (!payload.exp || payload.exp * 1000 <= Date.now()) throw new Error('JWT expired');
    return storedToken;
  } catch {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    return null;
  }
};

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => loadValidToken());
  const [userRole, setUserRole] = useState(() => (
    localStorage.getItem('authToken') ? localStorage.getItem('userRole') : null
  ));

  const login = async (username, password, otp = '') => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    formData.append('client_secret', otp || '');
    const response = await apiClient.post('/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    const newToken = response.data.access_token;
    const payload = decodeJwtPayload(newToken);
    localStorage.setItem('authToken', newToken);
    localStorage.setItem('userRole', payload.type);
    setToken(newToken);
    setUserRole(payload.type);
  };

  const stageReplacementToken = useCallback((nextToken) => {
    if (nextToken) sessionStorage.setItem('pvnPendingAuthToken', nextToken);
    else sessionStorage.removeItem('pvnPendingAuthToken');
  }, []);

  const promoteReplacementToken = useCallback(() => {
    const pending = sessionStorage.getItem('pvnPendingAuthToken');
    if (!pending) return false;
    const payload = decodeJwtPayload(pending);
    if (!payload.exp || payload.exp * 1000 <= Date.now()) {
      sessionStorage.removeItem('pvnPendingAuthToken');
      return false;
    }
    localStorage.setItem('authToken', pending);
    localStorage.setItem('userRole', payload.type);
    sessionStorage.removeItem('pvnPendingAuthToken');
    setToken(pending);
    setUserRole(payload.type);
    return true;
  }, []);

  const discardReplacementToken = useCallback(() => {
    sessionStorage.removeItem('pvnPendingAuthToken');
  }, []);

  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    sessionStorage.removeItem('pvnPendingAuthToken');
    sessionStorage.removeItem('pvnPanelSettingsChange');
    setToken(null);
    setUserRole(null);
  };

  const isAuthenticated = Boolean(token);

  return (
    <AuthContext.Provider value={{
      isAuthenticated,
      login,
      logout,
      userRole,
      stageReplacementToken,
      promoteReplacementToken,
      discardReplacementToken,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

// Context hook intentionally lives beside its provider.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext);
