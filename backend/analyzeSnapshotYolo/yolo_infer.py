"""
YOLOv8n(ONNX) 추론 + 좌석 매핑 공용 모듈.

이 파일은 로컬 튜닝(tools/local_test_yolo.py)과 Lambda
(backend/analyzeSnapshotYolo/lambda_function.py) 양쪽에서 그대로 사용한다.
런타임 의존성은 onnxruntime / numpy / Pillow 뿐이며 torch/ultralytics는 쓰지 않는다.
"""
import base64
import io
from typing import Optional

import numpy as np
from PIL import Image

INPUT_SIZE = 640
LETTERBOX_COLOR = (114, 114, 114)

# COCO 클래스 ID
PERSON_CLASS_ID = 0
CHAIR_CLASS_ID = 56
STUFF_CLASS_IDS = {
    24: "backpack",
    26: "handbag",
    28: "suitcase",
    63: "laptop",
    67: "cell phone",
    73: "book",
}

# 신뢰도 임계값 (실사진으로 튜닝 예정)
CHAIR_CONF = 0.30
PERSON_CONF = 0.40
STUFF_CONF = 0.25
NMS_IOU_THRESHOLD = 0.45

# "앉아있는 자세"만 인정하려는 근사 필터 — Bedrock의 의미론적 판단을 대체하는
# 크기 기반 근사치다. 카메라에서 충분히 가까운(=화면에 크게 잡히는) 사람만
# person_present로 인정해, 배경을 지나가는 보행자를 걸러낸다.
PERSON_MIN_HEIGHT_RATIO = 0.25

SEAT_ZONE_HORIZONTAL_PADDING_RATIO = 0.2


def decode_image(image_base64: str) -> Image.Image:
    if "," in image_base64:
        image_base64 = image_base64.split(",")[1]
    image_bytes = base64.b64decode(image_base64)
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def letterbox(image: Image.Image, new_size: int = INPUT_SIZE):
    """종횡비를 유지한 채 new_size x new_size로 리사이즈 + 패딩."""
    orig_w, orig_h = image.size
    scale = min(new_size / orig_w, new_size / orig_h)
    new_unpad_w = round(orig_w * scale)
    new_unpad_h = round(orig_h * scale)

    resized = image.resize((new_unpad_w, new_unpad_h), Image.BILINEAR)

    pad_w = new_size - new_unpad_w
    pad_h = new_size - new_unpad_h
    pad_left = pad_w // 2
    pad_top = pad_h // 2

    padded = Image.new("RGB", (new_size, new_size), LETTERBOX_COLOR)
    padded.paste(resized, (pad_left, pad_top))

    return padded, scale, pad_left, pad_top


def preprocess(image_base64: str):
    image = decode_image(image_base64)
    orig_w, orig_h = image.size

    padded, scale, pad_left, pad_top = letterbox(image, INPUT_SIZE)

    arr = np.asarray(padded, dtype=np.float32) / 255.0  # HWC, RGB, [0,1]
    arr = arr.transpose(2, 0, 1)  # CHW
    input_tensor = np.expand_dims(arr, axis=0).astype(np.float32)  # NCHW

    return input_tensor, scale, pad_left, pad_top, orig_w, orig_h


def run(session, input_tensor: np.ndarray) -> np.ndarray:
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_tensor})
    return outputs[0]  # (1, 84, 8400)


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list:
    """클래스 내부 NMS (numpy 직접 구현, torchvision 미사용)."""
    if len(boxes) == 0:
        return []

    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)

        remaining = np.where(iou <= iou_threshold)[0]
        order = order[remaining + 1]

    return keep


