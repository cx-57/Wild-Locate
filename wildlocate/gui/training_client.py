import json
from pathlib import Path
import sys

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from wildlocate.core.registry import cleanup_job
from wildlocate.core.training import new_job_id


class TrainingClient(QObject):
    event_received = pyqtSignal(dict)
    log = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        interpreter = Path(sys.executable)
        if interpreter.name.lower() == "pythonw.exe":
            interpreter = interpreter.with_name("python.exe")
        self.process.setProgram(str(interpreter))
        self.process.started.connect(self.send_pending)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_log)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.finished)
        self.busy = False
        self.job_id = None
        self._pending = None
        self._buffer = b""
        self._stopping = False

    def request(self, action, **payload):
        if self.busy:
            return
        self.busy = True
        self._pending = {"action": action, **payload}
        if self.process.state() == QProcess.ProcessState.NotRunning:
            self.job_id = new_job_id()
            self._buffer = b""
            self.process.setArguments(["-u", "-m", "wildlocate.core.training_worker", "--job-id", self.job_id])
            self.process.start()
        else:
            self.send_pending()

    def send_pending(self):
        if self._pending is not None:
            self.process.write((json.dumps(self._pending) + "\n").encode("utf-8"))
            self._pending = None

    def read_output(self):
        self._buffer += bytes(self.process.readAllStandardOutput())
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            if not line.strip() or self._stopping:
                continue
            try:
                event = json.loads(line)
                if event["event"] != "progress":
                    self.busy = False
                self.event_received.emit(event)
            except (ValueError, KeyError, TypeError):
                self.close()
                self.event_received.emit({"event": "error", "message": "Training returned an unreadable response. Please try again."})
                return

    def read_log(self):
        self.log.emit(bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace"))

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.busy = False
            self.event_received.emit({"event": "error", "message": "The training process could not start. Check the application installation."})

    def finished(self, *_):
        self.read_output()
        was_busy = self.busy
        self.busy = False
        self._pending = None
        if self.job_id:
            try:
                cleanup_job(self.job_id)
            except OSError as exc:
                self.log.emit(f"Temporary training data could not be removed: {exc}")
        if was_busy and not self._stopping:
            self.event_received.emit({"event": "error", "message": "Training stopped unexpectedly. Your enabled models are unchanged; try again."})

    def close(self):
        self._stopping = True
        self.busy = False
        self._pending = None
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(3000)
        self._buffer = b""
        self._stopping = False

    def cancel(self):
        self.close()
        self.event_received.emit({"event": "cancelled"})
