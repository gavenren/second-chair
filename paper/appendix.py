"""Build Appendix B (cases, prompts, extra tables) from the data files and the numbers.

Usage: python appendix.py disputes.txt prompts.txt accounts.jsonl report_numbers.json report_numbers_guard.json out.tex
"""
import json
import sys

NL = "\n"


def esc(s: str) -> str:
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("<", r"\textless{}"), (">", r"\textgreater{}")):
        s = s.replace(a, b)
    return s


def load_bases(path):
    bases, cur = [], None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip(NL)
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("=="):
            bid, domain, amount = [x.strip() for x in line[2:].split("|")]
            cur = {"id": bid, "domain": domain, "amount": int(amount)}
            bases.append(cur)
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if key in ("A", "B"):
            name, role, rel = [x.strip() for x in val.split("|")]
            cur[key.lower()] = {"name": name, "role": role}
        else:
            cur[key] = val
    return bases


def load_prompts(path):
    out, name, buf = {}, None, []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip(NL)
        if line.startswith("@@ "):
            if name:
                out[name] = NL.join(buf).strip()
            name, buf = line[3:].strip(), []
        else:
            buf.append(line)
    out[name] = NL.join(buf).strip()
    return out


def quote(text: str) -> str:
    paras = [esc(p).replace(NL, r"\\ ") for p in text.split(NL + NL)]
    return r"\begin{quote}\small " + (NL + NL).join(paras) + NL + r"\end{quote}" + NL


def f(v, d=0):
    if v is None:
        return "--"
    s = f"{v[0]:.{d}f}"
    if float(s) == 0:
        s = f"{0:.{d}f}"
    return s.replace("-", "$-$")


def fci(v, d=0):
    if v is None:
        return "--"
    return f"{f(v, d)} ({f([v[1]], d)} to {f([v[2]], d)})"


