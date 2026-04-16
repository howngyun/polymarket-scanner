#!/usr/bin/env bash
# 스캐너 실행. 터미널에서 `bash run.sh`
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate
cd scanner
python3 scanner.py
