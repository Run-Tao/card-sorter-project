import argparse
from src.evaluate import evaluate_folder


def main():
    parser = argparse.ArgumentParser(description="评估扑克牌识别基线")
    parser.add_argument("--images", default="data/test", help="测试图片目录")
    parser.add_argument("--templates", default="data/templates", help="参考模板目录")
    parser.add_argument("--output", default="outputs", help="报告输出目录")
    parser.add_argument("--threshold", type=float, default=0.35, help="最低相似度阈值")
    parser.add_argument("--margin-threshold", type=float, default=0.02, help="前两类分数最小差值")
    args = parser.parse_args()
    evaluate_folder(args.images, args.templates, args.output,
                    args.threshold, args.margin_threshold)


if __name__ == "__main__":
    main()