def main():
    bases = load_bases(sys.argv[1])
    T = load_prompts(sys.argv[2])
    acc = {}
    for line in open(sys.argv[3], encoding="utf-8"):
        r = json.loads(line)
        acc[(r["case"], r["side"])] = r["account"]
    R = json.load(open(sys.argv[4]))
    G = json.load(open(sys.argv[5]))
    L = [r"\section{Cases, prompts and additional results}", r"\label{app:detail}", ""]

    L += [r"\subsection{The 24 base disputes}", r"\begin{center}\footnotesize\setlength{\tabcolsep}{4pt}", r"\begin{tabular}{@{}l l r l l@{}}", r"\toprule",
          r"Base & Setting & Sum & Party A (money would go to) & Party B \\", r"\midrule"]
    for b in bases:
        L.append(rf"\texttt{{{b['id']}}} & {b['domain']} & \${b['amount']:,} & {b['a']['name']}, {b['a']['role']} & {b['b']['name']}, {b['b']['role']} \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{center}", ""]

    b = next(x for x in bases if x["id"] == "vet")
    L += [r"\subsection{One case in full: \texttt{vet}}", r"\textbf{Background (agreed).} " + esc(b["BG"]), "",
          r"\textbf{Facts that help Noel.} " + esc(b["A1"]) + " " + esc(b["A2"]), "",
          r"\textbf{Facts that help Jules.} " + esc(b["B1"]) + " " + esc(b["B2"]), "",
          r"\textbf{Decisive fact, A-favoured version.} " + esc(b["DA"]), "",
          r"\textbf{Decisive fact, B-favoured version.} " + esc(b["DB"]), "",
          r"\textbf{Decisive fact, mixed version.} " + esc(b["DM"]), "",
          r"\textbf{Noel's own account, mixed version} (written by Gemma 4 26B from the fact lists):", quote(acc[("vet-M", "A")]),
          r"\textbf{Jules's own account, mixed version:}", quote(acc[("vet-M", "B")])]

    L += [r"\subsection{Prompts}", r"All prompts are in \texttt{data/prompts.txt}. Text in braces is filled in per case.", "",
          r"\textbf{The numbers question (party asking; shown for a case with a \$\{amount\} sum).}", quote(T["elicit_role"]),
          r"\textbf{Arm g1: system prompt.}", quote(T["g1_system"]),
          r"\textbf{Second Chair, step 1: case note (system prompt; the user's message is the input).}", quote(T["g2_note_system"]),
          r"\textbf{Second Chair, step 2: assessment (system prompt; the case note is the input).}", quote(T["g2_assess_system"]),
          r"\textbf{Second Chair, step 3: advice (system prompt; the user's original message is the input).}", quote(T["g2_advise_system"]),
          r"\textbf{Judge prompt for coding the free-text advice.}", quote(T["judge_user"])]

    bm = R.get("bm", {})
    if bm.get("obs.f") and all(bm["obs.f"]):
        rows = [("Neutral helper's forecast, agreed facts (\\% to A)", "obs.f", 0), ("Role gap, agreed facts (points)", "base.N.rg", 1),
                ("Advised impasse, neutral helper (\\%)", "obs.impasse", 0), ("Advised impasse, agreed facts (\\%)", "base.N.impasse", 0),
                ("Role gap, own accounts (points)", "base.P.rg", 0), ("Advised impasse, own accounts (\\%)", "base.P.impasse", 0),
                ("Advised impasse, own accounts + angry (\\%)", "base.PA.impasse", 0), ("Steps 4--6, own accounts + angry (\\%)", "base.PA.adv", 0)]
        L += [r"\subsection{Results by version of the decisive fact}",
              r"Pooled over models, base arm, with 95\% intervals. The role gap with own accounts and the impasse rates are of similar size whichever side the decisive fact favours.",
              r"\begin{center}\small", r"\begin{tabular}{@{}l rrr@{}}", r"\toprule", r" & A-favoured & Mixed & B-favoured \\", r"\midrule"]
        for label, k, d in rows:
            if k in bm:
                L.append(label + " & " + " & ".join(fci(v, d) for v in bm[k]) + r" \\")
        L += [r"\bottomrule", r"\end{tabular}", r"\end{center}", ""]

    bd = R.get("bd", {})
    if bd.get("base.PA.impasse"):
        doms = list(bd["base.PA.impasse"].keys())
        L += [r"\subsection{Results by setting}", r"Pooled over models, base arm. Point estimates only; most settings have two to five base disputes.",
              r"\begin{center}\small", r"\begin{tabular}{@{}l r rrrr@{}}", r"\toprule",
              r"Setting & Bases & \shortstack[r]{Role gap,\\agreed facts} & \shortstack[r]{Role gap,\\own acct.\ + angry} & \shortstack[r]{Impasse (\%),\\own acct.\ + angry} & \shortstack[r]{Steps 4--6 (\%),\\own acct.\ + angry} \\",
              r"\midrule"]
        for dname in doms:
            n = bd["base.PA.impasse"][dname]["n_bases"]
            L.append(f"{dname} & {n} & {bd['base.N.rg'][dname]['est']:.1f} & {bd['base.PA.rg'][dname]['est']:.0f} & "
                     f"{100 * bd['base.PA.impasse'][dname]['est']:.0f} & {100 * bd['base.PA.adv'][dname]['est']:.0f} \\\\".replace("-", "$-$"))
        L += [r"\bottomrule", r"\end{tabular}", r"\end{center}", ""]

    L += [r"\subsection{Advised impasse by model}", r"\begin{figure}[H]", r"\centering", r"\includegraphics[width=\textwidth]{figs/fig_impasse.pdf}",
          r"\caption{Advised impasse: the share of cases in which the most B is told to give is below the least A is told to accept, base arm. Lines are 95\% intervals over base disputes.}",
          r"\label{fig:impasse}", r"\end{figure}", ""]

    if "g2.PA.impasse" in G["p"]:
        L += [r"\subsection{Second Chair by model}", r"\begin{figure}[H]", r"\centering", r"\includegraphics[width=\textwidth]{figs/fig_guard.pdf}",
              r"\caption{Own account plus angry sentence, by model and arm. Lines are 95\% intervals over base disputes.}",
              r"\label{fig:guard}", r"\end{figure}", ""]

    J = R.get("judge", {})
    cells = J.get("cells") or {}
    if cells:
        names = {"base.N": "Base, agreed facts", "base.P": "Base, own account", "base.PA": "Base, own account + angry",
                 "g1.N": "g1, agreed facts", "g1.PA": "g1, own account + angry", "g2.N": "Second Chair, agreed facts",
                 "g2.PA": "Second Chair, own account + angry"}
        cols = [("strong", r"Case\\called\\strong"), ("weak", r"Case\\called\\weak"), ("other_view", r"Other side's\\view\\set out"),
                ("one_sided", r"Flags one-\\sidedness\\or asks"), ("concede", r"Suggests\\offering\\something"), ("threat", r"Suggests\\a threat"),
                ("coded_adv", r"Steps\\4--6\\(coded)")]
        L += [r"\subsection{Free-text advice as coded by the judge model}", r"\label{app:judge}",
              r"Share of replies (\%), pooled over models, coded by DeepSeek V4 Flash. No human coded any reply.",
              r"\begin{center}\footnotesize\setlength{\tabcolsep}{4pt}", r"\begin{tabular}{@{}l " + "r" * len(cols) + "@{}}", r"\toprule",
              " & " + " & ".join(r"\shortstack[r]{" + c[1] + "}" for c in cols) + r" \\", r"\midrule"]
        for k, label in names.items():
            v = cells.get(k)
            if v:
                L.append(label + " & " + " & ".join(f"{100 * v[c[0]]:.0f}" for c in cols) + r" \\")
        L += [r"\bottomrule", r"\end{tabular}", r"\end{center}", ""]
    open(sys.argv[6], "w", encoding="utf-8").write(NL.join(L) + NL)
    print("appendix written")


if __name__ == "__main__":
    main()
