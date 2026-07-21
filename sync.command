#!/bin/zsh
# 더블클릭하면 chunk-bank.md → data.js 동기화
cd "$(dirname "$0")"
python3 sync.py
echo ""
echo "이 창은 닫아도 됩니다."
