import pytest

from eil.analytics import compare_stations, load_rows, provisional_report, station_metrics


def test_dataset_and_known_anomaly():
    rows = load_rows()
    assert len(rows) > 100
    ranking = compare_stations(rows)
    assert len(ranking) == 4
    assert ranking[0]["station_id"] == "S03"
    assert ranking[0]["delta_percentage_points"] > 8
    assert ranking[0]["illumination_delta_lux"] < -100


def test_metrics_have_provenance_and_stable_denominator():
    value = station_metrics("S03", "incident")
    assert value["false_ejects"] <= value["inspected"]
    assert value["source_rows"]
    assert abs(value["false_eject_rate"] - value["false_ejects"] / value["inspected"]) < 0.000001


def test_reject_unexpected_station_and_period():
    with pytest.raises(ValueError):
        station_metrics("../../secrets", "baseline")
    with pytest.raises(ValueError):
        station_metrics("S01", "future")


def test_report_labels_hypothesis_as_uncertain():
    report = provisional_report()
    assert report["ranking"][0]["station_id"] == "S03"
    assert "not establish" in report["uncertainty"]


def test_explicit_path_cannot_bypass_dataset_allowlist(tmp_path):
    with pytest.raises(ValueError, match="allowlisted"):
        load_rows(tmp_path / "secrets.csv")


@pytest.mark.parametrize("name", ["../secrets.csv", "C:/Windows/win.ini"])
def test_configured_dataset_cannot_escape_data_directory(monkeypatch, name):
    monkeypatch.setattr("eil.analytics.DATASET_NAME", name)
    with pytest.raises(ValueError, match="allowlisted"):
        load_rows()
