import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NodeToolArchiveTests(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('node_tool_installer',ROOT/'scripts/pvnetwork_install.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def archive(self,path,members):
        with tarfile.open(path,'w:xz') as tar:
            for name,value,link in members:
                info=tarfile.TarInfo(name);info.mode=0o755
                if link is not None:info.type=tarfile.SYMTYPE;info.linkname=link;tar.addfile(info)
                else:info.size=len(value);tar.addfile(info,io.BytesIO(value))

    def test_official_style_internal_links_are_staged_then_published(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);tools=root/'tools';tools.mkdir();archive=root/'node.tar.xz'
            self.archive(archive,[('node-ci/bin/node',b'ci-node',None),('node-ci/lib/npm/cli.js',b'ci-npm',None),('node-ci/bin/npm',b'','../lib/npm/cli.js')])
            module.extract_node_tool(archive,tools,'node-ci')
            self.assertEqual((tools/'node-ci/bin/npm').read_bytes(),b'ci-npm')
            self.assertEqual((tools/'node-ci/bin/node').stat().st_mode&0o777,0o755)

    def test_linked_parent_members_cannot_escape_staging(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);tools=root/'tools';tools.mkdir();archive=root/'node.tar.xz'
            self.archive(archive,[('node-ci/bin',b'','../lib'),('node-ci/bin/overwrite',b'ci-bad',None)])
            with self.assertRaisesRegex(ValueError,'link'):
                module.extract_node_tool(archive,tools,'node-ci')
            self.assertFalse((tools/'node-ci').exists())

    def test_traversal_duplicate_and_outside_links_refuse_before_publication(self):
        module=self.module()
        cases=[[('../escape',b'ci-bad',None)],[('node-ci/bin/node',b'ci-a',None),('node-ci/bin/node',b'ci-b',None)],[('node-ci/bin/npm',b'','../../../outside')]]
        for members in cases:
            with self.subTest(members=members),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);tools=root/'tools';tools.mkdir();archive=root/'node.tar.xz';self.archive(archive,members)
                with self.assertRaises(ValueError):module.extract_node_tool(archive,tools,'node-ci')
                self.assertFalse((tools/'node-ci').exists());self.assertFalse((root/'escape').exists())

    def test_existing_partial_tool_directory_is_preserved(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);tools=root/'tools';existing=tools/'node-ci';existing.mkdir(parents=True);(existing/'operator').write_bytes(b'ci-owned')
            archive=root/'node.tar.xz';self.archive(archive,[('node-ci/bin/node',b'ci-node',None)])
            with self.assertRaisesRegex(ValueError,'existing'):
                module.extract_node_tool(archive,tools,'node-ci')
            self.assertEqual((existing/'operator').read_bytes(),b'ci-owned')

    def test_health_probe_rejects_untrusted_schemes_and_credentials_before_access(self):
        from unittest.mock import patch
        module=self.module()
        for url in ['file:///etc/passwd','http://panel.example.com/healthz','https://ci-user:ci-value@panel.example.com/healthz','https:///healthz']:
            with self.subTest(url=url),patch.object(module.urllib.request,'urlopen') as open_url:
                with self.assertRaisesRegex(ValueError,'HTTPS'):
                    module.verify_http(url)
                open_url.assert_not_called()
