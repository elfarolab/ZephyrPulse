import logging
import time
import unittest
from progress import stage, Progress


class ProgressTests(unittest.TestCase):
    def test_heartbeat_and_completion(self):
        with self.assertLogs(level=logging.INFO) as logs:
            with stage('fixture', interval=.01):
                time.sleep(.06)
        self.assertIn('fixture: started', logs.output[0])
        self.assertTrue(any('still running' in line for line in logs.output))
        self.assertIn('fixture: completed', logs.output[-1])

    def test_failed_stage_never_reports_success(self):
        with self.assertLogs(level=logging.INFO) as logs:
            with self.assertRaises(RuntimeError):
                with stage('fixture'):
                    raise RuntimeError('failure')
        self.assertIn('interrupted/failed', logs.output[-1])
        self.assertFalse(any('completed' in line for line in logs.output))

    def test_counts_and_debug(self):
        with self.assertLogs(level=logging.DEBUG) as logs:
            p=Progress('fixture',2)
            p.item(1,'abc'); p.done(1); p.done(2)
        self.assertTrue(any('starting 1/2 abc' in line for line in logs.output))
        self.assertTrue(any('2/2 processed (100.0%' in line for line in logs.output))
        with self.assertLogs(level=logging.INFO) as logs:
            Progress('empty',0)
        self.assertIn('0 items queued', logs.output[0])
