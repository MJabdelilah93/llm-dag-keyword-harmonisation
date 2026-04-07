"""
figure2_thematic_comparison.py
==============================
Generates Figure 2: three-panel co-word network comparison
(Raw / B3 Jaro-Winkler / Full LLM-DAG).
No API calls. Seed=42 throughout.
"""

import io, sys, itertools, pathlib
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
try:
    from adjustText import adjust_text
    HAS_ADJUSTTEXT = True
except ImportError:
    HAS_ADJUSTTEXT = False

SEED = 42
np.random.seed(SEED)

BASE    = pathlib.Path(r"c:\Users\AbdelilahElMajjaoui\Downloads\PhD\Article 7\concept_harmonisation")
INTERN  = BASE / "data" / "interim"
MAPS    = BASE / "results" / "downstream_harmonisation_maps"
FIGDIR  = BASE / "results" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

FREQ_THRESH = 5
TOP_N       = 60      # keywords shown per panel
LABEL_TOP_N = 18      # labelled keywords per panel

# ── Louvain ───────────────────────────────────────────────────────────────────
try:
    import community as community_louvain
    HAS_LOUVAIN = True
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "python-louvain", "-q"])
    try:
        import community as community_louvain
        HAS_LOUVAIN = True
    except ImportError:
        HAS_LOUVAIN = False

def louvain(G):
    if HAS_LOUVAIN:
        part = community_louvain.best_partition(G, resolution=1.0, random_state=SEED)
        q    = community_louvain.modularity(part, G)
    else:
        from networkx.algorithms.community import greedy_modularity_communities
        comms = list(greedy_modularity_communities(G))
        part  = {n: i for i, c in enumerate(comms) for n in c}
        q     = nx.algorithms.community.quality.modularity(G, comms)
    return part, q

# ── Load corpus ───────────────────────────────────────────────────────────────
print("Loading corpus...")
df_c = pd.read_csv(INTERN / "scopus_ce_merged_deduped.csv",
                   usecols=["EID", "Author Keywords"], encoding="utf-8")
article_to_kws = {}
for _, row in df_c.iterrows():
    eid  = str(row["EID"])
    cell = row["Author Keywords"]
    if pd.isna(cell) or not str(cell).strip():
        article_to_kws[eid] = []
        continue
    article_to_kws[eid] = [k.strip() for k in str(cell).split(";") if k.strip()]
articles = list(article_to_kws.keys())
print(f"  Articles: {len(articles):,}")


# ── Build co-word network for one condition ───────────────────────────────────
def build_network(kw_map_df, freq_thresh=FREQ_THRESH, top_n=TOP_N):
    """
    kw_map_df: DataFrame with columns [keyword, canonical_form, freq]
    Returns (G_sub, canon_freq, partition, q)
      G_sub = subgraph of top_n most-frequent canonical nodes
    """
    kw_to_canon = dict(zip(kw_map_df["keyword"], kw_map_df["canonical_form"]))

    # Co-word counting
    edge_count   = defaultdict(int)
    canon_to_eids = defaultdict(set)
    for eid, kws in article_to_kws.items():
        canons = list({kw_to_canon.get(k, k) for k in kws})
        for c in canons:
            canon_to_eids[c].add(eid)
        for a, b in itertools.combinations(sorted(canons), 2):
            edge_count[(a, b)] += 1

    canon_freq = {c: len(e) for c, e in canon_to_eids.items()}
    freq5      = {c for c, f in canon_freq.items() if f >= freq_thresh}

    # Full graph
    G_full = nx.Graph()
    G_full.add_nodes_from(freq5)
    for (a, b), w in edge_count.items():
        if a in freq5 and b in freq5:
            G_full.add_edge(a, b, weight=w)

    # Louvain on full graph
    part_full, q_full = louvain(G_full)

    # Select top-N nodes by frequency for visualisation
    top_nodes = sorted(freq5, key=lambda k: -canon_freq.get(k, 0))[:top_n]
    G_sub = G_full.subgraph(top_nodes).copy()
    part_sub = {n: part_full[n] for n in top_nodes if n in part_full}

    return G_sub, canon_freq, part_sub, q_full, len(freq5)


