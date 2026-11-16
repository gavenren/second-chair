# An Angel on Each Shoulder

Code and data for the report 'An Angel on Each Shoulder: Chatbots Believe Whoever Is Talking,
and Advise Both Sides of a Dispute into Impasse' (AI x Epistemics Research Sprint, November
2026, Track 3: Epistemic Products). Everything in this repository was written during the sprint.

## What it does

Both parties to the same money dispute ask the same chatbot what to do. For 72 cases and seven
hosted models the code collects, for each party and for a neutral helper, the free-text advice
and four numbers: the forecast outcome, the walk-away point, how far one side is in the right,
and the recommended next step on a six-rung ladder. From these it computes

- the role gap (does the forecast depend on who asks?),
- the advised bargaining zone (do the two advised walk-away points overlap?),
- escalation (how often is a firm demand or stronger recommended, and what does one angry
  sentence add?),
- how much of the gap comes from one-sided information and how much from being addressed,
- the same outcomes under two fixes: a one-paragraph system prompt (g1) and Second Chair (g2:
  neutral case note, independent assessment that allows for the unheard side, then advice).

## Layout

    data/disputes.txt     24 base disputes, each with A-favoured, mixed and B-favoured versions
    data/prompts.txt      every prompt (data/prompts_before_g2_revision.txt: earlier g2 wording)
    data/accounts.jsonl   each party's own account of each case, with the checker's labels
    PLAN.md               analysis plan written before the main run, with a dated addendum
    src/cases.py          parse the disputes, build the 72 cases
    src/prompts.py        build every message
    src/client.py         Adaption Responses API client (streaming, cache, rate limiter)
    src/make_accounts.py  write and check the own accounts
    src/run.py            run trials (arms base, g1, g2)
    src/judge.py          code the free-text advice with a judge model
    src/analyze.py        every number, with bootstrap intervals over base disputes
    src/verify_independent.py  re-derive the headline estimates with separate code
    src/export.py         the numbers the report uses, as one JSON file
    src/hedges.py         keyword check used in the report
    src/queue*.sh, src/final_analysis.sh   the order in which things were run
    tests/                unit tests (pytest)
    runs/<model>/trials.jsonl   one line per trial, including the full advice text
    runs/judge/<judge>/codes.jsonl   judge codes
    runs_default/         trials collected at the default reasoning setting before the switch
    out/                  numbers.json, numbers_guard.json, report_numbers*.json, summaries
    paper/                LaTeX parts, figure and table code, build script
    deliver/              the report PDF

## Reproduce

Requirements: Python 3.12, pip install adaption numpy pytest (matplotlib and pdflatex for the
report), and ADAPTION_API_KEY in the environment for anything that calls a model.

    python -m pytest -q tests
    python src/make_accounts.py                      # writes data/accounts.jsonl
    python src/run.py --models gemma-4-31b-it ... --arms base g2 g1
    python src/judge.py --judge deepseek-v4-flash --models ... --arms base g2 g1 --every 2
    src/final_analysis.sh 72                         # out/numbers.json and the exports
    paper/build.sh out/report_numbers.json out/report_numbers_guard.json data

Notes on the Adaption API: reasoning effort defaults to the highest setting; the runs use
effort none (low for GLM 5.3 Flash). More than about ten concurrent requests trigger
rate-limit errors. Calls are streamed because the gateway cuts non-streamed calls at 60 s.

## Caveats

No human disputants, no human coding of replies, written cases, open-weight models only. See
the Limitations appendix of the report. Nothing here is legal advice.
