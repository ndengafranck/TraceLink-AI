"""Pure tests of the evidence engine: no database, no web server."""

from datetime import datetime, timedelta, timezone

from app.evidence import Point, evaluate, haversine_km

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
DOUALA = (4.0511, 9.7679)
YAOUNDE = (3.8480, 11.5021)


def ev(**kw):
    args = dict(
        observed_at=NOW - timedelta(minutes=5),
        lat=DOUALA[0],
        lon=DOUALA[1],
        accuracy_m=30.0,
        existing=[],
        now=NOW,
    )
    args.update(kw)
    return evaluate(**args)


def test_haversine_zero_and_known_distance():
    assert haversine_km(*DOUALA, *DOUALA) == 0
    assert 185 < haversine_km(*DOUALA, *YAOUNDE) < 200  # Douala to Yaounde, about 194 km


def test_fresh_good_sighting_is_accepted():
    v = ev()
    assert v.status == "accepted" and v.flags == () and v.reason is None


def test_future_timestamp_is_rejected():
    assert ev(observed_at=NOW + timedelta(minutes=10)).reason == "future_timestamp"


def test_small_clock_difference_is_tolerated():
    assert ev(observed_at=NOW + timedelta(minutes=1)).status == "accepted"


def test_older_than_seven_days_is_rejected():
    v = ev(observed_at=NOW - timedelta(days=8))
    assert v.status == "rejected" and v.reason == "too_old"


def test_older_than_a_day_is_flagged_stale():
    v = ev(observed_at=NOW - timedelta(hours=30))
    assert v.status == "flagged" and v.flags == ("stale",)


def test_sighting_from_before_the_report_is_normal():
    # A phone is lost first and reported later, so earlier sightings are expected.
    assert ev(observed_at=NOW - timedelta(hours=3)).status == "accepted"


def test_poor_accuracy_is_flagged():
    v = ev(accuracy_m=5000)
    assert v.status == "flagged" and v.flags == ("low_accuracy",)


def test_near_copy_is_rejected_as_duplicate():
    existing = [Point(NOW - timedelta(minutes=5), *DOUALA)]
    v = ev(observed_at=NOW - timedelta(minutes=4), existing=existing)
    assert v.status == "rejected" and v.reason == "duplicate"


def test_same_place_much_later_is_not_a_duplicate():
    existing = [Point(NOW - timedelta(minutes=30), *DOUALA)]
    assert ev(existing=existing).status == "accepted"


def test_impossible_speed_after_is_flagged():
    existing = [Point(NOW - timedelta(minutes=10), *DOUALA)]
    v = ev(observed_at=NOW - timedelta(minutes=8), lat=YAOUNDE[0], lon=YAOUNDE[1],
           existing=existing)
    assert v.status == "flagged" and "implausible_movement" in v.flags


def test_impossible_speed_compared_with_a_later_sighting_is_flagged():
    existing = [Point(NOW - timedelta(minutes=1), *YAOUNDE)]
    v = ev(observed_at=NOW - timedelta(minutes=3), existing=existing)
    assert v.status == "flagged" and "implausible_movement" in v.flags


def test_small_offset_at_the_same_instant_is_just_gps_noise():
    existing = [Point(NOW - timedelta(minutes=10), *DOUALA)]
    v = ev(observed_at=NOW - timedelta(minutes=10) + timedelta(seconds=130),
           lat=DOUALA[0] + 0.0010, lon=DOUALA[1], existing=existing)  # about 110 m
    assert v.status == "accepted"


def test_walking_pace_is_plausible():
    existing = [Point(NOW - timedelta(minutes=10), *DOUALA)]
    v = ev(observed_at=NOW - timedelta(minutes=1), lat=DOUALA[0] + 0.0009, lon=DOUALA[1],
           existing=existing)  # about 100 m in 9 minutes
    assert v.status == "accepted"


def test_several_problems_are_all_reported():
    existing = [Point(NOW - timedelta(minutes=10), *DOUALA)]
    v = ev(observed_at=NOW - timedelta(minutes=8), lat=YAOUNDE[0], lon=YAOUNDE[1],
           accuracy_m=5000, existing=existing)
    assert set(v.flags) == {"low_accuracy", "implausible_movement"}
