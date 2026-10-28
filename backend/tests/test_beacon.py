from datetime import datetime, timedelta, timezone

from app.beacon import WINDOW_SECONDS, beacon_id, matches, window_of

SECRET = bytes(range(32))


def test_known_vector_for_the_android_app():
    # The Android app must produce exactly these values (HMAC-SHA256, first 8 bytes, hex).
    assert beacon_id(SECRET, 1000) == "49fddab5e57da4b6"
    assert beacon_id(SECRET, 1001) == "89ea7a65868fb23c"


def test_id_changes_every_window_and_depends_on_secret():
    assert beacon_id(SECRET, 5) != beacon_id(SECRET, 6)
    assert beacon_id(SECRET, 5) != beacon_id(bytes(32), 5)


def test_window_boundaries():
    t = datetime.fromtimestamp(WINDOW_SECONDS * 7, tz=timezone.utc)
    assert window_of(t) == 7 and window_of(t - timedelta(seconds=1)) == 6


def test_neighbouring_windows_match_but_not_further():
    t = datetime.fromtimestamp(WINDOW_SECONDS * 100 + 10, tz=timezone.utc)
    for w in (99, 100, 101):
        assert matches(SECRET, beacon_id(SECRET, w), t)
    for w in (98, 102):
        assert not matches(SECRET, beacon_id(SECRET, w), t)
    assert not matches(SECRET, "0" * 16, t)
