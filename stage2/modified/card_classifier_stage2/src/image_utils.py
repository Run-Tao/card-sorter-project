from pathlib import Path
import cv2
import numpy as np

CARD_WIDTH = 500
CARD_HEIGHT = 700


def read_image(path):
    path = str(path)
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图像：{path}")
    return image


def _order_quad(points):
    """Order four points around the quadrilateral and make the short edge horizontal."""
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    center = pts.mean(axis=0)
    angles = np.arctan2(pts[:, 1] - center[1], pts[:, 0] - center[0])
    pts = pts[np.argsort(angles)]
    # Start from the point closest to the upper-left corner.
    start = int(np.argmin(pts[:, 0] + pts[:, 1]))
    pts = np.roll(pts, -start, axis=0)
    # In [TL, TR, BR, BL] order, edge 0 should be the short edge of a portrait card.
    edge0 = np.linalg.norm(pts[1] - pts[0])
    edge1 = np.linalg.norm(pts[2] - pts[1])
    if edge0 > edge1:
        pts = np.roll(pts, -1, axis=0)
    return pts.astype(np.float32)


def rectify_card(image, width=CARD_WIDTH, height=CARD_HEIGHT):
    """Detect and perspective-warp one card; fall back to resizing the full image.

    The card's long axis is normalized to vertical. Its 0/180-degree ambiguity is
    intentionally retained; the classifier checks both corner orientations.
    """
    if image is None or image.size == 0:
        raise ValueError("输入图像为空")
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 35, 120)
    kernel = np.ones((5, 5), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0.0
    image_area = float(h * w)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.03 or area <= best_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        pts = approx.reshape(4, 2).astype(np.float32)
        ordered = _order_quad(pts)
        side_a = (np.linalg.norm(ordered[1] - ordered[0]) + np.linalg.norm(ordered[3] - ordered[2])) / 2
        side_b = (np.linalg.norm(ordered[2] - ordered[1]) + np.linalg.norm(ordered[0] - ordered[3])) / 2
        ratio = max(side_a, side_b) / max(1.0, min(side_a, side_b))
        if 1.25 <= ratio <= 2.05:
            best, best_area = ordered, area
    if best is None:
        # Keep backward compatibility with the original assumption that a single
        # card fills most of the frame. This fallback may distort the background.
        return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA), False
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(best, dst)
    warped = cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_CUBIC)
    return warped, True


def corner_roi(image, corner="tl", x_ratio=0.30, y_ratio=0.24):
    """Crop one normalized rank/suit corner from a canonical portrait card."""
    h, w = image.shape[:2]
    cw = max(1, int(w * x_ratio))
    ch = max(1, int(h * y_ratio))
    if corner == "tl":
        roi = image[0:ch, 0:cw]
    elif corner == "br":
        roi = image[h-ch:h, w-cw:w]
        roi = cv2.rotate(roi, cv2.ROTATE_180)
    else:
        raise ValueError("corner 必须为 'tl' 或 'br'")
    if roi.size == 0:
        raise ValueError("裁剪出的牌角区域为空")
    return roi


def normalize_roi(roi, size=(120, 90)):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(gray)


def make_preview(image, label, score, output_path):
    preview = image.copy()
    text = f"{label} | score={score:.3f}"
    cv2.rectangle(preview, (0, 0), (preview.shape[1], 38), (30, 30, 30), -1)
    cv2.putText(preview, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 255, 255), 2, cv2.LINE_AA)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix or ".jpg"
    ok, encoded = cv2.imencode(suffix, preview)
    if not ok:
        raise ValueError("无法编码输出预览图")
    encoded.tofile(str(output_path))