# ── Load maps and build networks ──────────────────────────────────────────────
conditions = [
    ("raw",         "raw_map.csv",         "Raw (unharmonised)\nVocab: 3,646  |  Q = 0.413"),
    ("b3",          "b3_map.csv",           "B3 Jaro-Winkler\nVocab: 2,880  |  Q = 0.220"),
    ("full_llm_dag","full_llm_dag_map.csv", "Full LLM-DAG\nVocab: 3,464  |  Q = 0.237"),
]

networks = {}
for key, fname, label in conditions:
    print(f"Building network: {key}...")
    df_map = pd.read_csv(MAPS / fname)
    G, cf, part, q, full_vocab = build_network(df_map)
    networks[key] = {"G": G, "cf": cf, "part": part, "q": q,
                     "label": label, "full_vocab": full_vocab}
    nc = len(set(part.values()))
    print(f"  Nodes={G.number_of_nodes()} Edges={G.number_of_edges()} "
          f"Communities={nc} Q={q:.4f}")


# ── Shared layout: compute on raw, reuse for all three ───────────────────────
print("Computing layout (shared spring layout on raw network)...")
G_raw  = networks["raw"]["G"]
G_b3   = networks["b3"]["G"]
G_llm  = networks["full_llm_dag"]["G"]

# Use spring layout on the raw graph — gives best force-directed spread
pos_raw = nx.spring_layout(G_raw, seed=SEED, k=3.5 / np.sqrt(G_raw.number_of_nodes() + 1),
                           iterations=150, weight="weight")

# For B3 and LLM-DAG: use positions from raw where available, spring for new nodes
def inherit_or_spring(G, pos_ref, seed=SEED):
    fixed_nodes = [n for n in G.nodes() if n in pos_ref]
    fixed_pos   = {n: pos_ref[n] for n in fixed_nodes}
    if fixed_nodes:
        return nx.spring_layout(G, pos=fixed_pos, fixed=fixed_nodes,
                                seed=seed, k=3.5 / np.sqrt(G.number_of_nodes() + 1),
                                iterations=120, weight="weight")
    return nx.spring_layout(G, seed=seed, k=3.5 / np.sqrt(G.number_of_nodes() + 1),
                            iterations=150, weight="weight")

pos_b3  = inherit_or_spring(G_b3,  pos_raw)
pos_llm = inherit_or_spring(G_llm, pos_raw)

layouts = {"raw": pos_raw, "b3": pos_b3, "full_llm_dag": pos_llm}

# ── Colour palette ────────────────────────────────────────────────────────────
PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B3", "#937860", "#DA8BC3", "#8C8C8C",
    "#CCB974", "#64B5CD",
]

def comm_colours(partition):
    comms = sorted(set(partition.values()))
    return {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(comms)}

# ── Identify sustainability nodes ─────────────────────────────────────────────
SUST_KEYWORDS = {"sustainable development", "sustainability", "sustainable",
                 "sustainable development goals", "sdgs",
                 "sustainable consumption", "sustainable production",
                 "sustainable innovation", "sustainable supply chain"}

def is_sust(node):
    nl = node.lower()
    return any(s in nl for s in ["sustain", "sdg"])

