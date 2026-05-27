"""
leap42.py — The Leap 42 Calendar Library
=========================================
A parsimonious decimal calendar and timekeeping architecture.

Version: 0.1.0

Architecture
------------
Layer 1 — Core arithmetic (stdlib only: math for from_adn, re for parse):
    is_leap, month_length, year_length, to_ordinal, from_ordinal,
    to_adn, from_adn, to_timestamp, from_timestamp, serialize, parse,
    date_valid, next_date, prev_date, date_diff,
    normalize_date, normalize, day_of_week,
    MONTH_NAMES, month_name

Layer 2 — Gregorian bridge (requires math, uses Meeus 1998 Ch.27):
    dec_solstice_jdn    -- JDN of December solstice for any year 1000-3000
    gregorian_to_jdn    -- Gregorian date -> Julian Day Number
    jdn_to_gregorian    -- Julian Day Number -> Gregorian date
    gregorian_to_l42    -- Gregorian date -> L42 date, given epoch_jdn
    l42_to_gregorian    -- L42 date -> Gregorian date, given epoch_jdn
    today               -- current L42 date in UTC, given epoch_jdn
    now                 -- current L42 datetime in UTC, given epoch_jdn

Epoch design
------------
This library is epoch-agnostic. Cultural Year 0 is not prescribed;
month names are not prescribed. To use the Gregorian bridge, supply
epoch_jdn: the Julian Day Number of your community's chosen Year 0,
Month 1, Day 1 (which should be a December solstice).

Example epoch declarations:
    # Unix-adjacent: Year 0 starts at the Dec 21, 1969 solstice
    UNIX_EPOCH_JDN = dec_solstice_jdn(1969)  # JDN 2440577

    # CE-anchored: Year 0 starts at the Dec 21, 2000 solstice
    CE2000_EPOCH_JDN = dec_solstice_jdn(2000)  # JDN 2451900

The library makes no default choice. Pass epoch_jdn explicitly.

Calendar specification
----------------------
- 10 months per year
- Months 1-9: 36 days each
- Month 10: 41 days (standard) or 42 days (leap year)
- Standard year: 9 × 36 + 41 = 365 days
- Leap year:     9 × 36 + 42 = 366 days
- Leap rule: (Y mod 4 = 0) and (Y mod 100 != 0 or Y mod 400 = 0)
- Year starts on the December winter solstice (UTC)

Decimal time specification
--------------------------
- 1 day = 10 hours
- 1 hour = 100 minutes
- 1 minute = 100 seconds
- 1 day = 100,000 decimal seconds
- 1 decimal second = 0.864 SI seconds
- Time scalar T = h*10000 + m*100 + s,  T in [0, 99999]

Unix/SI truncation note
-----------------------
unix_seconds_to_timestamp() and timestamp_to_unix_seconds() use integer
floor division to convert between SI seconds (86,400/day) and decimal
seconds (100,000/day). Because these quantities are incommensurable, most
conversions are lossy: unix_seconds_to_timestamp(1, e) may not round-trip
back to 1. This is mathematically expected. Use these functions only for
day-level interoperability. If you need sub-second fidelity, preserve the
rational representation (ts, si_remainder) separately.

Astronomical note
-----------------
dec_solstice_jdn uses the Meeus (1998) algorithm (Astronomical
Algorithms, 2nd ed., Chapter 27, Table 27.a/b). Accuracy: <2.5 minutes
for years 1000-3000 CE. All computations use UTC. The formula gives the
calendar day on which the solstice falls in UTC; days that straddle UTC
midnight may differ by one day from local-timezone interpretations.

References
----------
Meeus, Jean. Astronomical Algorithms. 2nd ed. Willmann-Bell, 1998.
Mazurk, Adam. The Leap 42 Calendar. Zenodo, 2026.
https://doi.org/10.5281/zenodo.20400857
"""

__version__ = "0.1.0"

import math as _math
import re as _re

#: Placeholder month names (indices 0–9 correspond to months 1–10).
#: These are informal working names only. The Leap 42 calendar does not
#: prescribe culturally authoritative month names; communities may adopt
#: their own. To use custom names, replace or shadow this tuple.
MONTH_NAMES = (
    "Oneuary", "Twouary", "Threeuary", "Fouruary", "Fiveuary",
    "Sixuary", "Sevenuary", "Eightuary", "Nineuary", "Tenuary",
)


