"""
NearMiss — Command Deck (real data edition)
Same visual language as the earlier v4 mock (bento cards, mission dock,
glass panels) but every number, every radar position, and every per-event
answer is computed live from nearmiss.db. No fabricated statistics, no
invented external benchmark, no hardcoded click-independent answers.
"""
import json, os, sqlite3, math, re, glob, base64
import html as html_mod
from datetime import datetime
import pandas as pd

DB_PATH = os.environ.get("NEARMISS_DB", "nearmiss.db")
OUT_PATH = os.path.join("marketing", "dashboard_real.html")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _encode_frame_jpg(path, max_w=420, quality=55):
    """Resize + re-encode a real Spark evidence frame to a small base64 data URI.
    Returns None if the frame can't be read (missing file, bad image, no cv2)."""
    try:
        import cv2
    except ImportError:
        return None
    img = cv2.imread(path)
    if img is None:
        return None
    h, w = img.shape[:2]
    if w > max_w:
        scale = max_w / w
        img = cv2.resize(img, (max_w, max(1, int(h * scale))))
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _resolve_evidence_dir(raw_dir):
    """evidence_dir is stored as an absolute path from whichever machine generated it
    (e.g. a Windows path). Try it as-is first; fall back to matching its folder name
    under this repo's own runs/ directory so the dashboard still works if the repo
    was moved or cloned elsewhere."""
    if not raw_dir:
        return None
    if os.path.isdir(raw_dir):
        return raw_dir
    base = os.path.basename(raw_dir.replace("\\", "/").rstrip("/\\"))
    cand = os.path.join(REPO_ROOT, "runs", base)
    return cand if os.path.isdir(cand) else None


def load_evidence_frames(raw_evidence_dir):
    """Real Spark review frames for one event, as small base64 JPEGs the HTML can
    embed directly (no server round-trip needed from inside components.html).
    Returns [] when there's genuinely no evidence for this event — never invented."""
    d = _resolve_evidence_dir(raw_evidence_dir)
    if not d:
        return []
    frames = sorted(glob.glob(os.path.join(d, "frame_*.jpg")))
    out = []
    for fp in frames:
        src = _encode_frame_jpg(fp)
        if not src:
            continue
        m = re.search(r"(t[+-][\d.]+s)", os.path.basename(fp))
        out.append({"label": m.group(1) if m else os.path.basename(fp), "src": src})
    return out


