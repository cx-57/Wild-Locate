import io
import json

from src import prediction_worker, service


def test_worker_keeps_json_separate_from_backend_output(monkeypatch, capsys):
    requests = [
        {"species": "Fisher", "latitude": 42, "longitude": -71},
        {"species": "Coyote", "latitude": 42, "longitude": -71},
    ]
    calls = []
    def assess(*args):
        calls.append(args)
        print("Extraction progress belongs on stderr")
        # Transport marker, not a prediction.
        return {"features": {}}
    monkeypatch.setattr(service, "assess_habitat", assess)
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(json.dumps(item) for item in requests)))
    prediction_worker.main()
    output = capsys.readouterr()
    assert len(output.out.splitlines()) == 2
    assert all(json.loads(line) == {"result": {"features": {}}} for line in output.out.splitlines())
    assert "Extraction progress" in output.err
    assert calls == [("Fisher", 42, -71), ("Coyote", 42, -71)]


def test_worker_handles_errors_and_continues_reading(monkeypatch, capsys):
    def unavailable(*args):
        raise service.PredictionError("Choose another location.", "location_unavailable")
    monkeypatch.setattr(service, "assess_habitat", unavailable)
    request = json.dumps({"species": "Fisher", "latitude": 42, "longitude": -71})
    monkeypatch.setattr("sys.stdin", io.StringIO("invalid json\n" + request + "\n"))
    prediction_worker.main()
    responses = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert responses[0]["code"] == "worker_error"
    assert responses[1] == {"error": "Choose another location.", "code": "location_unavailable"}