def month_name(month: int) -> str:
    """Return the placeholder name for a month number in [1, 10].

    Uses the MONTH_NAMES tuple. Raises ValueError for out-of-range input.
    """
    if not (1 <= month <= 10):
        raise ValueError(f"Month must be 1-10, got {month}")
    return MONTH_NAMES[month - 1]

# =============================================================================
# LAYER 1: CORE ARITHMETIC
# Stdlib only: math (used by from_adn) and re (used by parse) are imported
# at module top. All other functions use pure integer arithmetic.
# =============================================================================

def is_leap(year: int) -> bool:
    """Return True if year is a Leap 42 leap year.

    Uses the Gregorian-compatible rule:
        (year mod 4 = 0) and (year mod 100 != 0 or year mod 400 = 0)
    """
    return (year % 4 == 0) and (year % 100 != 0 or year % 400 == 0)


def month_length(year: int, month: int) -> int:
    """Return the number of days in (year, month).

    Months 1-9: always 36.
    Month 10:   42 in leap years, 41 otherwise.

    Raises ValueError for month outside [1, 10].
    """
    if not (1 <= month <= 10):
        raise ValueError(f"Month must be 1-10, got {month}")
    if month <= 9:
        return 36
    return 42 if is_leap(year) else 41


def year_length(year: int) -> int:
    """Return the number of days in year (365 or 366)."""
    return 366 if is_leap(year) else 365


def date_valid(year: int, month: int, day: int) -> bool:
    """Return True if (year, month, day) is a valid Leap 42 date."""
    if not (1 <= month <= 10):
        return False
    return 1 <= day <= month_length(year, month)


def to_ordinal(year: int, month: int, day: int) -> int:
    """Return the day-of-year ordinal in [1, year_length(year)].

    Months 1-9: ordinal = 36*(month-1) + day
    Month 10:   ordinal = 324 + day
    """
    if not date_valid(year, month, day):
        raise ValueError(f"Invalid date ({year}, {month}, {day})")
    if month <= 9:
        return 36 * (month - 1) + day
    return 324 + day


def from_ordinal(year: int, ordinal: int) -> tuple:
    """Return (year, month, day) for an ordinal day in [1, year_length(year)].

    Inverse of to_ordinal: from_ordinal(y, to_ordinal(y, m, d)) == (y, m, d).
    """
    max_ord = year_length(year)
    if not (1 <= ordinal <= max_ord):
        raise ValueError(f"Ordinal {ordinal} out of range [1, {max_ord}] for year {year}")
    if ordinal <= 324:
        month = (ordinal - 1) // 36 + 1
        day = ordinal - 36 * (month - 1)
    else:
        month = 10
        day = ordinal - 324
    return year, month, day


def to_adn(year: int, month: int, day: int) -> int:
    """Return the Absolute Day Number: a monotonic integer timeline.

    ADN uses the Gregorian-compatible leap rule for accumulated leap days.
    ADN(Y=0, M=1, D=1) = 0 by definition (epoch-relative).

    The caller anchors ADN to an absolute date via the epoch_jdn offset
    in the Gregorian bridge layer.
    """
    if not date_valid(year, month, day):
        raise ValueError(f"Invalid date ({year}, {month}, {day})")
    # Unified formula valid for all integer years (positive, zero, and negative).
    # Uses Python's floor division, which handles negative numbers correctly.
    # ADN(0, 1, 1) = 0 by definition.
    # Derived from the proleptic Gregorian day count with a fixed offset of 366
    # (the number of days in year 0, which is leap).
    n = year - 1
    return 365 * n + n // 4 - n // 100 + n // 400 + to_ordinal(year, month, day) - 1 + 366


def from_adn(adn: int) -> tuple:
    """Return (year, month, day) for a given Absolute Day Number.

    Inverse of to_adn.
    """
    # Estimate year from ADN. Year 1 starts at ADN 366 (year 0 has 366 days).
    # Rough estimate: year ≈ (adn - 366) / 365.25 + 1
    year = _math.floor((adn - 366) / 365.25) + 1
    # Correct upward if estimate is too low
    while to_adn(year + 1, 1, 1) <= adn:
        year += 1
    # Correct downward if estimate is too high
    while to_adn(year, 1, 1) > adn:
        year -= 1
    ordinal = adn - to_adn(year, 1, 1) + 1
    return from_ordinal(year, ordinal)


