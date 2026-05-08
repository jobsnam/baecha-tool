import io
import zipfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image

from cut_and_stamp import extract_date_from_image, find_section_headers, stamp_image

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 120 * 1024 * 1024  # 120MB (다장 업로드)

ALLOWED_EXT = {".png", ".jpg", ".jpeg"}


def allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


@app.errorhandler(413)
def too_large(_e):
    return jsonify(
        {
            "error": "업로드 용량이 너무 큽니다. 한 번에 올리는 용량을 줄이거나(예: 5장씩), "
            "이미지 해상도를 낮춰 보세요."
        }
    ), 413


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scan", methods=["POST"])
def scan():
    """업로드된 이미지의 노선 목록 반환"""
    file = request.files.get("file")
    if not file or not allowed(file.filename):
        return jsonify({"error": "이미지 파일을 업로드해주세요."}), 400

    img = Image.open(file.stream).convert("RGB")
    headers = find_section_headers(img)
    routes = [rnum for _, rnum in headers]
    date_text, day_text = extract_date_from_image(img)

    return jsonify({"routes": routes, "date": date_text, "day": day_text})


@app.route("/process", methods=["POST"])
def process():
    """여러 이미지 업로드 → 지정 노선 크롭 + 날짜 삽입 → ZIP 반환"""
    files = request.files.getlist("files")
    route = request.form.get("route", "5002").replace("번", "").strip()
    font_size = int(request.form.get("size", 58))
    color_hex = request.form.get("color", "cc0000").lstrip("#")

    if not files:
        return jsonify({"error": "파일을 선택해주세요."}), 400

    zip_buf = io.BytesIO()
    errors = []
    processed = 0

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in files:
            if not file or not allowed(file.filename):
                continue

            try:
                raw = file.read()
                if not raw:
                    continue
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                date_text, day_text = extract_date_from_image(img)

                if not date_text:
                    errors.append(f"{file.filename}: 날짜 읽기 실패")
                    continue

                cropped, err = stamp_image(
                    img, route, date_text, day_text, font_size, color_hex
                )
                if err:
                    errors.append(f"{file.filename}: {err}")
                    continue

                date_safe = date_text.replace("/", "-")
                out_name = f"{route}번_{date_safe}_{Path(file.filename).stem}.png"

                img_buf = io.BytesIO()
                cropped.save(img_buf, format="PNG")
                zf.writestr(out_name, img_buf.getvalue())
                processed += 1

            except Exception as e:
                errors.append(f"{file.filename}: {e}")

    if processed == 0:
        msg = "처리된 파일이 없습니다."
        if errors:
            msg += " 오류: " + " / ".join(errors)
        return jsonify({"error": msg}), 400

    zip_buf.seek(0)
    zip_name = f"{route}번_배차일보.zip"
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
