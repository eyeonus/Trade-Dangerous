"""
Comprehensive unit tests for tradedangerous.db.utils functions.

Tests cover:
  - parse_ts: diverse timestamp format parsing into UTC-naive datetimes
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import pytest
import typing

from . import utils

if typing.TYPE_CHECKING:
    from typing import Any


# Far future epoch value: approximately year 10000 in Unix epoch seconds
# This value exceeds the valid range for datetime.fromtimestamp() on many
# systems and is used to test out-of-range epoch handling
FAR_FUTURE_EPOCH = 253402300800


class TestParseTs:
    """Comprehensive tests for parse_ts() function."""

    # Basic test of each type, ensuring it discriminates

    def test_parse_ts_none_returns_none(self) -> None:
        """parse_ts(None) should return None."""
        result: datetime | None = utils.parse_ts(None)
        assert result is None

    def test_parse_ts_naive_datetime_with_microseconds_clears_microseconds(self) -> None:
        """parse_ts with naive datetime should clear microseconds."""
        dt = datetime(2025, 1, 15, 10, 30, 45, 123456)
        result: datetime | None = utils.parse_ts(dt)
        
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 45
        assert result.microsecond == 0

    def test_parse_ts_aware_datetime_utc_converts_to_naive(self) -> None:
        """parse_ts with UTC-aware datetime should convert to naive."""
        dt = datetime(2025, 1, 15, 10, 30, 45, 123456, tzinfo=timezone.utc)
        result: datetime | None = utils.parse_ts(dt)
        
        assert result is not None
        assert result.tzinfo is None
        assert result.microsecond == 0
        assert result == datetime(2025, 1, 15, 10, 30, 45)

    def test_parse_ts_aware_datetime_with_est_offset_converts_to_utc_naive(self) -> None:
        """parse_ts with EST (-05:00) datetime should convert to UTC then naive."""
        # EST is UTC-5, so 10:30 EST = 15:30 UTC
        est = timezone(timedelta(hours=-5))
        dt = datetime(2025, 1, 15, 10, 30, 45, 123456, tzinfo=est)
        result: datetime | None = utils.parse_ts(dt)
        
        assert result is not None
        assert result.tzinfo is None
        assert result.hour == 15  # 10 + 5 hours
        assert result.microsecond == 0

    def test_parse_ts_aware_datetime_with_positive_offset_converts_to_utc_naive(self) -> None:
        """parse_ts with UTC+05:30 (IST) datetime should convert to UTC then naive."""
        # IST is UTC+5:30, so 10:30 IST = 05:00 UTC
        ist = timezone(timedelta(hours=5, minutes=30))
        dt = datetime(2025, 1, 15, 10, 30, 45, tzinfo=ist)
        result: datetime | None = utils.parse_ts(dt)
        
        assert result is not None
        assert result.tzinfo is None
        assert result.hour == 5  # 10 - 5 = 5
        assert result.minute == 0  # 30 - 30 = 0

    @pytest.mark.parametrize("epoch,expected_dt", [
        (0, datetime(1970, 1, 1, 0, 0, 0)),  # epoch start
        (1, datetime(1970, 1, 1, 0, 0, 1)),  # epoch + 1 second
        (1*60*60 + 1*60 + 7, datetime(1970, 1, 1, 1, 1, 7)),  # epoch + 1 hour, 1 minute, and 7 seconds
        (24 * 60 * 60 + 3, datetime(1970, 1, 2, 0, 0, 3)),  # 1 day and 3 seconds
        (86400, datetime(1970, 1, 2, 0, 0, 0)),
    ])
    def test_parse_ts_integer_epoch_converts_to_datetime(self, epoch: int, expected_dt: datetime) -> None:
        """parse_ts with integer epoch seconds should convert to datetime."""
        result: datetime | None = utils.parse_ts(epoch)
        
        assert result is not None, f"Failed to parse epoch {epoch}"
        assert result == expected_dt, f"Expected {expected_dt}, got {result} for epoch {epoch}"
        assert result.microsecond == 0

    @pytest.mark.parametrize("epoch,expected_dt", [
        (0.0, datetime(1970, 1, 1, 0, 0, 0)),  # epoch start
        (7200.001, datetime(1970, 1, 1, 2, 0, 0)),  # epoch + 2 hours and some milliseconds
        (86400.5, datetime(1970, 1, 2, 0, 0, 0)),  # 1 day + 0.5 seconds
    ])
    def test_parse_ts_float_epoch_converts_to_datetime(self, epoch: float, expected_dt: datetime) -> None:
        """parse_ts with float epoch seconds should convert to datetime (microseconds zeroed)."""
        result: datetime | None = utils.parse_ts(epoch)
        
        assert result is not None, f"Failed to parse epoch {epoch}"
        assert result == expected_dt, f"Expected {expected_dt}, got {result} for epoch {epoch}"
        assert result.microsecond == 0

    @pytest.mark.parametrize("invalid_epoch", [
        float('inf'),
        float('-inf'),
        float('nan'),
    ])
    def test_parse_ts_invalid_epoch_returns_none(self, invalid_epoch: float) -> None:
        """parse_ts with invalid epoch (inf, nan) should return None."""
        result: datetime | None = utils.parse_ts(invalid_epoch)
        assert result is None, f"Expected None for invalid epoch {invalid_epoch}, got {result}"

    def test_parse_ts_out_of_range_epoch_returns_none(self) -> None:
        """parse_ts with epoch out of valid range should return None."""
        result = utils.parse_ts(FAR_FUTURE_EPOCH)
        assert result is None, f"Expected None for out-of-range epoch {FAR_FUTURE_EPOCH}, got {result}"

    @pytest.mark.parametrize("invalid_value", (  # type: ignore[reportUnknownArgumentType]
        object,
        object(),
        True,
        False,
        b'1970-01-01T00:00:00',
        timezone,
        timezone(timedelta(hours=1)),
    ))
    def test_parse_ts_invalid_type_returns_none(self, invalid_value: Any) -> None:
        """parse_ts with other types should return None."""
        result: datetime | None = utils.parse_ts(invalid_value)
        assert result is None, f"Expected None for unexpected types: {invalid_value!r}"

    # String Parsing: Basic Formats

    def test_parse_ts_iso_basic_format(self) -> None:
        """parse_ts('2026-01-15T10:30:45') should parse ISO format."""
        result: datetime | None = utils.parse_ts("2026-01-15T10:30:45")
        
        assert result is not None
        assert result == datetime(2026, 1, 15, 10, 30, 45)
        assert result.microsecond == 0

    def test_parse_ts_iso_with_fractional_seconds(self) -> None:
        """parse_ts with fractional seconds should discard them (microsecond=0)."""
        result: datetime | None = utils.parse_ts("2026-01-15T10:30:45.123456")
        
        assert result is not None
        assert result == datetime(2026, 1, 15, 10, 30, 45)
        assert result.microsecond == 0

    def test_parse_ts_iso_with_partial_fractional_seconds(self) -> None:
        """parse_ts with partial fractional seconds (.567) should discard them."""
        result: datetime | None = utils.parse_ts("2026-01-15T10:30:45.567")
        
        assert result is not None
        assert result == datetime(2026, 1, 15, 10, 30, 45)
        assert result.microsecond == 0

    def test_parse_ts_date_only_format(self) -> None:
        """parse_ts('2026-01-15') should parse date-only format."""
        result: datetime | None = utils.parse_ts("2026-01-15")
        
        assert result is not None
        assert result == datetime(2026, 1, 15, 0, 0, 0)

    def test_parse_ts_legacy_space_separated_datetime(self) -> None:
        """parse_ts('2026-01-15 10:30:45') should parse space-separated format."""
        result: datetime | None = utils.parse_ts("2026-01-15 10:30:45")
        
        assert result is not None
        assert result == datetime(2026, 1, 15, 10, 30, 45)

    # String Parsing: Timezone Handling

    @pytest.mark.parametrize("input_str,expected_hour,expected_minute", [
        ("2026-01-15T10:30:45Z", 10, 30),  # uppercase Z
        ("2026-01-15T10:30:45z", 10, 30),  # lowercase z
        ("2026-01-15T10:30:45+05:30", 5, 0),  # positive HH:MM
        ("2026-01-15T10:30:45-08:00", 18, 30),  # negative HH:MM
        ("2026-01-15T10:30:45+0530", 5, 0),  # positive HHMM no colon
        ("2026-01-15T10:30:45-0530", 16, 0),  # negative HHMM no colon
        ("2026-01-15T10:30:45+05", 5, 30),  # positive HH only
        ("2026-01-15T10:30:45-05", 15, 30),  # negative HH only
        ("2026-01-15T10:30:45 +05:30", 5, 0),  # space before positive offset
        ("2026-01-15T10:30:45 -05:30", 16, 0),  # space before negative offset
    ], ids=[
        "uppercase-Z",
        "lowercase-z",
        "positive-HH:MM",
        "negative-HH:MM",
        "positive-HHMM-no-colon",
        "negative-HHMM-no-colon",
        "positive-HH-only",
        "negative-HH-only",
        "space-before-positive",
        "space-before-negative",
    ])
    def test_parse_ts_timezone_offset_formats(self, input_str: str, expected_hour: int, expected_minute: int) -> None:
        """Parametrized test for various timezone offset format parsing."""
        result: datetime | None = utils.parse_ts(input_str)
        
        assert result is not None, f"Failed to parse {input_str}"
        assert result.hour == expected_hour, \
            f"Expected hour {expected_hour}, got {result.hour} for input {input_str}"
        assert result.minute == expected_minute, \
            f"Expected minute {expected_minute}, got {result.minute} for input {input_str}"
        assert result.tzinfo is None, f"Result should be naive, got tzinfo={result.tzinfo}"

    # String Parsing: Normalization

    def test_parse_ts_z_converted_to_plus_00_00(self) -> None:
        """parse_ts should convert 'Z' to '+00:00' internally (verified by result)."""
        result_z: datetime | None = utils.parse_ts("2026-01-15T10:30:45Z")
        result_plus: datetime | None = utils.parse_ts("2026-01-15T10:30:45+00:00")

        assert result_z is not None
        assert result_z == result_plus

    def test_parse_ts_hhmm_normalized_to_hh_mm(self) -> None:
        """parse_ts should normalize +HHMM to +HH:MM format."""
        result_no_colon: datetime | None = utils.parse_ts("2026-01-15T10:30:45+0530")
        result_colon: datetime | None = utils.parse_ts("2026-01-15T10:30:45+05:30")
        
        assert result_no_colon == result_colon

    def test_parse_ts_space_to_t_conversion(self) -> None:
        """parse_ts should convert first space between date/time to 'T'."""
        result = utils.parse_ts("2026-01-15 10:30:45")
        assert result is not None
        expected: datetime | None = utils.parse_ts("2026-01-15T10:30:45")
        
        assert result == expected

    # Edge Cases

    def test_parse_ts_empty_string_returns_none(self) -> None:
        """parse_ts('') should return None."""
        result: datetime | None = utils.parse_ts("")
        assert result is None

    def test_parse_ts_whitespace_only_string_returns_none(self) -> None:
        """parse_ts('   ') should return None."""
        result: datetime | None = utils.parse_ts("   ")
        assert result is None

    def test_parse_ts_invalid_format_returns_none(self) -> None:
        """parse_ts with invalid format should return None (no exception)."""
        result: datetime | None = utils.parse_ts("not a date")
        assert result is None

    def test_parse_ts_invalid_format_garbage_returns_none(self) -> None:
        """parse_ts with garbage input should return None."""
        result: datetime | None = utils.parse_ts("!!!@@@###")
        assert result is None

    def test_parse_ts_out_of_range_date_feb_30_returns_none(self) -> None:
        """parse_ts('2026-02-30') should return None (invalid date)."""
        result: datetime | None = utils.parse_ts("2026-02-30")
        assert result is None

    def test_parse_ts_leap_year_feb_29(self) -> None:
        """parse_ts('2024-02-29') should parse (leap year)."""
        result: datetime | None = utils.parse_ts("2024-02-29")
        
        assert result is not None
        assert result == datetime(2024, 2, 29, 0, 0, 0)

    def test_parse_ts_non_leap_year_feb_29_returns_none(self) -> None:
        """parse_ts('2023-02-29') should return None (not a leap year)."""
        result: datetime | None = utils.parse_ts("2023-02-29")
        assert result is None

    def test_parse_ts_epoch_start(self) -> None:
        """parse_ts epoch 0 should yield 1970-01-01."""
        result: datetime | None = utils.parse_ts(0)
        assert result == datetime(1970, 1, 1, 0, 0, 0)

    def test_parse_ts_negative_epoch_before_1970(self) -> None:
        """parse_ts with negative epoch (before 1970) may fail on some systems."""
        result: datetime | None = utils.parse_ts(-86400)  # 1 day before epoch
        
        # Negative epochs are not reliably supported on all systems/OSes
        # Windows in particular may not support dates before 1970
        # So we just verify that if it works, it's a datetime
        if result is not None:
            assert isinstance(result, datetime)

    def test_parse_ts_far_future_year_9999(self) -> None:
        """parse_ts('9999-12-31') should parse far future dates."""
        result: datetime | None = utils.parse_ts("9999-12-31")
        
        assert result is not None
        assert result.year == 9999
        assert result.month == 12
        assert result.day == 31

    def test_parse_ts_year_1900_boundary(self) -> None:
        """parse_ts('1900-01-01') should parse historical dates."""
        result: datetime | None = utils.parse_ts("1900-01-01")
        
        assert result is not None
        assert result.year == 1900
        assert result.month == 1
        assert result.day == 1

    # Timezone Arithmetic Verification

    def test_parse_ts_utc_plus_5_from_10_00_yields_05_00_utc(self) -> None:
        """Verify UTC+05:00 input '10:00' yields UTC '05:00'."""
        result: datetime | None = utils.parse_ts("2026-01-15T10:00:00+05:00")

        assert result is not None
        assert result.hour == 5, f"Expected hour 5, got {result.hour}"
        assert result.minute == 0, f"Expected minute 0, got {result.minute}"

    def test_parse_ts_utc_minus_8_from_10_00_yields_18_00_utc(self) -> None:
        """Verify UTC-08:00 input '10:00' yields UTC '18:00'."""
        result: datetime | None = utils.parse_ts("2026-01-15T10:00:00-08:00")
        
        assert result is not None
        assert result.hour == 18, f"Expected hour 18, got {result.hour}"
        assert result.minute == 0, f"Expected minute 0, got {result.minute}"

    def test_parse_ts_utc_z_from_10_00_yields_10_00_utc(self) -> None:
        """Verify UTC+00:00 (Z) input '10:00' yields UTC '10:00'."""
        result: datetime | None = utils.parse_ts("2026-01-15T10:00:00Z")
        
        assert result is not None
        assert result.hour == 10, f"Expected hour 10, got {result.hour}"
        assert result.minute == 0, f"Expected minute 0, got {result.minute}"

    # Error Handling & Graceful Degradation

    def test_parse_ts_does_not_raise_on_invalid_input(self) -> None:
        """parse_ts should not raise exceptions for invalid input, return None instead."""
        # These should all return None without raising
        assert utils.parse_ts("invalid@#$%") is None, "Expected None for invalid characters"
        assert utils.parse_ts("2025-13-45") is None, "Expected None for invalid month/day"
        assert utils.parse_ts("not a timestamp") is None, "Expected None for non-timestamp string"


# PARAMETRIZED TESTS: Comprehensive coverage with multiple inputs

class TestParseTs_Parametrized:
    """Parametrized tests for comprehensive edge case coverage."""

    @pytest.mark.parametrize("input_str,expected_hour,expected_minute", [
        ("2026-01-15T12:00:00+00:00", 12, 0),
        ("2026-01-15T12:00:00+01:00", 11, 0),
        ("2026-01-15T12:00:00-01:00", 13, 0),
        ("2026-01-15T12:00:00+05:30", 6, 30),
        ("2026-01-15T12:00:00-05:30", 17, 30),
    ])
    def test_parse_ts_various_offsets(self, input_str: str, expected_hour: int, expected_minute: int) -> None:
        """Parametrized test for various UTC offset conversions."""
        result: datetime | None = utils.parse_ts(input_str)
        
        assert result is not None, f"Failed to parse {input_str}"
        assert result.hour == expected_hour, \
            f"Expected hour {expected_hour}, got {result.hour} for {input_str}"
        assert result.minute == expected_minute, \
            f"Expected minute {expected_minute}, got {result.minute} for {input_str}"

    @pytest.mark.parametrize("input_val,should_succeed", [
        ("2026-01-15",                True),
        ("2026-01-15T10:30:45",       True),
        ("2026-01-15T10:30:45Z",      True),
        ("2026-01-15T10:30:45+05:00", True),
        ("invalid",                   False),
        ("",                          False),
        ("2026-13-01",                False),
        ("2026-01-32",                False),
    ])
    def test_parse_ts_string_validity(self, input_val: str, should_succeed: bool) -> None:
        """Parametrized test for string validity checks."""
        result: datetime | None = utils.parse_ts(input_val)
        
        if should_succeed:
            assert result is not None, f"Expected success for {input_val}"
        else:
            assert result is None, f"Expected None for {input_val}"

    @pytest.mark.parametrize("epoch_val", [
        0,
        1,
        86400,
    ])
    def test_parse_ts_valid_epochs(self, epoch_val: int) -> None:
        """Parametrized test for various valid epoch values."""
        result: datetime | None = utils.parse_ts(epoch_val)
        
        assert result is not None, f"Failed to parse epoch {epoch_val}"
        assert isinstance(result, datetime), f"Expected datetime, got {type(result)}"
        assert result.microsecond == 0, f"Expected microsecond=0, got {result.microsecond}"
