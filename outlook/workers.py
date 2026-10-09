"""Background task runner bridging worker threads to Qt main thread."""

from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtCore import QObject, pyqtSignal

_executor = ThreadPoolExecutor(max_workers=8)
_tasks = set()


class Task(QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def _run(self):
        try:
            result = self.fn()
        except Exception as exc:  # noqa: BLE001 - surface any failure to UI
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.done.emit(result)
        finally:
            self.finished.emit()
            _tasks.discard(self)


def submit(fn, on_done=None, on_failed=None, on_finished=None) -> Task:
    task = Task(fn)
    if on_done is not None:
        task.done.connect(on_done)
    if on_failed is not None:
        task.failed.connect(on_failed)
    if on_finished is not None:
        task.finished.connect(on_finished)
    _tasks.add(task)
    _executor.submit(task._run)
    return task
