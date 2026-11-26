import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pulse import Git


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.PIPE, text=True).strip()


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root/'src'
        self.src.mkdir()
        git(self.src, 'init', '-b', 'main')
        git(self.src, 'config', 'user.email', 'test@example.com')
        git(self.src, 'config', 'user.name', 'Test')
        self.commit('first')
        git(self.src, 'tag', 'v1.0.0')
        self.repo = Git(self.root/'mirror.git')
        self.opts = {'attempts': 2, 'retry_delay_seconds': 0}

    def commit(self, msg):
        (self.src/'file').write_text(msg)
        git(self.src, 'add', 'file')
        git(self.src, 'commit', '-m', msg)
        return git(self.src, 'rev-parse', 'HEAD')

    def sync(self, seed=None):
        return self.repo.fetch(str(self.src), 'main', self.opts, seed)

    def test_initial_and_incremental(self):
        self.assertEqual(self.sync(), git(self.src, 'rev-parse','HEAD'))
        self.assertEqual(self.repo.git('tag').strip(), 'v1.0.0')
        head = self.commit('second')
        git(self.src, 'tag', 'v1.1.0')
        self.assertEqual(self.sync(), head)
        self.assertIn('v1.1.0', self.repo.git('tag'))
        self.assertEqual(self.repo.git('rev-parse','--is-shallow-repository').strip(), 'false')

    def test_retry_and_transport_settings(self):
        original = subprocess.run
        branch_calls = []
        def injected(cmd, *args, **kwargs):
            if 'fetch' in cmd and '+refs/heads/main:refs/heads/main' in cmd:
                branch_calls.append(cmd)
                if len(branch_calls) == 1:
                    raise subprocess.CalledProcessError(128, cmd)
            return original(cmd,*args,**kwargs)
        with patch('git_transport.subprocess.run', side_effect=injected):
            self.sync()
        self.assertEqual(len(branch_calls),2)
        self.assertIn('http.version=HTTP/1.1', branch_calls[0])
        self.assertIn('http.lowSpeedTime=120', branch_calls[0])

    def test_failed_tags_preserve_branch(self):
        original = subprocess.run
        def injected(cmd,*args,**kwargs):
            if 'fetch' in cmd and 'refs/tags/*:refs/tags/*' in cmd:
                raise subprocess.CalledProcessError(128,cmd)
            return original(cmd,*args,**kwargs)
        with patch('git_transport.subprocess.run',side_effect=injected):
            with self.assertRaises(subprocess.CalledProcessError): self.sync()
        self.assertEqual(self.repo.git('rev-parse','refs/heads/main').strip(),git(self.src,'rev-parse','HEAD'))
        self.assertEqual(self.sync(),git(self.src,'rev-parse','HEAD'))
        self.assertIn('v1.0.0',self.repo.git('tag'))

    def test_seed_and_upstream_update(self):
        seed = self.root/'seed'
        subprocess.run(['git','clone','--quiet',str(self.src),str(seed)],check=True)
        old = git(seed,'rev-parse','HEAD')
        new = self.commit('new upstream')
        self.assertEqual(self.sync(seed),new)
        self.assertEqual(git(seed,'rev-parse','HEAD'),old)
        self.assertEqual(self.repo.git('remote','get-url','origin').strip(),str(self.src))

    def test_invalid_repo_is_preserved(self):
        self.repo.path.mkdir()
        marker = self.repo.path/'important'
        marker.write_text('keep')
        with self.assertRaisesRegex(RuntimeError,'Invalid Git repository'):
            self.sync()
        self.assertEqual(marker.read_text(),'keep')

    def test_shallow_seed_rejected(self):
        seed = self.root/'shallow'
        self.commit('second')
        subprocess.run(['git','clone','--quiet','--depth','1',self.src.as_uri(),str(seed)],check=True)
        with self.assertRaisesRegex(ValueError,'shallow'):
            self.sync(seed)
