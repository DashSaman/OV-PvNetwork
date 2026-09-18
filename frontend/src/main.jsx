import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext.jsx';
import './i18n';

// OV_THEME_BOOT_V2
try {
  const saved =
    window.localStorage.getItem(
      'ov-dashboard-theme'
    );

  const theme =
    saved === 'light'
      ? 'light'
      : 'dark';

  document.documentElement.setAttribute(
    'data-ov-theme',
    theme
  );

  document.body.setAttribute(
    'data-ov-theme',
    theme
  );
} catch {
  document.documentElement.setAttribute(
    'data-ov-theme',
    'dark'
  );
}

const base = import.meta.env.VITE_URLPATH || '';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter basename={`/${base}`}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
