from pathlib import Path
import csv
from .classifier import TemplateCardClassifier, IMAGE_EXTS
from .card_labels import normalize_label
from .image_utils import read_image, make_preview


def label_from_filename(path):
    # Examples: AS_test_01.jpg, JOKER_brandA_02.png
    return normalize_label(Path(path).stem.split("_")[0])


def evaluate_folder(images_dir, templates_dir, output_dir="outputs", threshold=0.35,
                    margin_threshold=0.02):
    images_dir = Path(images_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    classifier = TemplateCardClassifier(templates_dir, threshold=threshold,
                                        margin_threshold=margin_threshold)
    paths = sorted(p for p in images_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    if not paths:
        raise RuntimeError(f"测试目录中没有图片：{images_dir}")
    rows = []
    correct = accepted = accepted_correct = 0
    for path in paths:
        result = classifier.predict(path)
        truth = label_from_filename(path)
        ok = result["label"] == truth
        is_accepted = result["label"] != "UNKNOWN"
        correct += int(ok)
        accepted += int(is_accepted)
        accepted_correct += int(ok and is_accepted)
        result["truth"] = truth
        result["correct"] = ok
        rows.append(result)
        try:
            image = read_image(path)
            make_preview(image, result["label"], result["score"],
                         output_dir / f"{path.stem}_prediction.jpg")
        except Exception as exc:
            print(f"[WARN] 无法生成预览 {path.name}: {exc}")
    csv_path = output_dir / "evaluation.csv"
    fieldnames = ["image", "truth", "label", "correct", "accepted", "best_label", "score",
                  "corner", "second_label", "second_score", "margin", "quad_detected",
                  "template_count", "class_count"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    total = len(rows)
    accuracy = correct / total
    coverage = accepted / total
    accepted_accuracy = accepted_correct / accepted if accepted else 0.0
    quad_success = sum(bool(r["quad_detected"]) for r in rows) / total
    print(f"测试图片数：{total}")
    print(f"整体准确率（UNKNOWN 按错误计）：{accuracy:.2%}")
    print(f"接受覆盖率：{coverage:.2%}")
    print(f"已接受样本准确率：{accepted_accuracy:.2%}")
    print(f"四边形检测成功率：{quad_success:.2%}")
    print(f"CSV 报告：{csv_path.resolve()}")
    print("注意：相似度不是概率；测试图片必须与所有参考模板独立。")
    return {"accuracy": accuracy, "coverage": coverage,
            "accepted_accuracy": accepted_accuracy, "quad_success": quad_success}
