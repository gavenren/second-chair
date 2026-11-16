"""LaTeX tables and derived text values for the report.

Usage: python tables.py report_numbers.json report_numbers_guard.json outdir
Writes table_models.tex, table_guard.tex and extra_auto.json (values for <<x:...>> placeholders).
"""
import json
import sys

NAMES = {"gemma-4-31b-it": "Gemma 4 31B", "gemma-4-26b-a4b-it": "Gemma 4 26B", "deepseek-v4-flash": "DeepSeek V4 Flash",
         "glm-5.3-flash": "GLM 5.3 Flash", "glm-5.2": "GLM 5.2", "qwen3.8-27b": "Qwen 3.8 27B", "qwen3.5-397b": "Qwen 3.5 397B"}


def f(v, d=0):
    if v is None:
        return "--"
    s = f"{v[0]:.{d}f}"
    if float(s) == 0:
        s = f"{0:.{d}f}"
    return s.replace("-", "$-$")


def table_models(R):
    cols = [("base.N.rg", 1), ("base.N.right_gap", 1), ("obs.impasse", 0), ("base.N.impasse", 0), ("base.P.impasse", 0), ("base.PA.impasse", 0),
            ("op.rg", 0), ("base.P.rg", 0), ("base.P.adv", 0), ("base.PA.adv", 0), ("base.anger.adv", 0), ("base.PA.mutual", 0)]
    L = [r"\setlength{\tabcolsep}{3.6pt}", r"\begin{tabular}{@{}l rr rrrr rr rrrr@{}}", r"\toprule",
         r" & \multicolumn{2}{c}{Agreed facts} & \multicolumn{4}{c}{Advised impasse (\%)} & \multicolumn{2}{c}{Own-account gap} & \multicolumn{4}{c}{Steps 4--6 (\%)} \\",
         r"\cmidrule(lr){2-3}\cmidrule(lr){4-7}\cmidrule(lr){8-9}\cmidrule(l){10-13}",
         r"Model & \shortstack[r]{Role\\gap} & \shortstack[r]{Right\\gap} & Helper & \shortstack[r]{Agreed\\facts} & \shortstack[r]{Own\\acct.} & \shortstack[r]{+ angry} & Helper & Party & \shortstack[r]{Own\\acct.} & \shortstack[r]{+ angry} & Anger & \shortstack[r]{Both\\sides} \\",
         r"\midrule"]
    for i, m in enumerate(R["models"]):
        L.append(NAMES[m] + " & " + " & ".join(f(R["pm"][k][i], d) for k, d in cols) + r" \\")
    L.append(r"\midrule")
    L.append(r"\textbf{Pooled} & " + " & ".join(r"\textbf{" + f(R["p"][k], d) + "}" for k, d in cols) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def table_guard(G):
    p, ms = G["p"], G["ms"]
    rows = [("Role gap in the forecast (points)", "rg", 1), ("Room to settle: advised zone (points)", "zone", 1), ("Advised impasse (\\% of cases)", "impasse", 0),
            ("Sent to steps 4--6 (\\% of conversations)", "adv", 0), ("Both sides sent to steps 4--6 (\\% of cases)", "mutual", 0),
            ("Distance from the full-information forecast", "err", 1), ("Merit sensitivity (points)", "MS", 0), ("Reply length (words)", "words", 0)]
    arms = [a for a in ("base", "g1", "g2") if a + ".PA.rg" in p]
    head = {"base": "Base", "g1": "g1", "g2": "g2"}
    n = len(arms)
    L = [r"\begin{tabular}{@{}l " + "r" * n + " " + "r" * n + "@{}}", r"\toprule",
         r" & \multicolumn{%d}{c}{Agreed facts (N)} & \multicolumn{%d}{c}{Own account + angry (PA)} \\" % (n, n),
         r"\cmidrule(lr){2-%d}\cmidrule(l){%d-%d}" % (n + 1, n + 2, 2 * n + 1),
         " & " + " & ".join(head[a] for a in arms) + " & " + " & ".join(head[a] for a in arms) + r" \\", r"\midrule"]
    for label, q, d in rows:
        cells = []
        for c in ("N", "PA"):
            for a in arms:
                if q == "MS":
                    v = (ms.get(f"{a}.{c}.fmean") or {}).get("p")
                else:
                    v = p.get(f"{a}.{c}.{q}")
                cells.append(f(v, d))
        L.append(label + " & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def frac_words(x):
    opts = [(0.5, "half"), (0.6, "three fifths"), (0.667, "two thirds"), (0.7, "seven tenths"), (0.75, "three quarters"), (0.8, "four fifths"), (0.9, "nine tenths")]
    return min(opts, key=lambda t: abs(t[0] - x))[1]


def main():
    R = json.load(open(sys.argv[1]))
    G = json.load(open(sys.argv[2]))
    out = sys.argv[3]
    open(out + "/table_models.tex", "w").write(table_models(R))
    open(out + "/table_guard.tex", "w").write(table_guard(G))
    p = R["p"]
    X = {}
    X["info_share"] = frac_words(p["op.rg"][0] / p["base.P.rg"][0])
    X["info_share_pct"] = f"{100 * p['op.rg'][0] / p['base.P.rg'][0]:.0f}"
    X["abs_P_zone"] = f"{abs(p['base.P.zone'][0]):.0f}"
    X["abs_PA_zone"] = f"{abs(p['base.PA.zone'][0]):.0f}"
    n_ok = sum(R["trials"].values())
    n_bad = sum(R["unresolved_errors"].values())
    _p = 100 * n_bad / (n_ok + n_bad)
    X["pct_unresolved"] = f"{_p:.2f}" if _p < 0.1 else f"{_p:.1f}"
    X["n_guard_cases"] = str(G["n_cases"])
    X["n_guard_trials"] = f"{sum(v for k, v in G['trials'].items() if not k.endswith('|base')):,}"
    s = R["steps"]
    for k in ("base|N", "base|P", "base|PA"):
        if k in s:
            adv = sum(s[k][3:])
            X["step4_of_adv:" + k] = f"{100 * s[k][3] / adv:.0f}"
            X["step3:" + k] = f"{100 * s[k][2] / sum(s[k]):.0f}"
    json.dump(X, open(out + "/extra_auto.json", "w"), indent=1)
    print("tables written;", X)


if __name__ == "__main__":
    main()
