from pathlib import Path
import cv2
from .card_labels import is_valid_label, normalize_label
from .image_utils import read_image, rectify_card, corner_roi, normalize_roi

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class TemplateCardClassifier:
    """Template baseline with card rectification, dual-corner rotation handling,
    multiple reference images per identity, and score+margin rejection.

    Scores are normalized-correlation similarities, not probabilities.
    """
    def __init__(self, template_dir, threshold=0.35, margin_threshold=0.02,
                 x_ratio=0.30, y_ratio=0.24):
        self.template_dir = Path(template_dir)
        self.threshold = float(threshold)
        self.margin_threshold = float(margin_threshold)
        self.x_ratio = float(x_ratio)
        self.y_ratio = float(y_ratio)
        self.templates = {}
        self._load_templates()

    def _load_templates(self):
        if not self.template_dir.exists():
            raise FileNotFoundError(f"模板目录不存在：{self.template_dir}")
        for path in sorted(self.template_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            # Supports AS.jpg and AS_brand2.jpg, allowing several references per class.
            label = normalize_label(path.stem.split("_")[0])
            if not is_valid_label(label):
                continue
            image = read_image(path)
            canonical, _ = rectify_card(image)
            # Store BOTH opposite corners.  A template may itself be upside down,
            # so a single TL reference would fail for half of the inputs.
            refs = [
                normalize_roi(corner_roi(canonical, corner, self.x_ratio, self.y_ratio))
                for corner in ("tl", "br")
            ]
            self.templates.setdefault(label, []).append({"name": path.name, "images": refs})
        if not self.templates:
            raise RuntimeError(
                f"在 {self.template_dir} 中没有找到有效模板。"
                "请使用 AS.jpg、10H.png、JOKER.jpg 等文件名。"
            )

    @staticmethod
    def _similarity(a, b):
        result = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
        score = float(result[0, 0])
        if score != score:
            return -1.0
        return score

    def predict(self, image_path):
        image = read_image(image_path)
        canonical, quad_detected = rectify_card(image)
        # Compare both physical corner positions; rectification normalizes the card's
        # long axis, while this handles the remaining 180-degree orientation ambiguity.
        per_label = {}
        for corner in ("tl", "br"):
            query = normalize_roi(corner_roi(canonical, corner, self.x_ratio, self.y_ratio))
            for label, refs in self.templates.items():
                score = max(self._similarity(query, ref_image)
                            for ref in refs for ref_image in ref["images"])
                previous = per_label.get(label)
                if previous is None or score > previous["score"]:
                    per_label[label] = {"label": label, "score": score, "corner": corner}
        candidates = sorted(per_label.values(), key=lambda item: item["score"], reverse=True)
        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        margin = best["score"] - second["score"] if second else None
        accepted = best["score"] >= self.threshold and (margin is None or margin >= self.margin_threshold)
        return {
            "image": str(image_path),
            "label": best["label"] if accepted else "UNKNOWN",
            "best_label": best["label"],
            "score": best["score"],
            "corner": best["corner"],
            "second_label": second["label"] if second else "",
            "second_score": second["score"] if second else None,
            "margin": margin,
            "accepted": accepted,
            "quad_detected": quad_detected,
            "template_count": sum(len(v) for v in self.templates.values()),
            "class_count": len(self.templates),
        }