def to_timestamp(year: int, month: int, day: int,
                 hour: int, minute: int, second: int) -> int:
    """Return the Leap 42 timestamp scalar.

    TS = ADN * 100_000 + T
    where T = hour*10000 + minute*100 + second, T in [0, 99999].

    Lexicographic ordering of (year, month, day, hour, minute, second)
    equals chronological ordering of TS.
    """
    if not (0 <= hour <= 9):
        raise ValueError(f"Hour must be 0-9, got {hour}")
    if not (0 <= minute <= 99):
        raise ValueError(f"Minute must be 0-99, got {minute}")
    if not (0 <= second <= 99):
        raise ValueError(f"Second must be 0-99, got {second}")
    adn = to_adn(year, month, day)
    t = hour * 10000 + minute * 100 + second
    return adn * 100_000 + t


def from_timestamp(ts: int) -> tuple:
    """Return (year, month, day, hour, minute, second) for a timestamp scalar.

    Inverse of to_timestamp.
    """
    adn, t = divmod(ts, 100_000)
    hour, rem = divmod(t, 10000)
    minute, second = divmod(rem, 100)
    year, month, day = from_adn(adn)
    return year, month, day, hour, minute, second


def serialize(year: int, month: int, day: int,
              hour: int = None, minute: int = None, second: int = None) -> str:
    """Return the canonical string representation.

    Date only:      YYYY-MM-DD
    Date + time:    YYYY-MM-DDThh.mm.ss

    Year is zero-padded to at least 4 digits. Negative years use a leading '-'.
    Month, day, hour, minute, second are always 2 digits.

    Example: serialize(208, 10, 42, 5, 50, 0) -> '0208-10-42T05.50.00'
    """
    if not date_valid(year, month, day):
        raise ValueError(f"Invalid date ({year}, {month}, {day})")
    sign = "-" if year < 0 else ""
    y = abs(year)
    date_str = f"{sign}{y:04d}-{month:02d}-{day:02d}"
    if hour is None:
        return date_str
    if not (0 <= hour <= 9 and 0 <= minute <= 99 and 0 <= second <= 99):
        raise ValueError(f"Invalid time ({hour}, {minute}, {second})")
    return f"{date_str}T{hour:02d}.{minute:02d}.{second:02d}"


def parse(s: str) -> tuple:
    """Parse a canonical Leap 42 string.

    Accepts ONLY strings matching the canonical forms:
        YYYY-MM-DD
        YYYY-MM-DDThh.mm.ss

    where YYYY is an optional '-' followed by at least 4 digits,
    and all other fields are exactly 2 digits.

    Returns (year, month, day) or (year, month, day, hour, minute, second).

    Raises ValueError for any non-canonical input, including trailing content,
    non-canonical padding, or invalid field values.

    Satisfies: serialize(*parse(x)) == x for all valid canonical strings.
    """
    s = s.strip()

    # Strict regex: canonical forms only
    _DATE_RE = _re.compile(
        r'^(-?\d{4,})-(\d{2})-(\d{2})(?:T(\d{2})\.(\d{2})\.(\d{2}))?$'
    )
    m = _DATE_RE.fullmatch(s)
    if m is None:
        raise ValueError(f"Not a canonical Leap 42 string: {s!r}")

    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))

    if not date_valid(year, month, day):
        raise ValueError(f"Invalid Leap 42 date in {s!r}: ({year}, {month}, {day})")

    if m.group(4) is None:
        # Date-only form: verify it serializes back identically
        canonical = serialize(year, month, day)
        if canonical != s:
            raise ValueError(
                f"Non-canonical date string {s!r}; canonical form is {canonical!r}"
            )
        return year, month, day

    hour = int(m.group(4))
    minute = int(m.group(5))
    second = int(m.group(6))

    if not (0 <= hour <= 9):
        raise ValueError(f"Hour must be 0-9, got {hour} in {s!r}")
    if not (0 <= minute <= 99):
        raise ValueError(f"Minute must be 0-99, got {minute} in {s!r}")
    if not (0 <= second <= 99):
        raise ValueError(f"Second must be 0-99, got {second} in {s!r}")

    # Verify round-trip canonicality
    canonical = serialize(year, month, day, hour, minute, second)
    if canonical != s:
        raise ValueError(
            f"Non-canonical timestamp string {s!r}; canonical form is {canonical!r}"
        )
    return year, month, day, hour, minute, second


def next_date(year: int, month: int, day: int) -> tuple:
    """Return the date following (year, month, day)."""
    if not date_valid(year, month, day):
        raise ValueError(f"Invalid date ({year}, {month}, {day})")
    if day < month_length(year, month):
        return year, month, day + 1
    if month < 10:
        return year, month + 1, 1
    return year + 1, 1, 1


