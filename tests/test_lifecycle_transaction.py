import importlib.util
from pathlib import Path
import tempfile
import unittest
import socket
import sys
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]


class LifecycleTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('pvnetwork_lifecycle_tx',ROOT/'scripts/pvnetwork_lifecycle.py')
        cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)

    def test_failed_build_never_switches_active_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old';old.mkdir();pointer=root/'panel';pointer.symlink_to(old,target_is_directory=True)
            candidate=root/'new';candidate.mkdir()
            def build():raise RuntimeError('build failure')
            with self.assertRaises(RuntimeError):self.module.commit_release(pointer,candidate,build,lambda:None,lambda:None)
            self.assertEqual(pointer.resolve(),old)

    def test_failed_post_switch_health_restores_previous_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old';old.mkdir();pointer=root/'panel';pointer.symlink_to(old,target_is_directory=True)
            new=root/'new';new.mkdir();events=[]
            def verify():
                if pointer.resolve()==new:raise RuntimeError('bad health')
                events.append('recovery verified')
            with self.assertRaises(RuntimeError):self.module.commit_release(pointer,new,lambda:None,lambda:events.append('restart'),verify)
            self.assertEqual(pointer.resolve(),old)
            self.assertEqual(events,['restart','restart','recovery verified'])

    def test_success_switches_only_after_build_and_preflight(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'old';old.mkdir();pointer=root/'panel';pointer.symlink_to(old,target_is_directory=True)
            new=root/'new';new.mkdir();events=[]
            def build():self.assertEqual(pointer.resolve(),old);events.append('prepared')
            def verify():self.assertEqual(pointer.resolve(),new);events.append('verified')
            self.module.commit_release(pointer,new,build,lambda:events.append('restart'),verify)
            self.assertEqual(events,['prepared','restart','verified'])

    @unittest.skipUnless(sys.platform=='linux','real Linux canary socket reuse regression')
    def test_canary_retry_accepts_closed_socket_time_wait(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1];listener.listen()
            with socket.create_connection(('127.0.0.1',port),timeout=2) as client:
                accepted,_=listener.accept();accepted.close()
                self.assertEqual(client.recv(1),b'')
        # Reproduce the old inline bind: a dead canary is still in TIME_WAIT.
        with socket.socket() as old_probe,self.assertRaises(OSError):old_probe.bind(('127.0.0.1',port))
        self.module.canary_port_available(port)

    @unittest.skipUnless(sys.platform=='linux','real Linux canary socket reuse regression')
    def test_canary_retry_still_refuses_an_actual_listener(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1];listener.listen()
            with self.assertRaises(OSError):self.module.canary_port_available(port)
