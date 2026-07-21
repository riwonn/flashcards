#!/bin/zsh
# 더블클릭하면 chunk-bank.md → 덱 동기화 + GitHub Pages 배포
cd "$(dirname "$0")"
python3 sync.py

# 변경사항이 있으면 GitHub에 올려서 웹 주소(riwonn.github.io/flashcards)에도 반영
if [ -d .git ] && ! git diff --quiet HEAD 2>/dev/null; then
  git add -A
  git commit -q -m "덱 동기화: $(date '+%Y-%m-%d %H:%M')"
  if git push -q 2>/dev/null; then
    echo "🌍 웹 배포 완료 — 1~2분 뒤 https://riwonn.github.io/flashcards/ 에 반영돼요"
  else
    echo "⚠️ GitHub 푸시 실패 — 인터넷 연결이나 gh auth status를 확인해주세요 (로컬 덱은 정상 갱신됨)"
  fi
fi

echo ""
echo "이 창은 닫아도 됩니다."
