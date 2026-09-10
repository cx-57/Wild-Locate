"""Private JSON-lines transport for the desktop app's isolated Python worker.

The desktop sends requests on stdin. Keeping this process alive allows the
existing extractor to reuse its cache; closing it cancels work safely without
terminating a Qt thread or changing the prediction calculation.
"""

from __future__ import annotations

from contextlib import redirect_stdout
import json
import sys


def main() -> None:
    # Reserve stdout for the transport, including during heavy backend imports.
    with redirect_stdout(sys.stderr):
        from src.service import PredictionError, assess_habitat

    for line in sys.stdin:
        try:
            request = json.loads(line)
            with redirect_stdout(sys.stderr):
                result = assess_habitat(request["species"], request["latitude"], request["longitude"])
            response = {"result": result}
        except PredictionError as exc:
            response = {"error": str(exc), "code": exc.code}
        except Exception:
            response = {"error": "The analysis request could not be completed. Please try again.", "code": "worker_error"}
        print(json.dumps(response, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
