"""
figure1_dag_workflow.py
------------------------
Generates Figure 1: 9-node LLM-DAG workflow diagram for the M7 manuscript.

Outputs (to outputs/figures/):
    figure1_dag_workflow.pdf   — vector, publication quality
    figure1_dag_workflow.svg   — editable vector
    figure1_dag_workflow.png   — 300 DPI raster preview
"""

import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT    = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
OUT_DIR = ROOT / "outputs" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Palette ────────────────────────────────────────────────────────────────────
BLUE    = "#4472C4";  BLUE_BG   = "#EAF0FB"
ORANGE  = "#ED7D31";  ORANGE_BG = "#FDF1E8"
GREEN   = "#70AD47";  GREEN_BG  = "#ECF6E3"
GREY    = "#8C8C8C";  GREY_BG   = "#F3F3F3"
DARK    = "#1A1A1A"
ARROW_C = "#404040"

# ── Figure canvas ──────────────────────────────────────────────────────────────
# 180mm wide × 252mm tall  →  7.09 × 9.92 inches
FIG_W, FIG_H = 7.09, 9.92
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))

# Data coordinate system: x ∈ [0, 1], y ∈ [0, 1]
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# Aspect-ratio correction factor: 1 data-unit in x represents FIG_W inches;
# in y it represents FIG_H inches.  Used to make rounded corners look circular.
AR = FIG_H / FIG_W   # ≈ 1.40

# ── Layout constants ───────────────────────────────────────────────────────────
NW   = 0.355   # main node width (data coords)
NH   = 0.0685  # main node height — 2-line nodes
NH5  = 0.057   # guard node height — 1-line node

N9W  = 0.280   # Node 9 width
MRBW = 0.240   # manual-review box width
MRBH = 0.057

XM   = 0.305   # main-column x-centre
XR   = 0.785   # right-column x-centre
RAIL = 0.590   # logging-rail x

# y-centres for N1–N8 (top → bottom)
ys = {
    1: 0.895,
    2: 0.810,
    3: 0.725,
    4: 0.615,
    5: 0.538,
    6: 0.422,
    7: 0.337,
    8: 0.252,
}
Y9  = 0.088          # Node 9 y-centre
YMR = ys[5]          # Manual review queue y-centre


# ── Helper: draw one node ──────────────────────────────────────────────────────
def draw_node(xc, yc, w, h, color, num_str, label_str, zorder=5):
    """Rounded-rect node with coloured left accent strip, number, and label."""
    xl = xc - w / 2
    yb = yc - h / 2
    pad = 0.008            # FancyBboxPatch inner pad (data coords)
    rnd = f"round,pad={pad}"

    # Drop shadow
    ax.add_patch(FancyBboxPatch(
        (xl + 0.005, yb - 0.005 / AR), w, h,
        boxstyle=rnd, lw=0,
        facecolor="#BEBEBE", alpha=0.30, zorder=zorder - 1,
    ))

    # Main body (white fill, coloured border)
    ax.add_patch(FancyBboxPatch(
        (xl, yb), w, h,
        boxstyle=rnd, lw=1.8,
        edgecolor=color, facecolor="white", zorder=zorder,
    ))

    # Left accent strip
    aw = 0.036            # accent strip width
    inner_h = h - 2 * pad / AR  # avoid clip against outer rounded corner
    inner_y = yb + pad / AR
    ax.add_patch(FancyBboxPatch(
        (xl + pad * 0.5, inner_y), aw, inner_h,
        boxstyle="round,pad=0.003", lw=0,
        facecolor=color, alpha=0.90, zorder=zorder + 1,
    ))

    # Number text inside accent strip
    ax.text(xl + pad * 0.5 + aw / 2, yc, num_str,
            ha="center", va="center",
            fontsize=7.5, color="white", fontweight="bold",
            fontfamily="DejaVu Sans", zorder=zorder + 2)

    # Label text (centred in the body to the right of accent strip)
    label_cx = xl + pad * 0.5 + aw + (w - pad * 0.5 - aw) / 2
    ax.text(label_cx, yc, label_str,
            ha="center", va="center",
            fontsize=8.5, color=DARK, fontweight="bold",
            fontfamily="DejaVu Sans", linespacing=1.30,
            zorder=zorder + 2)


# ── Helper: solid vertical arrow ──────────────────────────────────────────────
def solid_arrow(x, y_from, y_to, lw=1.5, color=ARROW_C):
    ax.annotate("",
        xy=(x, y_to), xytext=(x, y_from),
        arrowprops=dict(
            arrowstyle="->", color=color, lw=lw,
            mutation_scale=13,
            connectionstyle="arc3,rad=0",
        ), zorder=4,
    )


