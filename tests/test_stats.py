from voice.stats import percentile


def test_percentile_uses_nearest_rank():
    values = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    assert percentile(values, 50) == 500
    assert percentile(values, 95) == 1000


def test_percentile_of_empty_list_is_none():
    assert percentile([], 50) is None