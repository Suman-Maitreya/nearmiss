# NearMiss — UI Redesign Brief

**Purpose of this doc**: hand to Manus (or any UI-focused agent) so it can redesign the dashboard, authority report, and landing page without breaking the underlying pipeline or data layer.

---

## 1. Product

**NearMiss** is a pedestrian-vehicle near-miss detection system for city Department of Transportation traffic safety engineers. It turns any traffic camera into a continuous near-miss auditor and routes ambiguous events to a human analyst dashboard.

**Powered by**: Meta SAM 3.1 (perception) + Meta Muse Spark 1.3 (visual review).
**Pilot deployment**: FLUID Jurong Lake Intersection, 3 drone sessions, ~57 min of real intersection footage.
**Validation**: 45 near-miss events detected, 22 critical, 100% recall on physical-contact events vs FLUID ground truth.

---

## 2. Target user

**Primary**: Traffic safety engineer at a city Department of Transportation.
**Context**: Needs defensible evidence to petition for signal timing changes, protected crosswalks, or new cameras. Reports to a budget committee or city engineer. Not a software person — needs the dashboard to be *dense but legible*, like Palantir Gotham or Bloomberg Terminal, not a toy.

**Secondary**: Smart city vendors, campus facilities teams.

**Judging context**: This is a Meta Global AI Developer Hackathon 2026 submission. Judges want to see a product, not a prototype.

---

## 3. Current state

### Dashboard (`nearmiss/dashboard.py`)
A Streamlit app with 5 pages reached via a sidebar radio:
- **Overview** — site context strip, hero gradient banner, 4 KPI cards, severity bar chart, PET histogram, per-session summary cards
- **Events** — filterable table, inspect-one-event panel with evidence frames + Spark observation
- **Review Queue** — events the AI flagged for human decision, with Confirm / Dismiss / Escalate buttons
- **Coverage** — per-session audit trail (what was processed, counts, median PET)
- **Reports** — session picker, Generate button, download HTML + inline preview of a one-page Authority Report

