from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RenameFrontendContractTests(unittest.TestCase):
    def test_quick_edit_username_remains_readonly(self):
        text=(ROOT/'frontend/src/components/InlineUserQuickEdit.jsx').read_text()
        self.assertIn('quick-edit-username',text); self.assertIn('readOnly',text); self.assertIn('safe multi-node profile migration',text)

    def test_rename_modal_contains_required_safety_and_progress_contract(self):
        path=ROOT/'frontend/src/components/RenameUserModal.jsx'
        self.assertTrue(path.exists(),'RenameUserModal missing')
        text=path.read_text()
        for marker in ('new_username','/rename','preflight','staging','cutover','revoking_old','cleanup_pending','completed','renameOldProfilesWarning','renameSessionsWarning','setInterval','clearInterval'):
            self.assertIn(marker,text,marker)
        self.assertIn('1000',text)
        self.assertIn('acknowledged',text)
        self.assertNotIn('private_key',text)
        self.assertNotIn('profile_bytes',text)

    def test_table_has_rename_action_and_busy_state(self):
        text=(ROOT/'frontend/src/components/UserTable.jsx').read_text()
        self.assertIn('onRename',text); self.assertIn('busyUserUuids',text)
        self.assertIn("Rename Username",text)
        self.assertIn('renameBusy',text)
        self.assertIn('disabled:',text)

    def test_management_recovers_active_jobs_and_mounts_modal(self):
        text=(ROOT/'frontend/src/pages/UserManagement.jsx').read_text()
        self.assertIn("'/users/rename/active'",text)
        self.assertIn('busyRenameJobs',text)
        self.assertIn('RenameUserModal',text)
        self.assertIn('handleOpenRename',text)
        self.assertIn('onRename=',text)
        self.assertIn('busyUserUuids=',text)

    def test_modal_css_is_mobile_scroll_safe(self):
        text=(ROOT/'frontend/src/components/RenameUserModal.css').read_text()
        self.assertIn('max-height',text); self.assertIn('overflow-y',text); self.assertIn('@media',text)

    def test_english_and_persian_strings_exist(self):
        en=(ROOT/'frontend/src/lang/en.json').read_text(); fa=(ROOT/'frontend/src/lang/fa.json').read_text()
        for marker in ('renameUsername','renameOldProfilesWarning','renameSessionsWarning','renameCleanupPending'):
            self.assertIn(marker,en); self.assertIn(marker,fa)


if __name__=='__main__': unittest.main()