# ── Draw one panel ────────────────────────────────────────────────────────────
def draw_panel(ax, key, G, pos, cf, partition, label, label_top=LABEL_TOP_N):
    if G.number_of_nodes() == 0:
        ax.set_visible(False)
        return

    c_map = comm_colours(partition)
    nodes = list(G.nodes())

    # Node sizes (log frequency, scaled)
    max_f = max(cf.get(n, 1) for n in nodes)
    sizes = [max(80, 3000 * (np.log1p(cf.get(n, 1)) / np.log1p(max_f)) ** 1.5)
             for n in nodes]

    # Node colours
    node_colours = [c_map.get(partition.get(n, 0), "#8C8C8C") for n in nodes]

    # Edges — draw first (background)
    edges     = list(G.edges(data="weight", default=1))
    max_w     = max((w for _, _, w in edges), default=1)
    edge_wids = [max(0.3, 2.5 * (w / max_w) ** 0.6) for _, _, w in edges]

    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edgelist=[(u, v) for u, v, _ in edges],
        width=edge_wids,
        edge_color="#BBBBBB",
        alpha=0.18,
    )

    # Nodes
    sust_nodes   = [n for n in nodes if is_sust(n)]
    normal_nodes = [n for n in nodes if not is_sust(n)]

    idx_n = [nodes.index(n) for n in normal_nodes]
    idx_s = [nodes.index(n) for n in sust_nodes]

    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        nodelist=normal_nodes,
        node_size=[sizes[i] for i in idx_n],
        node_color=[node_colours[i] for i in idx_n],
        linewidths=0.5,
        edgecolors="#555555",
    )

    # Sustainability nodes: highlighted with red border in B3, distinctive in LLM-DAG
    if sust_nodes:
        border_col = "#CC0000" if key == "b3" else "#1A6B1A"
        border_w   = 2.0       if key == "b3" else 1.8
        nx.draw_networkx_nodes(
            G, pos, ax=ax,
            nodelist=sust_nodes,
            node_size=[sizes[i] for i in idx_s],
            node_color=[node_colours[i] for i in idx_s],
            linewidths=border_w,
            edgecolors=border_col,
        )

    # Labels — top N by frequency using adjustText to avoid overlaps
    top_label_nodes = sorted(nodes, key=lambda n: -cf.get(n, 0))[:label_top]
    max_lf = cf.get(top_label_nodes[0], 1) if top_label_nodes else 1

    texts = []
    for n in top_label_nodes:
        if n not in pos:
            continue
        x, y = pos[n]
        fsize = max(6.5, 11.0 * (np.log1p(cf.get(n, 1)) / np.log1p(max_lf)) ** 0.6)
        lbl = n if len(n) <= 26 else n[:24] + "…"
        fw = "bold" if cf.get(n, 0) > max_lf * 0.25 else "normal"
        t = ax.text(x, y, lbl, fontsize=fsize, ha="center", va="center",
                    fontweight=fw, color="#111111",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white",
                              ec="none", alpha=0.65))
        texts.append(t)

    if HAS_ADJUSTTEXT and texts:
        adjust_text(texts, ax=ax,
                    expand_points=(1.4, 1.6),
                    expand_text=(1.2, 1.4),
                    force_text=(0.6, 0.8),
                    force_points=(0.4, 0.5),
                    arrowprops=dict(arrowstyle="-", color="#AAAAAA",
                                    lw=0.5, alpha=0.6))

    # Panel subtitle
    ax.set_title(label, fontsize=10, fontweight="bold", pad=8, loc="center",
                 linespacing=1.6)
    ax.axis("off")

    # Community legend (small)
    comms_present = sorted(set(partition.get(n, 0) for n in nodes))
    handles = [mpatches.Patch(color=c_map[c], label=f"Cluster {c+1}")
               for c in comms_present]
    ax.legend(handles=handles, fontsize=6.5, loc="lower left",
              framealpha=0.7, frameon=True, edgecolor="#CCCCCC",
              handlelength=1.0, handleheight=0.8)


# ── Compose figure ────────────────────────────────────────────────────────────
print("Drawing figure...")
plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.spines.left":  False,
    "axes.spines.bottom":False,
    "figure.facecolor":  "white",
    "axes.facecolor":    "white",
})

fig, axes = plt.subplots(1, 3, figsize=(21, 8))
fig.subplots_adjust(left=0.01, right=0.99, top=0.87, bottom=0.05,
                    wspace=0.06)

for ax, (key, _, _) in zip(axes, conditions):
    nd = networks[key]
    draw_panel(ax, key, nd["G"], layouts[key],
               nd["cf"], nd["part"], nd["label"])

# ── Sust. annotation arrows ───────────────────────────────────────────────────
# Mark the B3 sustainability mega-node and the LLM-DAG split
def find_sust_node(G, cf):
    """Return the largest sustainability-related node."""
    s_nodes = [n for n in G.nodes() if is_sust(n)]
    if not s_nodes:
        return None
    return max(s_nodes, key=lambda n: cf.get(n, 0))

sust_b3  = find_sust_node(G_b3,  networks["b3"]["cf"])
sust_llm = find_sust_node(G_llm, networks["full_llm_dag"]["cf"])

if sust_b3 and sust_b3 in pos_b3:
    axes[1].annotate(
        "Over-merged\nsustain* cluster",
        xy=pos_b3[sust_b3],
        xytext=(pos_b3[sust_b3][0] + 0.3, pos_b3[sust_b3][1] + 0.35),
        fontsize=7.5, color="#CC0000", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#CC0000", lw=1.3),
        bbox=dict(boxstyle="round,pad=0.2", fc="#FFF0F0", ec="#CC0000", alpha=0.85),
    )