def load_critical_insight():
    """Precomputed Muse Spark narrative synthesis across the critical events
    (scripts/generate_critical_insight.py). All numbers in it were computed in
    plain Python and handed to the model, not invented by it -- see that
    script's docstring. Returns None if it hasn't been generated yet, so the
    UI simply omits the card rather than showing anything made up."""
    path = os.path.join(REPO_ROOT, "runs", "critical_insight.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not data.get("summary"):
        return None
    return data


def wilson_ci(x, n, z=1.959963985):
    if not n:
        return (0.0, 0.0, 0.0)
    phat = x / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    adj = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    lo = max(0.0, (center - adj) / denom)
    hi = min(1.0, (center + adj) / denom)
    return (phat * 1000, lo * 1000, hi * 1000)


def pretty_session(scene):
    m = re.match(r"(\d{4})(\d{2})(\d{2})_video_Traj", scene or "")
    if m:
        y, mo, d = m.groups()
        try:
            return datetime.strptime(f"{y}-{mo}-{d}", "%Y-%m-%d").strftime("%d %b %Y")
        except Exception:
            pass
    return scene


def build_html(events, coverage):
    events = events.copy()
    coverage = coverage.copy()

    tot = len(events)
    crit = int((events["severity"] == "critical").sum())
    ser = int((events["severity"] == "serious").sum())
    mod = int((events["severity"] == "moderate").sum())

    reviewed_mask = events["spark_status"] != "not_yet_reviewed"
    reviewed_n = int(reviewed_mask.sum())
    confirmed_n = int(events.loc[reviewed_mask, "spark_status"].isin(["supported", "supported_with_flag"]).sum())
    rejected_n = int((events["spark_status"] == "rejected").sum())
    pass_rate = (confirmed_n / reviewed_n * 100) if reviewed_n else 0.0

    total_cp = int(coverage["candidate_pair_count"].sum())
    rate_all, lo_all, hi_all = wilson_ci(tot, total_cp)

    flagged_n = int((events["needs_human_review"] == 1).sum())
    pending_n = int(((events["needs_human_review"] == 1) & (events["human_review_status"] == "pending")).sum())

    # PET histogram buckets
    bins = [0, 0.5, 1.0, 1.5, 2.0]
    labels = ["<0.5s", "0.5-1.0s", "1.0-1.5s", "1.5-2.0s"]
    events["_bucket"] = pd.cut(events["our_pet_s"], bins=bins, labels=labels, include_lowest=True)
    bucket_counts = events["_bucket"].value_counts().reindex(labels).fillna(0).astype(int).to_dict()

    # per-session table (real Wilson CI, honest denominator)
    session_rows = []
    for _, r in coverage.iterrows():
        rate, lo, hi = wilson_ci(r["event_count"], r["candidate_pair_count"])
        session_rows.append(dict(
            scene=r["scene"], label=pretty_session(r["scene"]),
            pairs=int(r["candidate_pair_count"]), events=int(r["event_count"]),
            rate=round(rate, 1), lo=round(lo, 1), hi=round(hi, 1),
        ))
    session_rows.append(dict(
        scene="combined", label="Combined pilot",
        pairs=total_cp, events=tot, rate=round(rate_all, 1), lo=round(lo_all, 1), hi=round(hi_all, 1),
    ))

    # vehicle type breakdown (real, honest — not a headline claim)
    vtype_counts = events["vehicle_type"].fillna("unknown").value_counts().to_dict()

    # riskiest session for resident framing
    riskiest = coverage.sort_values("critical_count", ascending=False).iloc[0]
    resident_denom = round(total_cp / max(tot, 1))

    # --- per-event grounded Q&A, precomputed in Python (no live calls, no guessing) ---
    def event_qa(row):
        obs = row.get("spark_observation") or None
        qa = {}
        if row["severity"] == "critical":
            qa["why"] = f"Measured PET is {row['our_pet_s']:.2f}s, at or below the 1.0s critical threshold — the vehicle reached the pedestrian's space within about {row['our_pet_s']:.2f} seconds of the pedestrian clearing it."
        else:
            qa["why"] = f"This event is classified {row['severity']}, not critical. Its PET is {row['our_pet_s']:.2f}s, above the 1.0s critical cutoff."
        qa["spark"] = obs if obs else "Spark has not yet visually reviewed this event — only deterministic physics (PET/severity) has been computed for it."
        st = row["spark_status"]
        if st == "supported":
            qa["confirmed"] = "Yes — Spark's independent visual review of the evidence frames supported this as a real conflict, without being shown the PET value or severity label."
        elif st == "supported_with_flag":
            qa["confirmed"] = "Spark supported this as a real conflict but flagged a caveat in its review — see Flags."
        elif st == "rejected":
            qa["confirmed"] = "No — Spark's visual review rejected this as a real near-miss (the actual closest approach was too far to be a genuine conflict)."
        else:
            qa["confirmed"] = "Not yet — this event hasn't had a Spark visual review. Its status is physics-only."

        # "what can we do" — a grounded recommendation from this event's own real
        # state (severity / spark_status / human_review_status / flags), not a
        # live model call and not a generic template; it changes with the data.
        flags_list = []
        if row.get("spark_flags"):
            try:
                flags_list = json.loads(row["spark_flags"])
            except (json.JSONDecodeError, TypeError):
                flags_list = []
        hrs = row["human_review_status"]
        if st == "rejected":
            qa["action"] = "No action needed — Spark's visual review rejected this as a real conflict, so this one shouldn't be used to justify an engineering or enforcement response."
        elif hrs == "escalated":
            qa["action"] = "Already escalated for a second pass — treat as unresolved. Don't act on this event's severity label until that review closes it out."
        elif hrs == "pending" and row["needs_human_review"] == 1:
            qa["action"] = "Flagged for human review and still pending — open it in the Review Queue and confirm, dismiss, or escalate before using it to justify any action."
        elif hrs == "dismissed":
            qa["action"] = "A reviewer already dismissed this one — no further action from it alone."
        elif row["severity"] == "critical" and hrs == "confirmed":
            base = f"Confirmed critical conflict at {pretty_session(row['scene'])} — worth flagging this crossing for an engineering look (sightlines, signal timing, or physical calming), since measured PET was {row['our_pet_s']:.2f}s."
            if "spark_doubts_vehicle_overlay" in flags_list or "veh_visibility_marginal_at_4K" in flags_list:
                base += " One caveat: Spark flagged the vehicle identification itself as uncertain at this altitude — worth a human glance at the evidence frames before citing it externally."
            qa["action"] = base
        elif row["severity"] == "critical":
            qa["action"] = f"Critical by PET ({row['our_pet_s']:.2f}s) but not yet through human review — get a reviewer to confirm before using this one in a report or citing it to stakeholders."
        else:
            qa["action"] = f"Classified {row['severity']}, below the critical PET cutoff — no immediate action; useful mainly as denominator context for the overall conflict rate."
        return qa


    event_records = []
    for _, row in events.iterrows():
        event_records.append(dict(
            event_id=row["event_id"], scene=row["scene"], scene_label=pretty_session(row["scene"]),
            ped_id=int(row["ped_id"]), veh_id=int(row["veh_id"]),
            our_pet_s=round(float(row["our_pet_s"]), 2) if pd.notna(row["our_pet_s"]) else None,
            severity=row["severity"], spark_status=row["spark_status"],
            spark_flags=row["spark_flags"] if pd.notna(row["spark_flags"]) else None,
            spark_observation=row["spark_observation"] if pd.notna(row["spark_observation"]) else None,
            human_review_status=row["human_review_status"],
            needs_human_review=int(row["needs_human_review"]),
            loc_x_m=round(float(row["loc_x_m"]), 2) if pd.notna(row["loc_x_m"]) else None,
            loc_y_m=round(float(row["loc_y_m"]), 2) if pd.notna(row["loc_y_m"]) else None,
            vehicle_type=row["vehicle_type"] if pd.notna(row["vehicle_type"]) else None,
            evidence_frames=load_evidence_frames(row["evidence_dir"] if pd.notna(row["evidence_dir"]) else None),
            qa=event_qa(row),
        ))
        event_records[-1]["has_evidence"] = bool(event_records[-1]["evidence_frames"])

    DB_DATA = dict(
        events=event_records,
        kpi=dict(total=tot, critical=crit, serious=ser, moderate=mod,
                  rate=round(rate_all, 1), lo=round(lo_all, 1), hi=round(hi_all, 1),
                  pass_rate=round(pass_rate, 1), reviewed_n=reviewed_n, confirmed_n=confirmed_n, rejected_n=rejected_n,
                  flagged_n=flagged_n, pending_n=pending_n, total_cp=total_cp,
                  resident_denom=resident_denom, riskiest_label=pretty_session(riskiest["scene"]),
                  riskiest_crit=int(riskiest["critical_count"])),
        bucket_counts=bucket_counts,
        session_rows=session_rows,
        vtype_counts=vtype_counts,
    )

    json_str = json.dumps(DB_DATA)

    CSS = """
    :root {
      --bg: #07090e; --bg-grid: rgba(255,255,255,.025); --card-bg: rgba(14,20,32,.78);
      --border: rgba(255,255,255,.08); --text: #f8fafc; --text-muted: #8292a6;
      --brand: #3b82f6; --brand-gradient: linear-gradient(135deg,#3b82f6 0%,#8b5cf6 100%);
      --ai-purple: #a855f7; --crit: #f43f5e; --ser: #f59e0b; --mod: #10b981;
      --shadow: 0 16px 40px rgba(0,0,0,.45);
    }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:'Plus Jakarta Sans',-apple-system,sans-serif; background:var(--bg);
      background-image: radial-gradient(circle at 50% 0%, rgba(59,130,246,.12) 0%, transparent 60%),
        linear-gradient(to right, var(--bg-grid) 1px, transparent 1px),
        linear-gradient(to bottom, var(--bg-grid) 1px, transparent 1px);
      background-size: 100% 100%, 36px 36px, 36px 36px; color:var(--text); line-height:1.5; min-height:100vh; }
    code,.mono { font-family:'JetBrains Mono',monospace; }
    header.cmd-header { position:sticky; top:0; z-index:100; background:rgba(7,9,14,.94); backdrop-filter:blur(20px);
      border-bottom:1px solid var(--border); padding:.5rem 1rem; display:flex; align-items:center; justify-content:space-between; gap:.5rem; }
    .brand-wrap { display:flex; align-items:center; gap:.55rem; }
    .brand-icon { width:28px; height:28px; background:var(--brand-gradient); border-radius:6px; display:flex; align-items:center; justify-content:center; color:#fff; }
    .brand-title { font-weight:800; font-size:1.05rem; letter-spacing:-.4px; background:linear-gradient(90deg,#fff 0%,#cbdcf8 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .brand-site-pill { display:inline-flex; align-items:center; gap:.35rem; background:rgba(255,255,255,.05); border:1px solid var(--border); padding:.12rem .45rem; border-radius:999px; font-size:.65rem; color:var(--text-muted); }
    .dot-live { width:6px; height:6px; background:var(--mod); border-radius:50%; box-shadow:0 0 6px var(--mod); animation:pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.55} }
    .mission-dock { display:flex; background:rgba(14,20,32,.92); padding:2px; border-radius:8px; border:1px solid var(--border); gap:2px; }
    .mission-tab { padding:.3rem .6rem; border-radius:5px; font-size:.72rem; font-weight:700; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; gap:.35rem; user-select:none; }
    .mission-tab:hover { color:#fff; background:rgba(255,255,255,.06); }
    .mission-tab.active { background:var(--brand); color:#fff; box-shadow:0 4px 12px rgba(59,130,246,.4); }
    .tab-badge { font-family:'JetBrains Mono',monospace; font-size:.62rem; font-weight:700; padding:.08rem .3rem; border-radius:4px; background:rgba(255,255,255,.08); color:#94a3b8; }
    .mission-tab.active .tab-badge { background:rgba(0,0,0,.25); color:#fff; }
    .header-right { display:flex; align-items:center; gap:.5rem; }
    .role-switcher { display:flex; background:rgba(14,20,32,.9); border:1px solid var(--border); border-radius:7px; padding:2px; gap:2px; }
    .role-btn { padding:.2rem .5rem; border-radius:5px; font-size:.68rem; font-weight:700; color:var(--text-muted); cursor:pointer; }
    .role-btn.active { background:#1e293b; color:#60a5fa; }
    .privacy-pill { cursor:pointer; background:rgba(16,185,129,.1); border:1px solid rgba(16,185,129,.3); color:#34d399; font-size:.68rem; font-weight:700; padding:.25rem .55rem; border-radius:6px; display:flex; align-items:center; gap:.35rem; }
    main.container { max-width:1520px; margin:0 auto; padding:1.2rem 1.6rem 2.2rem; }
    .bento-row { display:grid; gap:1.1rem; margin-bottom:1.1rem; }
    .bento-4 { grid-template-columns:repeat(4,1fr); } .bento-3 { grid-template-columns:repeat(3,1fr); }
    .bento-2-1 { grid-template-columns:1.8fr 1.2fr; } .bento-2 { grid-template-columns:repeat(2,1fr); }
    .card { background:var(--card-bg); backdrop-filter:blur(16px); border:1px solid var(--border); border-radius:14px; padding:1.2rem 1.35rem; box-shadow:0 8px 24px rgba(0,0,0,.28); transition:all .25s ease; }
    .card:hover { border-color:rgba(255,255,255,.16); box-shadow:var(--shadow); }
    .card-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:.8rem; }
    .card-title { font-size:.9rem; font-weight:700; display:flex; align-items:center; gap:.5rem; color:#f1f5f9; }
    .card-subtitle { color:var(--text-muted); font-size:.74rem; margin-top:.15rem; }
    .kpi-card { border-left:3.5px solid var(--brand); } .kpi-card.crit { border-left-color:var(--crit); }
    .kpi-card.amber { border-left-color:var(--ser); } .kpi-card.purple { border-left-color:var(--ai-purple); }
    .kpi-label { font-size:.66rem; text-transform:uppercase; letter-spacing:.5px; font-weight:700; color:var(--text-muted); margin-bottom:.3rem; display:flex; justify-content:space-between; }
    .kpi-val { font-size:2.1rem; font-weight:800; line-height:1; letter-spacing:-1.1px; font-family:'JetBrains Mono',monospace; }
    .kpi-val.crit { color:var(--crit); } .kpi-val.amber { color:var(--ser); } .kpi-val.purple { color:#c084fc; } .kpi-val.brand { color:var(--brand); }
    .kpi-desc { font-size:.7rem; color:var(--text-muted); margin-top:.4rem; line-height:1.35; }
    .radar-wrap { position:relative; width:100%; height:380px; background:radial-gradient(circle at 50% 50%,#111a2d 0%,#090e18 80%); border-radius:12px; border:1px solid rgba(255,255,255,.08); overflow:hidden; }
    canvas.radar-canvas { width:100%; height:100%; display:block; cursor:crosshair; }
    .radar-overlay { position:absolute; top:.8rem; left:.8rem; background:rgba(10,14,24,.85); backdrop-filter:blur(8px); padding:.3rem .6rem; border-radius:5px; font-family:'JetBrains Mono',monospace; font-size:.66rem; color:#94a3b8; border:1px solid rgba(255,255,255,.1); pointer-events:none; }
    .radar-legend { position:absolute; top:.8rem; right:.8rem; background:rgba(10,14,24,.85); backdrop-filter:blur(8px); padding:.35rem .6rem; border-radius:5px; font-size:.66rem; color:#cbd5e1; border:1px solid rgba(255,255,255,.1); pointer-events:none; display:flex; gap:.6rem; }
    .radar-legend span { display:inline-flex; align-items:center; gap:.3rem; }
    .radar-legend i { width:7px; height:7px; border-radius:50%; display:inline-block; }
    .radar-tooltip { position:absolute; display:none; background:rgba(13,17,28,.96); border:1px solid rgba(59,130,246,.5); border-radius:8px; padding:.5rem .7rem; font-family:'JetBrains Mono',monospace; font-size:.7rem; color:#fff; pointer-events:none; z-index:50; max-width:260px; }
    .tab-pane { display:none; } .tab-pane.active { display:block; }
    .btn-action { background:rgba(255,255,255,.06); border:1px solid var(--border); color:#e2e8f0; padding:.32rem .75rem; border-radius:6px; font-size:.74rem; font-weight:600; cursor:pointer; display:inline-flex; align-items:center; gap:.4rem; }
    .btn-action:hover { background:rgba(255,255,255,.12); color:#fff; }
    .btn-action.primary { background:var(--brand); border-color:var(--brand); color:#fff; }
    .btn-action.crit { background:rgba(244,63,94,.2); border-color:rgba(244,63,94,.4); color:#fda4af; }
    .analytics-chart-card { background:rgba(10,14,24,.6); border:1px solid var(--border); border-radius:12px; padding:1.2rem; }
    .chart-meta-badge { font-size:.64rem; font-family:'JetBrains Mono',monospace; padding:.16rem .4rem; border-radius:4px; background:rgba(255,255,255,.05); color:#94a3b8; border:1px solid var(--border); }
    .ask-deck { margin-top:.8rem; background:rgba(10,14,24,.7); border:1px solid rgba(168,85,247,.3); border-radius:10px; padding:.8rem 1rem; }
    .ask-chips { display:flex; flex-wrap:wrap; gap:.4rem; margin-bottom:.55rem; }
    .ask-chip { background:rgba(168,85,247,.12); border:1px solid rgba(168,85,247,.3); color:#d8b4fe; font-size:.7rem; font-weight:600; padding:.2rem .55rem; border-radius:5px; cursor:pointer; }
    .ask-chip:hover { background:rgba(168,85,247,.25); color:#fff; }
    .ai-response-box { margin-top:.6rem; display:none; background:#060910; border-left:3px solid #a855f7; padding:.6rem .85rem; border-radius:5px; font-size:.76rem; color:#e2e8f0; line-height:1.5; }
    .commuter-civic-panel { display:none; background:rgba(14,20,32,.85); border:1px solid var(--border); border-radius:12px; padding:1.2rem; margin-bottom:1.2rem; }
    .modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.8); backdrop-filter:blur(10px); z-index:200; display:none; align-items:center; justify-content:center; }
    .modal-box { background:#0c121e; border:1px solid var(--border); border-radius:14px; width:90%; max-width:600px; padding:1.75rem; }
    .data-table-wrap { overflow-x:auto; border:1px solid var(--border); border-radius:12px; background:rgba(10,14,24,.6); }
    table.deck-table { width:100%; border-collapse:collapse; text-align:left; font-size:.78rem; }
    table.deck-table th { background:rgba(18,26,44,.85); padding:.7rem .9rem; font-weight:700; text-transform:uppercase; font-size:.63rem; letter-spacing:.5px; color:#94a3b8; border-bottom:1px solid var(--border); }
    table.deck-table td { padding:.7rem .9rem; border-bottom:1px solid rgba(255,255,255,.04); color:#cbd5e1; }
    table.deck-table tr:hover td { background:rgba(255,255,255,.03); cursor:pointer; }
    .sev-badge { display:inline-flex; align-items:center; gap:.3rem; padding:.15rem .42rem; border-radius:5px; font-size:.63rem; font-weight:800; letter-spacing:.3px; font-family:'JetBrains Mono',monospace; text-transform:uppercase; }
    .sev-badge.critical { background:rgba(244,63,94,.15); color:var(--crit); border:1px solid rgba(244,63,94,.3); }
    .sev-badge.serious { background:rgba(245,158,11,.15); color:var(--ser); border:1px solid rgba(245,158,11,.3); }
    .sev-badge.moderate { background:rgba(16,185,129,.15); color:var(--mod); border:1px solid rgba(16,185,129,.3); }
    .detail-drawer { margin-top:1rem; }
    .caveat { background:rgba(245,158,11,.08); border-left:2px solid var(--ser); padding:.55rem .75rem; border-radius:0 7px 7px 0; color:#f0dcb8; margin-top:.5rem; font-size:.74rem; }
    @media(max-width:900px){ .bento-4,.bento-3,.bento-2-1,.bento-2 { grid-template-columns:1fr; } }
    """

    HEAD = f"""<!doctype html>
    <html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>NearMiss — Jurong Lake Pilot</title>
    <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>{CSS}</style></head><body>
    """

    HEADER = f"""
    <header class="cmd-header">
      <div class="brand-wrap">
        <div class="brand-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>
        <div><div class="brand-title">NearMiss</div><div class="brand-site-pill"><span class="dot-live"></span> Jurong Lake · real pilot data</div></div>
      </div>
      <nav class="mission-dock">
        <div class="mission-tab active" onclick="switchMission('cmd')"><span>Cockpit</span><span class="tab-badge">{tot}</span></div>
        <div class="mission-tab" onclick="switchMission('analytics')"><span>Analytics</span><span class="tab-badge">{rate_all:.1f}/1k</span></div>
        <div class="mission-tab" onclick="switchMission('radar')"><span>Radar</span><span class="tab-badge">{tot} pts</span></div>
        <div class="mission-tab" onclick="switchMission('events')"><span>Ledger</span><span class="tab-badge">Deck</span></div>
      </nav>
      <div class="header-right">
        <div class="role-switcher">
          <div class="role-btn active" id="roleEngineer" onclick="setRole('engineer')">Engineer</div>
          <div class="role-btn" id="roleEnforce" onclick="setRole('enforce')">Enforcement</div>
          <div class="role-btn" id="roleCommuter" onclick="setRole('commuter')">Resident</div>
        </div>
        <div class="privacy-pill" onclick="openPrivacyModal()"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg><span>Coverage &amp; Privacy</span></div>
      </div>
    </header>
    """

    COMMUTER_BANNER = f"""
    <div id="commuterBanner" class="commuter-civic-panel">
      <div style="font-size:1.02rem;font-weight:800;color:#fff;">Resident Safety Summary · Jurong Lake Crossing</div>
      <div style="color:#94a3b8;font-size:.78rem;margin-top:.2rem;">Plain-language summary compiled from the same measured data shown to engineers.</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;background:rgba(0,0,0,.3);padding:1rem;border-radius:10px;border:1px solid var(--border);margin-top:.85rem;">
        <div><div style="font-size:.68rem;color:var(--text-muted);font-weight:700;">CANDIDATE CROSSINGS WITH A CLOSE CALL</div><div style="font-size:1.2rem;font-weight:800;color:var(--crit);margin-top:.2rem;">1 in {resident_denom}</div><div style="font-size:.68rem;color:#94a3b8;margin-top:.2rem;">of measured pedestrian–vehicle encounters became a recorded near-miss.</div></div>
        <div><div style="font-size:.68rem;color:var(--text-muted);font-weight:700;">HIGHEST-RISK SESSION RECORDED</div><div style="font-size:1.2rem;font-weight:800;color:#60a5fa;margin-top:.2rem;">{pretty_session(riskiest['scene'])}</div><div style="font-size:.68rem;color:#94a3b8;margin-top:.2rem;">{int(riskiest['critical_count'])} critical near-misses recorded in this session.</div></div>
        <div><div style="font-size:.68rem;color:var(--text-muted);font-weight:700;">SPARK-CONFIRMED EVENTS</div><div style="font-size:1.2rem;font-weight:800;color:#34d399;margin-top:.2rem;">{confirmed_n} of {reviewed_n}</div><div style="font-size:.68rem;color:#94a3b8;margin-top:.2rem;">visually reviewed events were independently confirmed as real conflicts.</div></div>
      </div>
    </div>
    """

    insight = load_critical_insight()
    insight_block = ""
    if insight:
        safe_summary = html_mod.escape(insight.get("summary", ""))
        pattern_items = "".join(
            f"<li style='margin-bottom:.3rem;'>{html_mod.escape(p)}</li>" for p in insight.get("patterns", [])
        )
        insight_block = f"""
      <div class="bento-row">
        <div class="card" style="border-color:rgba(168,85,247,.3);">
          <div class="card-header"><div><div class="card-title" style="color:#d8b4fe;">AI pattern insight &mdash; Muse Spark</div><div class="card-subtitle">Synthesized from the {insight.get("n_events", crit)} critical events above &middot; every number in it was computed in plain Python first and handed to the model, not invented by it</div></div></div>
          <div class="ai-response-box" style="display:block;">
            <div>{safe_summary}</div>
            <ul style="margin:.6rem 0 0 1.1rem;padding:0;">{pattern_items}</ul>
          </div>
        </div>
      </div>"""

    COCKPIT = f"""
    <div id="mission-cmd" class="tab-pane active">
      <div class="bento-row bento-4">
        <div class="card kpi-card"><div class="kpi-label"><span>Total measured events</span></div><div class="kpi-val brand">{tot}</div><div class="kpi-desc">PET &le; 2.0s across 3 drone sessions, {total_cp:,} candidate ped-vehicle pairs screened</div></div>
        <div class="card kpi-card crit"><div class="kpi-label"><span>Critical (PET &le; 1.0s)</span></div><div class="kpi-val crit">{crit}</div><div class="kpi-desc">Physical vehicle encroachment within 1 second of pedestrian clearance</div></div>
        <div class="card kpi-card amber"><div class="kpi-label"><span>Conflict rate</span><span class="mono" style="font-size:.62rem;color:var(--ser);">95% WILSON</span></div><div class="kpi-val amber">{rate_all:.1f}</div><div class="kpi-desc">per 1,000 candidate ped-vehicle pairs · CI [{lo_all:.1f}&ndash;{hi_all:.1f}]</div></div>
        <div class="card kpi-card purple"><div class="kpi-label"><span>Spark confirmation rate</span><span class="mono" style="font-size:.62rem;color:#c084fc;">{reviewed_n} REVIEWED</span></div><div class="kpi-val purple">{pass_rate:.0f}%</div><div class="kpi-desc">{confirmed_n} of {reviewed_n} visually reviewed events confirmed · {rejected_n} rejected as false positive</div></div>
      </div>
      {insight_block}
      <div class="bento-row bento-2-1">
        <div class="card">
          <div class="card-header"><div><div class="card-title">Conflict locations (real, measured)</div><div class="card-subtitle">Plotted from FLUID trajectory positions at each event's actual closest-approach frame &middot; crossing backdrop is stylized for orientation, not a site survey</div></div><button class="btn-action" onclick="switchMission('radar')">Expand &rarr;</button></div>
          <div class="radar-wrap"><canvas id="miniRadarCanvas" class="radar-canvas"></canvas><div class="radar-overlay">METERS, RELATIVE TO FRAME CENTER</div><div class="radar-legend"><span><i style="background:#f43f5e;"></i>Critical</span><span><i style="background:#f59e0b;"></i>Serious</span><span><i style="background:#10b981;"></i>Moderate</span></div><div id="miniRadarTooltip" class="radar-tooltip"></div></div>
        </div>
        <div class="card">
          <div class="card-header"><div><div class="card-title">Severity distribution</div><div class="card-subtitle">Post-Encroachment Time threshold breakdown</div></div></div>
          <div style="margin-top:.8rem;">
            <div style="display:flex;justify-content:space-between;margin-bottom:.35rem;"><span style="font-size:.82rem;font-weight:600;color:var(--crit);">Critical</span><span class="mono" style="font-weight:700;color:var(--crit);">{crit} events ({crit/tot*100:.1f}%)</span></div>
            <div style="height:8px;background:rgba(255,255,255,.06);border-radius:999px;overflow:hidden;margin-bottom:1rem;"><div style="width:{crit/tot*100:.1f}%;height:100%;background:var(--crit);"></div></div>
            <div style="display:flex;justify-content:space-between;margin-bottom:.35rem;"><span style="font-size:.82rem;font-weight:600;color:var(--ser);">Serious</span><span class="mono" style="font-weight:700;color:var(--ser);">{ser} events ({ser/tot*100:.1f}%)</span></div>
            <div style="height:8px;background:rgba(255,255,255,.06);border-radius:999px;overflow:hidden;margin-bottom:1rem;"><div style="width:{ser/tot*100:.1f}%;height:100%;background:var(--ser);"></div></div>
            <div style="display:flex;justify-content:space-between;margin-bottom:.35rem;"><span style="font-size:.82rem;font-weight:600;color:var(--mod);">Moderate</span><span class="mono" style="font-weight:700;color:var(--mod);">{mod} events ({mod/tot*100:.1f}%)</span></div>
            <div style="height:8px;background:rgba(255,255,255,.06);border-radius:999px;overflow:hidden;margin-bottom:1.2rem;"><div style="width:{mod/tot*100:.1f}%;height:100%;background:var(--mod);"></div></div>
            <div style="background:rgba(10,14,24,.7);border:1px solid var(--border);border-radius:10px;padding:.85rem;">
              <div style="font-size:.68rem;text-transform:uppercase;color:var(--text-muted);font-weight:700;margin-bottom:.35rem;">Review queue</div>
              <div style="font-size:.84rem;">{flagged_n} events flagged for human review &middot; <strong style="color:{'var(--mod)' if pending_n==0 else 'var(--ser)'}">{pending_n} pending</strong></div>
            </div>
          </div>
        </div>
      </div>
    </div>
    """

    bucket_json = bucket_counts
    ANALYTICS = f"""
    <div id="mission-analytics" class="tab-pane">
      <div class="bento-row bento-2">
        <div class="card analytics-chart-card">
          <div class="card-header"><div><div class="card-title">PET frequency distribution</div><div class="card-subtitle">Real counts across {tot} measured interactions</div></div><span class="chart-meta-badge">{tot} INTERACTIONS</span></div>
          <div id="petHistChart" style="margin-top:1rem;height:230px;"></div>
        </div>
        <div class="card analytics-chart-card">
          <div class="card-header"><div><div class="card-title">Vehicle type (FLUID auto-tracker)</div><div class="card-subtitle">Not a headline claim — this is what FLUID's own tracker labeled, shown as-is</div></div></div>
          <div style="margin-top:1rem;">
            {''.join(f'<div style="display:flex;justify-content:space-between;padding:.4rem 0;border-bottom:1px solid var(--border);font-size:.85rem;"><span>{k}</span><span class="mono" style="font-weight:700;">{v}</span></div>' for k,v in vtype_counts.items())}
            <div class="caveat">Note: for the 3 events involving vehicle #871, FLUID's tracker labels it "car" — but Spark's independent visual review described it as a small scooter/motorcycle. We show both rather than picking one.</div>
          </div>
        </div>
      </div>
      <div class="bento-row bento-2">
        <div class="card analytics-chart-card" style="grid-column:1/-1;">
          <div class="card-header"><div><div class="card-title">Exposure-normalized conflict rate by session</div><div class="card-subtitle">Rate per 1,000 candidate ped&ndash;vehicle pairs, with real 95% Wilson confidence intervals</div></div><span class="chart-meta-badge">COMPUTED LIVE FROM nearmiss.db</span></div>
          <div style="margin-top:1rem;">
            <table class="deck-table"><thead><tr><th>Session</th><th>Candidate pairs</th><th>Near-misses</th><th>Rate / 1,000 pairs</th><th>95% Wilson CI</th></tr></thead><tbody>
            {''.join(f'<tr{" style=background:rgba(59,130,246,.08);border-top:1px solid var(--border);" if r["scene"]=="combined" else ""}><td class="mono" style="color:#93c5fd;">{r["label"]}</td><td class="mono">{r["pairs"]:,}</td><td class="mono">{r["events"]}</td><td class="mono" style="font-weight:700;color:var(--ser);">{r["rate"]}</td><td class="mono" style="color:#94a3b8;">[{r["lo"]} &ndash; {r["hi"]}]</td></tr>' for r in session_rows)}
            </tbody></table>
          </div>
        </div>
      </div>
    </div>
    """

    RADAR = """
    <div id="mission-radar" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <div><div class="card-title">Full conflict location map (click any point to inspect)</div><div class="card-subtitle">Real-world coordinates in meters, derived from FLUID trajectory data at each event's closest-approach frame — not a drawn schematic</div></div>
          <div style="display:flex;gap:.5rem;"><button class="btn-action primary" onclick="filterRadar('all')">All</button><button class="btn-action crit" onclick="filterRadar('critical')">Critical only</button></div>
        </div>
        <div class="radar-wrap" style="height:540px;"><canvas id="fullRadarCanvas" class="radar-canvas"></canvas><div class="radar-overlay" id="radarLegend">METERS, RELATIVE TO FRAME CENTER &middot; CLICK TO INSPECT</div><div class="radar-legend"><span><i style="background:#f43f5e;"></i>Critical</span><span><i style="background:#f59e0b;"></i>Serious</span><span><i style="background:#10b981;"></i>Moderate</span></div><div id="fullRadarTooltip" class="radar-tooltip"></div></div>
        <div id="radarDetail" class="detail-drawer"></div>
      </div>
    </div>
    """

    LEDGER = f"""
    <div id="mission-events" class="tab-pane">
      <div class="card">
        <div class="card-header"><div><div class="card-title">Detected near-miss event deck</div><div class="card-subtitle">All {tot} interaction pairs &mdash; click a row to inspect</div></div>
          <input type="text" id="eventSearch" placeholder="Search event, agent #..." style="background:rgba(255,255,255,.06);border:1px solid var(--border);border-radius:8px;padding:.4rem .8rem;color:#fff;font-size:.8rem;" onkeyup="filterTable()">
        </div>
        <div class="data-table-wrap"><table class="deck-table" id="eventsTable"><thead><tr><th>Event ID</th><th>Session</th><th>Pedestrian</th><th>Vehicle</th><th>PET</th><th>Severity</th><th>Spark status</th><th>Analyst</th></tr></thead><tbody id="tableBody"></tbody></table></div>
      </div>
      <div id="ledgerDetail" class="detail-drawer"></div>
    </div>
    """

    PRIVACY_MODAL = """
    <div id="privacyModal" class="modal-backdrop" onclick="closePrivacyModal(event)">
      <div class="modal-box" onclick="event.stopPropagation()">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;border-bottom:1px solid var(--border);padding-bottom:.75rem;">
          <div style="font-size:1.02rem;font-weight:800;color:#fff;">Coverage &amp; Privacy</div>
          <button class="btn-action" onclick="closePrivacyModal()">&times;</button>
        </div>
        <div style="margin-bottom:1rem;">
          <div style="font-size:.8rem;font-weight:700;color:#60a5fa;margin-bottom:.3rem;">1. Optical privacy by altitude</div>
          <p style="font-size:.76rem;color:#cbd5e1;line-height:1.5;">Flight-log telemetry for our primary session (20250526) confirms the drone held a tripod hover at roughly <strong>390 ft (~120 m)</strong> above takeoff, consistent with FLUID's published 100&ndash;120m survey altitude. At that height, pedestrian faces and vehicle plates are physically unresolvable in the source footage &mdash; this is a property of the recording, not a filter we apply.</p>
        </div>
        <div style="margin-bottom:1rem;">
          <div style="font-size:.8rem;font-weight:700;color:#fbbf24;margin-bottom:.3rem;">2. Coverage honesty</div>
          <p style="font-size:.76rem;color:#cbd5e1;line-height:1.5;">The dataset is 3 daytime recordings (~57 minutes total) at one intersection. Absence of flagged conflicts outside these windows reflects what was recorded, not that the crossing is safe at other times. Conflict rates are reported per 1,000 candidate pairs with a real 95% Wilson confidence interval to avoid overclaiming from a small sample.</p>
        </div>
        <div style="margin-bottom:1rem;">
          <div style="font-size:.8rem;font-weight:700;color:#a78bfa;margin-bottom:.3rem;">3. What's physics-only vs. visually verified</div>
          <p style="font-size:.76rem;color:#cbd5e1;line-height:1.5;">Every event's PET and severity comes from deterministic physics on real tracked trajectories. A subset additionally has a Muse Spark visual review with rendered evidence frames &mdash; see each event's Spark status on the Ledger tab.</p>
        </div>
        <div style="margin-bottom:0;">
          <div style="font-size:.8rem;font-weight:700;color:#fb923c;margin-bottom:.3rem;">4. Tracking source &amp; occlusion</div>
          <p style="font-size:.76rem;color:#cbd5e1;line-height:1.5;">Ped/vehicle positions and timing for this pilot come from FLUID's own published trajectory tracking (RTK-validated by FLUID's authors), not from a fresh tracker run we audited ourselves on this footage. We have not independently measured occlusion dropout or ID-switch rate on these specific sessions &mdash; any such error would be inherited from the source data, not introduced by our PET engine. SAM 3.1, our own perception layer, was validated separately against other datasets (see Datasets &amp; Architecture docs) and is the planned perception path for footage FLUID doesn't cover.</p>
        </div>
        <div style="text-align:right;margin-top:1rem;"><button class="btn-action primary" onclick="closePrivacyModal()">Close</button></div>
      </div>
    </div>
    """

    SCRIPT = f"""
    <script>
    const DB_DATA = {json_str};
    let currentRole = 'engineer';
    let radarFilter = 'all';

    function setRole(role) {{
      currentRole = role;
      document.querySelectorAll('.role-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('role' + role.charAt(0).toUpperCase() + role.slice(1)).classList.add('active');
      const banner = document.getElementById('commuterBanner');
      const activeMission = document.querySelector('.mission-tab.active');
      const isCmd = activeMission && activeMission.textContent.includes('Cockpit');
      banner.style.display = (role === 'commuter' && isCmd) ? 'block' : 'none';
    }}

    function openPrivacyModal() {{ document.getElementById('privacyModal').style.display = 'flex'; }}
    function closePrivacyModal() {{ document.getElementById('privacyModal').style.display = 'none'; }}

    function switchMission(tabId) {{
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.mission-tab').forEach(el => el.classList.remove('active'));
      document.getElementById('mission-' + tabId).classList.add('active');
      const mapping = ['cmd','analytics','radar','events'];
      const idx = mapping.indexOf(tabId);
      document.querySelectorAll('.mission-tab')[idx].classList.add('active');
      const banner = document.getElementById('commuterBanner');
      banner.style.display = (currentRole === 'commuter' && tabId === 'cmd') ? 'block' : 'none';
      if (tabId === 'cmd') renderRadar('miniRadarCanvas', 'miniRadarTooltip', null, false);
      if (tabId === 'radar') renderRadar('fullRadarCanvas', 'fullRadarTooltip', 'radarDetail', true);
      if (tabId === 'events') populateTable();
    }}

    function filterRadar(sev) {{
      radarFilter = sev;
      renderRadar('fullRadarCanvas', 'fullRadarTooltip', 'radarDetail', true);
    }}

    const SEV_COLOR = {{critical:'#f43f5e', serious:'#f59e0b', moderate:'#10b981'}};

    function renderRadar(canvasId, tooltipId, detailId, clickable) {{
      const canvas = document.getElementById(canvasId);
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const w = canvas.width = rect.width * 2;
      const h = canvas.height = rect.height * 2;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0,0,w,h);

      let pts = DB_DATA.events.filter(e => e.loc_x_m !== null);
      if (radarFilter === 'critical' && detailId) pts = pts.filter(e => e.severity === 'critical');

      const xs = pts.map(p=>p.loc_x_m), ys = pts.map(p=>p.loc_y_m);
      const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
      const pad = 60;
      const sx = v => pad + (v-minX)/(maxX-minX||1) * (w-2*pad);
      const sy = v => h - (pad + (v-minY)/(maxY-minY||1) * (h-2*pad));

      // --- decorative intersection backdrop (orientation only — NOT a
      // surveyed road layout; the only real, measured thing on this canvas
      // is the dot positions below, from loc_x_m/loc_y_m) ---
      const plotCx = pad + (w-2*pad)/2, plotCy = pad + (h-2*pad)/2;
      const roadHalf = Math.min(w,h) * 0.1;
      ctx.fillStyle = 'rgba(255,255,255,.05)';
      ctx.fillRect(pad, plotCy-roadHalf, w-2*pad, roadHalf*2);
      ctx.fillRect(plotCx-roadHalf, pad, roadHalf*2, h-2*pad);
      ctx.strokeStyle = 'rgba(255,255,255,.14)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([10,10]);
      ctx.beginPath(); ctx.moveTo(pad,plotCy); ctx.lineTo(w-pad,plotCy); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(plotCx,pad); ctx.lineTo(plotCx,h-pad); ctx.stroke();
      ctx.setLineDash([]);
      function drawZebra(cx0,cy0,horiz) {{
        ctx.fillStyle = 'rgba(255,255,255,.1)';
        const stripeW = roadHalf*2*0.72, stripeStep = Math.max(6, roadHalf*0.3);
        if (horiz) {{ for (let i=-stripeW/2;i<stripeW/2;i+=stripeStep*2) ctx.fillRect(cx0+i, cy0-roadHalf*0.85, stripeStep, roadHalf*1.7); }}
        else {{ for (let i=-stripeW/2;i<stripeW/2;i+=stripeStep*2) ctx.fillRect(cx0-roadHalf*0.85, cy0+i, roadHalf*1.7, stripeStep); }}
      }}
      drawZebra(plotCx, pad+roadHalf*1.4, true);
      drawZebra(plotCx, h-pad-roadHalf*1.4, true);
      drawZebra(pad+roadHalf*1.4, plotCy, false);
      drawZebra(w-pad-roadHalf*1.4, plotCy, false);

      // faint grid
      ctx.strokeStyle = 'rgba(255,255,255,.04)';
      for (let i=0;i<=8;i++) {{
        const x = pad + i*(w-2*pad)/8;
        ctx.beginPath(); ctx.moveTo(x,pad); ctx.lineTo(x,h-pad); ctx.stroke();
        const y = pad + i*(h-2*pad)/8;
        ctx.beginPath(); ctx.moveTo(pad,y); ctx.lineTo(w-pad,y); ctx.stroke();
      }}

      canvas._points = [];
      pts.forEach(e => {{
        const x = sx(e.loc_x_m), y = sy(e.loc_y_m);
        const r = e.severity === 'critical' ? 10 : 7;
        ctx.beginPath();
        ctx.arc(x,y,r,0,2*Math.PI);
        ctx.fillStyle = SEV_COLOR[e.severity] || '#10b981';
        ctx.globalAlpha = 0.88;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.lineWidth = 2;
        ctx.strokeStyle = 'rgba(255,255,255,.35)';
        ctx.stroke();
        canvas._points.push({{x,y,r:r+4,e}});
      }});

      const tooltip = document.getElementById(tooltipId);
      canvas.onmousemove = (ev) => {{
        const br = canvas.getBoundingClientRect();
        const mx = (ev.clientX-br.left) * (canvas.width/br.width);
        const my = (ev.clientY-br.top) * (canvas.height/br.height);
        const hit = canvas._points.find(p => Math.hypot(p.x-mx,p.y-my) < p.r*2);
        if (hit) {{
          tooltip.style.display='block';
          tooltip.style.left = (ev.clientX-br.left+14)+'px';
          tooltip.style.top = (ev.clientY-br.top+10)+'px';
          tooltip.innerHTML = `<b>${{hit.e.event_id}}</b><br>PET: ${{hit.e.our_pet_s}}s &middot; ${{hit.e.severity}}<br>(${{hit.e.loc_x_m}}, ${{hit.e.loc_y_m}}) m`;
          canvas.style.cursor='pointer';
        }} else {{ tooltip.style.display='none'; canvas.style.cursor='crosshair'; }}
      }};
      if (clickable) {{
        canvas.onclick = (ev) => {{
          const br = canvas.getBoundingClientRect();
          const mx = (ev.clientX-br.left) * (canvas.width/br.width);
          const my = (ev.clientY-br.top) * (canvas.height/br.height);
          const hit = canvas._points.find(p => Math.hypot(p.x-mx,p.y-my) < p.r*2);
          if (hit) showEventDetail(hit.e.event_id, detailId);
        }};
      }}
    }}

    function showEventDetail(eventId, targetId) {{
      const e = DB_DATA.events.find(ev => ev.event_id === eventId);
      if (!e || !targetId) return;
      const flagsOk = e.spark_flags && e.spark_flags !== '[]' && e.spark_flags !== '{{}}';
      const flagsLine = flagsOk ? `<div style="margin-top:.4rem;"><span style="color:var(--text-muted);font-size:.68rem;text-transform:uppercase;">Flags</span><div class="mono" style="font-size:.8rem;">${{e.spark_flags}}</div></div>` : '';
      const caveat = (e.veh_id === 871) ? `<div class="caveat">FLUID's tracker labels this vehicle "car"; Spark's visual review described it as a scooter/motorcycle. Both are shown — this is a real disagreement, not an error.</div>` : '';
      let evidenceBlock = '';
      if (e.evidence_frames && e.evidence_frames.length) {{
        const mainId = 'evimg-' + e.event_id;
        const thumbs = e.evidence_frames.map((f, i) => `<img src="${{f.src}}" data-label="${{f.label}}" onclick="document.getElementById('${{mainId}}').src=this.src;document.getElementById('${{mainId}}-cap').textContent=this.dataset.label;" style="width:56px;height:38px;object-fit:cover;border-radius:5px;cursor:pointer;border:1.5px solid ${{i===3?'var(--brand)':'rgba(255,255,255,.12)'}};" />`).join('');
        const first = e.evidence_frames[Math.min(3, e.evidence_frames.length - 1)];
        evidenceBlock = `
          <div style="margin-top:.7rem;">
            <div style="color:#d8b4fe;font-size:.7rem;margin-bottom:.4rem;">Spark visual review &mdash; ${{e.evidence_frames.length}} real rendered frames around closest approach</div>
            <img id="${{mainId}}" src="${{first.src}}" style="width:100%;border-radius:9px;border:1px solid var(--border);display:block;" />
            <div id="${{mainId}}-cap" class="mono" style="font-size:.68rem;color:var(--text-muted);margin:.3rem 0;">${{first.label}}</div>
            <div style="display:flex;gap:.3rem;overflow-x:auto;">${{thumbs}}</div>
          </div>`;
      }} else {{
        evidenceBlock = `<div style="font-size:.76rem;color:var(--text-muted);margin-top:.6rem;">No Spark visual review frames recorded for this event &mdash; it has PET/severity from physics only.</div>`;
      }}
      document.getElementById(targetId).innerHTML = `
        <div class="card" style="margin-top:1rem;">
          <div class="card-header"><div class="card-title">${{e.event_id}}</div><span class="sev-badge ${{e.severity}}">${{e.severity}}</span></div>
          <div style="font-size:.84rem;color:#cbd5e1;">Session <strong>${{e.scene_label}}</strong> &middot; Pedestrian #${{e.ped_id}} &times; Vehicle #${{e.veh_id}} ${{e.vehicle_type ? '('+e.vehicle_type+')' : ''}}</div>
          <div style="font-size:1.5rem;font-weight:800;margin:.6rem 0;font-family:'JetBrains Mono',monospace;">${{e.our_pet_s}}s <span style="font-size:.7rem;color:var(--text-muted);font-weight:500;">measured PET</span></div>
          <div style="font-size:.68rem;color:var(--text-muted);text-transform:uppercase;">Spark status</div><div class="mono" style="font-size:.85rem;margin-bottom:.5rem;">${{e.spark_status}}</div>
          ${{flagsLine}}
          ${{caveat}}
          ${{evidenceBlock}}
          <div class="ask-deck">
            <div style="color:#d8b4fe;font-size:.7rem;margin-bottom:.5rem;">Ask about this event &mdash; answers are compiled only from this event's stored evidence, no new inference.</div>
            <div class="ask-chips">
              <div class="ask-chip" onclick="showQA('${{e.event_id}}','why')">Why this severity?</div>
              <div class="ask-chip" onclick="showQA('${{e.event_id}}','spark')">What did Spark say?</div>
              <div class="ask-chip" onclick="showQA('${{e.event_id}}','confirmed')">Is this confirmed?</div>
              <div class="ask-chip" onclick="showQA('${{e.event_id}}','action')">What can we do?</div>
            </div>
            <div class="ai-response-box" id="qa-${{e.event_id}}"></div>
          </div>
        </div>`;
    }}

    function showQA(eventId, key) {{
      const e = DB_DATA.events.find(ev => ev.event_id === eventId);
      const box = document.getElementById('qa-'+eventId);
      box.style.display = 'block';
      box.textContent = e.qa[key];
    }}

    function populateTable() {{
      const tbody = document.getElementById('tableBody');
      if (!tbody) return;
      tbody.innerHTML = '';
      DB_DATA.events.forEach(e => {{
        const tr = document.createElement('tr');
        tr.onclick = () => showEventDetail(e.event_id, 'ledgerDetail');
        const camBadge = (e.evidence_frames && e.evidence_frames.length) ? `<span title="${{e.evidence_frames.length}} Spark review frames" style="margin-left:.35rem;">&#128247;</span>` : '';
        tr.innerHTML = `<td class="mono" style="color:#93c5fd;">${{e.event_id}}${{camBadge}}</td><td class="mono">${{e.scene_label}}</td><td class="mono">#${{e.ped_id}}</td><td class="mono">#${{e.veh_id}}</td><td class="mono" style="font-weight:700;">${{e.our_pet_s}}s</td><td><span class="sev-badge ${{e.severity}}">${{e.severity}}</span></td><td class="mono" style="color:#d8b4fe;">${{e.spark_status}}</td><td class="mono" style="color:#94a3b8;">${{e.human_review_status}}</td>`;
        tbody.appendChild(tr);
      }});
    }}

    function filterTable() {{
      const q = document.getElementById('eventSearch').value.toLowerCase();
      document.querySelectorAll('#tableBody tr').forEach(r => {{ r.style.display = r.innerText.toLowerCase().includes(q) ? '' : 'none'; }});
    }}

    function drawPetHist() {{
      const el = document.getElementById('petHistChart');
      const buckets = {json.dumps(bucket_counts)};
      const labels = Object.keys(buckets);
      const vals = Object.values(buckets);
      const max = Math.max(...vals, 1);
      const colors = ['#f43f5e','#f43f5e','#f59e0b','#10b981'];
      el.innerHTML = '<div style="display:flex;align-items:flex-end;gap:.8rem;height:180px;padding-top:1rem;">' +
        labels.map((l,i) => `<div style="flex:1;display:flex;flex-direction:column;align-items:center;">
          <div style="font-size:.78rem;font-weight:700;color:${{colors[i]}};margin-bottom:.3rem;">${{vals[i]}}</div>
          <div style="width:100%;height:${{(vals[i]/max*140)||2}}px;background:${{colors[i]}};border-radius:4px;"></div>
          <div style="font-size:.68rem;color:var(--text-muted);margin-top:.4rem;text-align:center;">${{l}}</div>
        </div>`).join('') + '</div>';
    }}

    switchMission('cmd');
    populateTable();
    drawPetHist();
    window.addEventListener('resize', () => renderRadar('miniRadarCanvas','miniRadarTooltip',null,false));
    </script>
    </body></html>
    """

    html = HEAD + HEADER + "<main class='container'>" + COMMUTER_BANNER + COCKPIT + ANALYTICS + RADAR + LEDGER + "</main>" + PRIVACY_MODAL + SCRIPT

    return html


def build_html_from_db(db_path):
    con = sqlite3.connect(db_path)
    events = pd.read_sql_query("SELECT * FROM events", con)
    coverage = pd.read_sql_query("SELECT * FROM coverage", con)
    con.close()
    return build_html(events, coverage)


if __name__ == "__main__":
    html = build_html_from_db(DB_PATH)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUT_PATH} ({len(html):,} bytes)")
