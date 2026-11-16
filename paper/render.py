"""Fill the report template from report_numbers.json and write report.tex.

Placeholders in the .tex parts:
  <<e:KEY>>      pooled estimate, one decimal        <<e0:KEY>>   rounded to a whole number
  <<ci:KEY>>     "est (lo to hi)" with one decimal   <<ci0:KEY>>  whole numbers   <<pc:KEY>>  "est% (lo to hi)"
  <<lo:KEY>> <<hi:KEY>>  interval ends
  KEY may end in @model for a per-model value (model id as in the models list), and may start
  with G: to read from the --guard= file (the cases run in all three arms).
  <<ms:KEY>> / <<msci:KEY>>  merit sensitivity (pooled)
  <<x:NAME>>     values computed below
Any placeholder left unfilled is an error.

Usage: python render.py report_numbers.json out.tex part1.tex part2.tex ...
"""
import json
import re
import sys

NAMES = {"gemma-4-31b-it": "Gemma 4 31B", "gemma-4-26b-a4b-it": "Gemma 4 26B", "deepseek-v4-flash": "DeepSeek V4 Flash",
         "glm-5.3-flash": "GLM 5.3 Flash", "glm-5.2": "GLM 5.2", "qwen3.8-27b": "Qwen 3.8 27B", "qwen3.5-397b": "Qwen 3.5 397B"}


def minus(s: str) -> str:
    return s.replace("-", "−")


def fmt(v: float, d: int) -> str:
    s = f"{v:.{d}f}"
    if float(s) == 0:
        s = f"{0:.{d}f}"
    return minus(s)


