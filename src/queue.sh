#!/bin/sh
# Main run, in three balanced rounds of 24 cases. Resumable: finished trials are skipped.
M='gemma-4-31b-it gemma-4-26b-a4b-it deepseek-v4-flash glm-5.3-flash glm-5.2 qwen3.8-27b qwen3.5-397b'
P=.venv/bin/python
$P src/run.py --models $M --arms base --first-case 0 --n-cases 24
$P src/run.py --models $M --arms g2 g1 --first-case 0 --n-cases 24
$P src/run.py --models $M --arms base --first-case 24 --n-cases 48
$P src/run.py --models $M --arms g2 g1 --first-case 24 --n-cases 48
$P src/run.py --models $M --arms base --first-case 48 --n-cases 72
$P src/judge.py --judge deepseek-v4-flash --models $M --arms base g1 g2 --every 3
$P src/run.py --models $M --arms g2 g1 --first-case 48 --n-cases 72
echo QUEUE DONE
