import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
"""NearMiss dashboard — real pipeline, real pilot data, no invented numbers."""
import os, json, sqlite3, re, math
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components
from nearmiss import mission_deck

DB = os.environ.get("NEARMISS_DB", str(pathlib.Path(__file__).resolve().parent.parent / "nearmiss.db"))
st.set_page_config(page_title="NearMiss · Jurong Lake Pilot", page_icon="⚠️", layout="wide", initial_sidebar_state="collapsed")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
:root{--bg:#07090e;--panel:rgba(18,27,43,.64);--panel-2:rgba(24,37,58,.7);--border:rgba(151,178,225,.15);--text:#eef4ff;--muted:#94a5bf;--brand:#83b7ff;--accent:#bd9cff;--crit:#ff6e86;--ser:#ffc16b;--mod:#59e0b0;--shadow:0 18px 55px rgba(0,0,0,.3);--glass:blur(18px) saturate(145%)}
html,body,[class*="css"]{font-family:'Plus Jakarta Sans',sans-serif !important;color:var(--text)}
.stApp{background:radial-gradient(ellipse at 14% 4%,rgba(47,101,202,.18),transparent 35%),radial-gradient(ellipse at 86% 13%,rgba(125,72,196,.16),transparent 30%),var(--bg);background-attachment:fixed;color:var(--text)}
.block-container{padding:1rem 1.8rem 2rem;max-width:1520px}
.mono{font-family:'JetBrains Mono',monospace}

/* top command header */
.cmd-header{display:flex;align-items:center;justify-content:space-between;padding:.7rem 1rem;background:linear-gradient(115deg,rgba(24,37,59,.74),rgba(18,25,42,.54));border:1px solid var(--border);border-radius:13px;margin-bottom:1rem;box-shadow:var(--shadow),inset 0 1px rgba(255,255,255,.06);backdrop-filter:var(--glass);-webkit-backdrop-filter:var(--glass)}
.brand-wrap{display:flex;align-items:center;gap:.7rem}
.brand-icon{width:30px;height:30px;background:linear-gradient(145deg,rgba(87,146,255,.28),rgba(172,120,255,.2));border:1px solid rgba(151,188,255,.32);border-radius:9px;display:flex;align-items:center;justify-content:center;color:var(--brand);font-size:1rem}
.brand-title{font-weight:800;font-size:1.02rem;letter-spacing:-.3px}
.site-pill{display:inline-flex;align-items:center;gap:.4rem;color:var(--muted);font-size:.74rem;margin-top:.05rem}
.dot-live{width:6px;height:6px;background:var(--mod);border-radius:50%;box-shadow:0 0 6px var(--mod);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.55}}
.header-right{display:flex;gap:.5rem;align-items:center}
.tb-chip{background:rgba(255,255,255,.05);border:1px solid var(--border);padding:.28rem .65rem;border-radius:7px;font-size:.7rem;color:#aab5c2;font-family:'JetBrains Mono',monospace}

/* bento kpi cards */
.kpi{background:linear-gradient(145deg,rgba(28,41,63,.72),rgba(15,23,37,.58));border:1px solid var(--border);border-radius:13px;padding:1rem 1.1rem;position:relative;overflow:hidden;height:100%;transition:transform .25s ease,border-color .25s ease,box-shadow .25s ease;backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.07),0 12px 32px rgba(0,0,0,.18)}
.kpi:hover{transform:translateY(-3px);border-color:rgba(146,183,255,.38);box-shadow:0 20px 50px rgba(0,0,0,.28)}
.kpi:before{content:'';position:absolute;left:0;top:10px;bottom:10px;width:2.5px;border-radius:2px}
.kpi.k-blue:before{background:var(--brand)}.kpi.k-crit:before{background:var(--crit)}.kpi.k-amber:before{background:var(--ser)}.kpi.k-green:before{background:var(--mod)}
.kpi-label{color:var(--muted);font-size:.68rem;letter-spacing:.5px;text-transform:uppercase;font-weight:700;margin-bottom:.35rem;display:flex;justify-content:space-between}
.kpi-value{font-size:2rem;font-weight:800;line-height:1;letter-spacing:-1px;font-variant-numeric:tabular-nums;font-family:'JetBrains Mono',monospace}
.kpi-value.v-crit{color:var(--crit)}.kpi-value.v-amber{color:var(--ser)}.kpi-value.v-green{color:var(--mod)}.kpi-value.v-blue{color:var(--brand)}
.kpi-sub{color:var(--muted);font-size:.72rem;margin-top:.4rem;line-height:1.4}

