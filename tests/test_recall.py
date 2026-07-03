from jd_query_graph.recall import FakeRecallProvider


def test_fake_recall_provider_returns_stable_observation() -> None:
    provider = FakeRecallProvider({"term-alpha": 42})

    observation = provider.count("term-alpha")

    assert observation.provider == "fake-cts"
    assert observation.query_text == "term-alpha"
    assert observation.query_mode == "exact"
    assert observation.total == 42
    assert observation.status == "ok"
    assert observation.probe_run_id == "fake-probe-run"
    assert observation.request_hash
