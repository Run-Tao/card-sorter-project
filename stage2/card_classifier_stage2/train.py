# -*- coding: utf-8 -*-
"""Train the HOG+SVM and small-CNN baselines on the synthetic split.

Usage
-----
python train.py --model hog
python train.py --model cnn --epochs 15
python train.py --model both

Artifacts
---------
models/hog_svm.joblib
models/cnn.pt
outputs/train_hog.json
outputs/train_cnn.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import cv2
import numpy as np
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.card_labels import LABELS, LABEL_TO_INDEX
from src.features import extract_features
from src.image_utils import normalize_card_color, read_image


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def load_split(splits_path: Path, split: str):
    data = json.loads(splits_path.read_text(encoding="utf-8"))
    items = data["jackfurby"][split]
    # splits.json lives in data/; every path is relative to that directory.
    return [(splits_path.parent / item["path"], item["label"]) for item in items]


def load_cards(items):
    cards, labels = [], []
    for path, label in items:
        cards.append(read_image(path))
        labels.append(label)
    return cards, labels


def train_hog(args, root: Path):
    from joblib import dump

    print("[hog] loading split ...")
    train_items = load_split(root / "data" / "splits.json", "train")
    val_items = load_split(root / "data" / "splits.json", "val")
    train_cards, train_labels = load_cards(train_items)
    val_cards, val_labels = load_cards(val_items)
    print(f"[hog] train={len(train_cards)} val={len(val_cards)} mode={args.hog_mode}")

    t0 = time.time()
    # Rectified cards can have any 90-degree orientation; train on all four and
    # use the same 4-rotation TTA at inference.
    def rotations(img):
        return [img, cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE),
                cv2.rotate(img, cv2.ROTATE_180),
                cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)]

    X_train = np.stack([extract_features(v, mode=args.hog_mode,
                                         image_size=(args.width, args.height),
                                         equalize=args.equalize)
                        for c in train_cards for v in rotations(c)])
    X_val = np.stack([extract_features(v, mode=args.hog_mode,
                                       image_size=(args.width, args.height),
                                       equalize=args.equalize)
                      for c in val_cards for v in rotations(c)])
    print(f"[hog] features: {X_train.shape} in {time.time()-t0:.1f}s")

    y_train = np.array([LABEL_TO_INDEX[l] for l in train_labels for _ in range(4)])
    y_val = np.array([LABEL_TO_INDEX[l] for l in val_labels for _ in range(4)])

    best = None
    for alpha in args.C:
        clf = make_pipeline(
            StandardScaler(),
            SGDClassifier(loss="log_loss", alpha=alpha, max_iter=1500,
                          tol=1e-4, n_jobs=-1, random_state=args.seed,
                          class_weight="balanced"),
        )
        t_fit = time.time()
        clf.fit(X_train, y_train)
        pred = clf.predict(X_val)
        acc = float(accuracy_score(y_val, pred))
        print(f"[hog] alpha={alpha}: val acc={acc:.4f} ({time.time()-t_fit:.1f}s)")
        if best is None or acc > best[0]:
            best = (acc, alpha, clf, pred)
    acc, C, clf, pred = best
    labels_true = [LABELS[i] for i in y_val]
    labels_pred = [LABELS[i] for i in pred]
    report = classification_report(labels_true, labels_pred, labels=LABELS,
                                   zero_division=0, output_dict=True)
    cm = confusion_matrix(labels_true, labels_pred, labels=LABELS).tolist()
    out = {
        "model": "hog_svm",
        "accuracy": acc,
        "best_C": C,
        "feature_mode": args.hog_mode,
        "image_size": [args.width, args.height],
        "equalize": args.equalize,
        "train_size": len(train_cards),
        "val_size": len(val_cards),
        "feature_dim": int(X_train.shape[1]),
        "macro_f1": report["macro avg"]["f1-score"],
        "report": report,
        "confusion_matrix": cm,
        "classes": LABELS,
        "train_seconds": round(time.time() - t0, 2),
    }
    model_dir = root / "models"
    model_dir.mkdir(exist_ok=True)
    bundle = {
        "model": clf,
        "classes": LABELS,
        "mode": args.hog_mode,
        "image_size": [args.width, args.height],
        "equalize": args.equalize,
    }
    dump(bundle, model_dir / "hog_svm.joblib")
    (root / "outputs").mkdir(exist_ok=True)
    (root / "outputs" / "train_hog.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[hog] best C={C} val acc={acc:.4f}; saved models/hog_svm.joblib")
    return out


def augment_card(card: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Light geometric/photometric augmentation implemented with OpenCV only."""
    h, w = card.shape[:2]
    angle = float(rng.uniform(-10, 10))
    scale = float(rng.uniform(0.92, 1.08))
    tx, ty = rng.uniform(-0.04, 0.04, size=2) * (w, h)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    M[0, 2] += tx
    M[1, 2] += ty
    out = cv2.warpAffine(card, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    # Rectification has an unknown 0/90/180/270 orientation; augment with a
    # random quarter-turn so the model sees all four.
    k = int(rng.integers(0, 4))
    for _ in range(k):
        out = cv2.rotate(out, cv2.ROTATE_90_CLOCKWISE)
    if rng.random() < 0.5:
        alpha = float(rng.uniform(0.8, 1.2))
        beta = float(rng.uniform(-20, 20))
        out = cv2.convertScaleAbs(out, alpha=alpha, beta=beta)
    if rng.random() < 0.25:
        out = cv2.GaussianBlur(out, (3, 3), 0)
    if rng.random() < 0.25:
        noise = rng.normal(0, 4, out.shape).astype(np.float32)
        out = np.clip(out.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return out


class CardDataset:
    def __init__(self, cards, labels, image_size, train=False, seed=0):
        self.cards = cards
        self.labels = labels
        self.image_size = image_size
        self.train = train
        self.rng = np.random.default_rng(seed)

    def __len__(self):
        return len(self.cards)

    def __getitem__(self, idx):
        card = self.cards[idx]
        if self.train:
            card = augment_card(card, self.rng)
        rgb = normalize_card_color(card, size=self.image_size)
        x = rgb.astype(np.float32) / 255.0
        x = (x - 0.5) / 0.5
        return np.transpose(x, (2, 0, 1)), LABEL_TO_INDEX[self.labels[idx]]


def train_cnn(args, root: Path):
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader

    from src.model_cnn import build_model, count_parameters

    print("[cnn] loading split ...")
    train_items = load_split(root / "data" / "splits.json", "train")
    val_items = load_split(root / "data" / "splits.json", "val")
    train_cards, train_labels = load_cards(train_items)
    val_cards, val_labels = load_cards(val_items)
    print(f"[cnn] train={len(train_cards)} val={len(val_cards)}")
    image_size = (args.width, args.height)

    train_ds = CardDataset(train_cards, train_labels, image_size, train=True, seed=args.seed)
    val_ds = CardDataset(val_cards, val_labels, image_size, train=False)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              num_workers=0, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            num_workers=0)

    torch.manual_seed(args.seed)
    model = build_model(num_classes=52)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"[cnn] device={device} params={count_parameters(model):,}")
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss()

    best_acc, best_state, history = -1.0, None, []
    for epoch in range(1, args.epochs + 1):
        model.train()
        total, correct, loss_sum = 0, 0, 0.0
        t0 = time.time()
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            out = model(x)
            loss = criterion(out, y)
            loss.backward()
            optimizer.step()
            loss_sum += float(loss.item()) * len(y)
            correct += int((out.argmax(1) == y).sum().item())
            total += len(y)
        scheduler.step()
        model.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                val_correct += int((model(x).argmax(1) == y).sum().item())
                val_total += len(y)
        train_acc = correct / max(total, 1)
        val_acc = val_correct / max(val_total, 1)
        history.append({"epoch": epoch, "train_loss": round(loss_sum / max(total, 1), 4),
                        "train_acc": round(train_acc, 4),
                        "val_acc": round(val_acc, 4),
                        "seconds": round(time.time() - t0, 1)})
        print(f"[cnn] epoch {epoch:02d}: loss={loss_sum/max(total,1):.4f} "
              f"train={train_acc:.4f} val={val_acc:.4f} ({time.time()-t0:.1f}s)")
        if val_acc > best_acc:
            best_acc = val_acc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    ckpt = {
        "state_dict": best_state,
        "labels": LABELS,
        "image_size": list(image_size),
        "mean": 0.5,
        "std": 0.5,
        "val_accuracy": best_acc,
        "seed": args.seed,
        "history": history,
    }
    model_dir = root / "models"
    model_dir.mkdir(exist_ok=True)
    torch.save(ckpt, model_dir / "cnn.pt")
    out = {
        "model": "cnn",
        "val_accuracy": best_acc,
        "image_size": list(image_size),
        "train_size": len(train_cards),
        "val_size": len(val_cards),
        "params": count_parameters(model),
        "history": history,
        "seed": args.seed,
    }
    (root / "outputs").mkdir(exist_ok=True)
    (root / "outputs" / "train_cnn.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[cnn] best val acc={best_acc:.4f}; saved models/cnn.pt")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["hog", "cnn", "both"], default="both")
    ap.add_argument("--data-root", default=".", help="project root containing data/")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--width", type=int, default=64)
    ap.add_argument("--height", type=int, default=96)
    ap.add_argument("--hog-mode", choices=["full", "corner"], default="full")
    ap.add_argument("--equalize", action="store_true")
    ap.add_argument("--C", type=float, nargs="+", default=[1e-2, 1e-3, 1e-4],
                    help="SGD alpha values (smaller = less regularisation)")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    root = Path(args.data_root).resolve()
    set_seed(args.seed)
    if args.model in ("hog", "both"):
        train_hog(args, root)
    if args.model in ("cnn", "both"):
        train_cnn(args, root)


if __name__ == "__main__":
    main()
