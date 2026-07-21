#!/bin/bash
# 핸드폰에서 플래시카드 보기 — 이 파일을 더블클릭하면 서버가 켜져요.
# · 같은 와이파이: 아래 표시되는 192.168.x.x 주소로 접속
# · 외부(셀룰러): 아래 표시되는 trycloudflare.com 주소로 접속 (실행할 때마다 주소가 바뀜)
cd "$(dirname "$0")"
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
echo ""
echo "  📱 같은 와이파이에서:  http://${IP:-<맥의 IP>}:8787"

if command -v cloudflared >/dev/null 2>&1; then
  LOG=$(mktemp)
  cloudflared tunnel --url http://localhost:8787 >"$LOG" 2>&1 &
  TUNNEL_PID=$!
  trap 'kill $TUNNEL_PID 2>/dev/null' EXIT
  URL=""
  for _ in $(seq 1 30); do
    URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1)
    [ -n "$URL" ] && break
    sleep 1
  done
  echo ""
  if [ -n "$URL" ]; then
    echo "  🌍 외부(셀룰러)에서:   $URL"
    echo "     (이 주소는 실행할 때마다 바뀌어요)"
  else
    echo "  ⚠️ 외부 접속 터널 생성 실패 — 와이파이 주소만 사용 가능해요"
  fi
else
  echo ""
  echo "  ℹ️ 외부(셀룰러) 접속도 원하면 터미널에서:  brew install cloudflared"
fi

echo ""
echo "  이 창을 닫으면 서버가 꺼져요. 끝내려면 Ctrl+C 또는 창 닫기."
echo ""
python3 -m http.server 8787 --bind 0.0.0.0
