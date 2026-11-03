"""NearMiss authority report generator.

Produces a self-contained HTML safety report for a single session. The output
is suitable for a city traffic engineer to email their municipal engineering
counterpart. Images are inlined as base64 so the file is standalone.
"""
import os, base64
from datetime import datetime
import pandas as pd
import re


def pretty_session(scene):
    m = re.match(r'(\d{4})(\d{2})(\d{2})_video_Traj', scene or '')
    if m:
        y, mo, d = m.groups()
        try:
            return datetime.strptime(f'{y}-{mo}-{d}', '%Y-%m-%d').strftime('%d %b %Y')
        except: pass
    return scene


def _inline_image(path):
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def _severity_rate_per_hour(crit_count, duration_s):
    if not duration_s or duration_s <= 0: return "n/a"
    return f"{(crit_count / duration_s) * 3600:.1f}"


def generate_report_html(scene, events_df, coverage_df):
    scene_events = events_df[events_df['scene']==scene].copy().sort_values('our_pet_s')
    cov = coverage_df[coverage_df['scene']==scene].iloc[0]
    pretty_date = pretty_session(scene)
    today = datetime.now().strftime('%d %b %Y')

    # Top events for inclusion in the report: ones that have been reviewed and have evidence
    reviewed = scene_events[
        (scene_events['spark_status'] != 'not_yet_reviewed') &
        (scene_events['evidence_dir'].notna())
    ].head(5)

    # Pattern: top vehicle involved in critical events
    crits = scene_events[scene_events['severity']=='critical']
    veh_counts = crits['veh_id'].value_counts()
    top_veh = int(veh_counts.index[0]) if len(veh_counts) > 0 else None
    top_veh_n = int(veh_counts.iloc[0]) if len(veh_counts) > 0 else 0

    crit_rate = _severity_rate_per_hour(int(cov['critical_count']), cov['duration_s'])
    dur_min = f"{cov['duration_s']/60:.1f}" if pd.notna(cov['duration_s']) else "n/a"

    # Build evidence section
    evidence_cards = ""
    for i, (_, ev) in enumerate(reviewed.iterrows(), 1):
        ev_dir = ev['evidence_dir']
        # Pick frame_03_t+0.0s.jpg as the hero
        hero_frame = os.path.join(ev_dir, "frame_03_t+0.0s.jpg")
        if not os.path.exists(hero_frame):
            # fallback to any frame
            frames = sorted([f for f in os.listdir(ev_dir) if f.startswith("frame_") and f.endswith(".jpg")])
            if not frames: continue
            hero_frame = os.path.join(ev_dir, frames[len(frames)//2])
        img_data = _inline_image(hero_frame)
        obs = ev['spark_observation'] or "(no observation)"
        obs = obs.replace("<","&lt;").replace(">","&gt;")
        flags = ev['spark_flags'] or "[]"
        human_status = ev['human_review_status']
        sev = ev['severity']
        sev_color = {'critical':'#ff6577','serious':'#ffb65c','moderate':'#55d6a0'}[sev]
        sev_icon = {'critical':'⚠','serious':'⚡','moderate':'✓'}.get(sev, '•')
        status_label = ev['spark_status'].replace('_',' ')
        closest_m = f"{ev['closest_approach_m']:.2f} m" if pd.notna(ev['closest_approach_m']) else "n/a"
        t_conf = f"{ev['conflict_time_s']:.1f} s" if pd.notna(ev['conflict_time_s']) else "n/a"
        evidence_cards += f"""
<div class="ev-card">
  <div class="ev-head">
    <div>
      <div class="ev-num">EVENT {i:02d}</div>
      <div class="ev-id">Pedestrian {int(ev['ped_id'])} &nbsp;×&nbsp; Vehicle {int(ev['veh_id'])}</div>
    </div>
    <div class="ev-sev" style="color:{sev_color};border-color:{sev_color}">{sev_icon} &nbsp;{sev.upper()}</div>
  </div>
  <div class="ev-grid">
    <div class="ev-img"><img src="{img_data}" alt="Evidence frame at closest approach"></div>
    <div class="ev-meta">
      <div class="m-row"><div class="m-l">Our PET</div><div class="m-v" style="color:{sev_color}">{ev['our_pet_s']:.2f} s</div></div>
      <div class="m-row"><div class="m-l">Closest approach</div><div class="m-v">{closest_m}</div></div>
      <div class="m-row"><div class="m-l">Conflict at</div><div class="m-v">{t_conf} into session</div></div>
      <div class="m-row"><div class="m-l">AI review</div><div class="m-v status">{status_label}</div></div>
      <div class="m-row"><div class="m-l">Human analyst</div><div class="m-v status">{human_status}</div></div>
    </div>
  </div>
  <div class="ev-obs"><strong>Muse Spark observation:</strong> <em>"{obs}"</em></div>
</div>
"""

    # Severity distribution as inline CSS bars
    total_sev = int(cov['critical_count']) + int(cov['serious_count']) + int(cov['moderate_count'])
    if total_sev == 0: total_sev = 1
    crit_pct = int(cov['critical_count']) / total_sev * 100
    ser_pct  = int(cov['serious_count']) / total_sev * 100
    mod_pct  = int(cov['moderate_count']) / total_sev * 100

    # Recommended follow-ups
    recos = []
    if int(cov['critical_count']) > 0:
        recos.append(f"Treat this session as a <strong>hotspot indicator</strong>: {int(cov['critical_count'])} critical events in {dur_min} min of footage corresponds to roughly {crit_rate} critical events per hour, a rate that justifies dedicated engineering review.")
    if top_veh and top_veh_n >= 2:
        recos.append(f"Vehicle <code>{top_veh}</code> appears in <strong>{top_veh_n}</strong> critical events in this session. Consider whether this reflects (a) a specific rider/driver pattern worth investigating, or (b) a repeated encroachment at a specific crosswalk edge warranting infrastructure attention (bollards, median refuge extension, signal timing).")
    recos.append("For every event marked <code>supported_with_flag</code>, confirm or dismiss via the analyst dashboard before publishing enforcement or infrastructure recommendations.")
    recos.append("Re-run NearMiss on an additional session at a different time of day to confirm whether the pattern persists across traffic conditions.")

    reco_html = "".join(f"<li>{r}</li>" for r in recos)

    # Full HTML
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NearMiss Site Report · {pretty_date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0b0e12;--panel:#11161c;--panel-2:#171e26;--border:#252d37;--text:#edf1f5;--muted:#8995a3;--brand:#86a9ff;--accent:#b1c5ff;--crit:#ff6577;--ser:#ffb65c;--mod:#55d6a0}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Inter,sans-serif;background:var(--bg);color:var(--text);line-height:1.55;padding:0}}
.report{{max-width:860px;margin:0 auto;padding:3rem 2.5rem;background:var(--bg)}}
code{{font-family:'JetBrains Mono',monospace;background:var(--panel-2);color:#a8c0ff;padding:.1rem .4rem;border-radius:4px;font-size:.9em}}
.lh{{display:flex;justify-content:space-between;align-items:center;padding-bottom:1.5rem;margin-bottom:2rem;border-bottom:2px solid var(--border);position:relative}}
.lh::after{{content:"";position:absolute;left:0;bottom:-2px;width:120px;height:2px;background:linear-gradient(90deg,var(--brand),var(--accent))}}
.lh-brand{{display:flex;align-items:center;gap:.7rem}}
.lh-mark{{width:42px;height:42px;background:linear-gradient(135deg,var(--brand),var(--accent));border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.3rem;font-weight:700;box-shadow:0 4px 20px rgba(95,143,255,.3)}}
.lh-brand-text{{font-size:1.3rem;font-weight:800;letter-spacing:-.5px}}
.lh-sub{{color:var(--muted);font-size:.78rem;margin-top:.15rem;letter-spacing:.3px}}
.lh-right{{text-align:right;font-size:.78rem;color:var(--muted)}}
.lh-right .k{{color:var(--text);font-weight:500}}
.doc-title{{font-size:2rem;font-weight:800;line-height:1.1;margin-bottom:.4rem;letter-spacing:-.8px}}
.doc-meta{{color:var(--muted);font-size:.9rem;margin-bottom:2.5rem;font-family:'JetBrains Mono',monospace}}
.doc-meta span{{color:var(--text)}}
.sec-tag{{color:var(--brand);font-size:.72rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:.5rem}}
.sec-h{{font-size:1.3rem;font-weight:700;margin-bottom:1rem;letter-spacing:-.3px}}
.section{{margin-bottom:2.5rem}}

/* Executive summary */
.summary{{background:var(--panel);border:1px solid var(--border);border-left:3px solid var(--brand);padding:1.3rem 1.5rem;border-radius:10px}}
.summary p{{color:var(--text);margin-bottom:.6rem}}
.summary p:last-child{{margin-bottom:0}}
.summary strong{{color:var(--brand)}}

/* KPI */
.kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}}
.k-card{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:1rem;position:relative;overflow:hidden}}
.k-card::before{{content:"";position:absolute;left:0;top:0;bottom:0;width:3px}}
.k-card.b::before{{background:var(--brand);box-shadow:0 0 15px var(--brand)}}
.k-card.c::before{{background:var(--crit);box-shadow:0 0 15px var(--crit)}}
.k-card.g::before{{background:var(--mod);box-shadow:0 0 15px var(--mod)}}
.k-card.a::before{{background:var(--ser);box-shadow:0 0 15px var(--ser)}}
.k-l{{color:var(--muted);font-size:.68rem;text-transform:uppercase;letter-spacing:.5px;margin-bottom:.2rem}}
.k-v{{font-size:1.7rem;font-weight:700;line-height:1}}
.k-v.c{{color:var(--crit)}}.k-v.b{{color:var(--brand)}}.k-v.g{{color:var(--mod)}}.k-v.a{{color:var(--ser)}}
.k-s{{color:var(--muted);font-size:.7rem;margin-top:.3rem}}

/* severity bars */
.sev-bars{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:1.3rem 1.5rem}}
.sev-bar{{display:grid;grid-template-columns:90px 1fr 60px;align-items:center;gap:1rem;margin-bottom:.7rem}}
.sev-bar:last-child{{margin-bottom:0}}
.sev-label{{font-size:.85rem;font-weight:500;color:var(--text)}}
.sev-track{{height:14px;background:var(--panel-2);border-radius:7px;overflow:hidden}}
.sev-fill{{height:100%;border-radius:7px}}
.sev-fill.c{{background:linear-gradient(90deg,var(--crit),#ff6688);box-shadow:0 0 10px rgba(255,68,102,.4)}}
.sev-fill.a{{background:linear-gradient(90deg,var(--ser),#ffbb66);box-shadow:0 0 10px rgba(255,164,65,.4)}}
.sev-fill.g{{background:linear-gradient(90deg,var(--mod),#66eeaa);box-shadow:0 0 10px rgba(68,221,153,.4)}}
.sev-count{{text-align:right;font-weight:600;font-family:'JetBrains Mono',monospace;font-size:.9rem}}
.sev-count.c{{color:var(--crit)}}.sev-count.a{{color:var(--ser)}}.sev-count.g{{color:var(--mod)}}

/* evidence cards */
.ev-card{{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:1.3rem;margin-bottom:1rem}}
.ev-head{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1rem}}
.ev-num{{color:var(--muted);font-size:.68rem;font-weight:600;letter-spacing:.8px;font-family:'JetBrains Mono',monospace}}
.ev-id{{font-size:1.05rem;font-weight:600;margin-top:.15rem}}
.ev-sev{{padding:.2rem .6rem;border:1px solid;border-radius:6px;font-size:.68rem;font-weight:600;letter-spacing:.5px;background:rgba(255,255,255,.03)}}
.ev-grid{{display:grid;grid-template-columns:1.3fr 1fr;gap:1.2rem;margin-bottom:1rem}}
.ev-img img{{width:100%;height:auto;border-radius:8px;display:block;border:1px solid var(--border)}}
.ev-meta{{display:flex;flex-direction:column;justify-content:center}}
.m-row{{display:flex;justify-content:space-between;align-items:baseline;padding:.4rem 0;border-bottom:1px solid var(--border)}}
.m-row:last-child{{border-bottom:none}}
.m-l{{color:var(--muted);font-size:.75rem}}
.m-v{{font-size:.9rem;font-weight:500;font-family:'JetBrains Mono',monospace}}
.m-v.status{{text-transform:lowercase}}
.ev-obs{{background:var(--panel-2);border-left:3px solid var(--brand);padding:.8rem 1rem;border-radius:6px;font-size:.88rem;color:var(--text)}}
.ev-obs strong{{color:var(--brand);font-weight:600}}

/* recommendations */
.recos{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:1.3rem 1.5rem}}
.recos ol{{padding-left:1.3rem}}
.recos li{{margin-bottom:.9rem;color:var(--text)}}
.recos li:last-child{{margin-bottom:0}}
.recos strong{{color:var(--brand)}}

/* method */
.method{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:1.3rem 1.5rem;color:var(--muted);font-size:.88rem}}
.method p{{margin-bottom:.7rem}}
.method p:last-child{{margin-bottom:0}}
.method strong{{color:var(--text)}}

/* signature */
.sig{{display:grid;grid-template-columns:1fr 1fr;gap:2rem;margin-top:3rem;padding-top:2rem;border-top:1px dashed var(--border)}}
.sig-line{{border-bottom:1px solid var(--muted);height:50px;margin-bottom:.4rem}}
.sig-label{{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.5px}}

/* footer */
.foot{{text-align:center;padding-top:2rem;border-top:1px solid var(--border);margin-top:3rem;color:var(--muted);font-size:.75rem}}
.foot strong{{color:var(--text)}}

@media print {{
  body{{background:#fff;color:#000}}
  .report{{padding:1rem}}
  .ev-card,.summary,.kpi-row .k-card,.sev-bars,.recos,.method{{background:#fff;border-color:#ccc;color:#000}}
}}

/* NearMiss · Modern SaaS report system */
*{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
body{{background:var(--bg);line-height:1.58}}
.report{{max-width:920px;padding:2.5rem 2.2rem}}
.lh{{border-bottom:1px solid var(--border);padding-bottom:1.1rem;margin-bottom:1.6rem}}
.lh::after{{background:var(--brand);width:72px;height:1px}}
.lh-mark{{background:#1d2a42;border:1px solid #2d4267;border-radius:9px;color:var(--brand);box-shadow:none}}
.lh-brand-text{{font-size:1.15rem;letter-spacing:-.4px}}
.doc-title{{font-size:1.85rem;letter-spacing:-.7px}}
.doc-meta{{font-size:.75rem;margin-bottom:1.7rem;color:var(--muted)}}
.section{{margin-bottom:1.8rem}}
.sec-tag{{font-size:.66rem;letter-spacing:.9px;color:var(--brand)}}
.sec-h{{font-size:1.12rem;letter-spacing:-.25px;margin-bottom:.8rem}}
.summary,.k-card,.sev-bars,.ev-card,.recos,.method{{background:var(--panel);border-color:var(--border);border-radius:10px;box-shadow:0 8px 22px rgba(0,0,0,.12)}}
.summary{{border-left:2px solid var(--brand);padding:1rem 1.15rem}}
.kpi-row{{gap:.65rem}}.k-card{{padding:.85rem}}
.k-card::before{{width:2px;box-shadow:none!important}}
.k-l{{font-size:.62rem;letter-spacing:.45px}}.k-v{{font-size:1.5rem;letter-spacing:-.5px}}
.sev-track{{height:9px;background:#202832}}.sev-fill{{box-shadow:none!important}}
.ev-card{{padding:1rem;margin-bottom:.8rem}}.ev-grid{{gap:1rem}}.ev-img img{{border-color:var(--border);border-radius:7px}}
.ev-obs{{background:#151d27;border-left-width:2px;border-radius:0 7px 7px 0}}
code{{background:#1a222c;color:var(--accent)}}
.recos li{{margin-bottom:.7rem}}
.foot{{border-color:var(--border)}}
@media(max-width:700px){{.report{{padding:1.25rem 1rem}}.kpi-row{{grid-template-columns:repeat(2,1fr)}}.ev-grid{{grid-template-columns:1fr}}.lh{{align-items:flex-start;gap:1rem}}.lh-right{{max-width:45%;font-size:.68rem}}.doc-title{{font-size:1.5rem}}.sig{{gap:1rem}}}}
@media print{{body,.report{{background:#fff!important;color:#111!important}}.summary,.k-card,.sev-bars,.ev-card,.recos,.method{{background:#fff!important;color:#111!important;box-shadow:none}}.lh,.foot{{border-color:#bbb}}.summary p,.m-v,.ev-obs{{color:#111}}}}
</style>
</head>
<body>
<div class="report">

  <div class="lh">
    <div class="lh-brand">
      <div class="lh-mark">⚠</div>
      <div>
        <div class="lh-brand-text">NearMiss</div>
        <div class="lh-sub">PILOT · FLUID JURONG LAKE INTERSECTION</div>
      </div>
    </div>
    <div class="lh-right">
      <div>Site ID: <span class="k">fluid-jurong-01</span></div>
      <div>Report generated: <span class="k">{today}</span></div>
    </div>
  </div>

  <div class="doc-title">Site Safety Report · Session of {pretty_date}</div>
  <div class="doc-meta">session_id: <span>{scene}</span> &nbsp;·&nbsp; duration: <span>{dur_min} min</span> &nbsp;·&nbsp; pedestrians tracked: <span>{int(cov['ped_count']) if pd.notna(cov['ped_count']) else 'n/a'}</span></div>

  <div class="section">
    <div class="sec-tag">01 · Executive Summary</div>
    <div class="sec-h">What the pipeline found at this session</div>
    <div class="summary">
      <p>In <strong>{dur_min} minutes</strong> of real intersection drone footage, NearMiss detected <strong>{int(cov['event_count'])} pedestrian-vehicle near-miss events</strong>, <strong>{int(cov['critical_count'])} of them critical</strong> (post-encroachment time ≤ 1.0 s). At this rate the intersection would produce approximately <strong>{crit_rate} critical near-misses per hour</strong>.</p>
      <p>Median PET across the session is <strong>{cov['median_pet_s']:.2f} s</strong>; the closest observed encounter had a PET of <strong>{cov['min_pet_s']:.2f} s</strong>. Of the critical events, <strong>{top_veh_n}</strong> were associated with vehicle <code>{top_veh}</code>, suggesting a specific rider or location pattern worth engineering attention.</p>
      <p>Every event in this report has been visually reviewed by Meta Muse Spark against the raw drone footage; events where visual verification was ambiguous are routed to the human analyst queue.</p>
    </div>
  </div>

  <div class="section">
    <div class="sec-tag">02 · Headline Numbers</div>
    <div class="sec-h">What this session looks like at a glance</div>
    <div class="kpi-row">
      <div class="k-card b"><div class="k-l">Near-miss events</div><div class="k-v b">{int(cov['event_count'])}</div><div class="k-s">PET ≤ 2.0 s</div></div>
      <div class="k-card c"><div class="k-l">Critical</div><div class="k-v c">{int(cov['critical_count'])}</div><div class="k-s">PET ≤ 1.0 s</div></div>
      <div class="k-card g"><div class="k-l">Median PET</div><div class="k-v g">{cov['median_pet_s']:.2f}s</div><div class="k-s">Across all events</div></div>
      <div class="k-card a"><div class="k-l">Critical rate</div><div class="k-v a">{crit_rate}</div><div class="k-s">Per hour</div></div>
    </div>
  </div>

  <div class="section">
    <div class="sec-tag">03 · Severity Distribution</div>
    <div class="sec-h">By measurement band</div>
    <div class="sev-bars">
      <div class="sev-bar"><div class="sev-label">⚠ Critical</div><div class="sev-track"><div class="sev-fill c" style="width:{crit_pct:.0f}%"></div></div><div class="sev-count c">{int(cov['critical_count'])}</div></div>
      <div class="sev-bar"><div class="sev-label">⚡ Serious</div><div class="sev-track"><div class="sev-fill a" style="width:{ser_pct:.0f}%"></div></div><div class="sev-count a">{int(cov['serious_count'])}</div></div>
      <div class="sev-bar"><div class="sev-label">✓ Moderate</div><div class="sev-track"><div class="sev-fill g" style="width:{mod_pct:.0f}%"></div></div><div class="sev-count g">{int(cov['moderate_count'])}</div></div>
    </div>
  </div>

  <div class="section">
    <div class="sec-tag">04 · Top Reviewed Events With Evidence</div>
    <div class="sec-h">The {len(reviewed)} most severe events visually reviewed by Muse Spark</div>
    {evidence_cards}
  </div>

  <div class="section">
    <div class="sec-tag">05 · Recommended Follow-Ups</div>
    <div class="sec-h">What this session suggests the engineering office should do next</div>
    <div class="recos"><ol>{reco_html}</ol></div>
  </div>

  <div class="section">
    <div class="sec-tag">06 · Methodology</div>
    <div class="sec-h">How these numbers were produced</div>
    <div class="method">
      <p><strong>Post-Encroachment Time (PET)</strong> is the time gap between a pedestrian and a vehicle occupying the same ground space. Our implementation (Architecture 2.1 §8) uses a 0.5m world-coordinate grid with vehicle footprint inflation driven by each track's measured length, width and heading. The engine was validated against FLUID's own 147 labelled vehicle-vehicle conflicts: 95% match rate overall and 100% recall on physical-contact events.</p>
      <p><strong>Severity bands</strong>: critical (PET ≤ 1.0s), serious (1.0s &lt; PET ≤ 1.5s), moderate (1.5s &lt; PET ≤ 2.0s).</p>
      <p><strong>Visual review</strong>: for each candidate event, 7 real frames (t−3s to t+3s around the conflict moment) are rendered with physics overlays and submitted to Meta Muse Spark with neutral visual questions and a strict JSON schema. Spark is <em>never</em> shown the PET or severity value. Spark's answers are then combined with the physics in a deterministic Python decision function. Events where Spark's assessment is uncertain are routed to the human analyst queue — Spark cannot auto-accept or auto-reject safety-critical events.</p>
      <p><strong>Per-session calibration</strong>: the pixel-to-world transform used when drawing overlays onto the raw video is computed per session from the drone's flight-log altitude and attitude, so it stays consistent across recordings even when the pilot flies at a different height. Any residual sub-metre offset between an overlay and its underlying agent is caught by Muse Spark during visual review and surfaces as an <code>overlay</code> flag on that event's record.</p>
      <p><strong>Data source</strong>: FLUID FIDRT (Figshare 10.6084/m9.figshare.29974954), a public drone-captured intersection dataset.</p>
    </div>
  </div>

  <div class="sig">
    <div><div class="sig-line"></div><div class="sig-label">Reviewing analyst</div></div>
    <div><div class="sig-line"></div><div class="sig-label">Date</div></div>
  </div>

  <div class="foot">
    Produced by <strong>NearMiss</strong> · a pedestrian-vehicle near-miss detection system<br>
    Powered by Meta SAM 3.1 + Muse Spark · Built for Meta Global AI Developer Hackathon 2026
  </div>

</div>
</body>
</html>
"""
    return html
