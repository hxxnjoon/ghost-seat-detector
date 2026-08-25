"""
YOLOv8n(COCO 사전학습) 가중치를 ONNX로 export하는 1회성 로컬 스크립트.

Lambda 런타임에는 ultralytics/torch를 절대 포함하지 않는다 — 이 스크립트에서만
사용해 .onnx 파일을 생성하고, 이후 추론은 onnxruntime만으로 수행한다.

사용법:
    python3.11 -m venv tools/.venv-export
    source tools/.venv-export/bin/activate
    pip install -r tools/requirements-dev.txt
    python tools/export_yolov8n_onnx.py
"""
import shutil
from pathlib import Path

from ultralytics import YOLO

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DEST = REPO_ROOT / "backend" / "analyzeSnapshotYolo" / "model" / "yolov8n.onnx"


def main() -> None:
    model = YOLO("yolov8n.pt")  # 최초 실행 시 COCO 사전학습 가중치 자동 다운로드
    exported_path = model.export(format="onnx", imgsz=640, opset=12, simplify=True)

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(exported_path), str(DEST))
    print(f"ONNX 모델 저장 완료: {DEST} ({DEST.stat().st_size / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()
