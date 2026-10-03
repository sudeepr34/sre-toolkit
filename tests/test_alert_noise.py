from sre_toolkit.alert_noise import detect_flapping, fingerprint, group_alerts, noise_report


def _alert(name, ts, state="firing", **labels):
    return {"name": name, "timestamp": ts, "state": state, "labels": labels}


def test_fingerprint_ignores_volatile_labels():
    a = _alert("HighCPU", "2026-10-04T10:00:00", alert_id="1", instance="web-1")
    b = _alert("HighCPU", "2026-10-04T10:05:00", alert_id="2", instance="web-1")
    assert fingerprint(a) == fingerprint(b)


def test_fingerprint_differs_on_stable_labels():
    a = _alert("HighCPU", "2026-10-04T10:00:00", instance="web-1")
    b = _alert("HighCPU", "2026-10-04T10:00:00", instance="web-2")
    assert fingerprint(a) != fingerprint(b)


def test_group_alerts_clusters_duplicates():
    alerts = [
        _alert("HighCPU", "2026-10-04T10:00:00", instance="web-1"),
        _alert("HighCPU", "2026-10-04T10:01:00", instance="web-1"),
        _alert("DiskFull", "2026-10-04T10:02:00", instance="db-1"),
    ]
    groups = group_alerts(alerts)
    assert len(groups) == 2
    assert groups[0].count == 2  # sorted by count desc
    assert groups[0].first_seen == "2026-10-04T10:00:00"


def test_detect_flapping():
    alerts = [
        _alert("Flap", "t1", state="firing", instance="x"),
        _alert("Flap", "t2", state="resolved", instance="x"),
        _alert("Flap", "t3", state="firing", instance="x"),
        _alert("Flap", "t4", state="resolved", instance="x"),
        _alert("Steady", "t1", state="firing", instance="y"),
        _alert("Steady", "t2", state="firing", instance="y"),
    ]
    flapping = detect_flapping(alerts, min_transitions=3)
    assert len(flapping) == 1
    assert "Flap" in flapping[0]


def test_noise_report_counts():
    alerts = [
        _alert("HighCPU", "t1", instance="web-1"),
        _alert("HighCPU", "t2", instance="web-1"),
        _alert("DiskFull", "t3", instance="db-1"),
    ]
    report = noise_report(alerts)
    assert report["total_alerts"] == 3
    assert report["unique_fingerprints"] == 2
    assert report["duplicates_suppressed"] == 1
