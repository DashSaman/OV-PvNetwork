import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lifecycle_download',ROOT/'scripts/pvnetwork_lifecycle.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class LifecycleDownloadTests(unittest.TestCase):
    def test_download_uses_exact_published_asset_and_verifies_content(self):
        value=b'fixture archive';digest=hashlib.sha256(value).hexdigest();asset='pvnetwork-panel-v1.0.42.tar.gz'
        with tempfile.TemporaryDirectory() as folder,mock.patch.object(module.urllib.request,'urlopen',side_effect=[io.BytesIO((digest+'  '+asset).encode()),io.BytesIO(value)]) as fetch:
            archive,checksum=module.download_published_release('1.0.42',folder)
            self.assertEqual(archive.read_bytes(),value);self.assertEqual(checksum,digest)
            self.assertEqual(fetch.call_args_list[1].args[0],'https://github.com/DashSaman/OV-PvNetwork/releases/download/v1.0.42/'+asset)

    def test_wrong_filename_checksum_is_refused_before_archive_download(self):
        with tempfile.TemporaryDirectory() as folder,mock.patch.object(module.urllib.request,'urlopen',return_value=io.BytesIO(('a'*64+'  ../foreign').encode())) as fetch:
            with self.assertRaisesRegex(ValueError,'exact immutable asset'):module.download_published_release('1.0.42',folder)
            self.assertEqual(fetch.call_count,1);self.assertEqual(list(Path(folder).iterdir()),[])

    def test_wrong_content_never_leaves_an_installable_archive(self):
        with tempfile.TemporaryDirectory() as folder,mock.patch.object(module.urllib.request,'urlopen',side_effect=[io.BytesIO(('a'*64+'  pvnetwork-panel-v1.0.42.tar.gz').encode()),io.BytesIO(b'wrong')]):
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):module.download_published_release('1.0.42',folder)
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_branch_name_is_not_a_release_selector(self):
        with self.assertRaisesRegex(ValueError,'immutable'):module.published_version('main')
