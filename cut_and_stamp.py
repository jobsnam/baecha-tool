"""
배차일보 이미지 → 특정 노선 구역 자동 절개 + 날짜 자동 삽입

단일 파일:
    python cut_and_stamp.py --input 18001.png
    python cut_and_stamp.py --input 18001.png --route 5002

배치 처리 (폴더 내 전체):
    python cut_and_stamp.py --batch ./images --route 5002
    python cut_and_stamp.py --batch .          # 현재 폴더의 모든 png/jpg

옵션:
    --input   원본 이미지 파일 경로
    --batch   폴더 경로 (폴더 내 모든 이미지 일괄 처리)
    --route   절개할 노선 번호 (기본값: 5002)
    --date    날짜 텍스트 직접 지정 (생략 시 이미지에서 자동 읽기)
    --outdir  배치 결과 저장 폴더 (기본값: ./결과)
    --size    날짜 폰트 크기 (기본값: 58)
    --color   날짜 텍스트 색상 hex (기본값: cc0000)
    --list    이미지에 포함된 노선 목록만 출력
"""

import argparse
import re
import sys
from pathlib import Path


FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/Library/Fonts/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

import shutil
TESSERACT_CMD = shutil.which("tesseract") or "/usr/bin/tesseract"


def get_font(size: int):
    from PIL import ImageFont
    # index=4: Apple SD Gothic Neo SemiBold (도톰하지만 bold 아님)
    try:
        return ImageFont.truetype(FONT_PATHS[0], size=size, index=4)
    except Exception:
        pass
    for path in FONT_PATHS[1:]:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def row_brightness(img, y: int) -> float:
    """y 좌표 행의 평균 픽셀 밝기 반환"""
    w = img.size[0]
    pixels = [img.getpixel((x, y)) for x in range(0, w, 10)]
    return sum(sum(p[:3]) for p in pixels) / len(pixels) / 3


def find_section_headers(img) -> list[tuple[int, str]]:
    """
    이미지에서 노선 번호(XXXX번)가 포함된 헤더 행만 탐지.
    반환값: [(y좌표, 노선번호_문자열), ...]
    """
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    h, w = img.size[1], img.size[0]
    dark_ys = []
    prev_dark = False

    for y in range(60, h):
        if row_brightness(img, y) < 80:
            if not prev_dark:
                dark_ys.append(y)
            prev_dark = True
        else:
            prev_dark = False

    route_headers = []
    for y in dark_ys:
        area = img.crop((0, max(0, y - 2), min(w, 280), min(h, y + 38)))
        area = area.resize((area.width * 3, area.height * 3), resample=1)
        text = pytesseract.image_to_string(area, lang="kor+eng")
        m = re.search(r"(\d{3,4})[번\-]", text)
        if m:
            route_headers.append((y, m.group(1)))

    return route_headers


def extract_date_from_image(img) -> tuple[str | None, str | None]:
    """
    이미지 우측 상단에서 날짜(월/일)와 요일 자동 추출.
    예: '2026년 5월 17일 일요일' → ('5/17', '일')
    """
    DAY_MAP = {"월": "월", "화": "화", "수": "수", "목": "목",
               "금": "금", "토": "토", "일": "일"}
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

        w, h = img.size
        date_area = img.crop((int(w * 0.55), 40, w, 95))
        date_area = date_area.resize(
            (date_area.width * 2, date_area.height * 2), resample=1
        )

        text = pytesseract.image_to_string(date_area, lang="kor+eng")

        date_str = None
        m = re.search(r"(\d+)월\s*(\d+)일", text)
        if m:
            date_str = f"{m.group(1)}/{m.group(2)}"

        day_str = None
        d = re.search(r"([월화수목금토일])요일", text)
        if d:
            day_str = DAY_MAP.get(d.group(1))

        return date_str, day_str
    except Exception as e:
        print(f"[경고] 날짜 자동 읽기 실패: {e}")
    return None, None


def find_route_section(img, route: str) -> tuple[int, int] | None:
    """
    이미지에서 특정 노선 번호의 y 범위 (start, end) 반환.
    section_headers 에서 route number 헤더만 추려서 경계를 계산.
    """
    try:
        h = img.size[1]
        route_clean = route.replace("번", "").strip()

        headers = find_section_headers(img)  # [(y, route_str), ...]
        if not headers:
            return None

        for i, (y, rnum) in enumerate(headers):
            if rnum == route_clean:
                section_start = y
                section_end = headers[i + 1][0] if i + 1 < len(headers) else h
                return (section_start, section_end)

    except Exception as e:
        print(f"[오류] 노선 탐색 실패: {e}")
    return None


def list_routes(img):
    """이미지에 포함된 모든 노선 목록 출력"""
    try:
        headers = find_section_headers(img)
        h = img.size[1]
        print(f"\n[노선 목록] 총 {len(headers)}개 노선 발견:")
        for i, (y, rnum) in enumerate(headers):
            end_y = headers[i + 1][0] if i + 1 < len(headers) else h
            print(f"  {rnum}번   (y={y} ~ {end_y}, 높이={end_y - y}px)")
    except Exception as e:
        print(f"[오류] 노선 목록 읽기 실패: {e}")


