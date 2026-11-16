#!/bin/sh
# Final analysis: every number in the report. usage: src/final_analysis.sh <cases with all three arms>
M='gemma-4-31b-it gemma-4-26b-a4b-it deepseek-v4-flash glm-5.3-flash glm-5.2 qwen3.8-27b qwen3.5-397b'
P=.venv/bin/python
G=${1:-72}
$P src/analyze.py --models $M --n-cases 72 --n-boot 5000 --out out/numbers.json > out/summary.txt 2>&1
$P src/analyze.py --models $M --n-cases $G --n-boot 5000 --out out/numbers_guard.json > out/summary_guard.txt 2>&1
$P src/verify_independent.py --models $M > out/verify.txt 2>&1
$P src/export.py --numbers out/numbers.json --out out/report_numbers.json > out/export.txt
$P src/export.py --numbers out/numbers_guard.json --out out/report_numbers_guard.json >> out/export.txt
$P src/hedges.py > out/hedges.txt 2>&1
echo done >> out/export.txt
