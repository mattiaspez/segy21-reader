"""
SEG-Y 2.1 Web Viewer — Streamlit app.

Run with:
    streamlit run app.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from segy21 import SegyReader

# ------------------------------------------------------------------ #
# Page config
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="SEG-Y Viewer",
    page_icon="🌍",
    layout="wide",
)

st.title("SEG-Y 2.1 Viewer")

# ------------------------------------------------------------------ #
# Sidebar — file selection
# ------------------------------------------------------------------ #

st.sidebar.header("File")

# Directory browser
default_dir = str(Path(__file__).parent / "tests")
directory = st.sidebar.text_input("Directory", value=default_dir)

dir_path = Path(directory)
if not dir_path.is_dir():
    st.sidebar.error("Directory not found.")
    st.stop()

# Find all SEG-Y files recursively
segy_files = sorted(
    p for p in dir_path.rglob("*")
    if p.is_file() and p.suffix.lower() in (".segy", ".sgy", ".seg")
)

if not segy_files:
    st.sidebar.warning("No .segy / .sgy files found in this directory.")
    st.stop()

# Show relative paths so the subfolder is visible in the dropdown
file_labels = [str(p.relative_to(dir_path)) for p in segy_files]
default_label = next(
    (lbl for lbl in file_labels if "teapot" in lbl.lower()),
    file_labels[0],
)
selected_label = st.sidebar.selectbox("SEG-Y file", file_labels,
                                      index=file_labels.index(default_label))
file_path = str(dir_path / selected_label)

st.sidebar.caption(f"`{file_path}`")

# ------------------------------------------------------------------ #
# Data loading (cached)
# ------------------------------------------------------------------ #

@st.cache_data(show_spinner="Reading SEG-Y file…")
def load_segy(path: str):
    """Read all traces and return metadata + data cube."""
    with SegyReader(path) as r:
        txt   = str(r.textual_header)
        bh    = r.binary_header
        ext   = r.extended_textual_headers

        traces_data = []
        headers     = []

        for hdr, data in r.traces():
            headers.append({
                "trace_seq":  hdr.get("trace_seq_file", 0),
                "inline":     hdr.get("inline_no", 0),
                "crossline":  hdr.get("crossline_no", 0),
                "cdp_x":      hdr.get("cdp_x", 0),
                "cdp_y":      hdr.get("cdp_y", 0),
                "offset":     hdr.get("source_receiver_dist", 0),
                "num_samples":hdr.get("num_samples", 0),
                "sample_interval_us": hdr.get("sample_interval_us", 0),
            })
            traces_data.append(data.astype(np.float32))

    df = pd.DataFrame(headers)

    # Detect implausible inline/crossline values: real grid indices are small integers;
    # values > 100,000 indicate the standard bytes contain coordinates instead,
    # meaning the file uses non-standard header locations (pre-Rev-1 files).
    COORD_THRESHOLD = 100_000
    nonstandard_grid = (
        df["inline"].abs().max() > COORD_THRESHOLD or
        df["crossline"].abs().max() > COORD_THRESHOLD
    )

    # If inline/crossline are both 0, fall back to sequential numbering
    if df["inline"].eq(0).all() and df["crossline"].eq(0).all():
        df["inline"]    = 1
        df["crossline"] = range(1, len(df) + 1)

    n_samples  = bh.effective_samples_per_trace or (len(traces_data[0]) if traces_data else 0)
    dt_us      = bh.effective_sample_interval_us or 2000.0
    time_axis  = np.arange(n_samples) * dt_us / 1000.0   # ms

    cube = np.stack(traces_data, axis=0)  # shape (n_traces, n_samples)

    return {
        "textual":        txt,
        "binary":         bh,
        "extended":       ext,
        "headers":        df,
        "cube":           cube,
        "time_ms":        time_axis,
        "n_samples":      n_samples,
        "dt_us":          dt_us,
        "nonstandard_grid": nonstandard_grid,
    }

data = load_segy(file_path)

if data["nonstandard_grid"]:
    st.warning(
        "**Non-standard header layout detected.** "
        "The inline/crossline fields at the standard SEG-Y bytes (189–196) contain "
        "implausibly large values — this file likely stores inline/crossline at "
        "non-standard byte locations (common in pre-Rev-1 files). "
        "Inline and crossline numbers shown in the app may be incorrect.",
        icon="⚠️",
    )
    remap = st.checkbox(
        "Use CDP X/Y bytes (181–188) as inline/crossline instead",
        value=False,
        help="For some pre-Rev-1 files the standard CDP X/Y bytes happen to contain "
             "the inline/crossline grid numbers. Enable this to use those values.",
    )
else:
    remap = False

df = data["headers"].copy()
if remap:
    df["inline"]    = df["cdp_x"]
    df["crossline"] = df["cdp_y"]
cube = data["cube"]
time = data["time_ms"]
bh   = data["binary"]

# ------------------------------------------------------------------ #
# Height control fragment — only resizes chart via JS, never re-renders it
# ------------------------------------------------------------------ #

def _height_control():
    st.slider("Plot height (px)", 300, 1200, 600, step=50, key="_sec_height")


# ------------------------------------------------------------------ #
# Tabs
# ------------------------------------------------------------------ #

tab_section, tab_trace, tab_map, tab_headers = st.tabs([
    "📊 Section", "〰 Trace", "🗺 Map", "📋 Headers"
])

# ================================================================== #
# TAB 1 — SECTION VIEW
# ================================================================== #

with tab_section:
    st.subheader("Seismic Section")

    inlines    = sorted(df["inline"].unique())
    crosslines = sorted(df["crossline"].unique())

    col_ctrl, col_plot = st.columns([1, 4])

    with col_ctrl:
        orient = st.radio("Slice direction", ["Inline", "Crossline", "All traces"])

        if orient == "Inline":
            if len(inlines) > 1:
                selected = st.select_slider("Inline", options=inlines, value=inlines[0])
            else:
                selected = inlines[0]
                st.info(f"Single inline: {inlines[0]}")
        elif orient == "Crossline":
            if len(crosslines) > 1:
                selected = st.select_slider("Crossline", options=crosslines,
                                            value=crosslines[len(crosslines) // 2])
            else:
                selected = crosslines[0]
                st.info(f"Single crossline: {crosslines[0]}")
        else:
            selected = None

        display_mode = st.radio(
            "Display mode",
            ["Density", "Interpolated density", "Wiggles"],
            index=1,
        )

        if display_mode in ("Density", "Interpolated density"):
            colorscale = st.selectbox("Colour scale",
                                      ["rdbu", "greys", "picnic", "rdgy", "piyg", "balance", "icefire"],
                                      index=1)
            wiggle_scale = None
        else:
            wiggle_scale = st.slider("Wiggle scale", 0.2, 3.0, 1.0, step=0.1,
                                     help="Scales wiggle amplitude relative to trace spacing")
            colorscale = None

        clip_pct = st.slider("Clip percentile", 90, 100, 99,
                             help="Clips display range to this percentile of amplitude")

        _height_control()

    # ── Compute section data ──────────────────────────────────────────
    if orient == "Inline":
        mask = df["inline"] == selected
        x_label = "Crossline"
        x_vals  = df.loc[mask, "crossline"].values
    elif orient == "Crossline":
        mask = df["crossline"] == selected
        x_label = "Inline"
        x_vals  = df.loc[mask, "inline"].values
    else:
        mask    = pd.Series([True] * len(df))
        x_label = "Trace #"
        x_vals  = df.index.values

    section = cube[mask.values]

    with col_ctrl:
        if display_mode == "Wiggles" and section.shape[0] > 500:
            st.warning(f"Too many traces ({section.shape[0]}) for wiggle display (limit 500).")

    with col_plot:
        if section.shape[0] == 0:
            st.warning("No traces found for this selection.")
        else:
            vmax = np.nanpercentile(np.abs(section), clip_pct)
            vmax = vmax if vmax > 0 else 1.0
            title_str = (f"Inline {selected}" if orient == "Inline"
                         else f"Crossline {selected}" if orient == "Crossline"
                         else "All traces")
            uirev = f"{orient}_{selected}"

            if display_mode in ("Density", "Interpolated density"):
                zsmooth = "best" if display_mode == "Interpolated density" else False
                fig = go.Figure(go.Heatmap(
                    z=section.T, x=x_vals, y=time,
                    colorscale=colorscale, zmid=0,
                    zmin=-vmax, zmax=vmax, zsmooth=zsmooth,
                    colorbar=dict(title="Amplitude"),
                ))
            else:
                if section.shape[0] > 500:
                    st.warning(
                        f"Too many traces ({section.shape[0]}) for wiggle display "
                        f"(limit 500). Switch to Density mode or narrow your slice."
                    )
                    st.stop()
                fig = go.Figure()
                n_tr = len(x_vals)
                trace_spacing = (
                    abs((float(x_vals[-1]) - float(x_vals[0])) / (n_tr - 1))
                    if n_tr > 1 else 1.0
                ) or 1.0
                scale = wiggle_scale * trace_spacing / vmax
                for i, x_pos in enumerate(x_vals):
                    amp = section[i] * scale
                    fig.add_trace(go.Scatter(
                        x=x_pos + amp, y=time, mode="lines",
                        line=dict(color="black", width=0.8),
                        showlegend=False, hoverinfo="skip",
                    ))
                    pos_amp = np.maximum(amp, 0.0)
                    fig.add_trace(go.Scatter(
                        x=np.concatenate([x_pos + pos_amp, np.full(len(time), x_pos)[::-1]]),
                        y=np.concatenate([time, time[::-1]]),
                        fill="toself", fillcolor="black",
                        line=dict(width=0), showlegend=False, hoverinfo="skip",
                    ))
                fig.update_xaxes(range=[float(x_vals[0]) - trace_spacing,
                                        float(x_vals[-1]) + trace_spacing])

            stats_str = (
                f"{section.shape[0]} traces  ·  {section.shape[1]} samples  ·  "
                f"dt = {data['dt_us'] / 1000:.2f} ms  ·  "
                f"record = {time[-1]:.0f} ms"
            )
            plot_h = st.session_state.get("_sec_height", 600)
            fig.update_layout(
                title=dict(text=f"<b>{title_str}</b>", x=0.01, xanchor="left",
                           yanchor="top", font=dict(size=13)),
                annotations=[dict(
                    text=stats_str, xref="paper", yref="paper",
                    x=0.5, y=1.0, xanchor="center", yanchor="bottom",
                    showarrow=False, font=dict(size=11, color="grey"),
                )],
                xaxis_title=x_label,
                yaxis_title="Time (ms)", yaxis_autorange="reversed",
                height=plot_h, margin=dict(l=60, r=20, t=40, b=50),
                uirevision=uirev,
            )
            st.plotly_chart(fig, use_container_width=True, key="seismic_section",
                            config={"responsive": True})

# ================================================================== #
# TAB 2 — SINGLE TRACE
# ================================================================== #

with tab_trace:
    st.subheader("Single Trace Waveform")

    n_traces = len(df)
    if n_traces > 1:
        trace_idx = st.slider("Trace index", 0, n_traces - 1, 0)
    else:
        trace_idx = 0

    row   = df.iloc[trace_idx]
    tdata = cube[trace_idx]

    col_info, col_plot = st.columns([1, 3])

    with col_info:
        st.markdown("**Trace header**")
        st.write({
            "Trace #":    int(trace_idx),
            "Inline":     int(row["inline"]),
            "Crossline":  int(row["crossline"]),
            "CDP X":      int(row["cdp_x"]),
            "CDP Y":      int(row["cdp_y"]),
            "Offset":     int(row["offset"]),
            "Num samples":int(row["num_samples"]) or len(tdata),
        })
        st.markdown("**Amplitude stats**")
        st.write({
            "Min":  float(f"{tdata.min():.6g}"),
            "Max":  float(f"{tdata.max():.6g}"),
            "Mean": float(f"{tdata.mean():.6g}"),
            "Std":  float(f"{tdata.std():.6g}"),
        })

    with col_plot:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=tdata,
            y=time,
            mode="lines",
            line=dict(color="#1f77b4", width=1),
            fill="tozerox",
            fillcolor="rgba(31,119,180,0.15)",
        ))
        fig2.update_layout(
            xaxis_title="Amplitude",
            yaxis_title="Time (ms)",
            yaxis_autorange="reversed",
            height=550,
            margin=dict(l=60, r=20, t=30, b=50),
        )
        st.plotly_chart(fig2, use_container_width=True)

# ================================================================== #
# TAB 3 — MAP VIEW
# ================================================================== #

with tab_map:
    st.subheader("Trace Map (CDP positions)")

    if df["cdp_x"].eq(0).all() or df["cdp_y"].eq(0).all():
        # Fall back to inline/crossline grid
        fig3 = px.scatter(
            df.reset_index(),
            x="crossline", y="inline",
            color="index",
            labels={"index": "Trace #", "crossline": "Crossline", "inline": "Inline"},
            title="Trace positions (inline / crossline)",
            color_continuous_scale="Viridis",
        )
    else:
        fig3 = px.scatter(
            df.reset_index(),
            x="cdp_x", y="cdp_y",
            color="index",
            labels={"index": "Trace #", "cdp_x": "CDP X (m)", "cdp_y": "CDP Y (m)"},
            title="Trace positions (CDP coordinates)",
            color_continuous_scale="Viridis",
        )

    fig3.update_traces(marker=dict(size=8))
    fig3.update_layout(height=550)
    st.plotly_chart(fig3, use_container_width=True)

# ================================================================== #
# TAB 4 — HEADERS
# ================================================================== #

with tab_headers:
    t1, t2, t3 = st.tabs(["Textual", "Binary", "Extended"])

    with t1:
        st.code(data["textual"], language=None)

    with t2:
        st.text(bh.summary())
        st.markdown("---")
        st.markdown("**All binary header fields**")
        bh_dict = {
            k: v for k, v in vars(bh).items()
            if k != "raw" and not k.startswith("_")
        }
        st.dataframe(pd.DataFrame(
            bh_dict.items(), columns=["Field", "Value"]
        ), use_container_width=True, height=500)

    with t3:
        if not data["extended"]:
            st.info("No extended textual headers in this file.")
        for i, txt in enumerate(data["extended"], 1):
            with st.expander(f"Extended header #{i}", expanded=(i == 1)):
                st.code(txt[:2000] + ("…" if len(txt) > 2000 else ""), language=None)
