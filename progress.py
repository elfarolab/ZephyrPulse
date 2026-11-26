"""Console diagnostics independent of the collector and static renderer."""
import logging
import threading
import time
from contextlib import contextmanager


def elapsed(seconds):
    return f'{seconds:.1f}s' if seconds < 60 else f'{int(seconds)//60}m {int(seconds)%60:02d}s'


@contextmanager
def stage(name, interval=15):
    """Report wall-clock time, including when a subprocess is silent.

    A heartbeat confirms the Python process is alive, not that its child is making progress.
    """
    started = time.monotonic()
    stop = threading.Event()
    logging.info('%s: started', name)

    def heartbeat():
        while not stop.wait(interval):
            logging.info('%s: still running (%s elapsed)', name, elapsed(time.monotonic()-started))

    worker = threading.Thread(target=heartbeat, daemon=True)
    worker.start()
    try:
        yield
    except BaseException as exc:
        stop.set(); worker.join()
        logging.warning('%s: interrupted/failed after %s (%s)', name, elapsed(time.monotonic()-started), type(exc).__name__)
        raise
    else:
        stop.set(); worker.join()
        logging.info('%s: completed in %s', name, elapsed(time.monotonic()-started))
    finally:
        stop.set(); worker.join()


class Progress:
    """Throttled item counters; count an item only when its work has finished."""
    def __init__(self, label, total, interval=10):
        self.label, self.total, self.interval = label, total, interval
        self.started = self.last = time.monotonic()
        logging.info('%s: %d items queued', label, total)

    def item(self, index, detail=''):
        logging.debug('%s: starting %d/%d %s', self.label, index, self.total, detail)

    def done(self, count):
        now = time.monotonic()
        if count == 1 or count == self.total or now-self.last >= self.interval:
            logging.info('%s: %d/%d processed (%.1f%%, %s elapsed)', self.label, count, self.total, 100*count/self.total, elapsed(now-self.started))
            self.last = now