def prev_date(year: int, month: int, day: int) -> tuple:
    """Return the date preceding (year, month, day)."""
    if not date_valid(year, month, day):
        raise ValueError(f"Invalid date ({year}, {month}, {day})")
    if day > 1:
        return year, month, day - 1
    if month > 1:
        prev_m = month - 1
        return year, prev_m, month_length(year, prev_m)
    return year - 1, 10, month_length(year - 1, 10)


def date_diff(year1: int, month1: int, day1: int,
              year2: int, month2: int, day2: int) -> int:
    """Return the signed number of days from date1 to date2.

    Positive if date2 is after date1, negative if before, zero if equal.
    """
    return to_adn(year2, month2, day2) - to_adn(year1, month1, day1)


def normalize_date(year: int, month: int, day: int) -> tuple:
    """Normalize a potentially overflowing or underflowing date to (year, month, day).

    Accepts any integer values and returns the unique canonical 3-tuple
    representing the same day. Always returns exactly 3 fields.

    Examples:
        normalize_date(2024, 1, 37)   -> (2024, 2, 1)   # day overflow
        normalize_date(2024, 11, 1)   -> (2025, 1, 1)   # month overflow
        normalize_date(2024, 1, 0)    -> (2023, 10, 41) # day underflow
        normalize_date(2024, 0, 1)    -> (2023, 10, 1)  # month underflow
    """
    return _normalize_adn(year, month, day, 0)[:3]


def normalize(year: int, month: int, day: int,
              hour: int = 0, minute: int = 0, second: int = 0) -> tuple:
    """Normalize a potentially overflowing or underflowing date/time tuple.

    Accepts any integer values for all fields and always returns a canonical
    6-tuple (year, month, day, hour, minute, second). Time fields default to
    zero when not supplied.

    Always returns exactly 6 fields regardless of input. Use normalize_date()
    if you only need the date component.

    Examples:
        normalize(2024, 1, 37)              -> (2024, 2, 1, 0, 0, 0)
        normalize(2024, 11, 1)              -> (2025, 1, 1, 0, 0, 0)
        normalize(2024, 1, 0)              -> (2023, 10, 41, 0, 0, 0)
        normalize(2024, 1, 1, 0, 0, 100000) -> (2024, 1, 2, 0, 0, 0)
    """
    return _normalize_adn(year, month, day, hour * 10000 + minute * 100 + second)


def _normalize_adn(year: int, month: int, day: int, t_raw: int) -> tuple:
    """Internal: resolve (year, month, day, t_raw) to canonical 6-tuple.

    t_raw is the raw decimal time scalar (may overflow/underflow 100000).
    """
    # Normalise time: carry overflow/underflow days
    carry_days, t = divmod(t_raw, 100_000)

    # Compute ADN from potentially out-of-range (year, month, day) by
    # anchoring to (year, 1, 1) and adding month+day offsets manually.
    anchor_adn = to_adn(year, 1, 1)
    extra = day - 1
    if month >= 1:
        y_walk, m_walk = year, 1
        for _ in range(month - 1):
            extra += month_length(y_walk, m_walk)
            m_walk += 1
            if m_walk > 10:
                m_walk = 1
                y_walk += 1
    else:
        y_walk, m_walk = year, 0
        for _ in range(-month + 1):
            m_walk -= 1
            if m_walk < 1:
                m_walk = 10
                y_walk -= 1
            extra -= month_length(y_walk, m_walk)

    adn = anchor_adn + extra + carry_days
    yn, mn, dn = from_adn(adn)
    h, rem = divmod(t, 10000)
    mi, s = divmod(rem, 100)
    return yn, mn, dn, h, mi, s


def day_of_week(year: int, month: int, day: int, week_length: int = 6) -> int:
    """Return the day-of-week index for a given date.

    The paper's reference week is 6 days (since 36 = 6 × 6, giving each of
    months 1-9 exactly six complete weeks with no weekday drift).

    Returns an integer in [0, week_length - 1].
    Day 0 is conventionally the first day of Year 0, Month 1.

    week_length may be set to 7 (Gregorian-compatible continuity week),
    10 (decimal week), or any positive integer.

    Example with the default 6-day week:
        day_of_week(0, 1, 1) -> 0   # epoch day
        day_of_week(0, 1, 7) -> 0   # start of second week
    """
    if week_length < 1:
        raise ValueError(f"week_length must be >= 1, got {week_length}")
    return to_adn(year, month, day) % week_length