def stamp_image(img, route: str, date_text: str, day_text: str,
                font_size: int, color_hex: str) -> "Image":
    """이미지에서 노선 구역을 크롭하고 날짜/요일을 삽입해 반환."""
    from PIL import Image, ImageDraw

    w, h = img.size
    result = find_route_section(img, route)
    if not result:
        return None, f"{route}번 구역을 찾지 못했습니다."

    y_start, y_end = result
    cropped = img.crop((0, y_start, w, y_end))
    cw, ch = cropped.size

    font = get_font(font_size)
    day_font = get_font(int(font_size * 0.75))
    draw = ImageDraw.Draw(cropped)
    color = hex_to_rgb(color_hex)

    date_bbox = draw.textbbox((0, 0), date_text, font=font)
    date_w = date_bbox[2] - date_bbox[0]
    date_h = date_bbox[3] - date_bbox[1]

    padding = 25
    x = cw - date_w - padding
    y = int(ch * 0.65)
    draw.text((x, y), date_text, fill=color, font=font)

    if day_text:
        day_bbox = draw.textbbox((0, 0), day_text, font=day_font)
        day_w = day_bbox[2] - day_bbox[0]
        day_x = x + (date_w - day_w) // 2
        day_y = y + date_h + 4
        draw.text((day_x, day_y), day_text, fill=color, font=day_font)

    return cropped, None


def process_one(input_path: Path, route: str, date_arg, day_arg,
                font_size: int, color_hex: str, output_path: Path | None,
                list_only: bool):
    from PIL import Image

    img = Image.open(input_path).convert("RGB")
    w, h = img.size
    print(f"[원본] {input_path.name}  ({w} x {h} px)")

    if list_only:
        list_routes(img)
        return True

    date_text = date_arg
    day_text = day_arg
    if not date_text:
        date_text, day_auto = extract_date_from_image(img)
        if not day_text:
            day_text = day_auto
        if date_text:
            print(f"[날짜] 자동 읽기 성공: {date_text}" + (f"  요일: {day_text}" if day_text else ""))
        else:
            print(f"[오류] {input_path.name} - 날짜 자동 읽기 실패 (--date 로 지정하세요)")
            return False

    print(f"[탐색] {route}번 구역 찾는 중...")
    cropped, err = stamp_image(img, route, date_text, day_text, font_size, color_hex)
    if err:
        print(f"[오류] {input_path.name} - {err}")
        return False

    date_safe = date_text.replace("/", "-")
    out = output_path or input_path.parent / f"{route}번_{date_safe}.png"
    cropped.save(out)
    print(f"[완료] {input_path.name} → {out.name}")
    return True


def process(args):
    if args.batch:
        folder = Path(args.batch)
        if not folder.is_dir():
            print(f"[오류] 폴더 없음: {folder}")
            sys.exit(1)

        files = sorted(
            [f for f in folder.iterdir()
             if f.suffix.lower() in (".png", ".jpg", ".jpeg")]
        )
        if not files:
            print(f"[오류] {folder} 에 이미지 파일이 없습니다.")
            sys.exit(1)

        outdir = Path(args.outdir)
        outdir.mkdir(exist_ok=True)
        print(f"\n총 {len(files)}개 파일 처리 시작 → 결과: {outdir}/\n")

        ok, fail = 0, 0
        for f in files:
            date_safe = (args.date or "?").replace("/", "-")
            out = outdir / f"{args.route}번_{f.stem}_{date_safe}.png"
            success = process_one(f, args.route, args.date, args.day,
                                  args.size, args.color, out, args.list)
            if success:
                ok += 1
            else:
                fail += 1
            print()

        print(f"─────────────────────────────")
        print(f"완료 {ok}개 / 실패 {fail}개  →  {outdir}/")
    else:
        if not args.input:
            print("[오류] --input 또는 --batch 를 지정하세요.")
            sys.exit(1)
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"[오류] 파일 없음: {input_path}")
            sys.exit(1)
        process_one(input_path, args.route, args.date, args.day,
                    args.size, args.color, Path(args.output) if args.output else None,
                    args.list)


def main():
    parser = argparse.ArgumentParser(description="배차일보 노선 절개 + 날짜 자동 삽입")
    parser.add_argument("--input",  default=None,           help="원본 이미지 파일 경로")
    parser.add_argument("--batch",  default=None,           help="배치 처리할 폴더 경로")
    parser.add_argument("--outdir", default="결과",          help="배치 결과 저장 폴더 (기본값: 결과)")
    parser.add_argument("--route",  default="5002",         help="노선 번호 (기본값: 5002)")
    parser.add_argument("--date",   default=None,           help="날짜 텍스트 (생략 시 자동 읽기)")
    parser.add_argument("--day",    default=None,           help="요일 한 글자 (생략 시 자동 읽기, 예: 일)")
    parser.add_argument("--output", default=None,           help="단일 파일 결과 경로")
    parser.add_argument("--size",   type=int, default=58,   help="폰트 크기 (기본값: 58)")
    parser.add_argument("--color",  default="cc0000",       help="텍스트 색상 hex (기본값: cc0000)")
    parser.add_argument("--list",   action="store_true",    help="노선 목록만 출력")
    args = parser.parse_args()

    process(args)


if __name__ == "__main__":
    main()
