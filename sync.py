#!/usr/bin/env python3
"""chunk-bank.md + import/*.csv → data.js 로 변환하는 동기화 스크립트.

사용법:  python3 sync.py   (또는 sync.command 더블클릭)
"""
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHUNK_BANK = ROOT.parent / "Daily Note" / "chunk-bank.md"
IMPORT_DIR = ROOT / "import"
EXAMPLES = ROOT / "examples.json"  # 카드 id → 예문 리스트 (Claude가 생성)
PRESETS = ROOT / "presets.json"    # 테마 세트 정의 (Claude가 큐레이션)
APP = ROOT / "index.html"
WEBAPP = ROOT / "webapp.html"
DECK_START = "// ==DECK-START=="
DECK_END = "// ==DECK-END=="


def make_webapp(html: str) -> str:
    """index.html → 아티팩트 배포용 (문서 래퍼 제거, 웹용 안내 문구)."""
    out = html
    for tag in (
        "<!DOCTYPE html>",
        '<html lang="ko">',
        "</html>",
        "<head>",
        "</head>",
        "<body>",
        "</body>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
    ):
        out = out.replace(tag + "\n", "").replace(tag, "")
    out = out.replace(
        "chunk-bank.md가 바뀌면 <b>Flashcards/sync.command</b>를 더블클릭하세요",
        '덱 업데이트가 필요하면 Claude에게 "플래시카드 동기화 후 웹앱 업데이트"라고 말해주세요',
    )
    return out


def clean(cell: str) -> str:
    cell = cell.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    cell = re.sub(r"\*\*(.*?)\*\*", r"\1", cell)
    cell = cell.replace("`", "").replace("_", "")
    cell = re.sub(r"\n{3,}", "\n\n", cell)
    return "\n".join(line.strip() for line in cell.splitlines()).strip()


def card_id(ko: str, en: str) -> str:
    return hashlib.md5((ko + "||" + en).encode()).hexdigest()[:12]


def split_row(line: str):
    return line.strip().strip("|").split("|")


def row_to_card(headers, cells, section):
    def get(i):
        return clean(cells[i]) if i < len(cells) else ""

    h0 = headers[0] if headers else ""
    if "한국어" in h0:
        # | 한국어 | ❌ 직역 | ✅ 네이티브 |  → 앞면: 한국어, 뒷면: 네이티브
        ko, literal, en = get(0), get(1), get(2)
        note = f"❌ 직역: {literal}" if literal and literal not in ("—", "-") else ""
    elif "표현" in h0:
        # | (✅) 표현 | 뜻/맥락/쓰임새 | (출처) |  → 앞면: 뜻, 뒷면: 표현
        en, ko = get(0), get(1)
        src = get(2)
        note = f"출처: {src}" if src and src not in ("—", "-") else ""
        # 뜻 셀의 "뜻 — 예문/설명" 구조: 예문에 정답이 새는 걸 막기 위해 앞면은 뜻만 남긴다
        parts = re.split(r"\s*—\s*", ko, maxsplit=1)
        if len(parts) == 2 and parts[0].strip():
            ko = parts[0].strip()
            extra = parts[1].strip()
            if extra:
                note = extra + ("\n" + note if note else "")
    else:
        return None

    en = en.strip('"').strip()
    if ko in ("", "—", "-") or en in ("", "—", "-"):
        return None
    return {"id": card_id(ko, en), "ko": ko, "en": en, "note": note, "cat": section}


