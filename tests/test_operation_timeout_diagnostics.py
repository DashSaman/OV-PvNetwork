import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class TimeoutDiagnosticTests(unittest.TestCase):
    def test_partial_output_is_saved_privately_without_echoing_sensitive_arguments(self):
        cases=[('pvnetwork_install','command','last-install-error.log'),('pvnetwork_lifecycle','run','last-lifecycle-error.log'),('pvnetwork_node_install','run','last-error.log')]
        for name,function,filename in cases:
            with self.subTest(operation=name),tempfile.TemporaryDirectory() as folder:
                spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                state=Path(folder)/'state'
                failure=subprocess.TimeoutExpired(['ci-tool','ci-sensitive-argument'],1,output=b'ci-partial-output',stderr=b'ci-private-timeout-detail')
                with patch.object(module,'STATE',state),patch.object(module.subprocess,'run',side_effect=failure):
                    with self.assertRaises((ValueError,RuntimeError)) as caught:
                        getattr(module,function)(['ci-tool','ci-sensitive-argument'],timeout=1)
                self.assertNotIn('ci-sensitive-argument',str(caught.exception))
                self.assertNotIn('ci-private-timeout-detail',str(caught.exception))
                log=state/filename;self.assertIn('ci-partial-output',log.read_text());self.assertIn('ci-private-timeout-detail',log.read_text())
                self.assertEqual(log.stat().st_mode&0o777,0o600)


if __name__=='__main__':unittest.main()
