# Benchmarks

## SWELL-KW direction check (2026-09-28)

**Question:** does proki's focus intensity drop when people are interrupted?

**Data:** [SWELL-KW](https://ssh.datastations.nl/dataset.xhtml?persistentId=doi:10.17026/dans-x55-69zp)
(Koldijk et al., ICMI 2014; CC BY-NC-SA 4.0, not redistributed here). 25 people
did office work (reports, presentations, research) under three conditions,
every minute labelled: **N** normal, **I** email interruptions, **T** time pressure.

**Method** (`benchmarks/swell_kw.py`): the raw uLog computer logs are turned
into proki segments like ActivityWatch would record them (focused app changes
only on window activation; 3 min without input = away). Word, PowerPoint and
Internet Explorer count as deep, Outlook as shallow, everything else neutral.
Every labelled minute whose whole window lies in one condition is scored with
the default `FocusParams`.

**Alignment check:** the dataset's own keystrokes-per-minute are compared with
ours from the raw log, per participant. 23 of 25 match exactly (correlation
1.00, so labels and log times line up to the minute). **PP11 and PP16 don't
match at any time shift** (their label and log files don't belong together) and
are excluded automatically.

```
uv run python benchmarks/swell_kw.py DATA_DIR   # DATA_DIR: features.csv + logs/*.xml
```

**Result, 10-min window:**

| | normal | email interruptions | time pressure |
|---|---|---|---|
| intensity | 0.661 | **0.551** | 0.622 |
| depth | 0.997 | 0.939 | 0.998 |
| fit | 1.000 | 1.000 | 1.000 |
| hit rate | 0.946 | 0.955 | 0.936 |
| continuity | 0.709 | 0.621 | 0.679 |

Per participant, interrupted minutes scored lower than normal ones for
**20 of 23** people (median −0.086; sign test p ≈ 0.0005). With a 2-min window:
21 of 23. Time pressure: lower for 13 of 23, no clear effect (expected:
deadlines can sharpen focus as well as hurt it).

**What it shows about each component:**
- **depth** and **continuity** react to interruptions as intended.
- **fit** and **hit rate** are *not* tested: the lab used only 3–4 apps, so the
  working set never overflowed, and going to Outlook for an email is a return
  to a known item (a hit). Real desktops with many tabs are needed for these.
- The absolute level (~0.66 for normal office work) says nothing yet about
  what the numbers mean for one person; that still needs personal calibration.

**How strong is this evidence?** It's a sanity check, not proof that the score
measures focus. Interruptions add switches and Outlook time, and the metric is
built to penalize exactly those, so a drop is close to guaranteed if the code
works. What it does confirm: the pipeline (log → segments → score) behaves as
designed on independent real-world data, and the effect is visible for almost
every individual, not just on average.

**Limits:** lab setting, Windows 2012 software, categories assigned by us,
browser counted as one app (no domains).
