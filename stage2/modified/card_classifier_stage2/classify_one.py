import argparse
from pathlib import Path
from src.classifier import TemplateCardClassifier
from src.image_utils import read_image, make_preview


def main():
    parser = argparse.ArgumentParser(description="单张扑克牌识别：透视校正、双角标模板匹配与拒识")
    parser.add_argument("--image", required=True, help="待识别的单张牌图片")
    parser.add_argument("--templates", default="data/templates", help="模板目录")
    parser.add_argument("--threshold", type=float, default=0.35, help="最低相似度阈值，需在验证集校准")
    parser.add_argument("--margin-threshold", type=float, default=0.02, help="前两类分数最小差值，需在验证集校准")
    parser.add_argument("--output", default="outputs/prediction.jpg", help="预览图输出路径")
    args = parser.parse_args()
    classifier = TemplateCardClassifier(args.templates, threshold=args.threshold,
                                        margin_threshold=args.margin_threshold)
    result = classifier.predict(args.image)
    print(f"输出标签：{result['label']}")
    print(f"最佳候选：{result['best_label']}")
    print(f"相似度分数：{result['score']:.4f}")
    print(f"使用牌角：{result['corner']}")
    if result["second_score"] is None:
        print(f"次优候选：{result['second_label'] or '无'}（仅一个候选）")
        print("前两类分差：无（至少需要两个类别）")
    else:
        print(f"次优候选：{result['second_label']} ({result['second_score']:.4f})")
        print(f"前两类分差：{result['margin']:.4f}")
    print(f"四边形检测：{'成功' if result['quad_detected'] else '失败，使用整图缩放回退'}")
    print("提示：分数不是概率；相似度和分差阈值都必须用独立验证集校准。")
    image = read_image(args.image)
    make_preview(image, result["label"], result["score"], Path(args.output))
    print(f"预览图已保存：{Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
