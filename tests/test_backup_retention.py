from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BackupRetentionTests(unittest.TestCase):
    """PVN-1020 — admin-configurable automatic backup retention."""

    def test_model_and_migration(self):
        models = (ROOT / 'backend' / 'db' / 'models.py').read_text(encoding='utf-8')
        self.assertIn('backup_retention_days', models)
        migration = (ROOT / 'backend' / 'alembic' / 'versions' / 'h0a1b2c3d4e5_backup_retention.py').read_text(encoding='utf-8')
        self.assertIn('backup_retention_days', migration)
        self.assertIn('down_revision = "g9a0b1c2d3e4"', migration)

    def test_backups_router_applies_retention(self):
        source = (ROOT / 'backend' / 'routers' / 'backups.py').read_text(encoding='utf-8')
        self.assertIn('def _apply_retention(db)', source)
        self.assertIn('timedelta(days=days)', source)
        self.assertIn('shutil.rmtree', source)
        # Runs after a successful manual backup and on list (scheduled path).
        self.assertGreaterEqual(source.count('_apply_retention(db)'), 2)
        # 0 disables cleanup.
        self.assertIn('if days <= 0:', source)

    def test_security_api_exposes_and_persists_retention(self):
        source = (ROOT / 'backend' / 'routers' / 'security.py').read_text(encoding='utf-8')
        self.assertIn("'backup_retention_days':int(getattr(r,'backup_retention_days',10) or 10)", source)
        self.assertIn('r.backup_retention_days=max(0,int(q.backup_retention_days))', source)
        self.assertIn('backup_retention_days:int=Field(10,ge=0,le=3650)', source)

    def test_backup_panel_has_retention_field(self):
        page = (ROOT / 'frontend' / 'src' / 'components' / 'BackupRestorePanel.jsx').read_text(encoding='utf-8')
        self.assertIn('retention-input', page)
        self.assertIn('saveRetention', page)
        page = page.replace(chr(39), chr(34))
        self.assertIn('put("/security/"', page)

    def test_retention_labels_translated(self):
        langs = ['en', 'fa', 'ar', 'es', 'id', 'ja', 'pt_BR', 'ru', 'tr', 'uk', 'vi', 'zh_CN', 'zh_TW']
        for lang in langs:
            catalog = json.loads((ROOT / 'frontend' / 'src' / 'lang' / f'{lang}.json').read_text(encoding='utf-8'))
            for key in ('backupRetentionLabel', 'backupRetentionHelp', 'backupRetentionSaved', 'backupRetentionFailed'):
                self.assertIn(key, catalog, f'{lang}:{key}')


class RealtimeRateWindowTests(unittest.TestCase):
    """PVN-1020 — rolling-window rates that match the 10s node refresh."""

    def test_rates_use_rolling_window(self):
        source = (ROOT / 'backend' / 'operations' / 'user_live_rates.py').read_text(encoding='utf-8')
        self.assertIn('MIN_WINDOW = 10.0', source)
        self.assertIn('_samples', source)
        self.assertIn('_reference_index', source)

    def test_sparkline_plots_upload_too(self):
        spark = (ROOT / 'frontend' / 'src' / 'components' / 'NodeSparkline.jsx').read_text(encoding='utf-8')
        self.assertIn('dataKey="down"', spark)
        self.assertIn('dataKey="up"', spark)

    def test_speed_cell_widths_are_fixed(self):
        css = (ROOT / 'frontend' / 'src' / 'components' / 'UserTable.css').read_text(encoding='utf-8')
        self.assertIn('width: 148px', css)
        self.assertIn('min-width: 62px', css)


if __name__ == '__main__':
    unittest.main()
