# Leap42

**The Leap 42 Calendar — Python reference library**

A parsimonious decimal calendar and timekeeping architecture. Ten months,
36-day regular months, a single terminal month that absorbs all calendar
irregularity (41 days standard, 42 days in a leap year), and a decimal clock
(10 hours × 100 minutes × 100 seconds = 100,000 decimal seconds per day).

This library is the reference implementation for the paper:

> Mazurk, Adam. *The Leap 42 Calendar: A Parsimonious Decimal Calendar and
> Timekeeping Architecture.* Zenodo, 2026.
> https://doi.org/10.5281/zenodo.20400857

---

## Install

```
pip install leap42
```

Or copy `leap42.py` directly — it is a single-file library with no
dependencies beyond the Python standard library.

---

## Quick start

```python
import leap42 as L

# Choose your epoch: the JDN of your community's Year 0, Month 1, Day 1.
# This should be a December winter solstice.
# The library does not prescribe a cultural epoch — you declare it.

EPOCH = L.dec_solstice_jdn(1969)   # JDN of Dec 21, 1969 solstice

# Today's date
print(L.today(EPOCH))              # e.g. (56, 5, 13)

# Full datetime (decimal clock)
print(L.now(EPOCH))                # e.g. (56, 5, 13, 4, 17, 36)

# Convert from Gregorian
print(L.gregorian_to_l42(2026, 5, 26, EPOCH))   # (56, 5, 13)

# Convert to Gregorian
print(L.l42_to_gregorian(56, 5, 13, EPOCH))     # (2026, 5, 26)

# Serialize and parse
s = L.serialize(208, 10, 42, 5, 50, 0)
print(s)                           # 0208-10-42T05.50.00
print(L.parse(s))                  # (208, 10, 42, 5, 50, 0)

# Arithmetic
print(L.date_diff(56, 1, 1, 56, 5, 13))   # 156  (days elapsed)
print(L.next_date(56, 9, 36))             # (56, 10, 1)
print(L.day_of_week(56, 5, 13))           # 0-5  (6-day reference week)

# Normalize overflowing inputs
print(L.normalize(2024, 1, 37))   # (2024, 2, 1)  day overflow
print(L.normalize(0, 11, 1))      # (1, 1, 1)     month overflow
```

---

## Epoch design

The library is **epoch-agnostic**. Cultural Year 0 and month names are not
prescribed. To use the Gregorian bridge functions, supply `epoch_jdn`: the
Julian Day Number of whatever December solstice your community adopts as
Year 0, Month 1, Day 1.

```python
# Some example epoch choices — none is built in.
EPOCH_1969 = L.dec_solstice_jdn(1969)  # near the Unix epoch
EPOCH_2000 = L.dec_solstice_jdn(2000)  # near the J2000 epoch
EPOCH_2026 = L.dec_solstice_jdn(2026)  # near the paper's publication
```

Different communities can use the same library with different epoch
constants; all core arithmetic is shared.

---

## Calendar specification

| Property | Value |
|---|---|
| Months per year | 10 |
| Month lengths 1–9 | 36 days each |
| Month 10 (standard) | 41 days |
| Month 10 (leap year) | 42 days |
| Standard year | 365 days |
| Leap year | 366 days |
| Leap rule | Gregorian-compatible: `(Y%4==0) and (Y%100!=0 or Y%400==0)` |
| Year start | December winter solstice (UTC) |

## Decimal time specification

| Unit | Value |
|---|---|
| 1 day | 10 decimal hours |
| 1 hour | 100 decimal minutes |
| 1 minute | 100 decimal seconds |
| 1 day | 100,000 decimal seconds |
| 1 decimal second | 0.864 SI seconds |

---

## API reference

### Layer 1 — Core arithmetic (stdlib only)

| Function | Description |
|---|---|
| `is_leap(year)` | True if year is a leap year |
| `month_length(year, month)` | Days in given month |
| `year_length(year)` | 365 or 366 |
| `date_valid(year, month, day)` | Validity check |
| `to_ordinal(year, month, day)` | Day-of-year in \[1, year_length\] |
| `from_ordinal(year, ordinal)` | Inverse of `to_ordinal` |
| `to_adn(year, month, day)` | Absolute Day Number (monotonic integer) |
| `from_adn(adn)` | Inverse of `to_adn` |
| `to_timestamp(y, m, d, h, mi, s)` | Scalar timestamp `ADN × 100000 + T` |
| `from_timestamp(ts)` | Inverse of `to_timestamp` |
| `serialize(y, m, d[, h, mi, s])` | Canonical string `YYYY-MM-DD[Thh.mm.ss]` |
| `parse(s)` | Parse canonical string; raises ValueError on non-canonical input |
| `next_date(year, month, day)` | Following date |
| `prev_date(year, month, day)` | Preceding date |
| `date_diff(y1,m1,d1, y2,m2,d2)` | Signed day count from date1 to date2 |
| `MONTH_NAMES` | Tuple of placeholder month names (Oneuary … Tenuary) |
| `month_name(month)` | Placeholder name for month number 1–10 |
| `normalize_date(y, m, d)` | Normalise overflowing/underflowing date fields → always 3-tuple |
| `normalize(y, m, d[, h, mi, s])` | Normalise overflowing/underflowing fields → always 6-tuple |
| `day_of_week(y, m, d[, week_length=6])` | Day-of-week index |

### Layer 2 — Gregorian bridge (requires `math`)

| Function | Description |
|---|---|
| `dec_solstice_jdn(year)` | JDN of December solstice (Meeus 1998, ±2.5 min) |
| `gregorian_to_jdn(y, m, d)` | Proleptic Gregorian → Julian Day Number |
| `jdn_to_gregorian(jdn)` | Julian Day Number → proleptic Gregorian |
| `gregorian_to_l42(gy,gm,gd, epoch_jdn)` | Gregorian → L42 |
| `l42_to_gregorian(y,m,d, epoch_jdn)` | L42 → Gregorian |
| `today(epoch_jdn)` | Current L42 date in UTC |
| `now(epoch_jdn)` | Current L42 datetime in UTC |
| `unix_seconds_to_timestamp(unix_s, epoch_jdn)` | Unix → L42 timestamp |
| `timestamp_to_unix_seconds(ts, epoch_jdn)` | L42 timestamp → Unix |

**Note on Unix/SI conversion:** decimal seconds (0.864 SI s each) and SI
seconds are incommensurable. `unix_seconds_to_timestamp(1, e)` will not
round-trip back to `1` due to floor truncation. Use these functions for
day-level interoperability only.

---

## Self-test

```
python leap42.py
```

Runs the built-in test suite and prints `All tests passed.` on success.

---

## License

MIT — see `LICENSE`.