def unix_seconds_to_timestamp(unix_s: int, epoch_jdn: int) -> int:
    """Convert a Unix timestamp (seconds since 1970-01-01 00:00 UTC) to L42 TS.

    epoch_jdn: the Julian Day Number of your Year 0, Month 1, Day 1.

    Unix Day Number of Unix epoch (1970-01-01) = 2440588 (JDN).
    So Unix day = unix_s // 86400.
    Corresponding JDN = UNIX_EPOCH_JDN + unix_s // 86400.
    L42 ADN = JDN - epoch_jdn.
    Time of day: convert remaining SI seconds to decimal seconds.
    """
    UNIX_EPOCH_JDN = 2440588
    unix_days, si_rem = divmod(unix_s, 86400)
    jdn = UNIX_EPOCH_JDN + unix_days
    adn = jdn - epoch_jdn
    # Convert SI seconds to decimal seconds: 1 decimal second = 0.864 SI seconds
    # decimal_seconds = si_rem / 0.864  (but keep integer arithmetic)
    # T = floor(si_rem * 100000 / 86400)
    t = (si_rem * 100_000) // 86400
    return adn * 100_000 + t


def timestamp_to_unix_seconds(ts: int, epoch_jdn: int) -> int:
    """Convert a Leap 42 timestamp scalar to Unix seconds (truncated).

    Inverse of unix_seconds_to_timestamp (integer division, no sub-second info).
    """
    UNIX_EPOCH_JDN = 2440588
    adn, t = divmod(ts, 100_000)
    jdn = epoch_jdn + adn
    unix_days = jdn - UNIX_EPOCH_JDN
    si_rem = (t * 86400) // 100_000
    return unix_days * 86400 + si_rem


# =============================================================================
# LAYER 2: GREGORIAN BRIDGE
# Requires: import math (stdlib only)
# Uses the Meeus (1998) algorithm for December solstice.
# =============================================================================

def dec_solstice_jdn(year: int) -> int:
    """Return the Julian Day Number of the December solstice for a given year.

    Uses Jean Meeus, Astronomical Algorithms (1998), Chapter 27.
    Accuracy: < 2.5 minutes for years 1000-3000 CE.
    All results are in UTC. Returns the calendar day (JDN integer) on which
    the solstice falls.

    Valid range: years 1000-3000 CE. Behavior outside this range is undefined.
    """
    import math

    y = (year - 2000) / 1000.0

    # Polynomial JDE0: mean December solstice Julian Ephemeris Day
    # Source: Meeus (1998) Table 27.a, December solstice row
    JDE0 = (2451900.05952
            + 365242.74049 * y
            - 0.06223 * y ** 2
            - 0.00823 * y ** 3
            + 0.00032 * y ** 4)

    # Correction terms (Meeus Table 27.b)
    T = (JDE0 - 2451545.0) / 36525.0
    W = 35999.373 * T - 2.47
    delta_lambda = (1
                    + 0.0334 * math.cos(math.radians(W))
                    + 0.0007 * math.cos(math.radians(2 * W)))

    # 24 periodic correction terms; amplitudes in units of 10^-4 JDE days
    _TERMS = (
        (485, 324.96,   1934.136), (203, 337.23,  32964.467),
        (199, 342.08,     20.186), (182,  27.85, 445267.112),
        (156,  73.14,  45036.886), (136, 171.52,  22518.443),
        ( 77, 222.54,  65928.934), ( 74, 296.72,   3034.906),
        ( 70, 243.58,   9037.513), ( 58, 119.81,  33718.147),
        ( 52, 297.17,    150.678), ( 50,  21.02,   2281.226),
        ( 45, 247.54,  29929.562), ( 44, 325.15,  31555.956),
        ( 29,  60.93,   4443.417), ( 18, 155.12,  67555.328),
        ( 17, 288.79,   4562.452), ( 16, 198.04,  62894.029),
        ( 14, 199.76,  31436.921), ( 12,  95.39,  14577.848),
        ( 10, 287.11,  31931.756), (  8, 228.46,   1221.848),
        (  6, 318.13,  62894.029), (  5, 199.76,  31436.921),
    )
    S = sum(a * math.cos(math.radians(b + c * T))
            for a, b, c in _TERMS) / 10000.0

    jde = JDE0 + S / delta_lambda
    return int(jde + 0.5)  # Floor to calendar day (JDN integer)


