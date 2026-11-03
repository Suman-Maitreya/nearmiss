import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
"""NearMiss dashboard — product build (site conceit, branded header, report)."""
import os, json, sqlite3, re
from datetime import datetime
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

DB = os.environ.get("NEARMISS_DB", str(pathlib.Path(__file__).resolve().parent.parent / "nearmiss.db"))
st.set_page_config(page_title="NearMiss · Jurong Lake Pilot", page_icon="⚠️", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#070b14;--panel:rgba(18,27,43,.64);--panel-2:rgba(24,37,58,.7);--border:rgba(151,178,225,.15);--text:#eef4ff;--muted:#94a5bf;--brand:#83b7ff;--accent:#bd9cff;--crit:#ff6e86;--ser:#ffc16b;--mod:#59e0b0;--shadow:0 18px 55px rgba(0,0,0,.3);--glass:blur(18px) saturate(145%)}
html,body,[class*="css"]{font-family:'Inter',sans-serif !important;color:var(--text)}
.stApp{background:radial-gradient(ellipse at 14% 4%,rgba(47,101,202,.2),transparent 35%),radial-gradient(ellipse at 86% 13%,rgba(125,72,196,.18),transparent 30%),radial-gradient(ellipse at 68% 82%,rgba(29,160,158,.08),transparent 34%),var(--bg);background-attachment:fixed;color:var(--text)}
.block-container{padding:1.1rem 2rem 2rem;max-width:1500px}
section[data-testid="stSidebar"]{background:rgba(8,14,25,.74);border-right:1px solid var(--border);backdrop-filter:var(--glass);-webkit-backdrop-filter:var(--glass)}
section[data-testid="stSidebar"] *{color:var(--text) !important}
section[data-testid="stSidebar"] [data-testid="stRadio"] label{border-radius:9px;padding:.28rem .45rem;transition:background .22s ease,transform .22s ease,border-color .22s ease}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:rgba(127,169,255,.12);transform:translateX(3px)}
/* Product bar */
.topbar{display:flex;align-items:center;justify-content:space-between;padding:.78rem 1rem;background:linear-gradient(115deg,rgba(24,37,59,.74),rgba(18,25,42,.54));border:1px solid var(--border);border-radius:13px;margin-bottom:1.2rem;box-shadow:var(--shadow),inset 0 1px rgba(255,255,255,.06);backdrop-filter:var(--glass);-webkit-backdrop-filter:var(--glass);animation:rise .55s ease both}
.tb-left{display:flex;align-items:center;gap:.8rem}.tb-logo{width:34px;height:34px;background:linear-gradient(145deg,rgba(87,146,255,.24),rgba(172,120,255,.17));border:1px solid rgba(151,188,255,.3);border-radius:10px;display:flex;align-items:center;justify-content:center;color:var(--brand);font-size:1rem;box-shadow:inset 0 1px rgba(255,255,255,.12),0 0 24px rgba(81,135,255,.13)}
.tb-brand{font-weight:700;font-size:1rem;letter-spacing:-.35px}.tb-site{color:var(--muted);font-size:.76rem;margin-top:.08rem}.tb-site .green-dot{display:inline-block;width:7px;height:7px;background:var(--mod);border-radius:50%;margin-right:.4rem;vertical-align:middle;animation:pulse 2s infinite}
.tb-right{display:flex;gap:.45rem;align-items:center}.tb-chip{background:#151b22;border:1px solid var(--border);padding:.28rem .65rem;border-radius:7px;font-size:.7rem;color:#aab5c2;font-family:'JetBrains Mono',monospace}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(89,224,176,.42)}50%{opacity:.78;box-shadow:0 0 0 5px rgba(89,224,176,0)}}
@keyframes rise{from{opacity:0;transform:translateY(11px);filter:blur(3px)}to{opacity:1;transform:translateY(0);filter:blur(0)}}
@keyframes ambient{0%,100%{transform:translate3d(0,0,0) scale(1);opacity:.6}50%{transform:translate3d(-10px,9px,0) scale(1.08);opacity:1}}
/* Overview */
.hero{background:linear-gradient(115deg,rgba(29,46,75,.72),rgba(20,28,49,.56) 60%,rgba(36,30,68,.48));padding:1.5rem 1.7rem;border-radius:16px;margin-bottom:1rem;border:1px solid rgba(162,190,239,.2);position:relative;overflow:hidden;box-shadow:var(--shadow),inset 0 1px rgba(255,255,255,.09);backdrop-filter:var(--glass);-webkit-backdrop-filter:var(--glass);animation:rise .6s .05s ease both}
.hero:after{content:"";position:absolute;right:-90px;top:-150px;width:340px;height:340px;border-radius:50%;background:radial-gradient(circle,rgba(117,163,255,.25),rgba(163,108,255,.1) 33%,transparent 68%);filter:blur(7px);pointer-events:none;animation:ambient 9s ease-in-out infinite}
.hero-title{font-size:1.85rem;font-weight:700;line-height:1.15;letter-spacing:-.8px;margin:0;color:#f2f5f9}
.hero-sub{color:#b3c2d8;margin-top:.35rem;font-size:.88rem}.hero-pill{display:inline-flex;margin-top:.75rem;padding:.28rem .62rem;background:rgba(113,157,232,.11);border:1px solid rgba(143,179,240,.24);border-radius:7px;font-size:.68rem;color:#c8d8f5;letter-spacing:.15px;box-shadow:inset 0 1px rgba(255,255,255,.06)}
/* Metric cards */
.kpi{background:linear-gradient(145deg,rgba(28,41,63,.72),rgba(15,23,37,.58));border:1px solid var(--border);border-radius:13px;padding:.95rem 1rem;position:relative;overflow:hidden;height:100%;transition:transform .28s cubic-bezier(.2,.8,.2,1),border-color .28s ease,box-shadow .28s ease;animation:rise .58s ease both;backdrop-filter:var(--glass);-webkit-backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.07),0 12px 32px rgba(0,0,0,.18)}
.kpi:after{content:"";position:absolute;inset:0;background:linear-gradient(118deg,rgba(255,255,255,.065),transparent 35%);pointer-events:none}
.kpi:hover,.scard:hover,.detail-panel:hover{transform:translateY(-4px) scale(1.006);border-color:rgba(146,183,255,.38);box-shadow:0 20px 50px rgba(0,0,0,.28),0 0 26px rgba(91,145,255,.09),inset 0 1px rgba(255,255,255,.1)}
.kpi:before{content:'';position:absolute;left:0;top:10px;bottom:10px;width:2px;border-radius:2px}.kpi.k-blue:before{background:var(--brand)}.kpi.k-crit:before{background:var(--crit)}.kpi.k-amber:before{background:var(--ser)}.kpi.k-green:before{background:var(--mod)}
.kpi-label{color:var(--muted);font-size:.69rem;letter-spacing:.55px;text-transform:uppercase;font-weight:600;margin-bottom:.35rem}.kpi-value{font-size:2rem;font-weight:700;line-height:1;letter-spacing:-1px;font-variant-numeric:tabular-nums}
.kpi-value.v-crit{color:var(--crit)}.kpi-value.v-amber{color:var(--ser)}.kpi-value.v-green{color:var(--mod)}.kpi-value.v-blue{color:var(--brand)}.kpi-sub{color:var(--muted);font-size:.72rem;margin-top:.35rem}
.sec-h{font-size:.9rem;font-weight:600;letter-spacing:-.1px;margin:1.25rem 0 .65rem;color:var(--text);padding-bottom:.5rem;border-bottom:1px solid var(--border)}
.scard{background:linear-gradient(145deg,rgba(25,38,58,.68),rgba(14,21,34,.58));border:1px solid var(--border);border-radius:13px;padding:1rem 1.1rem;margin-bottom:.75rem;transition:transform .28s cubic-bezier(.2,.8,.2,1),border-color .28s ease,box-shadow .28s ease;backdrop-filter:var(--glass);-webkit-backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.055),0 12px 30px rgba(0,0,0,.15)}.scard-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem}.scard-name{font-weight:600;font-size:.9rem;color:var(--text)}.scard-name .scene-id{font-family:'JetBrains Mono',monospace;font-size:.67rem;color:var(--muted);font-weight:400;margin-left:.55rem}.scard-chip{background:rgba(112,151,217,.12);border:1px solid rgba(151,178,225,.16);color:#c4d5f4;padding:.2rem .55rem;border-radius:7px;font-size:.68rem;font-weight:500}
.scard-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}.scard-stat .k-l{color:var(--muted);font-size:.64rem;text-transform:uppercase;letter-spacing:.45px;margin-bottom:.17rem}.scard-stat .k-v{font-size:1.15rem;font-weight:600;font-variant-numeric:tabular-nums}.scard-stat .k-v.crit{color:var(--crit)}.scard-stat .k-v.ser{color:var(--ser)}.scard-stat .k-v.mod{color:var(--mod)}
.sev-chip{display:inline-block;padding:.17rem .48rem;border-radius:6px;font-size:.68rem;font-weight:600;letter-spacing:.2px}.sev-crit{background:rgba(255,101,119,.1);color:var(--crit);border:1px solid rgba(255,101,119,.26)}.sev-ser{background:rgba(255,182,92,.1);color:var(--ser);border:1px solid rgba(255,182,92,.25)}.sev-mod{background:rgba(85,214,160,.1);color:var(--mod);border:1px solid rgba(85,214,160,.25)}
.detail-panel{background:linear-gradient(145deg,rgba(25,39,61,.72),rgba(14,21,34,.62));border:1px solid var(--border);border-radius:13px;padding:1.1rem 1.25rem;transition:transform .28s ease,border-color .28s ease,box-shadow .28s ease;backdrop-filter:var(--glass);-webkit-backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.06),0 14px 34px rgba(0,0,0,.18)}.detail-row{margin-bottom:.65rem}.detail-label{color:var(--muted);font-size:.66rem;text-transform:uppercase;letter-spacing:.55px;margin-bottom:.15rem}.detail-value{color:var(--text);font-size:.9rem}.detail-value code{background:rgba(100,140,205,.15);color:#c5d7fa;padding:.1rem .35rem;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:.8rem}.obs{background:rgba(86,125,190,.1);border-left:2px solid var(--brand);padding:.7rem .85rem;border-radius:0 7px 7px 0;font-style:normal;color:#d0ddf0;margin-top:.45rem;font-size:.84rem}
[data-testid="stDataFrame"]{background:rgba(15,23,37,.68) !important;border-radius:12px;border:1px solid var(--border) !important;backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.05),var(--shadow)}
.stButton>button,.stDownloadButton>button{border-radius:9px;font-weight:600;padding:.48rem .8rem;border:1px solid rgba(160,188,236,.2);background:linear-gradient(145deg,rgba(42,61,91,.64),rgba(22,33,52,.72));color:var(--text);transition:all .22s ease;box-shadow:inset 0 1px rgba(255,255,255,.08)}.stButton>button:hover,.stDownloadButton>button:hover{background:linear-gradient(145deg,rgba(60,91,139,.75),rgba(30,47,73,.82));border-color:rgba(143,183,255,.48);color:#fff;transform:translateY(-2px);box-shadow:0 10px 28px rgba(38,87,162,.2),inset 0 1px rgba(255,255,255,.12)}button[kind="primary"]{background:linear-gradient(115deg,#91bbff,#c3a6ff)!important;color:#0c1220!important;border:1px solid rgba(223,232,255,.7)!important;box-shadow:0 5px 24px rgba(107,145,255,.22),inset 0 1px rgba(255,255,255,.5)!important}.stTextArea textarea,.stSelectbox div[data-baseweb="select"],.stMultiSelect div[data-baseweb="select"]{background:rgba(15,23,37,.75)!important;border-color:var(--border)!important;border-radius:9px!important;backdrop-filter:var(--glass)}
.page-title{font-size:1.65rem;font-weight:700;letter-spacing:-.65px;margin:.35rem 0 .18rem}.page-sub{color:var(--muted);font-size:.86rem;margin-bottom:1.1rem}
.report-stub{padding:2.5rem;text-align:center;background:var(--panel);border:1px dashed var(--border);border-radius:12px}.report-stub .big{font-size:2.2rem;margin-bottom:.5rem}
[data-testid="stPlotlyChart"]{background:linear-gradient(145deg,rgba(25,39,61,.58),rgba(14,21,34,.48));border:1px solid var(--border);border-radius:13px;padding:.35rem .45rem;animation:rise .6s ease both;backdrop-filter:var(--glass);-webkit-backdrop-filter:var(--glass);box-shadow:inset 0 1px rgba(255,255,255,.06),0 14px 36px rgba(0,0,0,.18)}
@media(max-width:900px){.block-container{padding:.8rem 1rem 1.5rem}.tb-chip{display:none}.scard-row{gap:.55rem}.hero-title{font-size:1.55rem}}
@media(max-width:600px){.topbar{align-items:flex-start}.tb-site{max-width:220px}.scard-row{grid-template-columns:repeat(2,1fr)}.hero{padding:1.1rem}.kpi-value{font-size:1.7rem}}
@supports not (backdrop-filter:blur(1px)){.topbar,.hero,.kpi,.scard,.detail-panel,[data-testid="stPlotlyChart"]{background-color:#131d2d}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important}}
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
    icon = {'critical': '⚠', 'serious': '⚡', 'moderate': '✓'}.get(sev, '•')
    return f'<span class="sev-chip {cls}">{icon} &nbsp;{sev}</span>'

def kpi_card(label, value, flavor='k-blue', val_cls='v-blue', subtitle=None):
    sub = f'<div class="kpi-sub">{subtitle}</div>' if subtitle else ''
    return f'<div class="kpi {flavor}"><div class="kpi-label">{label}</div><div class="kpi-value {val_cls}">{value}</div>{sub}</div>'

def theme_plot(fig, height=320):
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#8995a3', family='Inter', size=11), height=height, margin=dict(l=12,r=12,t=22,b=12), hoverlabel=dict(bgcolor='#171e26', bordercolor='#354150', font=dict(color='#edf1f5', family='Inter')), xaxis=dict(showgrid=False, zeroline=False, linecolor='#252d37', tickfont=dict(color='#aab5c2')), yaxis=dict(showgrid=False, zeroline=False, linecolor='#252d37', tickfont=dict(color='#aab5c2')))
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
st.sidebar.markdown("<div style='color:#8995a3;font-size:.75rem;letter-spacing:.5px;text-transform:uppercase;'>Navigate</div>", unsafe_allow_html=True)
PAGE = st.sidebar.radio("", ["Overview", "Events", "Review Queue", "Coverage", "Reports"], label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.markdown(f"<div style='color:#8995a3;font-size:.72rem;'>Site</div><div style='font-family:JetBrains Mono,monospace;font-size:.8rem;color:#b1c5ff;'>FLUID Jurong Lake</div>", unsafe_allow_html=True)
st.sidebar.markdown(f"<div style='color:#8995a3;font-size:.72rem;margin-top:1rem;'>DB</div><div style='font-family:JetBrains Mono,monospace;font-size:.72rem;color:#b1c5ff;word-break:break-all;'>{DB}</div>", unsafe_allow_html=True)

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
    c2.markdown(kpi_card("⚠ Critical (PET ≤ 1s)", crit, 'k-crit', 'v-crit'), unsafe_allow_html=True)
    c3.markdown(kpi_card("Flagged for review", flagged, 'k-amber', 'v-amber', subtitle=f"{pending} pending human decision"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Spark reviewed", reviewed, 'k-green', 'v-green'), unsafe_allow_html=True)

    chart_left, chart_right = st.columns([1, 1.45], gap="medium")
    with chart_left:
        st.markdown("<div class='sec-h'>⚠ Severity distribution</div>", unsafe_allow_html=True)
        sev = events['severity'].value_counts().reindex(['critical','serious','moderate']).fillna(0).astype(int)
        fig = go.Figure()
        colors = {'critical':'#ff6577','serious':'#ffb65c','moderate':'#55d6a0'}
        for s in ['critical','serious','moderate']:
            label = {'critical':'⚠ Critical', 'serious':'⚡ Serious', 'moderate':'✓ Moderate'}[s]
            fig.add_trace(go.Bar(x=[label], y=[int(sev[s])], marker=dict(color=colors[s], line=dict(width=0)), text=[int(sev[s])], textposition='outside', textfont=dict(size=15, color='#edf1f5'), name=label, hovertemplate=f'{label}: %{{y}} events<extra></extra>', showlegend=False))
        st.plotly_chart(theme_plot(fig, 300), use_container_width=True)

    with chart_right:
        st.markdown("<div class='sec-h'>PET distribution · time gap (seconds)</div>", unsafe_allow_html=True)
        fig2 = px.histogram(events, x='our_pet_s', nbins=20, color='severity', color_discrete_map={'critical':'#ff6577','serious':'#ffb65c','moderate':'#55d6a0'}, labels={'our_pet_s':'PET (seconds)'})
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
    st.markdown(f"<div style='color:#8995a3;font-size:.85rem;margin:.5rem 0 1rem 0;'>Showing {len(df_show)} of {len(events)} events</div>", unsafe_allow_html=True)
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
<div class='scard-row' style='margin-top:1rem;'><div class='scard-stat'><div class='k-l'>⚠ Critical</div><div class='k-v crit'>{int(r['critical_count'])}</div></div><div class='scard-stat'><div class='k-l'>⚡ Serious</div><div class='k-v ser'>{int(r['serious_count'])}</div></div><div class='scard-stat'><div class='k-l'>✓ Moderate</div><div class='k-v mod'>{int(r['moderate_count'])}</div></div><div class='scard-stat'><div class='k-l'>Median PET</div><div class='k-v'>{r['median_pet_s']:.2f}s</div></div></div>
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