def main():
    R = json.load(open(sys.argv[1]))
    out_path, parts = sys.argv[2], sys.argv[3:]
    G = R
    for a in parts[:]:
        if a.startswith("--guard="):
            G = json.load(open(a.split("=", 1)[1]))        # the same analysis on the cases run in all three arms
            parts.remove(a)
    models = R["models"]

    def get(key: str):
        src = R
        if key.startswith("G:"):
            src, key = G, key[2:]
        if "@" in key:
            k, m = key.split("@")
            v = src["pm"][k][models.index(m)]
        else:
            v = src["p"][key]
        if v is None:
            raise KeyError(key)
        return v

    X = {}
    X["n_models"] = str(len(models))
    X["n_cases"] = str(R["n_cases"])
    X["n_boot"] = f"{R['n_boot']:,}"
    X["n_trials_base"] = f"{sum(v for k, v in R['trials'].items() if k.endswith('|base')):,}"
    X["n_trials_all"] = f"{sum(R['trials'].values()):,}"
    X["n_trials_guard"] = f"{sum(v for k, v in R['trials'].items() if not k.endswith('|base')):,}"
    X["n_unresolved"] = str(sum(R["unresolved_errors"].values()))
    for src, pre in ((R, ""), (G, "G")):
        for key in src["pm"]:
            vals = [(v[0], m) for v, m in zip(src["pm"][key], models) if v is not None]
            if not vals:
                continue
            lo, hi = min(vals), max(vals)
            X[pre + "min:" + key], X[pre + "max:" + key] = fmt(lo[0], 0), fmt(hi[0], 0)
            X[pre + "min1:" + key], X[pre + "max1:" + key] = fmt(lo[0], 1), fmt(hi[0], 1)
            X[pre + "argmin:" + key], X[pre + "argmax:" + key] = NAMES[lo[1]], NAMES[hi[1]]
            X[pre + "npos:" + key] = str(sum(1 for v in src["pm"][key] if v is not None and v[1] > 0))   # interval above zero
            X[pre + "nneg:" + key] = str(sum(1 for v in src["pm"][key] if v is not None and v[2] < 0))   # interval below zero
            X[pre + "nup:" + key] = str(sum(1 for v in src["pm"][key] if v is not None and v[0] > 0))
    for k, v in R.get("ratio", {}).items():
        if v:
            X["ratio:" + k.split("/")[0]] = fmt(100 * v[0], 0)
            X["ratioci:" + k.split("/")[0]] = f"{fmt(100 * v[0], 0)}\\% ({fmt(100 * v[1], 0)} to {fmt(100 * v[2], 0)})"
    for src, pre in ((R, ""), (G, "G")):
        for k, c in src["steps"].items():
            tot = sum(c)
            for j in range(6):
                X[f"{pre}step{j + 1}:{k}"] = fmt(100 * c[j] / tot, 0)
            X[pre + "step23:" + k] = fmt(100 * (c[1] + c[2]) / tot, 0)
            X[pre + "stepn:" + k] = f"{tot:,}"
    for k, v in R.get("bm", {}).items():
        for mt, val in zip("AMB", v):
            if val is not None:
                X[f"bm:{k}:{mt}"] = fmt(val[0], 0)
                X[f"bm1:{k}:{mt}"] = fmt(val[0], 1)
                X[f"bmci:{k}:{mt}"] = f"{fmt(val[0], 0)} ({fmt(val[1], 0)} to {fmt(val[2], 0)})"
    J = R.get("judge", {})
    if J.get("self_vs_coded"):
        sv = J["self_vs_coded"]
        X["judge_n"] = f"{sv['n']:,}"
        X["judge_same_adv"] = fmt(100 * sv["same_adv"], 0)
        X["judge_same_step"] = fmt(100 * sv["same_step"], 0)
        X["judge_kappa"] = f"{sv['kappa_adv']:.2f}"
        for cell, v in J.get("cells", {}).items():
            if v:
                for q, val in v.items():
                    X[f"j:{cell}:{q}"] = fmt(100 * val, 0) if q != "coded_step" else fmt(val, 1)
    if J.get("judges_agree"):
        ag = J["judges_agree"]
        X["judge2_n"] = f"{ag['n']:,}"
        X["judge2_kappa"] = f"{ag['kappa_adv']:.2f}"
        for q in ("validates", "other_view", "one_sided", "concede", "threat", "step", "adv"):
            X["judge2_" + q] = fmt(100 * ag[q], 0)
    extra = {}
    for a in parts[:]:
        if a.endswith(".json"):
            extra.update(json.load(open(a)))
            parts.remove(a)
    X.update(extra)

    def sub(m):
        kind, key = m.group(1), m.group(2)
        if kind == "x":
            return X[key]
        if kind in ("ms", "msci", "ms0"):
            v = (G["ms"][key[2:]] if key.startswith("G:") else R["ms"][key])["p"]
            if v is None:
                return "??"
            if kind == "ms":
                return fmt(v[0], 1)
            if kind == "ms0":
                return fmt(v[0], 0)
            return f"{fmt(v[0], 1)} ({fmt(v[1], 1)} to {fmt(v[2], 1)})"
        v = get(key)
        d = 0 if kind.endswith("0") else 1
        if kind in ("e", "e0"):
            return fmt(v[0], d)
        if kind == "pc":
            return f"{fmt(v[0], 0)}\\% ({fmt(v[1], 0)} to {fmt(v[2], 0)})"
        if kind in ("ci", "ci0"):
            return f"{fmt(v[0], d)} ({fmt(v[1], d)} to {fmt(v[2], d)})"
        if kind == "lo0":
            return fmt(v[1], 0)
        if kind == "hi0":
            return fmt(v[2], 0)
        if kind == "lo":
            return fmt(v[1], 1)
        if kind == "hi":
            return fmt(v[2], 1)
        raise KeyError(kind)

    text = "".join(open(p, encoding="utf-8").read() for p in parts)
    for _ in range(3):          # text placeholders may contain number placeholders
        text = re.sub(r"<<(x|e0|e|ci0|ci|pc|lo0|hi0|lo|hi|ms0|msci|ms):([^>]+)>>", sub, text)
    left = re.findall(r"<<[a-zA-Z0-9]+:[^>]*>>|<<[A-Z_]+>>", text)
    if left:
        raise SystemExit("unfilled placeholders: " + ", ".join(sorted(set(left))[:20]))
    open(out_path, "w", encoding="utf-8").write(text)
    print("wrote", out_path, len(text), "chars")


if __name__ == "__main__":
    main()