def parse_chunk_bank(text: str):
    cards = []
    section = ""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^#{2,3}\s+(.*)", line)
        if m:
            section = re.sub(r"\s*\(.*?\)\s*$", "", m.group(1)).strip()
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(
            r"^\s*\|[\s\-:|]+\|?\s*$", lines[i + 1]
        ):
            headers = [clean(c) for c in split_row(line)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                card = row_to_card(headers, split_row(lines[i]), section)
                if card:
                    cards.append(card)
                i += 1
            continue
        i += 1
    return cards


HANGUL = re.compile(r"[가-힣]")
HEADER_WORDS = {"korean", "ko", "kr", "한국어", "front", "앞면",
                "english", "en", "영어", "back", "뒷면", "note", "메모", "비고"}


def read_csv_text(path: Path) -> str:
    """UTF-8 우선, 실패하면 CP949(엑셀 한국어 CSV) 폴백."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_csvs():
    cards = []
    for f in sorted(IMPORT_DIR.glob("*.csv")) + sorted(IMPORT_DIR.glob("*.tsv")):
        text = read_csv_text(f)
        sample = "\n".join(l for l in text.splitlines() if l.strip())[:500]
        delim = max([",", "\t", ";"], key=sample.count)
        for row in csv.reader(text.splitlines(), delimiter=delim):
            # 셀 양끝의 잔여 따옴표 제거 (스프레드시트 내보내기에서 자주 생김)
            cells = [re.sub(r'^["“”]+\s*|\s*["“”]+$', "", c.strip()).strip() for c in row]
            if not any(cells):
                continue
            if all(c.lower() in HEADER_WORDS for c in cells if c):
                continue
            ko = cells[0] if len(cells) > 0 else ""
            en = cells[1] if len(cells) > 1 else ""
            if not HANGUL.search(ko) and HANGUL.search(en):
                ko, en = en, ko  # 영어,한국어 순서면 뒤집기
            note = " · ".join(c for c in cells[2:] if c)
            if not ko or not en:
                continue
            cards.append(
                {"id": card_id(ko, en), "ko": ko, "en": en, "note": note,
                 "cat": f"CSV · {f.stem}"}
            )
    return cards


def main():
    if not CHUNK_BANK.exists():
        print(f"⚠️  chunk-bank.md 를 찾을 수 없어요: {CHUNK_BANK}")
        bank_cards = []
    else:
        bank_cards = parse_chunk_bank(CHUNK_BANK.read_text(encoding="utf-8"))

    csv_cards = parse_csvs()

    seen, cards = set(), []
    for c in bank_cards + csv_cards:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        cards.append(c)

    # 예문 병합
    examples = {}
    if EXAMPLES.exists():
        try:
            examples = json.loads(EXAMPLES.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  examples.json 파싱 실패 (예문 없이 진행): {e}")
    no_example = 0
    for c in cards:
        ex = examples.get(c["id"])
        if ex:
            c["ex"] = ex
        elif not c["cat"].startswith("CSV"):
            no_example += 1
    if no_example:
        print(f"ℹ️  예문 없는 카드 {no_example}장 — Claude에게 '플래시카드 예문 생성'을 요청하면 채워져요")

    # 테마 세트 로드 (덱에 없는 id는 걸러서 포함)
    presets = []
    if PRESETS.exists():
        try:
            valid = {c["id"] for c in cards}
            for p in json.loads(PRESETS.read_text(encoding="utf-8")):
                ids = [i for i in p.get("ids", []) if i in valid]
                if ids:
                    presets.append({"name": p["name"], "desc": p.get("desc", ""), "ids": ids})
        except Exception as e:
            print(f"⚠️  presets.json 파싱 실패 (세트 없이 진행): {e}")
    in_preset = {i for p in presets for i in p["ids"]}
    unassigned = sum(1 for c in cards if c["id"] not in in_preset)
    if presets and unassigned:
        print(f"ℹ️  세트에 속하지 않은 카드 {unassigned}장 — Claude에게 '플래시카드 세트 업데이트'를 요청하면 배정돼요")

    deck = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "bankCount": len(bank_cards),
        "csvCount": len(csv_cards),
        "cards": cards,
        "presets": presets,
    }
    # 카드 데이터를 index.html 안에 직접 내장 (별도 파일 로드 실패 원천 차단)
    payload = json.dumps(deck, ensure_ascii=False).replace("</", "<\\/")
    html = APP.read_text(encoding="utf-8")
    start = html.index(DECK_START) + len(DECK_START)
    end = html.index(DECK_END)
    html = (
        html[:start]
        + f" (sync.py가 자동으로 채우는 영역 — 직접 수정하지 마세요)\nwindow.CHUNK_DECK = {payload};\n"
        + html[end:]
    )
    APP.write_text(html, encoding="utf-8")
    WEBAPP.write_text(make_webapp(html), encoding="utf-8")
    print(f"✅ 동기화 완료 — chunk-bank {len(bank_cards)}장 + CSV {len(csv_cards)}장 → 총 {len(cards)}장")
    print(f"   → index.html + webapp.html 갱신 완료")


if __name__ == "__main__":
    main()
