import json
import time
from pathlib import Path

import dotenv
import requests

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
MODEL = "PaddleOCR-VL-1.6"

POLL_INTERVAL = 5
TIMEOUT = 300


def extract_pdf_ocr(path: str, output_dir: Path, stem: str) -> None:
    env = dotenv.dotenv_values(Path.home() / ".inkstone" / ".env")
    token = env.get("PADDLE_OCR_TOKEN", "")
    if not token:
        raise RuntimeError("PADDLE_OCR_TOKEN not configured in ~/.inkstone/.env")

    headers = {"Authorization": f"bearer {token}"}

    optional_payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": False,
    }

    with open(path, "rb") as f:
        resp = requests.post(
            JOB_URL,
            headers=headers,
            data={"model": MODEL, "optionalPayload": json.dumps(optional_payload)},
            files={"file": f},
        )

    if resp.status_code != 200:
        raise RuntimeError(f"OCR job submission failed: {resp.text}")

    job_id = resp.json()["data"]["jobId"]

    start = time.monotonic()
    while True:
        if time.monotonic() - start > TIMEOUT:
            raise TimeoutError("OCR job timed out after 5 minutes")

        time.sleep(POLL_INTERVAL)

        resp = requests.get(f"{JOB_URL}/{job_id}", headers=headers)
        data = resp.json()["data"]
        state = data["state"]

        if state in ("pending", "running"):
            continue
        if state == "failed":
            raise RuntimeError(f"OCR job failed: {data.get('errorMsg', 'unknown error')}")
        if state == "done":
            jsonl_url = data["resultUrl"]["jsonUrl"]
            break

    resp = requests.get(jsonl_url)
    resp.raise_for_status()

    pages = []
    for line in resp.text.strip().splitlines():
        result = json.loads(line)["result"]
        for res in result["layoutParsingResults"]:
            md_text = res["markdown"]["text"]
            images = res["markdown"].get("images", {})

            for rel_path, download_url in images.items():
                img_path = output_dir / rel_path
                img_path.parent.mkdir(parents=True, exist_ok=True)
                img_resp = requests.get(download_url)
                img_resp.raise_for_status()
                with open(img_path, "wb") as f:
                    f.write(img_resp.content)

            pages.append(md_text)

    merged = ""
    for i, page in enumerate(pages, 1):
        if i > 1:
            merged += "\n\n"
        merged += f"<!-- Page {i} -->\n\n{page}"

    md_path = output_dir / f"{stem}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(merged)
