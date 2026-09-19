import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FiAlertTriangle,
  FiArchive,
  FiCheckCircle,
  FiDatabase,
  FiDownloadCloud,
  FiRefreshCw,
  FiUploadCloud,
} from 'react-icons/fi';
import apiClient from '../services/api';


const delay = (milliseconds) => new Promise((resolve) => {
  window.setTimeout(resolve, milliseconds);
});


const errorText = (error) => (
  error?.response?.data?.detail
  || error?.response?.data?.msg
  || error?.message
  || 'عملیات انجام نشد. دوباره تلاش کنید.'
);


const formatBytes = (value) => {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  return `${(bytes / (1024 ** index)).toFixed(index ? 2 : 0)} ${units[index]}`;
};


const formatDate = (value) => {
  try {
    return new Intl.DateTimeFormat('fa-IR', {
      dateStyle: 'medium',
      timeStyle: 'medium',
    }).format(new Date(value));
  } catch {
    return value || '-';
  }
};


export default function BackupRestorePanel() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [downloading, setDownloading] = useState('');
  const [restoring, setRestoring] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [confirmation, setConfirmation] = useState('');
  const [job, setJob] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const loadBackups = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/backups/', { timeout: 30000 });
      if (alive.current) {
        setBackups(response.data?.data?.backups || []);
      }
    } catch (exception) {
      if (alive.current) setError(errorText(exception));
    } finally {
      if (alive.current && !quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBackups();
  }, [loadBackups]);

  const createBackup = async () => {
    setCreating(true);
    setError('');
    setMessage('');
    try {
      const response = await apiClient.post('/backups/', null, { timeout: 900000 });
      if (alive.current) {
        setMessage(response.data?.msg || 'بکاپ با موفقیت ساخته شد.');
      }
      await loadBackups(true);
    } catch (exception) {
      if (alive.current) setError(errorText(exception));
    } finally {
      if (alive.current) setCreating(false);
    }
  };

  const downloadBackup = async (backup) => {
    setDownloading(backup.id);
    setError('');
    setMessage('');
    try {
      const response = await apiClient.get(
        `/backups/${backup.id}/download`,
        { responseType: 'blob', timeout: 300000 },
      );
      const href = URL.createObjectURL(response.data);
      const anchor = document.createElement('a');
      anchor.href = href;
      anchor.download = `pvnetwork-backup-${backup.id}.tar.gz`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(href), 1000);
      if (alive.current) setMessage('فایل بکاپ دانلود شد. آن را محرمانه نگه دارید.');
    } catch (exception) {
      if (alive.current) setError(errorText(exception));
    } finally {
      if (alive.current) setDownloading('');
    }
  };

  const pollRestore = async (jobId) => {
    let temporaryFailures = 0;
    for (let attempt = 0; attempt < 240; attempt += 1) {
      await delay(2000);
      if (!alive.current) return;
      try {
        const response = await apiClient.get(
          `/backups/restore/${jobId}`,
          { timeout: 10000 },
        );
        temporaryFailures = 0;
        const next = response.data?.data;
        if (next) setJob(next);
        if (next?.state === 'succeeded') {
          setMessage('اطلاعات و تنظیمات پنل با موفقیت بازیابی شد.');
          await loadBackups(true);
          return;
        }
        if (next?.state === 'failed') {
          const terminalError = new Error(next.message || 'بازیابی ناموفق بود.');
          terminalError.restoreTerminal = true;
          throw terminalError;
        }
      } catch (exception) {
        if (exception?.restoreTerminal) throw exception;
        temporaryFailures += 1;
        if (exception?.response?.status === 401) return;
        if (temporaryFailures >= 25) throw exception;
      }
    }
    throw new Error('زمان انتظار بازیابی تمام شد؛ وضعیت سرویس را بررسی کنید.');
  };

  const restoreBackup = async () => {
    if (!selectedFile) {
      setError('ابتدا فایل بکاپ را انتخاب کنید.');
      return;
    }
    if (confirmation.trim() !== 'RESTORE') {
      setError('برای تأیید، عبارت RESTORE را دقیق وارد کنید.');
      return;
    }
    const approved = window.confirm(
      'اطلاعات فعلی کاربران، نودها و تنظیمات با محتوای این بکاپ جایگزین می‌شود. ادامه می‌دهید؟',
    );
    if (!approved) return;

    setRestoring(true);
    setError('');
    setMessage('');
    setJob({ state: 'uploading', step: 'uploading', progress: 2, message: 'Uploading backup' });
    try {
      const form = new FormData();
      form.append('file', selectedFile);
      form.append('confirmation', confirmation.trim());
      const response = await apiClient.post('/backups/restore', form, {
        timeout: 300000,
      });
      const started = response.data?.data;
      if (!started?.job_id) throw new Error('شناسه عملیات بازیابی دریافت نشد.');
      setJob(started);
      await pollRestore(started.job_id);
      if (alive.current) {
        setSelectedFile(null);
        setConfirmation('');
      }
    } catch (exception) {
      if (alive.current) setError(errorText(exception));
    } finally {
      if (alive.current) setRestoring(false);
    }
  };

  const progress = Math.max(0, Math.min(100, Number(job?.progress || 0)));

  return (
    <section className="ov-backup-panel" aria-labelledby="ov-backup-title">
      <style>{`
        .ov-backup-panel {
          --backup-bg: linear-gradient(145deg, rgba(12,21,39,.96), rgba(9,18,34,.9));
          --backup-soft: rgba(15,23,42,.68);
          --backup-border: rgba(148,163,184,.16);
          --backup-text: #e5eefb;
          --backup-muted: #94a3b8;
          direction: rtl;
          margin-top: 22px;
          padding: 22px;
          color: var(--backup-text);
          border: 1px solid var(--backup-border);
          border-radius: 20px;
          background: var(--backup-bg);
          box-shadow: 0 14px 38px rgba(0,0,0,.15);
        }
        html[data-ov-theme="light"] .ov-backup-panel {
          --backup-bg: linear-gradient(145deg, rgba(255,255,255,.98), rgba(248,250,252,.98));
          --backup-soft: rgba(241,245,249,.9);
          --backup-border: rgba(148,163,184,.24);
          --backup-text: #0f172a;
          --backup-muted: #475569;
          box-shadow: 0 12px 30px rgba(15,23,42,.08);
        }
        .ov-backup-head, .ov-backup-title, .ov-backup-actions,
        .ov-backup-status-head, .ov-backup-file-actions {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .ov-backup-head { justify-content: space-between; margin-bottom: 18px; }
        .ov-backup-title h2 { margin: 0; font-size: 20px; }
        .ov-backup-title p { margin: 4px 0 0; color: var(--backup-muted); font-size: 12px; }
        .ov-backup-icon {
          width: 46px; height: 46px; display: grid; place-items: center;
          border-radius: 14px; color: #38bdf8; background: rgba(56,189,248,.12);
        }
        .ov-backup-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .ov-backup-card {
          padding: 18px; border: 1px solid var(--backup-border);
          border-radius: 17px; background: var(--backup-soft);
        }
        .ov-backup-card h3 { margin: 0 0 8px; font-size: 16px; }
        .ov-backup-card p { margin: 0 0 14px; color: var(--backup-muted); font-size: 12px; line-height: 1.8; }
        .ov-backup-button {
          display: inline-flex; align-items: center; justify-content: center; gap: 8px;
          min-height: 40px; padding: 9px 14px; color: #fff; font-weight: 750;
          border: 0; border-radius: 11px; cursor: pointer; background: #2563eb;
        }
        .ov-backup-button.secondary { background: #334155; }
        .ov-backup-button.danger { background: #dc2626; }
        .ov-backup-button:disabled { opacity: .55; cursor: not-allowed; }
        .ov-backup-input {
          width: 100%; min-height: 42px; margin-bottom: 10px; padding: 9px 11px;
          color: var(--backup-text); border: 1px solid var(--backup-border);
          border-radius: 10px; background: rgba(2,6,23,.18);
        }
        html[data-ov-theme="light"] .ov-backup-input { background: #fff; }
        .ov-backup-notice {
          display: flex; gap: 9px; padding: 11px; margin-top: 12px;
          color: #fbbf24; border: 1px solid rgba(245,158,11,.25);
          border-radius: 11px; background: rgba(245,158,11,.08); font-size: 12px;
        }
        .ov-backup-message, .ov-backup-error {
          margin: 14px 0 0; padding: 11px 13px; border-radius: 11px; font-size: 13px;
        }
        .ov-backup-message { color: #34d399; background: rgba(16,185,129,.1); }
        .ov-backup-error { color: #f87171; background: rgba(239,68,68,.1); }
        .ov-backup-status { margin-top: 14px; }
        .ov-backup-status-head { justify-content: space-between; font-size: 12px; color: var(--backup-muted); }
        .ov-backup-progress { height: 9px; margin-top: 8px; overflow: hidden; border-radius: 999px; background: rgba(148,163,184,.16); }
        .ov-backup-progress span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg,#22d3ee,#3b82f6); transition: width .3s ease; }
        .ov-backup-table-wrap { margin-top: 18px; overflow-x: auto; border: 1px solid var(--backup-border); border-radius: 15px; }
        .ov-backup-table { width: 100%; min-width: 650px; border-collapse: collapse; }
        .ov-backup-table th, .ov-backup-table td { padding: 12px 14px; text-align: right; border-bottom: 1px solid var(--backup-border); font-size: 12px; }
        .ov-backup-table tr:last-child td { border-bottom: 0; }
        .ov-backup-table th { color: var(--backup-muted); font-weight: 700; background: rgba(148,163,184,.05); }
        .ov-backup-ok { display: inline-flex; align-items: center; gap: 5px; color: #34d399; }
        .ov-backup-empty { padding: 20px; text-align: center; color: var(--backup-muted); }
        @media (max-width: 850px) {
          .ov-backup-grid { grid-template-columns: 1fr; }
          .ov-backup-head { align-items: flex-start; flex-direction: column; }
          .ov-backup-actions { width: 100%; }
          .ov-backup-actions .ov-backup-button { flex: 1; }
        }
      `}</style>

      <div className="ov-backup-head">
        <div className="ov-backup-title">
          <div className="ov-backup-icon"><FiDatabase size={23} /></div>
          <div>
            <h2 id="ov-backup-title">بکاپ و بازیابی دستی</h2>
            <p>مدیریت نسخه‌های پشتیبان PVNetwork Panel از صفحه اصلی</p>
          </div>
        </div>
        <div className="ov-backup-actions">
          <button
            type="button"
            className="ov-backup-button secondary"
            disabled={loading || creating || restoring}
            onClick={() => loadBackups()}
          >
            <FiRefreshCw /> بروزرسانی
          </button>
          <button
            type="button"
            className="ov-backup-button"
            disabled={creating || restoring}
            onClick={createBackup}
          >
            <FiArchive /> {creating ? 'در حال ساخت…' : 'ساخت بکاپ جدید'}
          </button>
        </div>
      </div>

      <div className="ov-backup-grid">
        <div className="ov-backup-card">
          <h3>دانلود بکاپ</h3>
          <p>بکاپ جدید ابتدا ساخته و آزمایش می‌شود؛ سپس از جدول پایین قابل دانلود است.</p>
          <div className="ov-backup-notice">
            <FiAlertTriangle size={18} />
            فایل دانلودی شامل اطلاعات کاربران و تنظیمات محرمانه پنل است.
          </div>
        </div>

        <div className="ov-backup-card">
          <h3>بازیابی از فایل</h3>
          <p>دیتابیس و تنظیمات به زمان بکاپ برمی‌گردند؛ نسخه برنامه و کدهای فعلی حفظ می‌شوند.</p>
          <input
            className="ov-backup-input"
            type="file"
            accept=".tar.gz,.tgz,application/gzip"
            disabled={restoring}
            onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
          />
          <input
            className="ov-backup-input"
            type="text"
            dir="ltr"
            autoComplete="off"
            placeholder="برای تأیید بنویسید: RESTORE"
            value={confirmation}
            disabled={restoring}
            onChange={(event) => setConfirmation(event.target.value)}
          />
          <button
            type="button"
            className="ov-backup-button danger"
            disabled={restoring || !selectedFile || confirmation.trim() !== 'RESTORE'}
            onClick={restoreBackup}
          >
            <FiUploadCloud /> {restoring ? 'در حال بازیابی…' : 'شروع بازیابی'}
          </button>

          {job && (
            <div className="ov-backup-status">
              <div className="ov-backup-status-head">
                <span>{job.message || job.step}</span>
                <strong>{progress}%</strong>
              </div>
              <div className="ov-backup-progress"><span style={{ width: `${progress}%` }} /></div>
            </div>
          )}
        </div>
      </div>

      {message && <div className="ov-backup-message">{message}</div>}
      {error && <div className="ov-backup-error">{error}</div>}

      <div className="ov-backup-table-wrap">
        {loading ? (
          <div className="ov-backup-empty">در حال دریافت فهرست بکاپ‌ها…</div>
        ) : backups.length === 0 ? (
          <div className="ov-backup-empty">هنوز بکاپ معتبری وجود ندارد.</div>
        ) : (
          <table className="ov-backup-table">
            <thead>
              <tr>
                <th>زمان ایجاد</th>
                <th>شناسه</th>
                <th>حجم کامل</th>
                <th>وضعیت</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {backups.map((backup) => (
                <tr key={backup.id}>
                  <td>{formatDate(backup.created_at)}</td>
                  <td dir="ltr">{backup.id}</td>
                  <td dir="ltr">{formatBytes(backup.size_bytes)}</td>
                  <td>
                    {backup.verified ? (
                      <span className="ov-backup-ok"><FiCheckCircle /> تأییدشده</span>
                    ) : (
                      <span className="ov-backup-error">نامعتبر</span>
                    )}
                  </td>
                  <td>
                    <div className="ov-backup-file-actions">
                      <button
                        type="button"
                        className="ov-backup-button secondary"
                        disabled={!backup.verified || downloading === backup.id || restoring}
                        onClick={() => downloadBackup(backup)}
                      >
                        <FiDownloadCloud />
                        {downloading === backup.id ? 'در حال دانلود…' : 'دانلود'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