# ── Helper: horizontal solid arrow ───────────────────────────────────────────
def horiz_arrow(x_from, x_to, y, lw=1.4, color=ARROW_C):
    ax.annotate("",
        xy=(x_to, y), xytext=(x_from, y),
        arrowprops=dict(
            arrowstyle="->", color=color, lw=lw,
            mutation_scale=12,
            connectionstyle="arc3,rad=0",
        ), zorder=4,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Zone background panels
# ══════════════════════════════════════════════════════════════════════════════
ZPX = 0.023   # horizontal padding around nodes
ZPY = 0.020   # vertical padding above/below top and bottom nodes

zone_defs = [
    # (label, colour, bg, top_node, bot_node, top_nh, bot_nh)
    ("Deterministic\npreprocessing",  BLUE,   BLUE_BG,   1, 3, NH,  NH ),
    ("LLM inference\n& guard layer",  ORANGE, ORANGE_BG, 4, 5, NH,  NH5),
    ("Post-processing\n& output",     GREEN,  GREEN_BG,  6, 8, NH,  NH ),
]

for zlabel, zcolor, zbg, nt, nb, nh_t, nh_b in zone_defs:
    zx = XM - NW / 2 - ZPX
    zy = ys[nb] - nh_b / 2 - ZPY
    zw = NW + 2 * ZPX
    zh = (ys[nt] + nh_t / 2 + ZPY) - zy

    ax.add_patch(FancyBboxPatch(
        (zx, zy), zw, zh,
        boxstyle="round,pad=0.008", lw=0.9,
        edgecolor=zcolor, facecolor=zbg, alpha=0.55, zorder=0,
    ))

    # Rotated zone label in left margin
    ax.text(0.040, zy + zh / 2, zlabel,
            ha="center", va="center", rotation=90,
            fontsize=6.8, color=zcolor, fontweight="bold",
            fontfamily="DejaVu Sans", alpha=0.90, zorder=1)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Main nodes N1–N8
# ══════════════════════════════════════════════════════════════════════════════
node_specs = [
    (1, BLUE,   "01", "Corpus ingestion\n& snapshot",        NH ),
    (2, BLUE,   "02", "Deterministic\nnormalisation",         NH ),
    (3, BLUE,   "03", "Candidate\ngeneration",                NH ),
    (4, ORANGE, "04", "Pairwise LLM\nverification",           NH ),
    (5, ORANGE, "05", "Guard layer",                          NH5),
    (6, GREEN,  "06", "Clustering\n(connected components)",   NH ),
    (7, GREEN,  "07", "Canonical label\nassignment",          NH ),
    (8, GREEN,  "08", "Downstream theme\nconstruction",       NH ),
]

for n, color, num, label, nh in node_specs:
    draw_node(XM, ys[n], NW, nh, color, num, label)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Node 9 — logging & artefact export (right side, bottom)
# ══════════════════════════════════════════════════════════════════════════════
draw_node(XR, Y9, N9W, NH, GREEN, "09", "Logging &\nartefact export")


# ══════════════════════════════════════════════════════════════════════════════
# 4. Manual review queue box (dashed grey border)
# ══════════════════════════════════════════════════════════════════════════════
ax.add_patch(FancyBboxPatch(
    (XR - MRBW / 2, YMR - MRBH / 2), MRBW, MRBH,
    boxstyle="round,pad=0.008", lw=1.3,
    edgecolor=GREY, facecolor=GREY_BG,
    linestyle="--", alpha=0.92, zorder=5,
))
ax.text(XR, YMR, "Manual review\nqueue",
        ha="center", va="center",
        fontsize=8, color="#484848",
        fontfamily="DejaVu Sans", linespacing=1.30, zorder=6)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Sequential solid arrows N1 → N2 → … → N8
# ══════════════════════════════════════════════════════════════════════════════
nh_of = {1: NH, 2: NH, 3: NH, 4: NH, 5: NH5, 6: NH, 7: NH, 8: NH}

for n in range(1, 8):
    y_bot = ys[n]     - nh_of[n]     / 2
    y_top = ys[n + 1] + nh_of[n + 1] / 2
    solid_arrow(XM, y_bot, y_top)

# Label on the N5 → N6 arrow (match accepted)
mid_y_56 = (ys[5] - NH5 / 2 + ys[6] + NH / 2) / 2
ax.text(XM + 0.016, mid_y_56, "match (accepted)",
        ha="left", va="center",
        fontsize=6.5, color="#555555", fontstyle="italic",
        fontfamily="DejaVu Sans", zorder=6)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Arrow N5 → Manual review queue  (uncertain / flagged)
# ══════════════════════════════════════════════════════════════════════════════
x_n5_right = XM + NW / 2
x_mr_left  = XR - MRBW / 2

horiz_arrow(x_n5_right, x_mr_left, YMR, lw=1.3, color=ORANGE)

mid_x_mr = (x_n5_right + x_mr_left) / 2
ax.text(mid_x_mr, YMR + 0.021, "uncertain /\nflagged",
        ha="center", va="bottom",
        fontsize=6.3, color="#666666", fontstyle="italic",
        fontfamily="DejaVu Sans", linespacing=1.2, zorder=6)


# ══════════════════════════════════════════════════════════════════════════════
# 7. Provenance logging rail  — dashed arrows N1–N8 → Node 9
#    Approach: each node has a short dashed tick to a vertical rail at x=RAIL;
#    the rail connects down with a dashed arrow to Node 9.
#    This avoids arrow spaghetti while satisfying "dashed arrows from Nodes 1–8".
# ══════════════════════════════════════════════════════════════════════════════
RAIL_COLOR = "#AAAAAA"
RAIL_LS    = (0, (5, 4))    # custom dash pattern

# Vertical rail line
ax.plot(
    [RAIL, RAIL], [Y9, ys[1] + NH / 2],
    color=RAIL_COLOR, lw=0.85, linestyle=RAIL_LS, alpha=0.70, zorder=1,
)

# Short dashed ticks: right edge of each main node → rail
for n in range(1, 9):
    ax.annotate("",
        xy=(RAIL, ys[n]),
        xytext=(XM + NW / 2, ys[n]),
        arrowprops=dict(
            arrowstyle="-|>", color=RAIL_COLOR, lw=0.65,
            mutation_scale=7,
            linestyle=RAIL_LS,
            connectionstyle="arc3,rad=0",
        ), zorder=1,
    )

# Dashed arrow: rail bottom → Node 9 left edge
ax.annotate("",
    xy=(XR - N9W / 2, Y9),
    xytext=(RAIL, Y9),
    arrowprops=dict(
        arrowstyle="->", color=RAIL_COLOR, lw=0.85,
        mutation_scale=10,
        linestyle=RAIL_LS,
        connectionstyle="arc3,rad=0",
    ), zorder=1,
)

# Rail label (rotated, right of the rail line)
ax.text(RAIL + 0.012, (ys[1] + Y9) / 2,
        "provenance logging (all nodes)",
        ha="left", va="center", rotation=90,
        fontsize=5.5, color=RAIL_COLOR,
        fontstyle="italic", fontfamily="DejaVu Sans",
        alpha=0.85, zorder=1)


# ══════════════════════════════════════════════════════════════════════════════
# 8. Legend
# ══════════════════════════════════════════════════════════════════════════════
legend_handles = [
    mpatches.Patch(facecolor=BLUE_BG,   edgecolor=BLUE,   lw=1.3,
                   label="Deterministic preprocessing"),
    mpatches.Patch(facecolor=ORANGE_BG, edgecolor=ORANGE, lw=1.3,
                   label="LLM inference & guard layer"),
    mpatches.Patch(facecolor=GREEN_BG,  edgecolor=GREEN,  lw=1.3,
                   label="Post-processing & output"),
    mpatches.Patch(facecolor=GREY_BG,   edgecolor=GREY,   lw=1.1,
                   linestyle="--",
                   label="Human-in-the-loop (manual review)"),
    Line2D([0], [0], color=RAIL_COLOR, lw=1.1, linestyle="--",
           label="Provenance logging → Node 9"),
]

leg = ax.legend(
    handles=legend_handles,
    loc="lower center",
    bbox_to_anchor=(0.46, 0.001),
    fontsize=6.8, framealpha=0.97,
    edgecolor="#CCCCCC", ncol=2,
    handlelength=2.0, handleheight=0.95,
    columnspacing=1.0, handletextpad=0.55,
    borderpad=0.7,
)
leg.get_frame().set_linewidth(0.8)


# ══════════════════════════════════════════════════════════════════════════════
# 9. Figure title (caption-style, top centre)
# ══════════════════════════════════════════════════════════════════════════════
ax.text(
    0.50, 0.980,
    "Figure 1.  Auditable LLM-DAG workflow for keyword harmonisation",
    ha="center", va="top",
    fontsize=9.5, color=DARK, fontweight="bold",
    fontfamily="DejaVu Sans", zorder=10,
)


# ══════════════════════════════════════════════════════════════════════════════
# 10. Save  PDF / SVG / PNG
# ══════════════════════════════════════════════════════════════════════════════
SAVE_ARGS = dict(bbox_inches="tight", facecolor="white")

for ext, extra in [("pdf", {}), ("svg", {}), ("png", {"dpi": 300})]:
    fpath = OUT_DIR / f"figure1_dag_workflow.{ext}"
    fig.savefig(fpath, format=ext, **SAVE_ARGS, **extra)
    print(f"Saved: {fpath}")

plt.close(fig)
print("Done.")
