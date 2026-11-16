#!/bin/sh
# Build the report from the two numbers files. usage: ./build.sh numbers.json numbers_guard.json datadir
set -e
cd "$(dirname "$0")"
mkdir -p build
R=$1; G=$2; D=$3
python3 figs.py "$R" figs "$G"
python3 tables.py "$R" "$G" build
python3 appendix.py "$D/disputes.txt" "$D/prompts.txt" "$D/accounts.jsonl" "$R" "$G" build/92_appendix_b.tex
python3 render.py "$R" build/report.tex --guard="$G" build/extra_auto.json ${EXTRA:-extra_manual.json} 00_head.tex 10_intro.tex 20_related.tex 30_methods.tex 40_results.tex 50_discussion.tex 70_codedata.tex 80_refs.tex 90_appendix_a.tex build/92_appendix_b.tex 95_llm.tex
cd build && cp -r ../figs . 2>/dev/null; for i in 1 2 3; do pdflatex -interaction=nonstopmode report.tex > build.log 2>&1 || true; done
grep -E "^!|Overfull|undefined|Output written" build.log | head -20