.sec-h{font-size:.88rem;font-weight:700;letter-spacing:-.1px;margin:1.1rem 0 .6rem;color:var(--text);padding-bottom:.45rem;border-bottom:1px solid var(--border)}
.scard{background:linear-gradient(145deg,rgba(25,38,58,.68),rgba(14,21,34,.58));border:1px solid var(--border);border-radius:13px;padding:1rem 1.1rem;margin-bottom:.7rem;backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.055),0 12px 30px rgba(0,0,0,.15)}
.scard-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:.7rem}
.scard-name{font-weight:700;font-size:.9rem}
.scard-name .scene-id{font-family:'JetBrains Mono',monospace;font-size:.66rem;color:var(--muted);font-weight:400;margin-left:.5rem}
.scard-chip{background:rgba(112,151,217,.12);border:1px solid rgba(151,178,225,.16);color:#c4d5f4;padding:.2rem .55rem;border-radius:7px;font-size:.68rem;font-weight:600}
.scard-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}
.scard-stat .k-l{color:var(--muted);font-size:.63rem;text-transform:uppercase;letter-spacing:.4px;margin-bottom:.15rem}
.scard-stat .k-v{font-size:1.1rem;font-weight:700;font-variant-numeric:tabular-nums;font-family:'JetBrains Mono',monospace}
.scard-stat .k-v.crit{color:var(--crit)}.scard-stat .k-v.ser{color:var(--ser)}.scard-stat .k-v.mod{color:var(--mod)}

.sev-chip{display:inline-block;padding:.17rem .5rem;border-radius:6px;font-size:.68rem;font-weight:700;letter-spacing:.2px}
.sev-crit{background:rgba(255,110,134,.12);color:var(--crit);border:1px solid rgba(255,110,134,.3)}
.sev-ser{background:rgba(255,193,107,.12);color:var(--ser);border:1px solid rgba(255,193,107,.28)}
.sev-mod{background:rgba(89,224,176,.12);color:var(--mod);border:1px solid rgba(89,224,176,.28)}

