from contextlib import redirect_stdout
import json
import sys


def main():
    # Reserve stdout for the transport, including during heavy backend imports.
    with redirect_stdout(sys.stderr):
        from wildlocate.core.service import PredictionError, assess_habitat

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