if sust_llm and sust_llm in pos_llm:
    axes[2].annotate(
        "Distinctions\npreserved",
        xy=pos_llm[sust_llm],
        xytext=(pos_llm[sust_llm][0] + 0.3, pos_llm[sust_llm][1] + 0.35),
        fontsize=7.5, color="#1A6B1A", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#1A6B1A", lw=1.3),
        bbox=dict(boxstyle="round,pad=0.2", fc="#F0FFF0", ec="#1A6B1A", alpha=0.85),
    )

# ── Footer note ───────────────────────────────────────────────────────────────
fig.text(
    0.5, 0.007,
    f"Node size ∝ log(frequency). Top {TOP_N} nodes shown per panel (f ≥ {FREQ_THRESH}). "
    "Communities by Louvain (resolution=1.0, seed=42). "
    "Red border = over-merged sustainability cluster (B3). "
    "Green border = preserved distinct nodes (LLM-DAG).",
    ha="center", fontsize=7.5, color="#555555", style="italic",
)

# ── Save ──────────────────────────────────────────────────────────────────────
out_png = FIGDIR / "figure_2_thematic_comparison.png"
out_pdf = FIGDIR / "figure_2_thematic_comparison.pdf"

fig.savefig(out_png, dpi=300, bbox_inches="tight", facecolor="white")
fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"  Saved PNG: {out_png}")
print(f"  Saved PDF: {out_pdf}")

# ── Plain-text description ────────────────────────────────────────────────────
desc_lines = [
    "FIGURE 2 — DESCRIPTION",
    "=" * 60,
    "",
]
for key, _, lbl_short in conditions:
    nd   = networks[key]
    G    = nd["G"]
    part = nd["part"]
    cf   = nd["cf"]
    nc   = len(set(part.values()))
    top_kws = sorted(G.nodes(), key=lambda n: -cf.get(n, 0))[:LABEL_TOP_N]
    s_nodes = [n for n in G.nodes() if is_sust(n)]
    desc_lines += [
        f"Panel: {lbl_short}",
        f"  Nodes shown:    {G.number_of_nodes()}",
        f"  Edges shown:    {G.number_of_edges()}",
        f"  Communities:    {nc}",
        f"  Labelled nodes ({LABEL_TOP_N}):",
    ]
    for n in top_kws:
        comm = part.get(n, "?")
        sust = " [SUST]" if is_sust(n) else ""
        desc_lines.append(f"    f={cf.get(n,0):5d}  comm={comm}  {n}{sust}")
    desc_lines += [
        f"  Sustainability nodes in panel: {len(s_nodes)}",
    ]
    for n in sorted(s_nodes, key=lambda n: -cf.get(n, 0))[:10]:
        desc_lines.append(f"    f={cf.get(n,0):5d}  comm={part.get(n,'?')}  {n}")
    desc_lines.append("")

(FIGDIR / "figure_2_description.txt").write_text(
    "\n".join(desc_lines), encoding="utf-8")
print(f"  Saved description: {FIGDIR / 'figure_2_description.txt'}")

# ── Stdout summary ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("FIGURE 2 COMPLETE")
print("=" * 60)
for key, _, _ in conditions:
    nd  = networks[key]
    G   = nd["G"]
    nc  = len(set(nd["part"].values()))
    s_n = [n for n in G.nodes() if is_sust(n)]
    print(f"  {key:<15}: {G.number_of_nodes()} nodes  "
          f"{G.number_of_edges()} edges  {nc} communities  "
          f"{len(s_n)} sustain* nodes shown")

print(f"\n  Saved to:")
print(f"    {out_png}")
print(f"    {out_pdf}")
if sust_b3:
    print(f"\n  B3 sustainability highlight:    '{sust_b3}' "
          f"(f={networks['b3']['cf'].get(sust_b3,0)}) — red border, annotated")
if sust_llm:
    print(f"  LLM-DAG sustainability note:    '{sust_llm}' "
          f"(f={networks['full_llm_dag']['cf'].get(sust_llm,0)}) — green border, annotated")