.detail-panel{background:linear-gradient(145deg,rgba(25,39,61,.72),rgba(14,21,34,.62));border:1px solid var(--border);border-radius:13px;padding:1.1rem 1.25rem;backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.06),0 14px 34px rgba(0,0,0,.18)}
.detail-row{margin-bottom:.6rem}
.detail-label{color:var(--muted);font-size:.65rem;text-transform:uppercase;letter-spacing:.5px;margin-bottom:.15rem}
.detail-value{color:var(--text);font-size:.9rem}
.detail-value code{background:rgba(100,140,205,.15);color:#c5d7fa;padding:.1rem .35rem;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:.8rem}
.obs{background:rgba(86,125,190,.1);border-left:2px solid var(--brand);padding:.7rem .85rem;border-radius:0 7px 7px 0;color:#d0ddf0;margin-top:.4rem;font-size:.84rem}
.caveat{background:rgba(255,193,107,.08);border-left:2px solid var(--ser);padding:.6rem .8rem;border-radius:0 7px 7px 0;color:#f0dcb8;margin-top:.5rem;font-size:.78rem}

/* role switcher */
.role-switcher{display:flex;background:rgba(14,20,32,.9);border:1px solid var(--border);border-radius:8px;padding:2px;gap:2px}

/* ask evidence */
.ask-deck{margin-top:.85rem;background:rgba(10,14,24,.55);border:1px solid rgba(168,85,247,.28);border-radius:10px;padding:.85rem 1.05rem}
.ask-chip-note{color:#d8b4fe;font-size:.72rem;margin-bottom:.5rem}
.ai-answer{margin-top:.6rem;background:#0b0f18;border-left:3px solid #a855f7;padding:.65rem .85rem;border-radius:0 6px 6px 0;font-size:.8rem;color:#e4dcfa;line-height:1.5}

[data-testid="stPlotlyChart"]{background:linear-gradient(145deg,rgba(25,39,61,.58),rgba(14,21,34,.48));border:1px solid var(--border);border-radius:13px;padding:.35rem .45rem;backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.06),0 14px 36px rgba(0,0,0,.18)}
.stButton>button,.stDownloadButton>button{border-radius:9px;font-weight:700;padding:.46rem .8rem;border:1px solid rgba(160,188,236,.2);background:linear-gradient(145deg,rgba(42,61,91,.64),rgba(22,33,52,.72));color:var(--text)}
.stButton>button:hover{background:linear-gradient(145deg,rgba(60,91,139,.75),rgba(30,47,73,.82));border-color:rgba(143,183,255,.48);color:#fff}
.page-title{font-size:1.5rem;font-weight:800;letter-spacing:-.6px;margin:.3rem 0 .15rem}
.page-sub{color:var(--muted);font-size:.84rem;margin-bottom:1rem}
@media(max-width:900px){.scard-row{grid-template-columns:repeat(2,1fr)}}
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

def normalize_wav_for_asr(raw_wav_bytes, target_rate=16000):
    """The ASR endpoint requires mono, 16-bit integer PCM at 16kHz or 24kHz
    (RIFF/WAVE container) -- st.audio_input records at whatever rate/channel
    count the browser gives (often 48kHz stereo), which would otherwise fail
    silently or get rejected. Downmix to mono, resample to 16kHz, and
    re-encode as 16-bit PCM before sending."""
    import io, wave
    import numpy as np

    with wave.open(io.BytesIO(raw_wav_bytes), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(sampwidth, np.int16)
    audio = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if sampwidth == 1:
        audio = audio - 128.0  # uint8 PCM is unsigned, centre it
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)

    if framerate != target_rate and len(audio) > 1:
        try:
            from scipy.signal import resample
            audio = resample(audio, int(len(audio) * target_rate / framerate))
        except ImportError:
            # crude fallback: linear-interpolate if scipy isn't available
            old_idx = np.linspace(0, len(audio) - 1, num=len(audio))
            new_len = max(1, int(len(audio) * target_rate / framerate))
            new_idx = np.linspace(0, len(audio) - 1, num=new_len)
            audio = np.interp(new_idx, old_idx, audio)

    peak = np.max(np.abs(audio)) or 1.0
    scale = 32767.0 / peak if peak > 32767.0 else 1.0
    audio_16 = np.clip(audio * scale, -32768, 32767).astype(np.int16)

    out = io.BytesIO()
    with wave.open(out, "wb") as wf_out:
        wf_out.setnchannels(1)
        wf_out.setsampwidth(2)
        wf_out.setframerate(target_rate)
        wf_out.writeframes(audio_16.tobytes())
    return out.getvalue()

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
    icon = {'critical': '⚠', 'serious': '⚡', 'moderate': '✓'}.get(sev, '•')
    return f'<span class="sev-chip {cls}">{icon} &nbsp;{sev}</span>'

def kpi_card(label, value, flavor='k-blue', val_cls='v-blue', subtitle=None, badge=None):
    sub = f'<div class="kpi-sub">{subtitle}</div>' if subtitle else ''
    bd = f'<span class="mono" style="font-size:.6rem;color:var(--muted);">{badge}</span>' if badge else ''
    return f'<div class="kpi {flavor}"><div class="kpi-label"><span>{label}</span>{bd}</div><div class="kpi-value {val_cls}">{value}</div>{sub}</div>'

def theme_plot(fig, height=320):
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94a5bf', family='Plus Jakarta Sans', size=11), height=height, margin=dict(l=12,r=12,t=22,b=12), hoverlabel=dict(bgcolor='#171e26', bordercolor='#354150', font=dict(color='#eef4ff', family='Plus Jakarta Sans')), xaxis=dict(showgrid=False, zeroline=False, linecolor='#252d37', tickfont=dict(color='#aab5c2')), yaxis=dict(showgrid=False, zeroline=False, linecolor='#252d37', tickfont=dict(color='#aab5c2')))
    return fig

def wilson_ci(x, n, z=1.959963985):
    """Real Wilson score interval. x = events, n = candidate pairs. Returns rate-per-1000 and CI bounds."""
    if not n:
        return (0.0, 0.0, 0.0)
    phat = x / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    adj = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    lo = max(0.0, (center - adj) / denom)
    hi = min(1.0, (center + adj) / denom)
    return (phat * 1000, lo * 1000, hi * 1000)

ROLE_COPY = {
    "Engineer": dict(
        label="Engineer",
        overview_note="Raw conflict telemetry, PET distribution, and exposure-normalized rates for infrastructure review.",
    ),
    "Enforcement": dict(
        label="Enforcement",
        overview_note="Where and when conflicts cluster, to target patrol presence and signal-timing enforcement.",
    ),
    "Resident": dict(
        label="Resident",
        overview_note="Plain-language safety summary for people who use this crossing.",
    ),
}

# --- top bar ---
events = load_events()
coverage = load_coverage()
total_duration_min = coverage['duration_s'].dropna().sum() / 60 if 'duration_s' in coverage else 0

st.markdown(f"""
<div class="cmd-header">
  <div class="brand-wrap">
    <div class="brand-icon">⚠</div>
    <div>
      <div class="brand-title">NearMiss</div>
      <div class="site-pill"><span class="dot-live"></span>Jurong Lake Pilot Site · {len(coverage)} recording sessions · ~{total_duration_min:.0f} min analysed</div>
    </div>
  </div>
  <div class="header-right">
    <span class="tb-chip">site_id · fluid-jurong-01</span>
    <span class="tb-chip">pilot · live</span>
  </div>
</div>
""", unsafe_allow_html=True)

PAGE = st.radio("Section", ["Mission Deck", "Review Queue", "Coverage", "Reports"], horizontal=True, label_visibility="collapsed")
role = "Engineer"

# ===============================================================
if PAGE == "Mission Deck":
    try:
        deck_html = mission_deck.build_html(events, coverage)
        components.html(deck_html, height=1500, scrolling=True)
    except Exception as e:
        st.error(f"Mission Deck failed to render: {e}")
    PAGE = None  # skip the legacy branches below

if PAGE == "Overview":
    st.markdown(f"""<div class='detail-panel' style='margin-bottom:1rem;'>
<div style='font-size:1.3rem;font-weight:800;'>Pilot Overview</div>
<div style='color:var(--muted);font-size:.85rem;margin-top:.3rem;'>{ROLE_COPY[role]['overview_note']}</div>
</div>""", unsafe_allow_html=True)

    tot = len(events)
    crit = int((events['severity']=='critical').sum())
    flagged = int((events['needs_human_review']==1).sum())
    pending = int(((events['needs_human_review']==1) & (events['human_review_status']=='pending')).sum())

    reviewed_mask = events['spark_status'] != 'not_yet_reviewed'
    reviewed_n = int(reviewed_mask.sum())
    confirmed_n = int(events.loc[reviewed_mask, 'spark_status'].isin(['supported','supported_with_flag']).sum())
    pass_rate = (confirmed_n / reviewed_n * 100) if reviewed_n else 0.0

    total_cp = int(coverage['candidate_pair_count'].sum()) if 'candidate_pair_count' in coverage else 0
    rate, lo, hi = wilson_ci(tot, total_cp)

    if role == "Resident":
        c1, c2, c3 = st.columns(3)
        c1.markdown(kpi_card("Crossings with a close call", f"1 in {max(1, round(total_cp/max(tot,1)))}", 'k-crit', 'v-crit', subtitle="Candidate pedestrian–vehicle encounters that became a measured near-miss"), unsafe_allow_html=True)
        riskiest = coverage.sort_values('critical_count', ascending=False).iloc[0] if len(coverage) else None
        c2.markdown(kpi_card("Highest-risk session", pretty_session(riskiest['scene']) if riskiest is not None else "n/a", 'k-amber', 'v-amber', subtitle=f"{int(riskiest['critical_count'])} critical events recorded" if riskiest is not None else ""), unsafe_allow_html=True)
        c3.markdown(kpi_card("Median reaction window", f"{coverage['median_pet_s'].min():.2f}s", 'k-blue', 'v-blue', subtitle="Shortest median gap between pedestrian clearing and vehicle arrival, across sessions"), unsafe_allow_html=True)
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.markdown(kpi_card("Total events", tot, 'k-blue', 'v-blue'), unsafe_allow_html=True)
        c2.markdown(kpi_card("⚠ Critical (PET ≤ 1s)", crit, 'k-crit', 'v-crit'), unsafe_allow_html=True)
        c3.markdown(kpi_card("Conflict rate", f"{rate:.1f}", 'k-amber', 'v-amber', subtitle=f"per 1,000 candidate ped–vehicle pairs · 95% Wilson CI [{lo:.1f}–{hi:.1f}]", badge="WILSON 95%"), unsafe_allow_html=True)
        c4.markdown(kpi_card("Spark confirmation rate", f"{pass_rate:.0f}%", 'k-green', 'v-green', subtitle=f"{confirmed_n} of {reviewed_n} visually reviewed events confirmed as real conflicts"), unsafe_allow_html=True)

    chart_left, chart_right = st.columns([1, 1.45], gap="medium")
    with chart_left:
        st.markdown("<div class='sec-h'>⚠ Severity distribution</div>", unsafe_allow_html=True)
        sev = events['severity'].value_counts().reindex(['critical','serious','moderate']).fillna(0).astype(int)
        fig = go.Figure()
        colors = {'critical':'#ff6e86','serious':'#ffc16b','moderate':'#59e0b0'}
        for s in ['critical','serious','moderate']:
            label = {'critical':'⚠ Critical', 'serious':'⚡ Serious', 'moderate':'✓ Moderate'}[s]
            fig.add_trace(go.Bar(x=[label], y=[int(sev[s])], marker=dict(color=colors[s], line=dict(width=0)), text=[int(sev[s])], textposition='outside', textfont=dict(size=15, color='#eef4ff'), name=label, hovertemplate=f'{label}: %{{y}} events<extra></extra>', showlegend=False))
        st.plotly_chart(theme_plot(fig, 300), use_container_width=True)

    with chart_right:
        st.markdown("<div class='sec-h'>PET distribution · time gap (seconds)</div>", unsafe_allow_html=True)
        fig2 = px.histogram(events, x='our_pet_s', nbins=20, color='severity', color_discrete_map={'critical':'#ff6e86','serious':'#ffc16b','moderate':'#59e0b0'}, labels={'our_pet_s':'PET (seconds)'})
        fig2.update_traces(opacity=0.88, marker_line_width=0, hovertemplate='PET: %{x:.2f}s<br>Events: %{y}<extra></extra>')
        st.plotly_chart(theme_plot(fig2, 300), use_container_width=True)

    st.markdown("<div class='sec-h'>Per-session summary</div>", unsafe_allow_html=True)
    for _, r in coverage.iterrows():
        dur_s = f"~{r['duration_s']/60:.1f} min" if pd.notna(r['duration_s']) else "n/a"
        st.markdown(f"""<div class='scard'>
<div class='scard-head'><span class='scard-name'>{pretty_session(r['scene'])}<span class='scene-id'>{r['scene']}</span></span><span class='scard-chip'>{dur_s}</span></div>
<div class='scard-row'><div class='scard-stat'><div class='k-l'>Pedestrians</div><div class='k-v'>{int(r['ped_count']) if pd.notna(r['ped_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Vehicles</div><div class='k-v'>{int(r['veh_count']) if pd.notna(r['veh_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Candidate pairs</div><div class='k-v'>{int(r['candidate_pair_count']) if pd.notna(r['candidate_pair_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Events</div><div class='k-v'>{int(r['event_count'])}</div></div></div>
<div class='scard-row' style='margin-top:1rem;'><div class='scard-stat'><div class='k-l'>⚠ Critical</div><div class='k-v crit'>{int(r['critical_count'])}</div></div><div class='scard-stat'><div class='k-l'>⚡ Serious</div><div class='k-v ser'>{int(r['serious_count'])}</div></div><div class='scard-stat'><div class='k-l'>✓ Moderate</div><div class='k-v mod'>{int(r['moderate_count'])}</div></div><div class='scard-stat'><div class='k-l'>Median PET</div><div class='k-v'>{r['median_pet_s']:.2f}s</div></div></div>
</div>""", unsafe_allow_html=True)

elif PAGE == "Hotspot":
    st.markdown("<div class='page-title'>Conflict hotspot map</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Real-world conflict locations (meters), derived from FLUID trajectory data at each event's closest-approach frame. Not a schematic — plotted from measured positions.</div>", unsafe_allow_html=True)

    sess_display = {'(all sessions)':'(all)'}
    for s in coverage['scene'].unique(): sess_display[pretty_session(s)] = s
    pick_label = st.selectbox("Session", list(sess_display.keys()))
    pick_scene = sess_display[pick_label]

    hdf = events.dropna(subset=['loc_x_m','loc_y_m']).copy()
    if pick_scene != '(all)':
        hdf = hdf[hdf['scene'] == pick_scene]

    if len(hdf):
        fig = go.Figure()
        colors = {'critical':'#ff6e86','serious':'#ffc16b','moderate':'#59e0b0'}
        for sev in ['moderate','serious','critical']:
            sub = hdf[hdf['severity'] == sev]
            if len(sub):
                fig.add_trace(go.Scatter(
                    x=sub['loc_x_m'], y=sub['loc_y_m'], mode='markers',
                    marker=dict(size=12, color=colors[sev], line=dict(width=1, color='rgba(255,255,255,.4)')),
                    name=sev.capitalize(),
                    text=sub['event_id'],
                    hovertemplate='<b>%{text}</b><br>PET: '+sub['our_pet_s'].round(2).astype(str)+'s<br>('+sub['loc_x_m'].round(1).astype(str)+', '+sub['loc_y_m'].round(1).astype(str)+') m<extra></extra>',
                ))
        fig.update_layout(xaxis_title='x (meters, relative to frame center)', yaxis_title='y (meters, relative to frame center)')
        st.plotly_chart(theme_plot(fig, 520), use_container_width=True)

        st.markdown("<div class='sec-h'>Inspect an event from this map</div>", unsafe_allow_html=True)
        pick_ev = st.selectbox("Event", hdf.sort_values('our_pet_s')['event_id'].tolist(), key="hotspot_pick")
        st.session_state['_jump_to_event'] = pick_ev
        st.info("Open this event on the **Events** tab (selection carries over) to see frames and Spark's review.")
    else:
        st.markdown("<div class='detail-panel'>No located events for this session.</div>", unsafe_allow_html=True)

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
    st.markdown(f"<div style='color:var(--muted);font-size:.85rem;margin:.5rem 0 1rem 0;'>Showing {len(df_show)} of {len(events)} events</div>", unsafe_allow_html=True)
    st.dataframe(df_show, use_container_width=True, hide_index=True, column_config={'our_pet_s': st.column_config.NumberColumn('PET (s)', format='%.2f')})

    if len(df):
        st.markdown("<div class='sec-h'>Inspect one event</div>", unsafe_allow_html=True)
        ev_list = df['event_id'].tolist()
        jump_to = st.session_state.pop('_jump_to_event', None)
        default_idx = ev_list.index(jump_to) if jump_to in ev_list else 0
        pick_ev = st.selectbox("Event", ev_list, index=default_idx, label_visibility="collapsed")
        row = df[df['event_id']==pick_ev].iloc[0]
        cL, cR = st.columns([3,2])
        with cL:
            detail = f"""<div class='detail-panel'>
<div class='detail-row'><div class='detail-label'>Session</div><div class='detail-value'>{pretty_session(row['scene'])} <code>{row['scene']}</code></div></div>
<div class='detail-row'><div class='detail-label'>Agents</div><div class='detail-value'>Pedestrian <code>{int(row['ped_id'])}</code> &nbsp; · &nbsp; Vehicle <code>{int(row['veh_id'])}</code></div></div>"""
            if pd.notna(row.get('vehicle_type')):
                detail += f"<div class='detail-row'><div class='detail-label'>Vehicle type (FLUID auto-tracker)</div><div class='detail-value'><code>{row['vehicle_type']}</code></div></div>"
            if pd.notna(row['conflict_time_s']): detail += f"<div class='detail-row'><div class='detail-label'>Conflict time</div><div class='detail-value'>{row['conflict_time_s']:.1f} s into recording</div></div>"
            if pd.notna(row['closest_approach_m']): detail += f"<div class='detail-row'><div class='detail-label'>Closest approach</div><div class='detail-value'>{row['closest_approach_m']:.2f} m</div></div>"
            detail += f"<div class='detail-row'><div class='detail-label'>Our PET</div><div class='detail-value' style='font-size:1.4rem;font-weight:700;'>{row['our_pet_s']:.2f} s &nbsp; {sev_chip(row['severity'])}</div></div>"
            detail += f"<div class='detail-row'><div class='detail-label'>Spark status</div><div class='detail-value'><code>{row['spark_status']}</code></div></div>"
            flags = safe_str(row['spark_flags'])
            if flags: detail += f"<div class='detail-row'><div class='detail-label'>Flags</div><div class='detail-value'><code>{flags}</code></div></div>"
            obs = safe_str(row['spark_observation'])
            if obs: detail += f"<div class='detail-row'><div class='detail-label'>Spark observation</div><div class='obs'>{obs}</div></div>"
            if row.get('vehicle_type') == 'car' and int(row['veh_id']) == 871:
                detail += "<div class='caveat'>Note: FLUID's own tracker labels this vehicle \"car\", but Spark's independent visual review described it as a small scooter/motorcycle. We keep both — it's a real disagreement between the two sources, not an error.</div>"
            detail += "</div>"
            st.markdown(detail, unsafe_allow_html=True)

            # Feature: Ask about this event — grounded strictly in stored evidence, no live model call
            st.markdown("<div class='ask-deck'>", unsafe_allow_html=True)
            st.markdown("<div class='ask-chip-note'>Ask about this event — answers are compiled only from this event's stored evidence (PET, severity, Spark's own observation). No new inference is made.</div>", unsafe_allow_html=True)
            q_cols = st.columns(3)
            answer = None
            if q_cols[0].button("Why is this critical?", key=f"q1_{pick_ev}"):
                if row['severity'] == 'critical':
                    answer = f"Measured PET is {row['our_pet_s']:.2f}s, at or below the 1.0s critical threshold — meaning the vehicle reached the pedestrian's space within about {row['our_pet_s']:.2f} seconds of the pedestrian clearing it."
                else:
                    answer = f"This event is classified **{row['severity']}**, not critical. Its PET is {row['our_pet_s']:.2f}s, above the 1.0s critical cutoff."
            if q_cols[1].button("What did Spark say?", key=f"q2_{pick_ev}"):
                if obs:
                    answer = obs
                else:
                    answer = "Spark has not yet visually reviewed this event — only the deterministic physics (PET/severity) has been computed for it."
            if q_cols[2].button("Is this confirmed?", key=f"q3_{pick_ev}"):
                st_ = row['spark_status']
                if st_ == 'supported':
                    answer = "Yes — Spark's independent visual review of the evidence frames supported this as a real conflict, without being shown the PET value or severity label."
                elif st_ == 'supported_with_flag':
                    answer = "Spark supported this as a real conflict but flagged a caveat in its review — see Flags above."
                elif st_ == 'rejected':
                    answer = "No — Spark's visual review rejected this as a real near-miss (e.g. the actual closest approach was too far to be a genuine conflict)."
                else:
                    answer = "Not yet — this event hasn't had a Spark visual review. Its status is physics-only."
            if answer:
                st.markdown(f"<div class='ai-answer'>{answer}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

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
<div class='detail-row'><div class='detail-label'>PET</div><div class='detail-value' style='font-size:1.4rem; font-weight:700;'>{row['our_pet_s']:.2f} s &nbsp; {sev_chip(row['severity'])}</div></div>"""
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
        voice_col, _ = st.columns([2, 3])
        with voice_col:
            if hasattr(st, "audio_input"):
                voice_clip = st.audio_input("Or record a voice note", key=f"voice_{pick}")
            else:
                st.caption("Voice notes need a newer Streamlit (`pip install -U streamlit`) — using file upload instead.")
                voice_clip = st.file_uploader("Or upload a voice note (wav/mp3)", type=["wav", "mp3", "m4a"], key=f"voice_{pick}")
            if voice_clip is not None:
                if st.button("🎙️ Transcribe to note", key=f"transcribe_{pick}", use_container_width=True):
                    try:
                        import requests as _requests
                        key = os.environ["MODEL_API_KEY"]
                        audio_bytes = normalize_wav_for_asr(voice_clip.getvalue())
                        req_part = json.dumps({
                            "mode": "DIARIZATION",
                            "model": "muse-voice-transcribe-1.0",
                            "audioEncoding": "WAV",
                        })
                        r = _requests.post(
                            "https://api.meta.ai/v1/asr/transcribe",
                            headers={"Authorization": f"Bearer {key}"},
                            files={
                                "audio": ("voice_note.wav", audio_bytes, "audio/wav"),
                                "request": (None, req_part, "application/json"),
                            },
                            timeout=30,
                        )
                        r.raise_for_status()
                        transcript = r.json().get("transcript", "").strip()
                        st.session_state[f"note_{pick}"] = transcript or "(transcription returned no text)"
                        st.rerun()
                    except KeyError:
                        st.error("MODEL_API_KEY isn't set in this shell — voice transcription needs it (same key used for Spark review).")
                    except Exception as e:
                        st.error(f"Transcription failed: {e}")
        note = st.text_area("Note (optional)", key=f"note_{pick}", label_visibility="collapsed", placeholder="Optional analyst note — type, or record a voice note above and transcribe it in.")
        b1,b2,b3,b4 = st.columns(4)
        if b1.button("✅ Confirm", key=f"ok_{pick}", use_container_width=True): write_review(pick, 'confirmed', note or 'confirmed by analyst'); st.rerun()
        if b2.button("❌ Dismiss", key=f"dis_{pick}", use_container_width=True): write_review(pick, 'dismissed', note or 'dismissed by analyst'); st.rerun()
        if b3.button("❔ Unclear", key=f"unc_{pick}", use_container_width=True): write_review(pick, 'unclear', note or 'marked unclear by analyst'); st.rerun()
        if b4.button("⚠️ Escalate", key=f"esc_{pick}", use_container_width=True): write_review(pick, 'escalated', note or 'escalated by analyst'); st.rerun()

elif PAGE == "Coverage":
    st.markdown("<div class='page-title'>Coverage</div>", unsafe_allow_html=True)
    st.markdown("<div class='page-sub'>Honest audit trail: what the pipeline processed, per session — and what it did not.</div>", unsafe_allow_html=True)
    for _, r in coverage.iterrows():
        dur_s = f"~{r['duration_s']/60:.1f} min" if pd.notna(r['duration_s']) else "n/a"
        st.markdown(f"""<div class='scard'>
<div class='scard-head'><span class='scard-name'>{pretty_session(r['scene'])}<span class='scene-id'>{r['scene']}</span></span><span class='scard-chip'>{dur_s}</span></div>
<div class='scard-row'><div class='scard-stat'><div class='k-l'>Pedestrians tracked</div><div class='k-v'>{int(r['ped_count']) if pd.notna(r['ped_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Vehicles tracked</div><div class='k-v'>{int(r['veh_count']) if pd.notna(r['veh_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Candidate pairs</div><div class='k-v'>{int(r['candidate_pair_count']) if pd.notna(r['candidate_pair_count']) else 'n/a'}</div></div><div class='scard-stat'><div class='k-l'>Near-miss events</div><div class='k-v'>{int(r['event_count'])}</div></div></div>
<div class='scard-row' style='margin-top:1rem;'><div class='scard-stat'><div class='k-l'>⚠ Critical</div><div class='k-v crit'>{int(r['critical_count'])}</div></div><div class='scard-stat'><div class='k-l'>⚡ Serious</div><div class='k-v ser'>{int(r['serious_count'])}</div></div><div class='scard-stat'><div class='k-l'>✓ Moderate</div><div class='k-v mod'>{int(r['moderate_count'])}</div></div><div class='scard-stat'><div class='k-l'>Median PET</div><div class='k-v'>{r['median_pet_s']:.2f}s</div></div></div>
</div>""", unsafe_allow_html=True)

    reviewed_n = int((events['spark_status'] != 'not_yet_reviewed').sum())
    st.markdown(f"""<div class='detail-panel' style='margin-top:1rem;'>
<div class='sec-h' style='margin-top:0;'>What this pilot does and doesn't cover</div>
<div class='detail-value' style='line-height:1.6;'>
• Every event's PET and severity comes from deterministic physics on real tracked trajectories — not an AI guess.<br>
• {reviewed_n} of {len(events)} events additionally have a Spark visual review with rendered evidence frames; the remaining {len(events)-reviewed_n} are physics-verified but not yet visually reviewed.<br>
• Trajectory tracking (pedestrian/vehicle positions, IDs, and vehicle-type labels) comes from FLUID's own published tracker — not from a model we built. Our pipeline is the physics (PET) and the visual verification (Spark) layered on top.<br>
• Vehicle-type labels occasionally disagree with Spark's independent visual read of the same vehicle (see Events tab) — we surface that disagreement rather than silently picking one.<br>
• Coverage is limited to daylight footage from 3 recorded sessions at one intersection. Absence of detections outside these windows reflects what was recorded, not that the crossing is safe at other times.
</div></div>""", unsafe_allow_html=True)

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
