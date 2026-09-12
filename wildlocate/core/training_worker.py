"""JSON-lines commands and events for the isolated desktop training process."""

import argparse
from contextlib import redirect_stdout
import json
import sys
import traceback

from requests.exceptions import RequestException

from wildlocate.core.training import TrainingSession
from wildlocate.core.registry import cleanup_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--region", default="MA")
    args = parser.parse_args()
    output = sys.stdout

    def emit(event, **payload):
        output.write(json.dumps({"event": event, **payload}, allow_nan=False) + "\n")
        output.flush()

    session = TrainingSession(args.job_id, lambda message: emit("progress", message=message), region=args.region)
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                with redirect_stdout(sys.stderr):
                    if request["action"] == "resolve":
                        result = session.resolve(request["query"])
                        event = "resolved"
                    elif request["action"] == "prepare":
                        result = session.prepare()
                        event = "prepared"
                    elif request["action"] == "train":
                        result = session.train()
                        event = "completed"
                    elif request["action"] == "initialize":
                        result, event = session.initialize_environment(), "initialized"
                    else:
                        raise ValueError("Unknown training action.")
                emit(event, **result)
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                missing = isinstance(exc, FileNotFoundError) and "Missing required raw environmental datasets" in str(exc)
                if missing:
                    message = "Environmental datasets are missing. Download them below, then check the species data again."
                elif isinstance(exc, RequestException):
                    message = "Data could not be downloaded. Check your internet connection and try again. See Training details for the server response."
                else:
                    message = str(exc)
                emit("error", message=message, code="missing_environment" if missing else "training_failed")
    finally:
        cleanup_job(args.job_id)


if __name__ == "__main__":
    main()