def gregorian_to_jdn(year: int, month: int, day: int) -> int:
    """Convert a proleptic Gregorian date to a Julian Day Number.

    Valid for all dates after 4713 BC. Uses the standard algorithm.
    """
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return (day
            + (153 * m + 2) // 5
            + 365 * y
            + y // 4
            - y // 100
            + y // 400
            - 32045)


def jdn_to_gregorian(jdn: int) -> tuple:
    """Convert a Julian Day Number to a proleptic Gregorian date (year, month, day).

    Inverse of gregorian_to_jdn.
    """
    l = jdn + 68569
    n = (4 * l) // 146097
    l = l - (146097 * n + 3) // 4
    i = (4000 * (l + 1)) // 1461001
    l = l - (1461 * i) // 4 + 31
    j = (80 * l) // 2447
    day = l - (2447 * j) // 80
    l = j // 11
    month = j + 2 - 12 * l
    year = 100 * (n - 49) + i + l
    return year, month, day


def gregorian_to_l42(gyear: int, gmonth: int, gday: int,
                     epoch_jdn: int) -> tuple:
    """Convert a Gregorian date to a Leap 42 date.

    epoch_jdn: JDN of your Year 0, Month 1, Day 1.
               Use dec_solstice_jdn(year) to produce this from a Gregorian year.

    Returns (l42_year, l42_month, l42_day).

    The Gregorian date's position relative to the epoch is computed via JDN
    arithmetic, then mapped to L42 via from_adn. All operations are exact
    integer arithmetic once epoch_jdn is established.
    """
    jdn = gregorian_to_jdn(gyear, gmonth, gday)
    adn = jdn - epoch_jdn
    if adn < 0:
        # Before epoch: negative L42 years
        # Walk back year by year (rare edge case, not performance-sensitive)
        year = -1
        while adn < to_adn(year, 1, 1):
            year -= 1
        ordinal = adn - to_adn(year, 1, 1) + 1
        return from_ordinal(year, ordinal)
    return from_adn(adn)


def l42_to_gregorian(year: int, month: int, day: int,
                     epoch_jdn: int) -> tuple:
    """Convert a Leap 42 date to a Gregorian date.

    epoch_jdn: JDN of your Year 0, Month 1, Day 1.

    Returns (gregorian_year, gregorian_month, gregorian_day).
    """
    if not date_valid(year, month, day):
        raise ValueError(f"Invalid Leap 42 date ({year}, {month}, {day})")
    adn = to_adn(year, month, day)
    jdn = epoch_jdn + adn
    return jdn_to_gregorian(jdn)


def today(epoch_jdn: int) -> tuple:
    """Return the current Leap 42 date in UTC as (year, month, day).

    epoch_jdn: JDN of your Year 0, Month 1, Day 1.

    Uses the system clock (UTC). Requires Python's datetime module.
    """
    import datetime as _dt
    now_utc = _dt.datetime.now(_dt.timezone.utc)
    return gregorian_to_l42(now_utc.year, now_utc.month, now_utc.day, epoch_jdn)


def now(epoch_jdn: int) -> tuple:
    """Return the current Leap 42 datetime in UTC as (year, month, day, hour, minute, second).

    epoch_jdn: JDN of your Year 0, Month 1, Day 1.

    Decimal time is derived from the current UTC wall clock. Because decimal
    seconds (0.864 SI seconds each) do not align exactly with SI seconds, the
    returned second field is floor-truncated from the exact decimal value.
    Uses the system clock (UTC). Requires Python's datetime module.
    """
    import datetime as _dt
    utc = _dt.datetime.now(_dt.timezone.utc)
    l42_date = gregorian_to_l42(utc.year, utc.month, utc.day, epoch_jdn)
    # Convert current time-of-day SI seconds to decimal T scalar
    si_day_seconds = utc.hour * 3600 + utc.minute * 60 + utc.second
    t = (si_day_seconds * 100_000) // 86400
    h, rem = divmod(t, 10000)
    mi, s = divmod(rem, 100)
    return (*l42_date, h, mi, s)


# =============================================================================
# SELF-TEST
# Run: python leap42.py
# =============================================================================