def postprocess(
    raw_output: np.ndarray,
    scale: float,
    pad_left: int,
    pad_top: int,
    orig_w: int,
    orig_h: int,
    class_conf_thresholds: dict,
) -> list:
    """
    raw_output: (1, 84, 8400) — 4 bbox coords(cx,cy,w,h) + 80 class scores.
    class_conf_thresholds: {class_id: min_confidence} — 지정 안 된 클래스는 무시.
    반환: [{class_id, class_name, confidence, x1, y1, x2, y2}, ...] (원본 이미지 픽셀 좌표)
    """
    predictions = raw_output[0].T  # (8400, 84)
    boxes_cxcywh = predictions[:, :4]
    class_scores = predictions[:, 4:]

    class_ids = np.argmax(class_scores, axis=1)
    confidences = class_scores[np.arange(len(class_scores)), class_ids]

    detections_by_class: dict = {}

    for idx in range(len(predictions)):
        cls_id = int(class_ids[idx])
        conf = float(confidences[idx])

        threshold = class_conf_thresholds.get(cls_id)
        if threshold is None or conf < threshold:
            continue

        cx, cy, w, h = boxes_cxcywh[idx]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2

        # letterbox 패딩/스케일 역변환 → 원본 이미지 좌표
        x1 = (x1 - pad_left) / scale
        y1 = (y1 - pad_top) / scale
        x2 = (x2 - pad_left) / scale
        y2 = (y2 - pad_top) / scale

        x1 = max(0.0, min(x1, orig_w))
        y1 = max(0.0, min(y1, orig_h))
        x2 = max(0.0, min(x2, orig_w))
        y2 = max(0.0, min(y2, orig_h))

        if x2 <= x1 or y2 <= y1:
            continue

        detections_by_class.setdefault(cls_id, []).append((conf, x1, y1, x2, y2))

    results = []
    for cls_id, rows in detections_by_class.items():
        boxes = np.array([[x1, y1, x2, y2] for _, x1, y1, x2, y2 in rows], dtype=np.float32)
        scores = np.array([conf for conf, *_ in rows], dtype=np.float32)
        keep = _nms(boxes, scores, NMS_IOU_THRESHOLD)

        for i in keep:
            conf, x1, y1, x2, y2 = rows[i]
            results.append(
                {
                    "class_id": cls_id,
                    "class_name": STUFF_CLASS_IDS.get(
                        cls_id, "person" if cls_id == PERSON_CLASS_ID else "chair" if cls_id == CHAIR_CLASS_ID else str(cls_id)
                    ),
                    "confidence": conf,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                }
            )

    return results


def _build_seat_zones(chair_detections: list, image_width: int) -> list:
    """
    좌석 x존 3개를 결정한다.
    - 의자가 정확히 3개 탐지되면 의자 위치 기반(왼쪽→오른쪽) + 20% 가로 여유.
    - 그 외(0/1/2/4+ 개)는 화면을 x좌표 기준 균등 3분할하는 폴백을 사용한다.
      데모 안정성을 우선한 결정론적 폴백이며, 부분 탐지 시 의자 위치 정밀도는 잃는다.
    반환: [(x_min, x_max), ...] 좌석 1,2,3 순서 (왼쪽→오른쪽)
    """
    if len(chair_detections) == 3:
        sorted_chairs = sorted(chair_detections, key=lambda d: (d["x1"] + d["x2"]) / 2)
        zones = []
        for chair in sorted_chairs:
            width = chair["x2"] - chair["x1"]
            pad = width * SEAT_ZONE_HORIZONTAL_PADDING_RATIO
            zones.append((chair["x1"] - pad, chair["x2"] + pad))
        return zones

    third = image_width / 3
    return [(0, third), (third, 2 * third), (2 * third, image_width)]


def _zone_index_for_x(center_x: float, zones: list) -> Optional[int]:
    for i, (x_min, x_max) in enumerate(zones):
        if x_min <= center_x < x_max:
            return i
    # 마지막 존의 오른쪽 경계(image_width)에 걸치는 경우를 위한 보정
    if zones and center_x >= zones[-1][1]:
        return len(zones) - 1
    if zones and center_x < zones[0][0]:
        return 0
    return None


def map_detections_to_seats(detections: list, image_width: int, image_height: int) -> dict:
    """detections -> {"1": {"person_present": bool, "stuff_present": bool}, "2": {...}, "3": {...}}"""
    chair_detections = [d for d in detections if d["class_id"] == CHAIR_CLASS_ID]
    zones = _build_seat_zones(chair_detections, image_width)

    seats = {
        "1": {"person_present": False, "stuff_present": False},
        "2": {"person_present": False, "stuff_present": False},
        "3": {"person_present": False, "stuff_present": False},
    }

    for det in detections:
        cls_id = det["class_id"]
        center_x = (det["x1"] + det["x2"]) / 2
        zone_idx = _zone_index_for_x(center_x, zones)
        if zone_idx is None:
            continue
        seat_label = str(zone_idx + 1)

        if cls_id == PERSON_CLASS_ID:
            box_height = det["y2"] - det["y1"]
            if box_height >= PERSON_MIN_HEIGHT_RATIO * image_height:
                seats[seat_label]["person_present"] = True
        elif cls_id in STUFF_CLASS_IDS:
            seats[seat_label]["stuff_present"] = True

    return seats


def analyze(session, image_base64: str) -> dict:
    """전체 파이프라인: base64 이미지 -> 좌석 판정 dict."""
    input_tensor, scale, pad_left, pad_top, orig_w, orig_h = preprocess(image_base64)
    raw_output = run(session, input_tensor)

    class_conf_thresholds = {PERSON_CLASS_ID: PERSON_CONF, CHAIR_CLASS_ID: CHAIR_CONF}
    class_conf_thresholds.update({cls_id: STUFF_CONF for cls_id in STUFF_CLASS_IDS})

    detections = postprocess(raw_output, scale, pad_left, pad_top, orig_w, orig_h, class_conf_thresholds)
    return map_detections_to_seats(detections, orig_w, orig_h)