**Current visual direction**: dark navy theme (#0a0e1a), blue-purple gradient accents, severity colours (red/orange/green), Inter + JetBrains Mono via Google Fonts.

### Authority Report (`nearmiss/report.py`)
Generates a self-contained HTML report (single file, images base64-inlined) that a city engineer could email their boss. Dark theme matching the dashboard.

### Landing page (`marketing/index.html`)
Standalone product-marketing page: hero with "See the crash before it happens", problem/solution cards, how-it-works stages, pilot results, "powered by Meta" section, audience, CTA, footer.

---

## 4. Design direction (recommended)

Keep the dark-SaaS / ops-centre aesthetic — it fits the surveillance/traffic-safety domain. Push it further:

- **Typography**: tighter hierarchy, more intentional font-weight contrast
- **Density**: Streamlit's default spacing is too generous for an ops product — compress it
- **Motion**: subtle hover states, fade-ins on data load, pulsing live indicators
- **Information density**: show more at-a-glance on the Overview page without feeling cluttered — think Linear, Vercel, Grafana
- **Charts**: dark themed, no gridline noise, label-forward, with hover tooltips
- **Severity language**: red / orange / green is correct, but add icons (⚠️ ⚡ ✓) and use them consistently

Alternative directions acceptable:
- **Government-brief look** (lighter, think GOV.UK / USDS) — more credible for a city official
- **Palantir Gotham** feel — darker, more map-centric, more operational
- **Modern SaaS clean** — think Stripe/Linear — minimalist, white space, confident

**Pick ONE direction and execute it consistently** across dashboard, report, and landing page.

---

## 5. Files you may freely modify

| File | What's inside | Notes |
|---|---|---|
| `nearmiss/dashboard.py` | Streamlit app | Modify the CSS block at the top, all `st.markdown()` HTML blocks, column layouts, chart styling, button text, section headers, spacing. **Do not change the function names `load_events`, `load_coverage`, `write_review`, `pretty_session`, `safe_str`, `kpi_card`, `sev_chip`, `theme_plot` — downstream code depends on their signatures.** Do not change the sidebar `PAGE` list — those names drive the if/elif branches. |
| `nearmiss/report.py` | Authority report HTML generator | The whole `html = f"""..."""` block is yours. Keep the function signature `generate_report_html(scene, events_df, coverage_df) -> str` and keep the inputs used (`cov['critical_count']`, `ev['our_pet_s']`, etc.) matching the actual DB column names. |
| `marketing/index.html` | Landing page | Standalone HTML — rewrite it top to bottom if you want. Preserve the hero image reference `src="hero.jpg"` since that file is next to it. |
| `nearmiss/__init__.py` | package marker | Leave alone unless adding exports. |

---

## 6. Files you must NOT modify

| File / folder | Why |
|---|---|
| `nearmiss.db` | SQLite database with all detected events and Spark reviews. Delete it and the dashboard goes empty. |
| `nearmiss/physics.py` | The grid-PET engine. Any edit risks breaking the 100% contact recall validation. |
| `scripts/*.py` | Pipeline scripts (SAM, Spark, PET sweep, DB build, evidence rendering). Not UI. |
| `config.yaml` | Pipeline thresholds (PET bands, SAM prompts, calibration minimums). Changing values changes physics results. |
| `runs/real_evidence_*/` | Rendered evidence frames referenced by the dashboard via `evidence_dir` column. |
| `FLUID_NOTES.md`, `PERCEPTION_NOTES.md`, `PET_ENGINE_FINDINGS.md` | Research & validation notes. Not UI. |

---

## 7. Data contract

The dashboard reads two SQLite tables from `nearmiss.db`:

### `events` (one row per detected near-miss)

| Column | Type | Example |
|---|---|---|
| `event_id` | TEXT (PK) | `20250526_video_Traj_ped894_veh871` |
| `scene` | TEXT | `20250526_video_Traj` |
| `ped_id` | INTEGER | `894` |
| `veh_id` | INTEGER | `871` |
| `conflict_time_s` | REAL | `375.6` |
| `closest_approach_m` | REAL | `1.37` |
| `our_pet_s` | REAL | `0.00` |
| `severity` | TEXT | `critical` / `serious` / `moderate` |
| `spark_status` | TEXT | `supported` / `supported_with_flag` / `rejected` / `unclear` / `not_yet_reviewed` |
| `spark_flags` | TEXT (JSON array) | `["ped_visibility_marginal_at_4K"]` |
| `spark_observation` | TEXT | free-text from Muse Spark |
| `needs_human_review` | INTEGER (bool) | `1` / `0` |
| `human_review_status` | TEXT | `pending` / `confirmed` / `dismissed` / `escalated` |
| `human_review_note` | TEXT | analyst note |
| `evidence_dir` | TEXT | filesystem path to the 7 evidence frames |
| `created_at`, `updated_at` | TEXT | ISO timestamps |

### `coverage` (one row per processed recording session)

| Column | Type | Example |
|---|---|---|
| `scene` | TEXT (PK) | `20250526_video_Traj` |
| `duration_s` | REAL | `1729.2` |
| `ped_count`, `veh_count` | INTEGER | `322`, `922` |
| `candidate_pair_count` | INTEGER | `1080` |
| `event_count` | INTEGER | `28` |
| `critical_count`, `serious_count`, `moderate_count` | INTEGER | `17`, `4`, `7` |
| `median_pet_s`, `min_pet_s` | REAL | `0.35`, `0.00` |
| `processed_at` | TEXT | ISO timestamp |

---

## 8. Preserved functions

Do not rename or change the signatures of these — the dashboard depends on them:

```python
@st.cache_data(ttl=5)
def load_events() -> pd.DataFrame

@st.cache_data(ttl=5)
def load_coverage() -> pd.DataFrame

def write_review(event_id: str, status: str, note: str) -> None
# Writes human analyst decision back to the events table.

def safe_str(v) -> str | None
# Treats NaN/None as None so os.path checks don't throw.

def pretty_session(scene: str) -> str
# Converts "20250526_video_Traj" -> "Session · 26 May 2025"

def kpi_card(label, value, flavor='k-blue', val_cls='v-blue', subtitle=None) -> str
# Returns HTML for a KPI card.

def sev_chip(sev: str) -> str
# Returns HTML for a severity chip (red/orange/green).

def theme_plot(fig, height=320)
# Applies dark theme to a Plotly figure.
```

Preserve the 5 page names and their ordering in the sidebar:
```python
PAGE = st.sidebar.radio("", ["Overview", "Events", "Review Queue", "Coverage", "Reports"], ...)
```

---

## 9. Design tokens (current)

```
--bg:       #0a0e1a    (background, deep navy)
--panel:    #141928    (card background)
--panel-2:  #1b2137    (nested card / code block)
--border:   #253050    (subtle border)
--text:     #e8edf5    (primary text)
--muted:    #8690a6    (secondary text)
--brand:    #5f8fff    (primary action, blue)
--accent:   #a855f7    (gradient partner, purple)
--crit:     #ff4466    (critical severity, red)
--ser:      #ffa441    (serious severity, orange)
--mod:      #44dd99    (moderate severity, green)

Fonts: Inter (300-900), JetBrains Mono (400, 500) — both via Google Fonts.
```

Feel free to rework these entirely — but keep the three-level severity colour language (red / orange / green) because it maps to engineering convention and we don't want to confuse analysts.

---

## 10. How to test your changes

After editing:

```powershell
cd D:\META\nearmiss
.\.venv\Scripts\Activate.ps1
streamlit run nearmiss\dashboard.py
```

Open http://localhost:8501 and walk through all 5 pages:

- [ ] Overview page loads, shows 45 total / 22 critical / 10 Spark reviewed (or current numbers)
- [ ] Severity bar chart and PET histogram render
- [ ] Per-session cards show for 3 sessions
- [ ] Events page filters work (scene / severity / review state)
- [ ] Inspecting any Spark-reviewed event shows the 7 evidence frames inline
- [ ] Review Queue shows pending events, Confirm/Dismiss/Escalate writes to DB
- [ ] Coverage page shows per-session stats for all 3 sessions
- [ ] Reports page: pick a session, click Generate, preview renders inline, Download HTML button saves to `runs/`

If any of these break, roll back and reconsider.

---

## 11. Scope guardrails

- **Do not add new features** — polish what's there. The product is complete; this is a visual refresh.
- **Do not change the information architecture** (which page shows what). Users have been briefed on the current layout.
- **Do not add external JavaScript libraries** beyond what Streamlit allows. CSS is fine, inline SVG is fine, Plotly is fine.
- **Do not break mobile** — the landing page especially must look good at phone width (<900px). The dashboard is desktop-primary.

---

## 12. Done when

- All 5 dashboard pages have been visually reworked consistently
- The Authority Report (generated from the Reports page) matches the new visual language
- The landing page (`marketing/index.html`) matches the new visual language
- A judge opening the project cold goes *"oh — this is a product, not a prototype"*

Good luck.
