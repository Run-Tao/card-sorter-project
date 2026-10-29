# -*- coding: utf-8 -*-
"""Classify one card image with any of the three baselines."""

import argparse
from pathlib import Path

from src.classifier import create_classifier
from src.image_utils import read_image, make_preview


def build(args):
    if args.model == "template":
        return create_classifier("template", template_dir=args.templates,
                                 threshold=args.threshold)
    if args.model == "hog":
        return create_classifier("hog", model_path=args.model_path,
                                 threshold=args.threshold)
    if args.model == "cnn":
        return create_classifier("cnn", model_path=args.model_path,
                                 threshold=args.threshold)
    raise ValueError(args.model)


def main():
    ap = argparse.ArgumentParser(description="Single-card 52-class prediction")
    ap.add_argument("--image", required=True)
    ap.add_argument("--model", choices=["template", "hog", "cnn"], default="template")
    ap.add_argument("--templates", default="data/templates")
    ap.add_argument("--model-path", default=None,
                    help="models/hog_svm.joblib or models/cnn.pt")
    ap.add_argument("--threshold", type=float, default=None,
                    help="optional rejection threshold; None = always predict")
    ap.add_argument("--output", default="outputs/prediction.jpg")
    args = ap.parse_args()

    if args.model in ("hog", "cnn") and not args.model_path:
        args.model_path = ("models/hog_svm.joblib" if args.model == "hog"
                           else "models/cnn.pt")
    classifier = build(args)
    result = classifier.predict(args.image)
    print(f"model      : {result['classifier']}")
    print(f"prediction : {result['label']}")
    print(f"best       : {result['best_label']}  score={result['score']:.4f}")
    print(f"runner-up  : {result['second_label']}  score={result['second_score']:.4f}")
    print(f"margin     : {result['margin']:.4f}")
    print(f"corner     : {result['corner'] or '-'}  detected={result['detected']}")
    print("top-5      : " + ", ".join(f"{k}:{v:.3f}" for k, v in result["top5"]))
    print("NOTE: score is a similarity/softmax value, not a calibrated probability.")

    image = read_image(args.image)
    make_preview(image, result["label"], result["score"], Path(args.output),
                 quad=result.get("quad"))
    print(f"preview    : {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
