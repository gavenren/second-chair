"""Figures for the report, drawn from out/report_numbers.json (src/export.py).

Usage: python figs.py report_numbers.json figs/
"""
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#898781"
BLUES = ["#86b6ef", "#2a78d6", "#104281"]          # ordinal ramp: agreed facts, own account, own account + anger
STEP_COLS = ["#104281", "#2a78d6", "#9ec5f4", "#f6b9a0", "#eb6834", "#a8380f"]   # blue arm = conciliatory, warm arm = adversarial
NAMES = {"gemma-4-31b-it": "Gemma 4 31B", "gemma-4-26b-a4b-it": "Gemma 4 26B", "deepseek-v4-flash": "DeepSeek V4 Flash",
         "glm-5.3-flash": "GLM 5.3 Flash", "glm-5.2": "GLM 5.2", "qwen3.8-27b": "Qwen 3.8 27B", "qwen3.5-397b": "Qwen 3.5 397B"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK, "axes.spines.top": False,
    "axes.spines.right": False, "axes.spines.left": False, "xtick.major.size": 0, "ytick.major.size": 0,
    "legend.frameon": False, "pdf.fonttype": 42, "axes.titlesize": 8.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def grid(ax, axis="x"):
    ax.grid(axis=axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def fig_zone(R, out):
    """What the two sides are told, pooled: walk-away points and forecasts on one scale."""
    p = R["p"]
    rows = [("Neutral helper, agreed facts", "obs", None), ("Each party asks, agreed facts", "base.N", None),
            ("Neutral helper reads each party's account", "op", None),
            ("Each party asks, own account", "base.P", None), ("Own account + angry sentence", "base.PA", None)]
    if "g1.PA.wA" in p:
        rows.append(("  with consider-the-other-side prompt", "g1.PA", None))
    if "g2.PA.wA" in p:
        rows.append(("  with Second Chair", "g2.PA", None))
    fig, ax = plt.subplots(figsize=(6.9, 0.34 * len(rows) + 0.9))
    lo = min(min(p[k + ".wA"][0], p[k + ".wB"][0]) for _, k, _ in rows) - 9
    hi = max(max(p[k + ".wA"][0], p[k + ".wB"][0]) for _, k, _ in rows) + 30
    for i, (label, k, _) in enumerate(rows):
        y = len(rows) - 1 - i
        wa, wb = p[k + ".wA"][0], p[k + ".wB"][0]
        z = wb - wa
        col = BLUE if z >= 0 else ORANGE
        ax.plot([wa, wb], [y, y], color=col, linewidth=7, solid_capstyle="butt", alpha=0.9, zorder=2)
        ax.plot([wa], [y], marker="|", color=INK, markersize=13, markeredgewidth=1.4, zorder=3)
        ax.plot([wb], [y], marker="|", color=INK, markersize=13, markeredgewidth=1.4, zorder=3)
        left, right = (wa, wb) if wa <= wb else (wb, wa)
        ax.text(left - 0.8, y, ("A " if wa <= wb else "B ") + f"{left:.0f}", ha="right", va="center", color=INK2, fontsize=7.5)
        ax.text(right + 0.8, y, f"{right:.0f}" + (" B" if wa <= wb else " A"), ha="left", va="center", color=INK2, fontsize=7.5)
        ax.text(hi, y, ("room to settle  " if z >= 0 else "gap  ") + f"{z:+.0f}", ha="right", va="center", color=INK, fontsize=7.5,
                fontweight="bold")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(lo, hi)
    ax.set_xlabel("Share of the disputed amount going to party A (%)")
    grid(ax)
    ax.plot([], [], color=BLUE, linewidth=6, label="B is told to give at least what A is told to accept")
    ax.plot([], [], color=ORANGE, linewidth=6, label="A is told to refuse what B is told is the most to give")
    ax.legend(loc="lower center", bbox_to_anchor=(0.42, 1.0), ncol=1, fontsize=7.5, handlelength=1.4, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(out + "/fig_zone.pdf")
    plt.close(fig)


def fig_impasse(R, out):
    """Advised-impasse rate per model in four conditions."""
    models = R["models"]
    series = [("obs.impasse", "Neutral helper, agreed facts", GREY), ("base.N.impasse", "Parties, agreed facts", BLUES[0]),
              ("base.P.impasse", "Parties, own accounts", BLUES[1]), ("base.PA.impasse", "Own accounts + angry sentence", BLUES[2])]
    labels = [NAMES[m] for m in models] + ["All seven, pooled"]
    fig, ax = plt.subplots(figsize=(6.9, 3.0))
    n = len(labels)
    for si, (key, lab, col) in enumerate(series):
        vals = R["pm"][key] + [R["p"][key]]
        for i, v in enumerate(vals):
            if v is None:
                continue
            y = n - 1 - i + (1.5 - si) * 0.17
            ax.plot([v[1], v[2]], [y, y], color=col, linewidth=1.1, zorder=2)
            ax.plot([v[0]], [y], marker="o", color=col, markersize=5.2, markeredgecolor="#fcfcfb", markeredgewidth=0.9, zorder=3,
                    label=lab if i == 0 else None)
    ax.axhline(0.5, color=AXIS, linewidth=0.6)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels[::-1])
    ax.get_yticklabels()[0].set_fontweight("bold")
    ax.set_xlim(-2, 102)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlabel("Cases in which the two walk-away points do not overlap (%)")
    grid(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2, fontsize=7.5, labelcolor=INK2, columnspacing=1.2, handletextpad=0.3)
    fig.tight_layout()
    fig.savefig(out + "/fig_impasse.pdf")
    plt.close(fig)


def fig_steps(R, out):
    """Recommended next step: distribution over the six-rung ladder, pooled."""
    rows = [("op|OP", None), ("base|N", None), ("base|P", None), ("base|PA", None), ("g1|PA", None), ("g2|PA", None)]
    names = {"op|OP": "Neutral helper reads one party's account", "base|N": "Party asks, agreed facts", "base|P": "Party asks, own account",
             "base|PA": "Own account + angry sentence", "g1|PA": "  with consider-the-other-side prompt", "g2|PA": "  with Second Chair"}
    S = dict(R["steps"])
    if "base|OP" in S:
        S["op|OP"] = S["base|OP"]
    rows = [k for k, _ in rows if k in S]
    steps = ["1 let it go", "2 talk, compromise", "3 mediator", "4 firm written demand", "5 formal process", "6 pressure"]
    fig, ax = plt.subplots(figsize=(6.9, 0.32 * len(rows) + 1.1))
    for i, k in enumerate(rows):
        y = len(rows) - 1 - i
        tot = sum(S[k])
        x = 0.0
        for j, c in enumerate(S[k]):
            w = 100.0 * c / tot
            if w > 0:
                ax.barh(y, max(w - 0.35, 0.05), left=x + 0.175, height=0.62, color=STEP_COLS[j], label=steps[j] if i == 0 else None)
                if w >= 6:
                    ax.text(x + w / 2, y, f"{w:.0f}", ha="center", va="center", fontsize=7, color="#ffffff" if j in (0, 1, 4, 5) else INK)
            elif i == 0:
                ax.barh(y, 0, left=x, height=0.62, color=STEP_COLS[j], label=steps[j])
            x += w
        adv = 100.0 * sum(S[k][3:]) / tot
        pk = "op.adv" if k.startswith("op") else k.replace("|", ".") + ".adv"
        if pk in R["p"]:
            adv = R["p"][pk][0]          # same estimate as the text and tables (equal weight per model)
        ax.text(101.5, y, f"{adv:.0f}%", ha="left", va="center", fontsize=7.5, color=INK, fontweight="bold")
    ax.text(101.5, len(rows) - 0.42, "steps 4-6", ha="left", va="bottom", fontsize=7, color=INK2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([names[k] for k in rows][::-1])
    ax.set_xlim(0, 111)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_ylim(-0.55, len(rows) - 0.3)
    ax.set_xlabel("Share of conversations (%)")
    h, l = ax.get_legend_handles_labels()
    order = [l.index(s) for s in steps if s in l]
    ax.legend([h[i] for i in order], [l[i] for i in order], loc="lower center", bbox_to_anchor=(0.38, 1.0), ncol=3, fontsize=7.2,
              labelcolor=INK2, columnspacing=1.4, handlelength=0.9, handletextpad=0.4)
    fig.tight_layout()
    fig.savefig(out + "/fig_steps.pdf")
    plt.close(fig)


def fig_guard(R, out):
    """Second Chair against the base arm and the one-paragraph prompt, per model (own account + angry sentence)."""
    models = R["models"]
    labels = [NAMES[m] for m in models] + ["All seven, pooled"]
    panels = [("PA.impasse", "Advised impasse\n(% of cases)", (0, 100)), ("PA.mutual", "Both sides sent to\nsteps 4-6 (% of cases)", (0, 100)),
              ("PA.rg", "Role gap in the\nforecast (points)", None)]
    arms = [("base", "No system prompt", GREY), ("g1", "Consider-the-other-side prompt", BLUE), ("g2", "Second Chair", ORANGE)]
    arms = [a for a in arms if a[0] + ".PA.impasse" in R["p"]]
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 3.0), sharey=True)
    n = len(labels)
    for ax, (q, title, lim) in zip(axes, panels):
        for ai, (arm, lab, col) in enumerate(arms):
            key = arm + "." + q
            vals = (R["pm"].get(key) or [None] * len(models)) + [R["p"].get(key)]
            for i, v in enumerate(vals):
                if v is None:
                    continue
                y = n - 1 - i + (1 - ai) * 0.2
                ax.plot([v[1], v[2]], [y, y], color=col, linewidth=1.0, zorder=2)
                ax.plot([v[0]], [y], marker="o", color=col, markersize=4.8, markeredgecolor="#fcfcfb", markeredgewidth=0.8, zorder=3,
                        label=lab if i == 0 else None)
        ax.axhline(0.5, color=AXIS, linewidth=0.6)
        if lim:
            ax.set_xlim(lim[0] - 3, lim[1] + 3)
        else:
            ax.axvline(0, color=AXIS, linewidth=0.8)
        ax.set_title(title, fontsize=7.8)
        grid(ax)
    axes[0].set_yticks(range(n))
    axes[0].set_yticklabels(labels[::-1])
    axes[0].get_yticklabels()[0].set_fontweight("bold")
    axes[0].set_ylim(-0.6, n - 0.4)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=3, fontsize=7.5, labelcolor=INK2, bbox_to_anchor=(0.55, 1.0), handletextpad=0.3)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out + "/fig_guard.pdf")
    plt.close(fig)


if __name__ == "__main__":
    R = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    G = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else R     # the cases run in all three arms
    fig_zone(R, out)
    fig_impasse(R, out)
    fig_steps(R, out)
    if "g2.PA.impasse" in G["p"]:
        fig_guard(G, out)
    print("figures written")
