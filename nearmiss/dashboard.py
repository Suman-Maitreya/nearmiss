import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
"""NearMiss dashboard — product build (site conceit, branded header, report)."""
import os, json, sqlite3, re
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

DB = r"D:\META\nearmiss\nearmiss.db"
st.set_page_config(page_title="NearMiss · Jurong Lake Pilot", page_icon="⚠️", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#0a0e1a;--panel:#141928;--panel-2:#1b2137;--border:#253050;--text:#e8edf5;--muted:#8690a6;--brand:#5f8fff;--accent:#a855f7;--crit:#ff4466;--ser:#ffa441;--mod:#44dd99}
html,body,[class*="css"]{font-family:'Inter',sans-serif !important}
.stApp{background:var(--bg);color:var(--text)}
.block-container{padding-top:1rem;max-width:1400px}
section[data-testid="stSidebar"]{background:#0d1222;border-right:1px solid var(--border)}
section[data-testid="stSidebar"] *{color:var(--text) !important}

/* top site bar */
.topbar{display:flex;align-items:center;justify-content:space-between;padding:1rem 1.4rem;background:linear-gradient(90deg,rgba(95,143,255,.08),rgba(168,85,247,.06));border:1px solid var(--border);border-radius:14px;margin-bottom:1.6rem}
.tb-left{display:flex;align-items:center;gap:1rem}
.tb-logo{width:38px;height:38px;background:linear-gradient(135deg,#5f8fff,#a855f7);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;box-shadow:0 4px 20px rgba(95,143,255,.3)}
.tb-brand{font-weight:800;font-size:1.1rem;letter-spacing:-.3px}
.tb-site{color:var(--muted);font-size:.82rem;margin-top:.1rem}
.tb-site .green-dot{display:inline-block;width:7px;height:7px;background:var(--mod);border-radius:50%;box-shadow:0 0 10px var(--mod);margin-right:.4rem;vertical-align:middle;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.tb-right{display:flex;gap:.6rem;align-items:center}
.tb-chip{background:var(--panel);border:1px solid var(--border);padding:.35rem .8rem;border-radius:999px;font-size:.78rem;color:var(--muted);font-family:'JetBrains Mono',monospace}

/* hero */
.hero{background:linear-gradient(135deg,#1a2048 0%,#3b1f66 60%,#2b1b4a 100%);padding:2rem 2.2rem;border-radius:18px;margin-bottom:1.8rem;border:1px solid var(--border);box-shadow:0 8px 40px rgba(95,143,255,.08);position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:-80px;right:-80px;width:280px;height:280px;border-radius:50%;background:radial-gradient(circle,rgba(168,85,247,.3),transparent 70%)}
.hero-title{font-size:2.5rem;font-weight:800;line-height:1.1;margin:0;background:linear-gradient(90deg,#e8edf5,#a8c0ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero-sub{color:var(--muted);margin-top:.35rem;font-size:1rem}
.hero-pill{display:inline-block;margin-top:1rem;padding:.3rem .8rem;background:rgba(95,143,255,.12);border:1px solid rgba(95,143,255,.35);border-radius:999px;font-size:.78rem;color:#a8c0ff;letter-spacing:.4px;text-transform:uppercase}

/* KPI */
.kpi{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:1.1rem 1.3rem;position:relative;overflow:hidden;height:100%}
.kpi::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px}
.kpi.k-blue::before{background:var(--brand);box-shadow:0 0 20px var(--brand)}
.kpi.k-crit::before{background:var(--crit);box-shadow:0 0 20px var(--crit)}
.kpi.k-amber::before{background:var(--ser);box-shadow:0 0 20px var(--ser)}
.kpi.k-green::before{background:var(--mod);box-shadow:0 0 20px var(--mod)}
.kpi-label{color:var(--muted);font-size:.78rem;letter-spacing:.6px;text-transform:uppercase;font-weight:500;margin-bottom:.3rem}
.kpi-value{font-size:2.4rem;font-weight:700;line-height:1}
.kpi-value.v-crit{color:var(--crit)}.kpi-value.v-amber{color:var(--ser)}.kpi-value.v-green{color:var(--mod)}.kpi-value.v-blue{color:var(--brand)}
.kpi-sub{color:var(--muted);font-size:.78rem;margin-top:.35rem}

.sec-h{font-size:1.1rem;font-weight:600;letter-spacing:.3px;margin:1.8rem 0 .8rem 0;color:var(--text);padding-bottom:.4rem;border-bottom:1px solid var(--border)}

.scard{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:1.2rem 1.4rem;margin-bottom:1rem}
.scard-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem}
.scard-name{font-weight:600;font-size:1rem;color:var(--text)}
.scard-name .scene-id{font-family:'JetBrains Mono',monospace;font-size:.75rem;color:var(--muted);font-weight:400;margin-left:.6rem}
.scard-chip{background:rgba(95,143,255,.1);border:1px solid rgba(95,143,255,.3);color:var(--brand);padding:.25rem .7rem;border-radius:999px;font-size:.72rem;font-weight:500;letter-spacing:.4px}
.scard-row{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}
.scard-stat .k-l{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.5px;margin-bottom:.2rem}
.scard-stat .k-v{font-size:1.4rem;font-weight:600}
.scard-stat .k-v.crit{color:var(--crit)}.scard-stat .k-v.ser{color:var(--ser)}.scard-stat .k-v.mod{color:var(--mod)}

.sev-chip{display:inline-block;padding:.18rem .55rem;border-radius:999px;font-size:.72rem;font-weight:500;letter-spacing:.3px}
.sev-crit{background:rgba(255,68,102,.15);color:var(--crit);border:1px solid rgba(255,68,102,.4)}
.sev-ser{background:rgba(255,164,65,.15);color:var(--ser);border:1px solid rgba(255,164,65,.4)}
.sev-mod{background:rgba(68,221,153,.15);color:var(--mod);border:1px solid rgba(68,221,153,.4)}

.detail-panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:1.4rem 1.6rem}
.detail-row{margin-bottom:.7rem}
.detail-label{color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.5px;margin-bottom:.15rem}
.detail-value{color:var(--text);font-size:1rem}
.detail-value code{background:var(--panel-2);color:#a8c0ff;padding:.1rem .4rem;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:.85rem}
.obs{background:var(--panel-2);border-left:3px solid var(--brand);padding:.8rem 1rem;border-radius:6px;font-style:italic;color:var(--text);margin-top:.5rem}

[data-testid="stDataFrame"]{background:var(--panel) !important;border-radius:10px;border:1px solid var(--border) !important}

.stButton>button{border-radius:10px;font-weight:500;padding:.55rem 1rem;border:1px solid var(--border);background:var(--panel-2);color:var(--text);transition:all .15s}
.stButton>button:hover{background:var(--panel);border-color:var(--brand);color:var(--brand)}

.page-title{font-size:1.9rem;font-weight:700;margin:.5rem 0 .3rem 0}
.page-sub{color:var(--muted);margin-bottom:1.5rem}

.report-stub{padding:3rem;text-align:center;background:var(--panel);border:1px dashed var(--border);border-radius:14px}
.report-stub .big{font-size:2.5rem;margin-bottom:.6rem}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# --- data layer ---
@st.cache_data(ttl=5)
def load_events():
    con = sqlite3.connect(DB); df = pd.read_sql_query("SELECT * FROM events", con); con.close(); return df

@st.cache_data(ttl=5)
def load_coverage():
    con = sqlite3.connect(DB); df = pd.read_sql_query("SELECT * FROM coverage", con); con.close(); return df

def write_review(event_id, status, note):
    con = sqlite3.connect(DB)
    con.execute("UPDATE events SET human_review_status=?, human_review_note=?, updated_at=datetime('now') WHERE event_id=?", (status, note, event_id))
    con.commit(); con.close(); st.cache_data.clear()

def safe_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return None
    return str(v)

def pretty_session(scene):
    m = re.match(r'(\d{4})(\d{2})(\d{2})_video_Traj', scene or '')
    if m:
        y, mo, d = m.groups()
        try:
            return datetime.strptime(f'{y}-{mo}-{d}', '%Y-%m-%d').strftime('Session · %d %b %Y')
        except: pass
    return scene

def sev_chip(sev):
    cls = {'critical':'sev-crit','serious':'sev-ser','moderate':'sev-mod'}.get(sev,'sev-mod')
    return f'<span class="sev-chip {cls}">{sev}</span>'

def kpi_card(label, value, flavor='k-blue', val_cls='v-blue', subtitle=None):
    sub = f'<div class="kpi-sub">{subtitle}</div>' if subtitle else ''
    return f'<div class="kpi {flavor}"><div class="kpi-label">{label}</div><div class="kpi-value {val_cls}">{value}</div>{sub}</div>'

def theme_plot(fig, height=320):
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#8690a6', family='Inter'), height=height, margin=dict(l=10,r=10,t=20,b=10), xaxis=dict(gridcolor='#1f2537', zerolinecolor='#1f2537'), yaxis=dict(gridcolor='#1f2537', zerolinecolor='#1f2537'))
    return fig

# --- top bar (shown on every page) ---
events = load_events()
coverage = load_coverage()
total_duration_min = coverage['duration_s'].dropna().sum() / 60 if 'duration_s' in coverage else 70
site_badge_html = f"""
<div class="topbar">
  <div class="tb-left">
    <div class="tb-logo">⚠</div>
    <div>
      <div class="tb-brand">NearMiss</div>
      <div class="tb-site"><span class="green-dot"></span>Jurong Lake Pilot Site · {len(coverage)} recording sessions · ~{total_duration_min:.0f} min analysed</div>
    </div>
  </div>
  <div class="tb-right">
    <span class="tb-chip">site_id · fluid-jurong-01</span>
    <span class="tb-chip">pilot · live</span>
  </div>
</div>
"""
st.markdown(site_badge_html, unsafe_allow_html=True)

# --- sidebar nav ---
st.sidebar.markdown("<div style='font-size:1.4rem;font-weight:700;padding:0 0 1rem 0;'>⚠️ NearMiss</div>", unsafe_allow_html=True)
st.sidebar.markdown("<div style='color:#8690a6;font-size:.75rem;letter-spacing:.5px;text-transform:uppercase;'>Navigate</div>", unsafe_allow_html=True)
PAGE = st.sidebar.radio("", ["Overview", "Events", "Review Queue", "Coverage", "Reports"], label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.markdown(f"<div style='color:#8690a6;font-size:.72rem;'>Site</div><div style='font-family:JetBrains Mono,monospace;font-size:.8rem;color:#a8c0ff;'>FLUID Jurong Lake</div>", unsafe_allow_html=True)
st.sidebar.markdown(f"<div style='color:#8690a6;font-size:.72rem;margin-top:1rem;'>DB</div><div style='font-family:JetBrains Mono,monospace;font-size:.72rem;color:#a8c0ff;word-break:break-all;'>{DB}</div>", unsafe_allow_html=True)

# ===============================================================
if PAGE == "Overview":
    st.markdown("""<div class='hero'>
<div class='hero-title'>Pilot Overview</div>
<div class='hero-sub'>Pedestrian-vehicle near-miss detection, verified against FLUID ground truth</div>
<div class='hero-pill'>FLUID • Meta SAM 3.1 • Muse Spark • Architecture 2.1</div>
</div>""", unsafe_allow_html=True)

    tot = len(events)
    crit = int((events['severity']=='critical').sum())
    flagged = int((events['needs_human_review']==1).sum())
    pending = int(((events['needs_human_review']==1) & (events['human_review_status']=='pending')).sum())
    reviewed = int((events['spark_status']!='not_yet_reviewed').sum())

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(kpi_card("Total events", tot, 'k-blue', 'v-blue'), unsafe_allow_html=True)
    c2.markdown(kpi_card("Critical (PET ≤ 1s)", crit, 'k-crit', 'v-crit'), unsafe_allow_html=True)
    c3.markdown(kpi_card("Flagged for review", flagged, 'k-amber', 'v-amber', subtitle=f"{pending} pending human decision"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Spark reviewed", reviewed, 'k-green', 'v-green'), unsafe_allow_html=True)

    st.markdown("<div class='sec-h'>Severity distribution</div>", unsafe_allow_html=True)
    sev = events['severity'].value_counts().reindex(['critical','serious','moderate']).fillna(0).astype(int)
    fig = go.Figure()
    colors = {'critical':'#ff4466','serious':'#ffa441','moderate':'#44dd99'}
    for s in ['critical','serious','moderate']:
        fig.add_trace(go.Bar(x=[s], y=[int(sev[s])], marker=dict(color=colors[s]), text=[int(sev[s])], textposition='outside', textfont=dict(size=18, color='#e8edf5'), name=s, showlegend=False))
    st.plotly_chart(theme_plot(fig, 300), use_container_width=True)

    st.markdown("<div class='sec-h'>PET distribution (time gap between pedestrian and vehicle)</div>", unsafe_allow_html=True)
    fig2 = px.histogram(events, x='our_pet_s', nbins=20, color='severity', color_discrete_map={'critical':'#ff4466','serious':'#ffa441','moderate':'#44dd99'}, labels={'our_pet_s':'PET (seconds)'})
    fig2.update_traces(opacity=0.9)
    st.plotly_chart(theme_plot(fig2, 340), use_container_width=True)

    st.markdown("<div class='sec-h'>Per-session summary</div>", unsafe_allow_html=True)
    for _, r in coverage.iterrows():
        dur_s = f"~{r['duration_s']/60:.1f} min" if pd.notna(r['duration_s']) else "n/a"
        st.markdown(f"""<div class='scard'>
<div class='scard-head'><span class='scard-name'>{pretty_session(r['scene'])}<span class='scene-id'>{r['scene']}</span></span><span class='scard-chip'>{dur_s}</span></div>
<div class='scard-row'><div class='scard-stat'><div class='k-l'>Pedestrians</div><div class='k-v'>{int(r['ped_count']) if pd.notna(r['ped_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Vehicles</div><div class='k-v'>{int(r['veh_count']) if pd.notna(r['veh_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Candidate pairs</div><div class='k-v'>{int(r['candidate_pair_count']) if pd.notna(r['candidate_pair_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Events</div><div class='k-v'>{int(r['event_count'])}</div></div></div>
<div class='scard-row' style='margin-top:1rem;'><div class='scard-stat'><div class='k-l'>Critical</div><div class='k-v crit'>{int(r['critical_count'])}</div></div><div class='scard-stat'><div class='k-l'>Serious</div><div class='k-v ser'>{int(r['serious_count'])}</div></div><div class='scard-stat'><div class='k-l'>Moderate</div><div class='k-v mod'>{int(r['moderate_count'])}</div></div><div class='scard-stat'><div class='k-l'>Median PET</div><div class='k-v'>{r['median_pet_s']:.2f}s</div></div></div>
</div>""", unsafe_allow_html=True)

elif PAGE == "Events":
    st.markdown("<div class='page-title'>All detected events</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Filter, inspect, and investigate every pedestrian-vehicle near-miss.</div>", unsafe_allow_html=True)

    cfilt1, cfilt2, cfilt3 = st.columns(3)
    sess_display = {'(all)':'(all)'}
    for s in coverage['scene'].unique(): sess_display[pretty_session(s)] = s
    pick_label = cfilt1.selectbox("Session", list(sess_display.keys()))
    pick_scene = sess_display[pick_label]
    pick_sev = cfilt2.multiselect("Severity", ['critical','serious','moderate'], default=['critical','serious','moderate'])
    pick_rev = cfilt3.selectbox("Review state", ['(all)','needs human review','reviewed by Spark','not yet Spark-reviewed'])

    df = events.copy()
    if pick_scene != '(all)': df = df[df['scene']==pick_scene]
    df = df[df['severity'].isin(pick_sev)]
    if pick_rev == 'needs human review': df = df[df['needs_human_review']==1]
    elif pick_rev == 'reviewed by Spark': df = df[df['spark_status']!='not_yet_reviewed']
    elif pick_rev == 'not yet Spark-reviewed': df = df[df['spark_status']=='not_yet_reviewed']

    df_show = df[['event_id','ped_id','veh_id','our_pet_s','severity','spark_status','human_review_status']].copy()
    df_show['our_pet_s'] = df_show['our_pet_s'].round(2)
    df_show = df_show.sort_values('our_pet_s')
    st.markdown(f"<div style='color:#8690a6;font-size:.85rem;margin:.5rem 0 1rem 0;'>Showing {len(df_show)} of {len(events)} events</div>", unsafe_allow_html=True)
    st.dataframe(df_show, use_container_width=True, hide_index=True, column_config={'our_pet_s': st.column_config.NumberColumn('PET (s)', format='%.2f')})

    if len(df):
        st.markdown("<div class='sec-h'>Inspect one event</div>", unsafe_allow_html=True)
        pick_ev = st.selectbox("Event", df['event_id'].tolist(), label_visibility="collapsed")
        row = df[df['event_id']==pick_ev].iloc[0]
        cL, cR = st.columns([3,2])
        with cL:
            detail = f"""<div class='detail-panel'>
<div class='detail-row'><div class='detail-label'>Session</div><div class='detail-value'>{pretty_session(row['scene'])} <code>{row['scene']}</code></div></div>
<div class='detail-row'><div class='detail-label'>Agents</div><div class='detail-value'>Pedestrian <code>{int(row['ped_id'])}</code> &nbsp; · &nbsp; Vehicle <code>{int(row['veh_id'])}</code></div></div>"""
            if pd.notna(row['conflict_time_s']): detail += f"<div class='detail-row'><div class='detail-label'>Conflict time</div><div class='detail-value'>{row['conflict_time_s']:.1f} s into recording</div></div>"
            if pd.notna(row['closest_approach_m']): detail += f"<div class='detail-row'><div class='detail-label'>Closest approach</div><div class='detail-value'>{row['closest_approach_m']:.2f} m</div></div>"
            detail += f"<div class='detail-row'><div class='detail-label'>Our PET</div><div class='detail-value' style='font-size:1.4rem;font-weight:600;'>{row['our_pet_s']:.2f} s &nbsp; {sev_chip(row['severity'])}</div></div>"
            detail += f"<div class='detail-row'><div class='detail-label'>Spark status</div><div class='detail-value'><code>{row['spark_status']}</code></div></div>"
            flags = safe_str(row['spark_flags'])
            if flags: detail += f"<div class='detail-row'><div class='detail-label'>Flags</div><div class='detail-value'><code>{flags}</code></div></div>"
            obs = safe_str(row['spark_observation'])
            if obs: detail += f"<div class='detail-row'><div class='detail-label'>Spark observation</div><div class='obs'>{obs}</div></div>"
            detail += "</div>"
            st.markdown(detail, unsafe_allow_html=True)
        with cR:
            ev_dir = safe_str(row['evidence_dir'])
            if ev_dir and os.path.isdir(ev_dir):
                st.markdown("<div class='detail-label' style='margin-bottom:.6rem;'>Evidence frames</div>", unsafe_allow_html=True)
                frames = sorted([f for f in os.listdir(ev_dir) if f.startswith('frame_') and f.endswith('.jpg')])
                for f in frames: st.image(os.path.join(ev_dir, f), caption=f.replace('frame_','').replace('.jpg',''), use_container_width=True)
            else:
                st.markdown("""<div class='detail-panel' style='text-align:center; color: var(--muted);'><div style='font-size:2rem; margin-bottom:.5rem;'>📷</div><div>No evidence frames rendered for this event yet.</div><div style='font-size:.78rem; margin-top:.5rem;'>Run the batch renderer to populate.</div></div>""", unsafe_allow_html=True)

elif PAGE == "Review Queue":
    st.markdown("<div class='page-title'>Human review queue</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Events the AI flagged for a human analyst to confirm, dismiss, or escalate.</div>", unsafe_allow_html=True)
    q = events[(events['needs_human_review']==1) & (events['human_review_status']=='pending')]
    c1,_ = st.columns([1,3])
    c1.markdown(kpi_card("Pending review", len(q), 'k-amber', 'v-amber'), unsafe_allow_html=True)
    if len(q)==0:
        st.markdown("""<div class='detail-panel' style='margin-top:1.5rem; text-align:center;'><div style='font-size:2.5rem;'>✅</div><div style='font-size:1.1rem; margin-top:.5rem;'>Queue clear</div><div style='color: var(--muted); margin-top:.3rem;'>No events currently pending human review.</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown("<div class='sec-h'>Pick an event to review</div>", unsafe_allow_html=True)
        pick = st.selectbox("Event", q['event_id'].tolist(), label_visibility="collapsed")
        row = q[q['event_id']==pick].iloc[0]
        info = f"""<div class='detail-panel'>
<div class='detail-row'><div class='detail-label'>Event</div><div class='detail-value'><code>{row['event_id']}</code> &nbsp;·&nbsp; {pretty_session(row['scene'])}</div></div>
<div class='detail-row'><div class='detail-label'>PET</div><div class='detail-value' style='font-size:1.4rem; font-weight:600;'>{row['our_pet_s']:.2f} s &nbsp; {sev_chip(row['severity'])}</div></div>"""
        if pd.notna(row['closest_approach_m']): info += f"<div class='detail-row'><div class='detail-label'>Closest approach</div><div class='detail-value'>{row['closest_approach_m']:.2f} m</div></div>"
        obs = safe_str(row['spark_observation'])
        if obs: info += f"<div class='detail-row'><div class='detail-label'>Spark observation</div><div class='obs'>{obs}</div></div>"
        flags = safe_str(row['spark_flags'])
        if flags: info += f"<div class='detail-row'><div class='detail-label'>Flags</div><div class='detail-value'><code>{flags}</code></div></div>"
        info += "</div>"
        st.markdown(info, unsafe_allow_html=True)
        ev_dir = safe_str(row['evidence_dir'])
        if ev_dir and os.path.isdir(ev_dir):
            st.markdown("<div class='sec-h'>Evidence (t-3s → t+3s)</div>", unsafe_allow_html=True)
            frames = sorted([f for f in os.listdir(ev_dir) if f.startswith('frame_') and f.endswith('.jpg')])
            cols = st.columns(len(frames))
            for c,f in zip(cols, frames): c.image(os.path.join(ev_dir, f), caption=f.split('_')[-1].replace('.jpg',''), use_container_width=True)
        st.markdown("<div class='sec-h'>Analyst decision</div>", unsafe_allow_html=True)
        note = st.text_area("Note (optional)", key=f"note_{pick}", label_visibility="collapsed", placeholder="Optional analyst note...")
        b1,b2,b3 = st.columns(3)
        if b1.button("✅ Confirm — real near-miss", key=f"ok_{pick}", use_container_width=True): write_review(pick, 'confirmed', note or 'confirmed by analyst'); st.rerun()
        if b2.button("❌ Dismiss — false positive", key=f"dis_{pick}", use_container_width=True): write_review(pick, 'dismissed', note or 'dismissed by analyst'); st.rerun()
        if b3.button("⚠️ Escalate", key=f"esc_{pick}", use_container_width=True): write_review(pick, 'escalated', note or 'escalated by analyst'); st.rerun()

elif PAGE == "Coverage":
    st.markdown("<div class='page-title'>Coverage</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Honest audit trail: what the pipeline processed, per session.</div>", unsafe_allow_html=True)
    for _, r in coverage.iterrows():
        dur_s = f"~{r['duration_s']/60:.1f} min" if pd.notna(r['duration_s']) else "n/a"
        st.markdown(f"""<div class='scard'>
<div class='scard-head'><span class='scard-name'>{pretty_session(r['scene'])}<span class='scene-id'>{r['scene']}</span></span><span class='scard-chip'>{dur_s}</span></div>
<div class='scard-row'><div class='scard-stat'><div class='k-l'>Pedestrians tracked</div><div class='k-v'>{int(r['ped_count']) if pd.notna(r['ped_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Vehicles tracked</div><div class='k-v'>{int(r['veh_count']) if pd.notna(r['veh_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Candidate pairs</div><div class='k-v'>{int(r['candidate_pair_count']) if pd.notna(r['candidate_pair_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Near-miss events</div><div class='k-v'>{int(r['event_count'])}</div></div></div>
<div class='scard-row' style='margin-top:1rem;'><div class='scard-stat'><div class='k-l'>Critical</div><div class='k-v crit'>{int(r['critical_count'])}</div></div><div class='scard-stat'><div class='k-l'>Serious</div><div class='k-v ser'>{int(r['serious_count'])}</div></div><div class='scard-stat'><div class='k-l'>Moderate</div><div class='k-v mod'>{int(r['moderate_count'])}</div></div><div class='scard-stat'><div class='k-l'>Median PET</div><div class='k-v'>{r['median_pet_s']:.2f}s</div></div></div>
</div>""", unsafe_allow_html=True)

elif PAGE == "Reports":
    st.markdown("<div class='page-title'>Authority reports</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>One-click evidence packets ready to send to the city traffic engineering office.</div>", unsafe_allow_html=True)

    sess_display = {}
    for s in coverage['scene'].unique():
        sess_display[pretty_session(s)] = s
    c1, c2 = st.columns([2, 1])
    pick_label = c1.selectbox('Session for report', list(sess_display.keys()))
    pick_scene = sess_display[pick_label]
    gen = c2.button('Generate report', type='primary', use_container_width=True)

    if gen:
        from nearmiss.report import generate_report_html
        html = generate_report_html(pick_scene, events, coverage)
        today = datetime.now().strftime('%Y%m%d')
        safe_scene = pick_scene.replace('_', '-')
        out_path = os.path.join('runs', f'report_{safe_scene}_{today}.html')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        st.session_state['report_html'] = html
        st.session_state['report_path'] = out_path

    if 'report_html' in st.session_state:
        st.success(f"Report saved to: {st.session_state['report_path']}")
        st.download_button(label='Download HTML', data=st.session_state['report_html'],
            file_name=os.path.basename(st.session_state['report_path']), mime='text/html',
            use_container_width=False)
        st.markdown("<div class='sec-h'>Preview</div>", unsafe_allow_html=True)
        import streamlit.components.v1 as components
        components.html(st.session_state['report_html'], height=2000, scrolling=True)
