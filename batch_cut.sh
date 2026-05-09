#!/usr/bin/env bash
# 배차일보: 숫자 파일명 PNG/JPG 일괄 절개(기본 5002번) + 날짜 스탬프 → 결과/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PY="${ROOT}/venv/bin/python"
STAMP="${ROOT}/cut_and_stamp.py"
OUTDIR="${OUTDIR:-결과}"
ROUTE="${ROUTE:-5002}"

usage() {
  echo "배차일보 일괄 절개 → ${OUTDIR:-결과}/"
  echo ""
  echo "Usage: $0 [options]"
  echo "  --all       숫자 외 파일명도 포함 (dbg_*, debug_*, *번_*.* 제외)"
  echo "  --list      절개 없이 노선 목록만"
  echo "  --route N   노선 (기본 5002)"
  echo "  --outdir D  출력 폴더 (기본 결과)"
  echo "  Env: OUTDIR, ROUTE — 명령행이 우선"
  exit 0
}

LIST_ONLY=0
ALL_FILES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    --list) LIST_ONLY=1; shift ;;
    --all) ALL_FILES=1; shift ;;
    --route) ROUTE="$2"; shift 2 ;;
    --outdir) OUTDIR="$2"; shift 2 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
  esac
done

[[ -f "$STAMP" ]] || { echo "없음: $STAMP" >&2; exit 1; }
[[ -x "$PY" ]] || { echo "venv Python 없음: $PY" >&2; exit 1; }

mkdir -p "$OUTDIR"

shopt -s nullglob
FILES=()
if [[ "$ALL_FILES" -eq 1 ]]; then
  for f in *.png *.jpg *.jpeg; do
    case "$f" in
      dbg_*|debug_*) continue ;;
    esac
    [[ "$f" == *번_*.* ]] && continue
    FILES+=("$f")
  done
else
  for f in *.png *.jpg *.jpeg; do
    base="${f%.*}"
    [[ "$base" =~ ^[0-9]+$ ]] || continue
    FILES+=("$f")
  done
fi
shopt -u nullglob

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "처리할 이미지가 없습니다. 원본을 $ROOT 에 두거나 --all 을 쓰세요." >&2
  exit 1
fi

echo "출력: $OUTDIR/  노선: ${ROUTE}번  (${#FILES[@]}개)"
echo ""

while IFS= read -r f; do
  [[ -n "$f" ]] || continue
  stem="${f%.*}"
  out="${OUTDIR}/${ROUTE}번_${stem}.png"
  echo "======== $f ========"
  if [[ "$LIST_ONLY" -eq 1 ]]; then
    "$PY" "$STAMP" --input "$f" --list
  else
    "$PY" "$STAMP" --input "$f" --route "$ROUTE" --output "$out"
  fi
  echo ""
done < <(printf '%s\n' "${FILES[@]}" | sort -V)

echo "완료 → $OUTDIR/"
