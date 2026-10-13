import types
import unittest
from unittest.mock import Mock,patch


class BackupRetentionRuntimeTests(unittest.TestCase):
    def test_retention_loads_real_settings_model_without_runtime_name_error(self):
        from backend.routers import backups
        db=Mock();db.query.return_value.filter_by.return_value.first.return_value=types.SimpleNamespace(backup_retention_days=14)
        with patch.object(backups,'_list_backup_directories',return_value=[]):
            self.assertEqual(backups._apply_retention(db),0)
