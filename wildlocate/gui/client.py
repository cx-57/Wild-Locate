import json
from pathlib import Path
import sys

from PyQt6.QtCore import QObject, QProcess, pyqtSignal


class PredictionClient(QObject):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        interpreter = Path(sys.executable)
        # A .pyw launch uses pythonw, whose standard streams may be absent.
        # QProcess supplies pipes to the console interpreter without requiring
        # a terminal window; use the sibling from the same virtual environment.
        if interpreter.name.lower() == "pythonw.exe":
            interpreter = interpreter.with_name("python.exe")
        self.process.setProgram(str(interpreter))
        self.process.setArguments(["-u", "-m", "wildlocate.core.prediction_worker"])
        self.process.started.connect(self.send_pending)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.finished)
        self.busy = False
        self._buffer = b""
        self._pending = None

    def analyze(self, species, latitude, longitude):
        if self.busy:
            return
        self.busy = True
        self._pending = {"species": species, "latitude": latitude, "longitude": longitude}
        self._buffer = b""
        if self.process.state() == QProcess.ProcessState.NotRunning:
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
            if not self.busy or not line.strip():
                continue
            self.busy = False
            try:
                response = json.loads(line)
                if "error" in response:
                    self.failed.emit(response["error"])
                else:
                    self.succeeded.emit(response["result"])
            except (ValueError, KeyError, TypeError):
                self.failed.emit("The analysis returned an unreadable response. Please try again.")

    def read_error(self):
        self.process.readAllStandardError()

    def process_error(self, error):
        if self.busy and error == QProcess.ProcessError.FailedToStart:
            self.busy = False
            self._pending = None
            self.failed.emit("The Python analysis process could not start. Ensure wild-locate is installed in your active environment.")

    def finished(self, exit_code, exit_status):
        if self.busy:
            self.busy = False
            self._pending = None
            self.failed.emit("The analysis process stopped unexpectedly. Check the project dependencies and data, then try again.")

    def cancel(self):
        self.close()
        self.cancelled.emit()

    def close(self):
        self.busy = False
        self._pending = None
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
