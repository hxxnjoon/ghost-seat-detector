"""
tools/sample_images/ 안의 실제 좌석 사진들을 대상으로 YOLO 추론 + 좌석 매핑
결과를 눈으로 확인하기 위한 로컬 테스트 스크립트.

사용법:
    1) backend/analyzeSnapshotYolo/model/yolov8n.onnx 가 존재해야 함
       (먼저 tools/export_yolov8n_onnx.py 실행)
    2) tools/sample_images/ 에 실제 3좌석 촬영 사진(.jpg/.jpeg/.png)을 넣는다.
       (저장소의 image.png/docs/*.png는 다이어그램이라 사용 불가 — 실사진 필요)
    3) python tools/local_test_yolo.py

결과: 콘솔에 이미지별 좌석 판정 JSON 출력 + 박스가 그려진 이미지를
tools/sample_images_annotated/ 에 저장.
"""
import base64
import json
from pathlib import Path

import onnxruntime as ort
from PIL import Image, ImageDraw

import yolo_infer

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
MODEL_PATH = REPO_ROOT / "backend" / "analyzeSnapshotYolo" / "model" / "yolov8n.onnx"
SAMPLE_DIR = TOOLS_DIR / "sample_images"
ANNOTATED_DIR = TOOLS_DIR / "sample_images_annotated"

BOX_COLORS = {
    yolo_infer.PERSON_CLASS_ID: "red",
    yolo_infer.CHAIR_CLASS_ID: "blue",
}
DEFAULT_STUFF_COLOR = "orange"


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def annotate(image_path: Path, detections: list, seats: dict, zones_width: int) -> Image.Image:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    for det in detections:
        color = BOX_COLORS.get(det["class_id"], DEFAULT_STUFF_COLOR)
        draw.rectangle([det["x1"], det["y1"], det["x2"], det["y2"]], outline=color, width=3)
        draw.text((det["x1"], max(0, det["y1"] - 12)), f"{det['class_name']} {det['confidence']:.2f}", fill=color)

    third = zones_width / 3
    for x in (third, 2 * third):
        draw.line([(x, 0), (x, image.height)], fill="green", width=1)

    return image


def main() -> None:
    if not MODEL_PATH.exists():
        raise SystemExit(f"모델 파일이 없습니다: {MODEL_PATH}\n먼저 tools/export_yolov8n_onnx.py 를 실행하세요.")

    image_paths = sorted(
        p for p in SAMPLE_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )
    if not image_paths:
        raise SystemExit(
            f"{SAMPLE_DIR} 에 테스트할 사진이 없습니다. "
            "실제 3좌석 촬영 사진(.jpg/.jpeg/.png)을 넣고 다시 실행하세요."
        )

    ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)
    session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])

    for image_path in image_paths:
        image_base64 = image_to_base64(image_path)

        input_tensor, scale, pad_left, pad_top, orig_w, orig_h = yolo_infer.preprocess(image_base64)
        raw_output = yolo_infer.run(session, input_tensor)

        class_conf_thresholds = {
            yolo_infer.PERSON_CLASS_ID: yolo_infer.PERSON_CONF,
            yolo_infer.CHAIR_CLASS_ID: yolo_infer.CHAIR_CONF,
        }
        class_conf_thresholds.update({cid: yolo_infer.STUFF_CONF for cid in yolo_infer.STUFF_CLASS_IDS})

        detections = yolo_infer.postprocess(
            raw_output, scale, pad_left, pad_top, orig_w, orig_h, class_conf_thresholds
        )
        seats = yolo_infer.map_detections_to_seats(detections, orig_w, orig_h)

        print(f"\n=== {image_path.name} ===")
        print(json.dumps(seats, ensure_ascii=False, indent=2))
        print(f"탐지 개수: {len(detections)}")

        annotated = annotate(image_path, detections, seats, orig_w)
        out_path = ANNOTATED_DIR / f"{image_path.stem}_annotated.jpg"
        annotated.save(out_path, quality=90)
        print(f"주석 이미지 저장: {out_path}")


if __name__ == "__main__":
    main()
