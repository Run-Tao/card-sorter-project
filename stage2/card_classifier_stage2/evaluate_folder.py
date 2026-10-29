# -*- coding: utf-8 -*-
"""Evaluate a classifier over a folder tree (class subfolders or prefixed files)."""

import argparse
from pathlib import Path

from src.classifier import create_classifier
from src.evaluate import evaluate_folder


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
    ap = argparse.ArgumentParser(description="Batch evaluation for 52-class card recognition")
    ap.add_argument("--images", default="data/processed/jackfurby/test")
    ap.add_argument("--model", choices=["template", "hog", "cnn"], default="template")
    ap.add_argument("--templates", default="data/templates")
    ap.add_argument("--model-path", default=None,
                    help="models/hog_svm.joblib or models/cnn.pt")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--output", default="outputs/eval_template")
    ap.add_argument("--split-name", default=None)
    ap.add_argument("--save-previews", type=int, default=0)
    args = ap.parse_args()

    if args.model in ("hog", "cnn") and not args.model_path:
        args.model_path = ("models/hog_svm.joblib" if args.model == "hog"
                           else "models/cnn.pt")
    split_name = args.split_name or Path(args.images).name
    classifier = build(args)
    evaluate_folder(args.images, classifier, args.output, split_name,
                    save_previews=args.save_previews)


if __name__ == "__main__":
    main()
