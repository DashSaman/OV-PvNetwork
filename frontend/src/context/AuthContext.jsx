import React, { createContext, useState, useContext } from 'react';
import apiClient from '../services/api';

const AuthContext = createContext(null);

const decodeJwtPayload = (token) => {
  const parts = token.split('.');

  if (parts.length !== 3) {
    throw new Error('Invalid JWT');
  }

  let base64 = parts[1]
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const padding = (4 - (base64.length % 4)) % 4;
  base64 += '='.repeat(padding);

  const binary = atob(base64);

  const bytes = Uint8Array.from(
    binary,
    (char) => char.charCodeAt(0)
  );

  const json = new TextDecoder().decode(bytes);

  return JSON.parse(json);
};


const loadValidToken = () => {
  const storedToken = localStorage.getItem('authToken');

  if (!storedToken) {
    return null;
  }

  try {
    const payload = decodeJwtPayload(storedToken);

    if (
      !payload.exp ||
      payload.exp * 1000 <= Date.now()
    ) {
      throw new Error('JWT expired');
    }

    return storedToken;
  } catch {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    return null;
  }
};


export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => loadValidToken());

  const [userRole, setUserRole] = useState(() => {
    const storedToken = localStorage.getItem('authToken');

    if (!storedToken) {
      return null;
    }

    return localStorage.getItem('userRole');
  });


  const login = async (username, password, otp = '') => {
    const formData = new URLSearchParams();

    formData.append('username', username);
    formData.append('password', password);
    formData.append('client_secret', otp || '');

    const response = await apiClient.post(
      '/login',
      formData,
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    const newToken = response.data.access_token;

    const payload = decodeJwtPayload(newToken);
    const role = payload.type;

    localStorage.setItem('authToken', newToken);
    localStorage.setItem('userRole', role);

    setToken(newToken);
    setUserRole(role);
  };


  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');

    setToken(null);
    setUserRole(null);
  };


  const isAuthenticated = Boolean(token);


  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        login,
        logout,
        userRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};


export const useAuth = () => useContext(AuthContext);
