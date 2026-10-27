import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reviewergap import dataset, providers, reviewer, metrics


def test_dataset_labels_are_consistent():
    sols = dataset.generate(n=120, seed=1)
    assert len(sols) == 120
    for s in sols:
        if s.is_flawed:
            assert s.error_type in dataset.ERROR_TYPES
            assert 1 <= s.error_step <= len(s.steps)
        else:
            assert s.error_type is None and s.error_step is None
    # roughly half flawed
    frac = sum(s.is_flawed for s in sols) / len(sols)
    assert 0.35 < frac < 0.65


def test_dataset_is_deterministic():
    a = dataset.generate(n=50, seed=42)
    b = dataset.generate(n=50, seed=42)
    assert [s.to_dict() for s in a] == [s.to_dict() for s in b]


def test_mock_reviewer_runs_and_parses():
    sols = dataset.generate(n=60, seed=3)
    prov = providers.build("mock")
    vs = reviewer.review_all(prov, sols)
    assert len(vs) == 60
    for v in vs:
        assert isinstance(v.flagged, bool)
        assert v.error_step >= 0


def test_parse_handles_messy_output():
    flagged, step = reviewer._parse('reasoning...\n{"verdict":"flawed","error_step":2,"explanation":"x"}')
    assert flagged and step == 2
    flagged, step = reviewer._parse("I think this is correct overall.")
    assert flagged is False


def test_metrics_in_range_and_detect_signal():
    sols = dataset.generate(n=200, seed=5)
    vs = reviewer.review_all(providers.build("mock:miss=0.1"), sols)
    m = metrics.score(vs, "mock")
    assert 0.0 <= m.detection_rate <= 1.0
    assert 0.0 <= m.false_positive_rate <= 1.0
    # a decent checker should beat chance on blatant arithmetic errors
    assert m.detection_rate > 0.3
    # and clean solutions should rarely be flagged
    assert m.false_positive_rate < 0.2


def test_correlation_shape():
    sols = dataset.generate(n=200, seed=9)
    a = reviewer.review_all(providers.build("mock:miss=0.2,seed=1"), sols)
    b = reviewer.review_all(providers.build("mock:miss=0.2,seed=2"), sols)
    c = metrics.correlation(a, b)
    assert c["n_flawed_shared"] > 0
    assert -1.0 <= c["miss_phi_correlation"] <= 1.0
    assert c["combined_detection_if_either_flags"] >= 0.0


def test_plausible_errors_are_hardest():
    """The headline finding: near-correct errors are caught least often."""
    sols = dataset.generate(n=600, seed=11)
    vs = reviewer.review_all(providers.build("mock"), sols)
    m = metrics.score(vs, "mock")
    bt = m.by_error_type
    if "plausible_but_off" in bt and "arithmetic_slip" in bt:
        assert bt["plausible_but_off"] <= bt["arithmetic_slip"] + 0.05