def _run_tests():
    """Quick self-test suite. Raises AssertionError on failure."""
    # --- Leap rule ---
    assert is_leap(2000)
    assert is_leap(2024)
    assert is_leap(0)      # year 0 is leap
    assert is_leap(-4)     # year -4 is leap
    assert not is_leap(1900)
    assert not is_leap(2100)
    assert not is_leap(2023)
    assert not is_leap(-1)
    assert not is_leap(-3)

    # --- Month lengths ---
    assert month_length(2024, 1) == 36
    assert month_length(2024, 9) == 36
    assert month_length(2024, 10) == 42   # leap
    assert month_length(2023, 10) == 41   # standard
    assert month_length(-4, 10) == 42     # negative leap year
    assert month_length(-3, 10) == 41     # negative standard year
    assert year_length(2024) == 366
    assert year_length(2023) == 365
    assert year_length(0) == 366          # year 0 is leap
    assert year_length(-4) == 366         # year -4 is leap

    # --- Ordinal round-trip ---
    for y in [2023, 2024, -4, -3, 0]:
        for m in range(1, 11):
            for d in [1, month_length(y, m) // 2, month_length(y, m)]:
                assert from_ordinal(y, to_ordinal(y, m, d)) == (y, m, d)

    # --- ADN uniqueness and round-trip (including negative years) ---
    seen_adn = {}
    for y in range(-10, 11):
        for m in range(1, 11):
            for d in [1, month_length(y, m)]:
                adn = to_adn(y, m, d)
                key = (y, m, d)
                assert key not in seen_adn or seen_adn[key] == adn
                # No two distinct dates should share an ADN
                if adn in seen_adn.values():
                    collider = [k for k, v in seen_adn.items() if v == adn]
                    assert collider == [key], \
                        f"ADN collision: {key} and {collider[0]} both = {adn}"
                seen_adn[key] = adn
                assert from_adn(adn) == (y, m, d), \
                    f"from_adn(to_adn{key}) failed: got {from_adn(adn)}"

    # --- Key ADN values ---
    assert to_adn(0, 1, 1) == 0
    assert to_adn(-4, 10, 42) != to_adn(-3, 1, 1)   # the original collision bug
    # Year boundaries are contiguous
    for y in range(-5, 6):
        assert to_adn(y + 1, 1, 1) == to_adn(y, 10, month_length(y, 10)) + 1

    # --- ADN round-trip for larger years ---
    for y, m, d in [(0,1,1),(1,1,1),(100,5,18),(2024,10,42),(-4,10,42),(-100,1,1)]:
        assert from_adn(to_adn(y, m, d)) == (y, m, d)

    # --- Date sequence ---
    assert next_date(2024, 9, 36) == (2024, 10, 1)
    assert next_date(2024, 10, 42) == (2025, 1, 1)
    assert prev_date(2024, 1, 1) == (2023, 10, 41)
    assert prev_date(2024, 3, 1) == (2024, 2, 36)
    assert next_date(-4, 10, 42) == (-3, 1, 1)   # negative year boundary
    assert prev_date(-3, 1, 1) == (-4, 10, 42)

    # --- Serialize / parse round-trip (canonical strings only) ---
    for s in ["0208-10-42", "0208-10-42T05.50.00", "-0001-01-01", "2024-05-15T09.30.45"]:
        result = parse(s)
        assert serialize(*result) == s, \
            f"Round-trip failed: {s!r} -> {result!r} -> {serialize(*result)!r}"

    # --- parse() rejects malformed strings ---
    bad_strings = [
        "0208-10-42-foo",          # trailing garbage
        "0208-10-42T5.50.00",      # non-canonical hour padding
        "0208-10-42T05.50.0",      # non-canonical second padding
        "208-10-42",               # year too short (< 4 digits)
        "0208-10-42Textra",        # garbage after date
        "not-a-date",
    ]
    for bad in bad_strings:
        try:
            result = parse(bad)
            assert False, f"parse({bad!r}) should have raised ValueError, got {result}"
        except ValueError:
            pass  # expected

    # --- date_diff ---
    assert date_diff(2024, 1, 1, 2024, 1, 1) == 0
    assert date_diff(2024, 1, 1, 2024, 1, 2) == 1
    assert date_diff(2024, 1, 2, 2024, 1, 1) == -1

    # --- Gregorian JDN round-trip ---
    for g in [(2000, 1, 1), (1969, 12, 22), (2025, 3, 15), (-1, 3, 1)]:
        assert jdn_to_gregorian(gregorian_to_jdn(*g)) == g

    # --- dec_solstice_jdn spot checks ---
    sol_2000 = dec_solstice_jdn(2000)
    gy, gm, gd = jdn_to_gregorian(sol_2000)
    assert (gm, gd) == (12, 21), f"2000 solstice: expected Dec 21, got {gm}-{gd}"

    sol_2025 = dec_solstice_jdn(2025)
    gy, gm, gd = jdn_to_gregorian(sol_2025)
    assert (gm, gd) == (12, 21), f"2025 solstice: expected Dec 21, got {gm}-{gd}"

    # --- Gregorian bridge round-trip ---
    epoch = dec_solstice_jdn(2000)   # example epoch: Dec 21, 2000
    for g in [(2001, 3, 15), (2000, 12, 21), (2025, 6, 20)]:
        l42 = gregorian_to_l42(*g, epoch)
        back = l42_to_gregorian(*l42, epoch)
        assert back == g, f"Bridge round-trip failed: {g} -> {l42} -> {back}"

    # --- Unix timestamp bridge ---
    epoch = dec_solstice_jdn(1969)
    ts_unix_zero = unix_seconds_to_timestamp(0, epoch)
    back = timestamp_to_unix_seconds(ts_unix_zero, epoch)
    assert back == 0, f"Unix round-trip failed: ts={ts_unix_zero}, back={back}"

    # --- normalize_date (always 3-tuple) ---
    assert normalize_date(2024, 1, 37) == (2024, 2, 1)
    assert normalize_date(2024, 11, 1) == (2025, 1, 1)
    assert normalize_date(2024, 1, 0) == (2023, 10, 41)
    assert normalize_date(2024, 0, 1) == (2023, 10, 1)
    assert normalize_date(2024, 5, 18) == (2024, 5, 18)

    # --- normalize (always 6-tuple) ---
    assert normalize(2024, 1, 37) == (2024, 2, 1, 0, 0, 0)
    assert normalize(2024, 11, 1) == (2025, 1, 1, 0, 0, 0)
    assert normalize(2024, 1, 0) == (2023, 10, 41, 0, 0, 0)
    assert normalize(2024, 1, 1, 0, 0, 100_000) == (2024, 1, 2, 0, 0, 0)
    assert normalize(2024, 5, 18) == (2024, 5, 18, 0, 0, 0)
    assert normalize(2024, 5, 18, 3, 50, 0) == (2024, 5, 18, 3, 50, 0)
    # Underflow in time
    result = normalize(2024, 1, 1, 0, 0, -1)
    assert result == (2023, 10, 41, 9, 99, 99), f"normalize underflow: {result}"

    # --- day_of_week ---
    # 6-day week: epoch day (0,1,1) is day 0
    assert day_of_week(0, 1, 1) == 0
    assert day_of_week(0, 1, 7) == 0        # 6 days later = new week
    assert day_of_week(0, 1, 2) == 1
    assert day_of_week(0, 1, 6) == 5
    # 7-day week
    assert day_of_week(0, 1, 8, week_length=7) == 0  # 7 days later

    # --- today / now ---
    epoch_now = dec_solstice_jdn(2000)
    t = today(epoch_now)
    assert len(t) == 3
    assert date_valid(*t), f"today() returned invalid date: {t}"
    n = now(epoch_now)
    assert len(n) == 6
    assert date_valid(*n[:3]), f"now() returned invalid date: {n[:3]}"
    assert 0 <= n[3] <= 9,  f"now() hour out of range: {n[3]}"
    assert 0 <= n[4] <= 99, f"now() minute out of range: {n[4]}"
    assert 0 <= n[5] <= 99, f"now() second out of range: {n[5]}"

    print("All tests passed.")


if __name__ == "__main__":
    _run_tests()

    # Demo — live clock
    import datetime as _dt
    epoch = dec_solstice_jdn(1969)
    utc = _dt.datetime.now(_dt.timezone.utc)

    y, m, d, h, mi, s = now(epoch)
    ts = serialize(y, m, d, h, mi, s)

    month_name_str = month_name(m)

    print()
    print(f"Today (Gregorian UTC):")
    print(f"  {utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print(f"Leap 42 (epoch = 1969 Dec solstice):")
    print(f"  {ts}")
    print(f"  ({month_name_str} {d}, {h:02d}:{mi:02d}:{s:02d})")
    print()
    print(f"  L42 (0, 1, 1) = Gregorian {l42_to_gregorian(0, 1, 1, epoch)}")
    print(f"  Serialize example: {serialize(208, 10, 42, 5, 50, 0)}")
