#!/bin/sh
# Remaining work, reordered at 14:22 because the Mac was running on battery: the most
# informative pieces first. Waits for the run that is in progress, then continues.
M='gemma-4-31b-it gemma-4-26b-a4b-it deepseek-v4-flash glm-5.3-flash glm-5.2 qwen3.8-27b qwen3.5-397b'
P=.venv/bin/python
while pgrep -f 'src/run.py' > /dev/null; do sleep 5; done
$P src/run.py --models $M --arms base --first-case 0 --n-cases 24
$P src/judge.py --judge deepseek-v4-flash --models $M --arms base g2 g1 --every 2
$P src/run.py --models $M --arms base --first-case 24 --n-cases 48
$P src/judge.py --judge gemma-4-31b-it --models $M --arms base g2 g1 --every 6
$P src/run.py --models $M --arms g2 g1 --first-case 24 --n-cases 48
$P src/run.py --models $M --arms base --first-case 48 --n-cases 72
$P src/judge.py --judge deepseek-v4-flash --models $M --arms base g2 g1 --every 2
$P src/run.py --models $M --arms g2 g1 --first-case 48 --n-cases 72
$P src/judge.py --judge deepseek-v4-flash --models $M --arms base g2 g1 --every 2
$P src/judge.py --judge gemma-4-31b-it --models $M --arms base g2 g1 --every 6
echo QUEUE DONE
