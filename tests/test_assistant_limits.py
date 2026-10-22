from datetime import date, timedelta

from invest_intel.assistant.limits import DailyCounter, code_matches


def test_counter_refuses_after_the_limit_and_resets_the_next_day():
    day = [date(2026, 10, 22)]
    counter = DailyCounter(2, today=lambda: day[0])
    assert counter.try_acquire() and counter.try_acquire()
    assert not counter.try_acquire()
    day[0] += timedelta(days=1)
    assert counter.try_acquire()


def test_no_limit_means_unlimited():
    counter = DailyCounter(None)
    assert all(counter.try_acquire() for _ in range(1000))


def test_code_matches_ignores_whitespace_only():
    assert code_matches(" open-sesame\n", "open-sesame")
    assert not code_matches("open-sesam", "open-sesame")
    assert not code_matches("", "open-sesame")
