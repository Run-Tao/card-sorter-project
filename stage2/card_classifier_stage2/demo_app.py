# -*- coding: utf-8 -*-
"""Poker card recognition & sorting demo system (Flask backend).

Run:
    python demo_app.py
Open:
    http://127.0.0.1:7860

The backend performs real OpenCV preprocessing and real classifier inference.
Mechanical sorting is NOT connected; the UI labels it as a simulated/interface
stage.  Joker is a batch label only (no Joker training images exist), so Joker
entries in demo batches are explicitly marked as simulated, never as model
predictions.
"""

from __future__ import annotations

import base64
import csv
import json
import random
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
from flask import (Flask, abort, jsonify, render_template, request, send_file,
                   send_from_directory)

from src.card_labels import (INDEX_TO_LABEL, JOKER_LABEL, LABELS,
                             is_valid_label, normalize_batch_label)
from src.classifier import create_classifier
from src.controller import SortingController
from src.deck_manager import DeckManager
from src.two_deck_manager import TwoDeckSorter
from src.image_utils import (CANONICAL_SIZE, corner_roi, detect_card_quad,
                             image_quality, read_image, rectify_card)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
SIM_DIR = OUTPUTS / "simulated"
EXPORT_DIR = OUTPUTS / "exports"
UPLOAD_DIR = OUTPUTS / "uploads"

app = Flask(__name__, template_folder="demo/templates", static_folder="demo/static")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
_lock = threading.RLock()
_models: Dict[str, object] = {}
BATCH: Optional[dict] = None
CAMERA = {"cap": None, "error": ""}
SORTER = SortingController(simulated=True)
TEMPLATE_DIR = DATA / "templates"
_CORNER_READER = None
_CUSTOM_MATCHER = None
_SUIT_READER = None
_CARD_READER = None


def _custom_matcher():
    global _CUSTOM_MATCHER
    if _CUSTOM_MATCHER is None:
        from src.custom_templates import CustomTemplateMatcher
        _CUSTOM_MATCHER = CustomTemplateMatcher(ROOT / "data" / "templates_user")
    return _CUSTOM_MATCHER


def _suit_reader():
    global _SUIT_READER
    if _SUIT_READER is None:
        from src.suit_reader import SuitReader
        _SUIT_READER = SuitReader()
    return _SUIT_READER


def _card_reader():
    global _CARD_READER
    if _CARD_READER is None:
        from src.card_reader import CardReader
        _CARD_READER = CardReader()
    return _CARD_READER


def _card_record(image: np.ndarray) -> Dict:
    t0 = time.perf_counter()
    r = _card_reader().predict(image)
    forced = _custom_matcher().predict(image)
    if forced is not None:
        label = forced["best_label"]
        r.update({"label": label, "best_label": label,
                  "rank": label[:-1], "suit": label[-1],
                  "suit_name": {"S": "黑桃", "H": "红心", "D": "方块", "C": "梅花"}.get(label[-1], ""),
                  "accepted": True, "score": max(float(r.get("score", 0)), float(forced["score"])),
                  "method": "user_template_card"})
    card = r.get("rectified")
    if card is None:
        card = image
    overlay = image.copy()
    if r.get("quad"):
        pts = np.asarray(r["quad"], np.int32).reshape(-1, 1, 2)
        cv2.polylines(overlay, [pts], True, (0, 220, 170), 4)
    tl = corner_roi(card, "tl")
    br = corner_roi(card, "br", rotate_180=True)
    return {
        "time": datetime.now().strftime("%H:%M:%S"),
        "model": "card", "model_name": "数字 + 花色",
        "source": "upload", "truth": None,
        "label": r.get("label", "UNKNOWN"), "best_label": r.get("best_label", ""),
        "rank": r.get("rank", ""), "suit": r.get("suit", ""),
        "suit_name": r.get("suit_name", ""),
        "score": float(r.get("score", 0.0)), "score_kind": "双头融合",
        "accepted": bool(r.get("accepted")),
        "reason": ("双头识别：" + (r.get("label") or "")) if r.get("accepted") else "rank/suit 置信度不足",
        "correct": None, "top5": r.get("top5", []), "corner": "corner",
        "detected": bool(r.get("localized")),
        "detection_method": r.get("localization", ""),
        "manual_crop": False,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "quality": image_quality(image),
        "sort_bin": {"S": "BIN_SPADE", "H": "BIN_HEART",
                     "D": "BIN_DIAMOND", "C": "BIN_CLUB"}.get(r.get("suit", ""), "REVIEW"),
        "sort_bin_label": r.get("suit_name", "复核"),
        "sort_simulated": True, "sort_note": "数字+花色演示",
        "slot": "REVIEW",
        "input_image": _b64(overlay, max_width=760),
        "rectified_image": _b64(card, max_width=420),
        "tl_roi": _b64(tl, max_width=220),
        "br_roi": _b64(br, max_width=220),
        "thumb": _b64(card, max_width=90, quality=72),
    }


def _suit_record(image: np.ndarray) -> Dict:
    t0 = time.perf_counter()
    r = _suit_reader().predict(image)
    forced = _custom_matcher().predict(image)
    if forced is not None:
        r["suit"] = forced["best_label"][-1]
        r["suit_name"] = {"S": "黑桃", "H": "红心", "D": "方块", "C": "梅花"}.get(r["suit"], "")
        r["score"] = max(float(r.get("score", 0)), float(forced["score"]))
        r["label"] = r["best_label"] = r["suit"]
        r["accepted"] = True
        r["method"] = "user_template_suit"
    card = r.get("rectified")
    info = {"detected": r.get("localized"), "method": r.get("localization"),
            "quad": r.get("quad")}
    if card is None:
        card = image
    overlay = image.copy()
    if r.get("quad"):
        pts = np.asarray(r["quad"], np.int32).reshape(-1, 1, 2)
        cv2.polylines(overlay, [pts], True, (0, 220, 170), 4)
    tl = corner_roi(card, "tl")
    br = corner_roi(card, "br", rotate_180=True)
    return {
        "time": datetime.now().strftime("%H:%M:%S"),
        "model": "suit", "model_name": "仅花色（4 类）",
        "source": "upload", "truth": None,
        "label": r["suit"] if r.get("accepted") else "UNKNOWN",
        "best_label": r.get("suit", ""), "suit": r.get("suit", ""),
        "suit_name": r.get("suit_name", ""),
        "score": float(r.get("score", 0.0)), "score_kind": "花色置信度",
        "accepted": bool(r.get("accepted")),
        "reason": ("花色模式：" + r.get("suit_name", "")) if r.get("accepted") else "花色识别失败",
        "correct": None, "top5": r.get("top5", []), "corner": "corner",
        "detected": bool(r.get("localized")),
        "detection_method": r.get("localization", ""),
        "manual_crop": False,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        "quality": image_quality(image),
        "sort_bin": {"S": "BIN_SPADE", "H": "BIN_HEART",
                     "D": "BIN_DIAMOND", "C": "BIN_CLUB"}.get(r.get("suit", ""), "REVIEW"),
        "sort_bin_label": r.get("suit_name", "复核"),
        "sort_simulated": True, "sort_note": "仅花色演示",
        "slot": "REVIEW",
        "input_image": _b64(overlay, max_width=760),
        "rectified_image": _b64(card, max_width=420),
        "tl_roi": _b64(tl, max_width=220),
        "br_roi": _b64(br, max_width=220),
        "thumb": _b64(card, max_width=90, quality=72),
    }


def _corner_reader():
    global _CORNER_READER
    if _CORNER_READER is None:
        from src.corner_semantic import CornerSemanticReader
        _CORNER_READER = CornerSemanticReader(threshold=0.40)
    return _CORNER_READER

MODEL_INFO = {
    "card": {"name": "数字 + 花色", "kind": "定位 + rank 头 + suit 头", "score": "双头置信度"},
    "suit": {"name": "仅花色（4 类）", "kind": "定位 + 花色符号", "score": "花色置信度"},
    "ensemble": {"name": "决策树集成", "kind": "模板 + HOG + CNN + 决策树", "score": "meta probability"},
    "template": {"name": "模板匹配", "kind": "模板 NCC", "score": "相似度"},
    "hog_svm": {"name": "HOG + SVM", "kind": "传统特征 + 线性分类", "score": "softmax"},
    "cnn": {"name": "小型 CNN", "kind": "3 通道卷积网络", "score": "softmax"},
}
DEFAULT_THRESHOLD = {"card": 0.40, "suit": 0.45, "ensemble": 0.50, "template": 0.628, "hog_svm": 0.995, "cnn": 0.270}

CONFIGS = {
    "single54": {"label": "单副标准牌（52 + 2 Joker = 54）",
                 "num_decks": 1, "jokers_per_deck": 2},
    "two104": {"label": "两副无王（104 张）",
               "num_decks": 2, "jokers_per_deck": 0},
    "two108": {"label": "两副标准牌（104 + 4 Joker = 108）",
               "num_decks": 2, "jokers_per_deck": 2},
}


# ------------------------------------------------------------------ utilities
def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _b64(image: np.ndarray, max_width: int = 900, quality: int = 90) -> str:
    if image is None or image.size == 0:
        return ""
    h, w = image.shape[:2]
    if max_width and w > max_width:
        image = cv2.resize(image, (max_width, int(h * max_width / w)),
                           interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _decode_upload(file_storage) -> Optional[np.ndarray]:
    raw = np.frombuffer(file_storage.read(), dtype=np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        bgr = img[:, :, :3].astype(np.float32)
        img = (bgr * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    return img


def _classifier(model: str):
    key = {"template": "template", "hog": "hog_svm", "hog_svm": "hog_svm",
           "cnn": "cnn", "ensemble": "ensemble"}[model]
    with _lock:
        if key not in _models:
            if key == "template":
                _models[key] = create_classifier(
                    "template", template_dir=DATA / "templates", threshold=None)
            elif key == "hog_svm":
                _models[key] = create_classifier(
                    "hog", model_path=ROOT / "models" / "hog_svm.joblib", threshold=None)
            elif key == "ensemble":
                _models[key] = create_classifier(
                    "ensemble", model_dir=ROOT / "models", threshold=None)
            else:
                _models[key] = create_classifier(
                    "cnn", model_path=ROOT / "models" / "cnn.pt", threshold=None)
        return _models[key]


def _warmup():
    for model in ("template", "hog_svm", "cnn", "ensemble"):
        try:
            t0 = time.perf_counter()
            _classifier(model)
            print(f"[warmup] {model} ready in {time.perf_counter()-t0:.2f}s", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[warmup] {model} failed: {exc}", flush=True)


def _joker_placeholder(index: int = 1) -> np.ndarray:
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    path = SIM_DIR / f"joker_sim_{index}.png"
    if path.exists():
        return read_image(path)
    img = np.full((588, 420, 3), 245, np.uint8)
    cv2.rectangle(img, (8, 8), (411, 579), (30, 30, 30), 3)
    cv2.putText(img, "JOKER", (72, 250), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (20, 20, 190), 4)
    cv2.putText(img, "SIMULATED", (100, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (40, 40, 40), 2)
    cv2.putText(img, "NOT A MODEL PREDICTION", (58, 350),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1)
    cv2.putText(img, f"#{index}", (188, 500), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2)
    cv2.imwrite(str(path), img)
    return img


def _blank_image() -> np.ndarray:
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    path = SIM_DIR / "blank_failure.png"
    img = np.full((420, 300, 3), 35, np.uint8)
    cv2.putText(img, "BLANK / FAILURE", (22, 210), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (190, 190, 190), 2)
    cv2.imwrite(str(path), img)
    return img


# ---------------------------------------------------------------- inference
def _predict_record(image: np.ndarray, model: str, threshold: float,
                    reject: bool, truth: Optional[str], source: str,
                    ood_check: bool = True,
                    image_path: Optional[str] = None,
                    crop: Optional[list] = None,
                    corner_fallback: bool = True) -> Dict:
    manual_crop = False
    if crop:
        try:
            x1, y1, x2, y2 = [float(v) for v in crop]
            h, w = image.shape[:2]
            x1, x2 = sorted((max(0.0, min(1.0, x1)), max(0.0, min(1.0, x2))))
            y1, y2 = sorted((max(0.0, min(1.0, y1)), max(0.0, min(1.0, y2))))
            if x2 - x1 >= 0.03 and y2 - y1 >= 0.03:
                image = image[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)].copy()
                manual_crop = True
        except (TypeError, ValueError):
            manual_crop = False
    t0 = time.perf_counter()
    clf = _classifier(model)
    quality = image_quality(image)
    result = clf.predict(image)

    # Design / OOD check: the template bank is the only reference for the
    # "does this look like the training card design?" question.  It is also the
    # custom-enrollment path for unseen designs.
    tpl = _classifier("template")
    tpl_result = tpl.predict(image)
    tpl_score = float(tpl_result["score"])
    tpl_label = tpl_result["best_label"]
    custom_labels = getattr(tpl, "custom_labels", set())
    custom_match = tpl_label in custom_labels and tpl_score >= 0.55
    ood = bool(ood_check and not custom_match and tpl_score < 0.55)

    if custom_match:
        result = tpl_result
        model_name = "模板（自定义登记）"
        model_used = "template_custom"
        score = tpl_score
        accepted = True
        label = tpl_label
        reason = "匹配已登记的新牌面模板"
    else:
        score = float(result["score"])
        accepted = (not reject) or score >= threshold
        label = result["best_label"] if accepted else "UNKNOWN"
        model_name = MODEL_INFO[model]["name"]
        model_used = model
        reason = "accepted" if accepted else f"score {score:.4f} < threshold {threshold:.4f}"
        if ood:
            accepted = False
            label = "UNKNOWN"
            reason = (f"未见过的牌面设计：模板相似度 {tpl_score:.3f} < 0.55；"
                      "建议登记新模板或人工确认，不能强行按 52 类输出")
            # Cross-design fallback: OCR only the rank, then use the 52-class
            # model's suit cue (HOG is the most reliable suit cue here).
            try:
                if not corner_fallback:
                    raise RuntimeError("corner fallback disabled for batch")
                sem = _corner_reader().predict(image)
                rank = str(sem.get("rank") or "").strip().upper()
                if rank in {"A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"}:
                    hog_hint = result if model == "hog_svm" else _classifier("hog_svm").predict(image)
                    hint = str(hog_hint.get("best_label") or "")
                    sem_suit = str(sem.get("suit") or "").upper()
                    suit = sem_suit if sem_suit in {"S", "H", "D", "C"} else (
                        hint[-1] if hint and hint[-1] in {"S", "H", "D", "C"} else "")
                    candidate = rank + suit
                    if suit and is_valid_label(candidate):
                        result = dict(result)
                        result["best_label"] = candidate
                        result["score"] = float(sem.get("score", 0.0))
                        result["top5"] = [[candidate, float(sem.get("score", 0.0))]]
                        result["corner"] = "semantic"
                        accepted = True
                        ood = False
                        label = candidate
                        model_name = "角标语义（OCR + 整牌花色）"
                        model_used = "corner_semantic"
                        reason = f"角标语义：{rank} + 花色 {suit}（跨设计兜底）"
            except Exception as exc:  # noqa: BLE001
                print(f"[semantic] fallback failed: {exc}", flush=True)
    # Explicitly registered user samples take precedence over all models.
    forced = _custom_matcher().predict(image)
    if forced is not None:
        result = forced
        score = float(forced["score"])
        accepted = True
        label = forced["best_label"]
        model_name = "用户样张（已登记）"
        model_used = "user_template"
        ood = False
        reason = "匹配已登记的用户样张模板"
    latency = (time.perf_counter() - t0) * 1000
    rectified, info = rectify_card(image)
    if image.shape[1] == CANONICAL_SIZE[0] and image.shape[0] == CANONICAL_SIZE[1]:
        rectified = image
        info = {"detected": True, "method": "already_canonical", "quad": None}
    quad = info.get("quad") or (detect_card_quad(image).tolist()
                                if info.get("detected") and image.shape[1] != CANONICAL_SIZE[0]
                                else None)
    overlay = image.copy()
    if quad:
        pts = np.asarray(quad, np.int32).reshape(-1, 1, 2)
        cv2.polylines(overlay, [pts], True, (0, 220, 170), 4)
    tl = corner_roi(rectified, "tl")
    br = corner_roi(rectified, "br", rotate_180=True)
    cmd = SORTER.command(label if accepted else "UNKNOWN")
    return {
        "time": datetime.now().strftime("%H:%M:%S"),
        "model": model_used,
        "model_name": model_name,
        "source": source,
        "truth": truth,
        "image_path": image_path,
        "label": label,
        "best_label": result["best_label"] if not ood else "UNKNOWN",
        "score": score,
        "score_kind": MODEL_INFO.get(model, MODEL_INFO["template"])["score"],
        "accepted": accepted,
        "reason": reason,
        "correct": None if truth is None else (label == truth),
        "top5": result.get("top5", []),
        "corner": result.get("corner", ""),
        "detected": bool(info.get("detected")),
        "detection_method": info.get("method", ""),
        "manual_crop": manual_crop,
        "latency_ms": round(latency, 1),
        "quality": quality,
        "design_similarity": tpl_score,
        "design_label": tpl_label,
        "ood": ood,
        "custom_match": custom_match,
        "sort_bin": cmd.bin,
        "sort_bin_label": cmd.bin_label,
        "sort_simulated": cmd.simulated,
        "sort_note": cmd.note,
        "input_image": _b64(overlay, max_width=760),
        "rectified_image": _b64(rectified, max_width=420),
        "tl_roi": _b64(tl, max_width=220),
        "br_roi": _b64(br, max_width=220),
        "thumb": _b64(rectified, max_width=90, quality=72),
    }


def _record_public(rec: Dict) -> Dict:
    return {k: v for k, v in rec.items()
            if k not in {"input_image", "rectified_image", "tl_roi", "br_roi"}}


def _state() -> Dict:
    if BATCH is None:
        return {"active": False, "paused": False, "stopped": False,
                "config": None, "deck": None, "records": [], "current": None,
                "queue_len": 0, "index": 0}
    deck = BATCH["deck"].snapshot()
    return {
        "active": BATCH["active"],
        "paused": BATCH["paused"],
        "stopped": BATCH["stopped"],
        "config": BATCH["config"],
        "deck": deck,
        "records": [_record_public(r) for r in BATCH["records"][-40:]],
        "record_indices": [i for i in range(max(0, len(BATCH["records"]) - 40),
                                             len(BATCH["records"]))],
        "current": BATCH.get("current"),
        "queue_len": len(BATCH["queue"]),
        "index": BATCH["index"],
        "started_at": BATCH.get("started_at"),
        "elapsed_s": round(time.time() - BATCH.get("started_ts", time.time()), 1)
        if BATCH.get("started_ts") else 0,
    }


# ------------------------------------------------------------- batch queue
def _image_files(label: str, source: str):
    if source == "real":
        base = DATA / "processed" / "real52" / "all" / label
    else:
        base = DATA / "processed" / "jackfurby" / "test" / label
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir()
                  if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"})


def _build_queue(config: dict, source: str) -> list:
    if source not in {"synthetic", "real"}:
        raise ValueError("source must be synthetic or real")
    n = config["num_decks"]
    queue = []
    for label in LABELS:
        files = _image_files(label, source)[:n]
        if len(files) < n:
            raise RuntimeError(
                f"source {source} has only {len(files)} image(s) for {label}, need {n}")
        for f in files:
            queue.append({"path": str(f), "truth": label, "kind": "card", "source": source})
    for i in range(config["num_decks"] * config["jokers_per_deck"]):
        queue.append({"kind": "joker_sim", "truth": JOKER_LABEL, "index": i + 1,
                      "source": "simulated Joker"})
    random.Random(42).shuffle(queue)
    return queue


def _new_batch(config_name: str, model: str, source: str, reject: bool,
               threshold: float, queue: list, ood_check: bool = True) -> dict:
    cfg = dict(CONFIGS[config_name])
    cfg.update({"name": config_name, "model": model, "source": source,
                "reject": bool(reject), "threshold": float(threshold),
                "ood_check": bool(ood_check)})
    return {
        "config": cfg,
        "deck": TwoDeckSorter(cfg["num_decks"], cfg["jokers_per_deck"]),
        "queue": queue,
        "index": 0,
        "records": [],
        "current": None,
        "active": True,
        "paused": False,
        "stopped": False,
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "started_ts": time.time(),
    }


def _process_item(item: dict, cfg: dict) -> Dict:
    global BATCH
    assert BATCH is not None
    truth = item.get("truth")
    kind = item.get("kind", "card")
    if kind == "joker_sim":
        img = _joker_placeholder(item.get("index", 1))
        rec = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "model": "manual", "model_name": "人工 / 模拟",
            "source": "simulated Joker", "truth": JOKER_LABEL,
            "label": JOKER_LABEL, "best_label": JOKER_LABEL,
            "score": None, "score_kind": "无模型推理",
            "accepted": True, "reason": "模拟 Joker，明确未经过视觉模型",
            "correct": True, "top5": [], "corner": "",
            "detected": False, "detection_method": "simulated",
            "latency_ms": 0.0,
            "sort_bin": "REVIEW", "sort_bin_label": "复核槽",
            "sort_simulated": True, "sort_note": "Joker 需人工复核",
            "slot": "REVIEW",
            "input_image": _b64(img, max_width=760),
            "rectified_image": _b64(img, max_width=420),
            "tl_roi": "", "br_roi": "",
            "thumb": _b64(img, max_width=90, quality=72),
        }
        add = BATCH["deck"].add(JOKER_LABEL, {"reason": "simulated"})
    elif kind == "blank":
        img = _blank_image()
        add = BATCH["deck"].add("UNKNOWN", {"reason": "空白/预处理失败演示"})
        rec = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "model": "none", "model_name": "失败演示",
            "source": "simulated failure", "truth": None,
            "label": "UNKNOWN", "best_label": "UNKNOWN",
            "score": None, "score_kind": "—", "accepted": False,
            "reason": "空白图像 / 定位失败演示", "correct": None,
            "top5": [], "corner": "", "detected": False,
            "detection_method": "blank", "latency_ms": 0.0,
            "sort_bin": "REVIEW", "sort_bin_label": "复核槽",
            "sort_simulated": True, "sort_note": "失败图进入复核",
            "slot": "REVIEW",
            "input_image": _b64(img, max_width=760),
            "rectified_image": _b64(img, max_width=420),
            "tl_roi": "", "br_roi": "",
            "thumb": _b64(img, max_width=90, quality=72),
        }
    else:
        img = read_image(item["path"])
        if cfg.get("model") == "card":
            rec = _card_record(img)
            rec["truth"] = truth
            rec["source"] = item.get("source", "")
            if truth:
                rec["correct"] = rec["label"] == truth
            add = BATCH["deck"].add(rec["label"], {"reason": rec["reason"]})
        else:
            rec = _predict_record(img, cfg["model"], cfg["threshold"],
                                  cfg["reject"], truth, item.get("source", ""),
                                  ood_check=cfg.get("ood_check", True),
                                  image_path=item.get("path"),
                                  corner_fallback=False)
            add = BATCH["deck"].add(rec["label"], {"reason": rec["reason"]})
        if add["status"] == "DUPLICATE":
            rec["accepted"] = False
            rec["reason"] = f"重复牌：超出该批次允许数量（{add['label']}）"
        elif add["status"] in {"REJECTED", "INVALID_LABEL"}:
            rec["accepted"] = False
            rec["reason"] = rec["reason"] or "rejected"
    rec["batch_status"] = add["status"]
    rec["slot"] = add.get("slot", "REVIEW")
    return rec


# ------------------------------------------------------------------- routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/meta")
def api_meta():
    comparison = _read_json(OUTPUTS / "comparison" / "comparison.json", {"rows": []})
    calibration = _read_json(OUTPUTS / "calibration" / "thresholds.json", {})
    dataset = _read_json(DATA / "dataset_report.json", {})
    integrity = _read_json(DATA / "integrity_report.json", {})
    metrics = {m: {s: _read_json(OUTPUTS / "eval" / m / f"metrics_{s}.json", {})
                   for s in ("jackfurby_test", "real52_test")}
               for m in ("template", "hog_svm", "cnn")}
    samples = []
    for source, folder in (("synthetic", DATA / "processed" / "jackfurby" / "test"),
                           ("real", DATA / "processed" / "real52" / "all")):
        if not folder.exists():
            continue
        for i, label in enumerate(LABELS):
            if i % 3:
                continue
            files = _image_files(label, source)[:1]
            if not files:
                continue
            samples.append({"id": f"{source}:{label}:{files[0].name}",
                            "source": source, "label": label,
                            "file": files[0].name,
                            "thumb": _b64(read_image(files[0]), max_width=100, quality=78)})
    return jsonify({
        "models": MODEL_INFO,
        "default_threshold": DEFAULT_THRESHOLD,
        "configs": CONFIGS,
        "labels": LABELS,
        "samples": samples,
        "metrics": {"comparison": comparison, "calibration": calibration,
                    "dataset": dataset, "integrity": integrity,
                    "metrics": metrics,
                    "ensemble_eval": _read_json(OUTPUTS / "ensemble_eval.json", {})},
        "camera_available": False,
        "ood_threshold": 0.55,
        "limitations": [
            "分类器为 52 类普通牌；没有 Joker 训练数据，Joker 仅作为批次标签。",
            "演示批次中的 Joker 为明确标注的模拟事件，不是视觉识别结果。",
            "真实照片仅来自一套实体牌设计；跨品牌泛化未验证。",
            "机械分拣/ESP32 未接入；界面只展示控制接口与模拟状态。",
        ],
    })


@app.route("/api/card", methods=["POST"])
def api_card():
    payload = request.get_json(silent=True) or {}
    file = request.files.get("image")
    if file is not None:
        img = _decode_upload(file)
    elif payload.get("image_path"):
        img = read_image(payload["image_path"])
    else:
        sample = payload.get("sample") or {}
        source, label, filename = sample.get("source"), sample.get("label", ""), sample.get("file", "")
        if source == "synthetic":
            img = read_image(DATA / "processed" / "jackfurby" / "test" / label / filename)
        elif source == "real":
            img = read_image(DATA / "processed" / "real52" / "all" / label / filename)
        else:
            return jsonify({"error": "image or sample required"}), 400
    if img is None:
        return jsonify({"error": "cannot decode image"}), 400
    return jsonify(_card_record(img))


@app.route("/api/suit", methods=["POST"])
def api_suit():
    payload = request.get_json(silent=True) or {}
    file = request.files.get("image")
    if file is not None:
        img = _decode_upload(file)
    elif payload.get("image_path"):
        img = read_image(payload["image_path"])
    else:
        sample = payload.get("sample") or {}
        source, label, filename = sample.get("source"), sample.get("label", ""), sample.get("file", "")
        if source == "synthetic":
            img = read_image(DATA / "processed" / "jackfurby" / "test" / label / filename)
        elif source == "real":
            img = read_image(DATA / "processed" / "real52" / "all" / label / filename)
        else:
            return jsonify({"error": "image or sample required"}), 400
    if img is None:
        return jsonify({"error": "cannot decode image"}), 400
    return jsonify(_suit_record(img))


@app.route("/api/predict", methods=["POST"])
def api_predict():
    payload = request.get_json(silent=True) or {}
    model = request.form.get("model") or payload.get("model") or "hog_svm"
    if model not in MODEL_INFO:
        return jsonify({"error": "unknown model"}), 400
    if request.is_json:
        reject = bool(payload.get("reject", True))
    else:
        reject = str(request.form.get("reject", "1")).lower() in {"1", "true", "yes"}
    raw_threshold = request.form.get("threshold") if not request.is_json else payload.get("threshold")
    try:
        threshold = float(raw_threshold) if raw_threshold is not None else DEFAULT_THRESHOLD[model]
    except (TypeError, ValueError):
        threshold = DEFAULT_THRESHOLD[model]
    file = request.files.get("image")
    if file is None and payload.get("image_path"):
        path = Path(payload["image_path"])
        if not path.exists():
            return jsonify({"error": "image_path not found"}), 404
        img = read_image(path)
        truth, source_name = None, "upload"
        image_path = str(path)
    elif file is None:
        sample = payload.get("sample") or {}
        source = sample.get("source")
        label = sample.get("label", "")
        filename = sample.get("file", "")
        if source == "synthetic":
            path = DATA / "processed" / "jackfurby" / "test" / label / filename
        elif source == "real":
            path = DATA / "processed" / "real52" / "all" / label / filename
        else:
            return jsonify({"error": "image or sample required"}), 400
        if not path.exists():
            return jsonify({"error": "sample not found"}), 404
        img = read_image(path)
        truth = label if is_valid_label(label) else None
        source_name = source
        image_path = str(path)
    else:
        img = _decode_upload(file)
        if img is None:
            return jsonify({"error": "cannot decode image"}), 400
        truth, source_name = None, "upload"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        image_path = str(UPLOAD_DIR / f"single_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg")
        cv2.imwrite(image_path, img)
    try:
        crop = payload.get("crop")
        if not request.is_json and request.form.get("crop"):
            crop = json.loads(request.form.get("crop"))
        rec = _predict_record(img, model, threshold, reject, truth, source_name,
                              ood_check=bool(payload.get("ood_check", True)) if request.is_json else
                              str(request.form.get("ood_check", "1")).lower() in {"1", "true", "yes"},
                              image_path=image_path,
                              crop=crop)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return jsonify(rec)


@app.route("/api/batch/start", methods=["POST"])
def api_batch_start():
    global BATCH
    data = request.get_json(silent=True) or {}
    config_name = data.get("config", "two104")
    if config_name == "custom":
        try:
            num_decks = max(1, int(data.get("num_decks", 2)))
            jokers = max(0, int(data.get("jokers_per_deck", 0)))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid custom config"}), 400
        CONFIGS["custom"] = {"label": f"自定义：{num_decks} 副 + {jokers} Joker/副",
                             "num_decks": num_decks, "jokers_per_deck": jokers}
        config_name = "custom"
    if config_name not in CONFIGS:
        return jsonify({"error": "unknown config"}), 400
    model = data.get("model", "hog_svm")
    if model not in MODEL_INFO:
        return jsonify({"error": "unknown model"}), 400
    if model == "suit":
        return jsonify({"error": "花色模式只支持单张"}), 400
    source = data.get("source", "synthetic")
    reject = bool(data.get("reject", True))
    ood_check = bool(data.get("ood_check", True))
    try:
        threshold = float(data.get("threshold", DEFAULT_THRESHOLD[model]))
    except (TypeError, ValueError):
        threshold = DEFAULT_THRESHOLD[model]
    try:
        queue = _build_queue(CONFIGS[config_name], source)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400
    if model != "card":
        _classifier(model)
    with _lock:
        BATCH = _new_batch(config_name, model, source, reject, threshold, queue,
                           ood_check=ood_check)
    return jsonify({"ok": True, "state": _state()})


@app.route("/api/batch/start_upload", methods=["POST"])
def api_batch_start_upload():
    global BATCH
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files"}), 400
    model = request.form.get("model", "hog_svm")
    if model not in MODEL_INFO:
        return jsonify({"error": "unknown model"}), 400
    if model == "suit":
        return jsonify({"error": "花色模式只支持单张"}), 400
    reject = request.form.get("reject", "1").lower() in {"1", "true", "yes"}
    ood_check = request.form.get("ood_check", "1").lower() in {"1", "true", "yes"}
    try:
        threshold = float(request.form.get("threshold", DEFAULT_THRESHOLD[model]))
    except (TypeError, ValueError):
        threshold = DEFAULT_THRESHOLD[model]
    config_name = request.form.get("config", "two104")
    if config_name not in CONFIGS:
        return jsonify({"error": "unknown config"}), 400
    folder = UPLOAD_DIR / datetime.now().strftime("%Y%m%d_%H%M%S") / uuid.uuid4().hex[:8]
    folder.mkdir(parents=True, exist_ok=True)
    queue = []
    for i, f in enumerate(files):
        suffix = Path(f.filename or "").suffix.lower() or ".jpg"
        path = folder / f"{i:04d}{suffix}"
        f.save(str(path))
        prefix = Path(f.filename or "").stem.split("_")[0].upper()
        truth = prefix if is_valid_label(prefix) else None
        queue.append({"path": str(path), "truth": truth, "kind": "card",
                      "source": "upload"})
    _classifier(model)
    with _lock:
        BATCH = _new_batch(config_name, model, "upload", reject, threshold, queue,
                           ood_check=ood_check)
    return jsonify({"ok": True, "state": _state()})


@app.route("/api/enroll", methods=["POST"])
def api_enroll():
    """Register one canonical card as a custom template for an unseen design."""
    data = request.get_json(silent=True) or {}
    label = str(data.get("label") or request.form.get("label") or "").strip().upper()
    if not is_valid_label(label):
        return jsonify({"error": "标签必须是 52 类普通牌之一，例如 7S"}), 400
    file = request.files.get("image")
    if file is not None:
        image = _decode_upload(file)
        if image is None:
            return jsonify({"error": "cannot decode image"}), 400
    else:
        image_path = data.get("image_path") or request.form.get("image_path")
        if not image_path or not Path(image_path).exists():
            return jsonify({"error": "image or image_path required"}), 400
        image = read_image(image_path)
    rectified, _ = rectify_card(image)
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = TEMPLATE_DIR / f"{label}_custom_{stamp}_{uuid.uuid4().hex[:4]}.png"
    cv2.imwrite(str(out), rectified)
    # Reload only the template classifier; HOG/CNN stay loaded.
    _models.pop("template", None)
    tpl = _classifier("template")
    result = tpl.predict(rectified)
    return jsonify({
        "ok": True, "label": label, "template_path": str(out),
        "template_count": sum(len(v) for v in tpl.templates.values()),
        "custom_labels": sorted(getattr(tpl, "custom_labels", [])),
        "verification_label": result["best_label"],
        "verification_score": float(result["score"]),
    })


@app.route("/api/batch/config", methods=["POST"])
def api_batch_config():
    if BATCH is None:
        return jsonify({"error": "no active batch"}), 400
    data = request.get_json(silent=True) or {}
    if "reject" in data:
        BATCH["config"]["reject"] = bool(data["reject"])
    if "threshold" in data:
        try:
            BATCH["config"]["threshold"] = float(data["threshold"])
        except (TypeError, ValueError):
            return jsonify({"error": "invalid threshold"}), 400
    return jsonify({"ok": True, "state": _state()})


@app.route("/api/batch/step", methods=["POST"])
def api_batch_step():
    global BATCH
    with _lock:
        if BATCH is None:
            return jsonify({"error": "no active batch"}), 400
        if not BATCH["active"] or BATCH["paused"] or BATCH["stopped"]:
            return jsonify({"ok": True, "done": True, "state": _state()})
        if BATCH["index"] >= len(BATCH["queue"]):
            BATCH["active"] = False
            return jsonify({"ok": True, "done": True, "state": _state()})
        item = BATCH["queue"][BATCH["index"]]
        BATCH["index"] += 1
        try:
            rec = _process_item(item, BATCH["config"])
        except Exception as exc:  # noqa: BLE001
            BATCH["deck"].add_failure(str(exc))
            rec = {"time": datetime.now().strftime("%H:%M:%S"), "model": "—",
                   "model_name": "处理失败", "label": "FAILED", "best_label": "FAILED",
                   "accepted": False, "reason": str(exc), "score": None,
                   "truth": item.get("truth"), "source": item.get("source", ""),
                   "input_image": "", "rectified_image": "", "tl_roi": "", "br_roi": "",
                   "thumb": "", "top5": [], "detected": False, "latency_ms": 0,
                   "batch_status": "FAILED", "correct": None}
        BATCH["records"].append({**rec, "_internal": True})
        BATCH["current"] = rec
        done = BATCH["index"] >= len(BATCH["queue"])
        if done:
            BATCH["active"] = False
        return jsonify({"ok": True, "done": done, "record": rec, "state": _state()})


@app.route("/api/batch/pause", methods=["POST"])
def api_batch_pause():
    if BATCH is None:
        return jsonify({"error": "no active batch"}), 400
    BATCH["paused"] = True
    return jsonify({"ok": True, "state": _state()})


@app.route("/api/batch/resume", methods=["POST"])
def api_batch_resume():
    if BATCH is None:
        return jsonify({"error": "no active batch"}), 400
    BATCH["paused"] = False
    BATCH["active"] = BATCH["index"] < len(BATCH["queue"])
    return jsonify({"ok": True, "state": _state()})


@app.route("/api/batch/stop", methods=["POST"])
def api_batch_stop():
    if BATCH is None:
        return jsonify({"error": "no active batch"}), 400
    BATCH["stopped"] = True
    BATCH["active"] = False
    return jsonify({"ok": True, "state": _state()})


@app.route("/api/batch/reset", methods=["POST"])
def api_batch_reset():
    global BATCH
    with _lock:
        BATCH = None
    return jsonify({"ok": True, "state": _state()})


@app.route("/api/batch/correct", methods=["POST"])
def api_batch_correct():
    if BATCH is None:
        return jsonify({"error": "no active batch"}), 400
    data = request.get_json(silent=True) or {}
    try:
        index = int(data.get("index"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid record index"}), 400
    if index < 0 or index >= len(BATCH["records"]):
        return jsonify({"error": "record not found"}), 404
    rec = BATCH["records"][index]
    if rec.get("batch_status") == "DUPLICATE":
        return jsonify({"error": "重复牌记录不能通过修正绕过批次容量；请人工复核"}), 400
    label = str(data.get("label", "")).strip().upper()
    if not label:
        return jsonify({"error": "label required"}), 400
    old = rec.get("label", "UNKNOWN")
    res = BATCH["deck"].correct(old, label)
    if not res["ok"]:
        return jsonify({"error": res["reason"]}), 400
    rec["label"] = label if label not in {"UNKNOWN", "REJECT"} else "UNKNOWN"
    rec["best_label"] = rec["label"]
    rec["accepted"] = rec["label"] != "UNKNOWN"
    rec["batch_status"] = "CORRECTED"
    rec["reason"] = f"人工修正：{old} → {rec['label']}"
    rec["correct"] = None if rec.get("truth") is None else (rec["label"] == rec["truth"])
    return jsonify({"ok": True, "record": rec, "state": _state()})


@app.route("/api/batch/inject", methods=["POST"])
def api_batch_inject():
    if BATCH is None:
        return jsonify({"error": "no active batch"}), 400
    kind = (request.get_json(silent=True) or {}).get("type", "duplicate")
    with _lock:
        if kind == "joker":
            BATCH["queue"].insert(BATCH["index"], {
                "kind": "joker_sim", "truth": JOKER_LABEL,
                "index": BATCH["deck"].counts[JOKER_LABEL] + 1,
                "source": "simulated Joker"})
        elif kind == "blank":
            BATCH["queue"].insert(BATCH["index"], {
                "kind": "blank", "truth": None, "source": "simulated failure"})
        else:
            # duplicate: inject an extra physical card whose label is already at
            # capacity, so the duplicate detection is meaningful.
            labels = [r["best_label"] for r in BATCH["records"]
                      if r.get("best_label") in LABELS]
            label = None
            for cand in reversed(labels):
                if BATCH["deck"].counts[cand] >= BATCH["deck"].num_decks:
                    label = cand
                    break
            if label is None:
                return jsonify({"error": "尚未有标签达到批次容量；请先处理更多牌后再注入重复"}), 400
            files = _image_files(label, BATCH["config"]["source"]
                                 if BATCH["config"]["source"] in {"synthetic", "real"} else "synthetic")
            if not files:
                return jsonify({"error": "no source image"}), 400
            BATCH["queue"].insert(BATCH["index"], {
                "path": str(files[0]), "truth": label, "kind": "card",
                "source": "duplicate test"})
        if BATCH["index"] >= len(BATCH["queue"]) - 1:
            BATCH["active"] = True
            BATCH["stopped"] = False
    return jsonify({"ok": True, "state": _state()})


@app.route("/api/batch/state")
def api_batch_state():
    return jsonify(_state())


@app.route("/api/batch/record/<int:index>")
def api_batch_record(index: int):
    if BATCH is None or index < 0 or index >= len(BATCH["records"]):
        abort(404)
    return jsonify(BATCH["records"][index])


@app.route("/api/export/batch.<fmt>")
def api_export_batch(fmt: str):
    if BATCH is None:
        abort(404)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    state = _state()
    if fmt == "json":
        path = EXPORT_DIR / f"batch_{stamp}.json"
        path.write_text(json.dumps({"state": state, "records": BATCH["records"]},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        return send_file(path, as_attachment=True, download_name=path.name)
    if fmt != "csv":
        abort(404)
    path = EXPORT_DIR / f"batch_{stamp}.csv"
    fields = ["time", "model", "source", "truth", "label", "best_label", "score",
              "accepted", "correct", "reason", "latency_ms", "detected",
              "detection_method", "batch_status"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(BATCH["records"])
    return send_file(path, as_attachment=True, download_name=path.name)


@app.route("/api/export/logs.<fmt>")
def api_export_logs(fmt: str):
    if BATCH is None:
        abort(404)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "json":
        path = EXPORT_DIR / f"logs_{stamp}.json"
        path.write_text(json.dumps(BATCH["records"], ensure_ascii=False, indent=2),
                        encoding="utf-8")
    elif fmt == "csv":
        path = EXPORT_DIR / f"logs_{stamp}.csv"
        fields = ["time", "model", "source", "truth", "label", "best_label", "score",
                  "accepted", "correct", "reason", "latency_ms", "batch_status"]
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(BATCH["records"])
    else:
        abort(404)
    return send_file(path, as_attachment=True, download_name=path.name)


@app.route("/media/eval/<model>/<path:filename>")
def media_eval(model: str, filename: str):
    folder = OUTPUTS / "eval" / model
    if not folder.exists():
        abort(404)
    return send_from_directory(folder, filename)


@app.route("/api/camera/status")
def api_camera_status():
    return jsonify({"open": CAMERA["cap"] is not None, "error": CAMERA["error"]})


@app.route("/api/camera/open", methods=["POST"])
def api_camera_open():
    if CAMERA["cap"] is not None:
        return jsonify({"ok": True})
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        CAMERA["error"] = "未检测到可用摄像头（索引 0）。可使用图片/示例模式继续演示。"
        return jsonify({"error": CAMERA["error"]}), 503
    CAMERA["cap"] = cap
    CAMERA["error"] = ""
    return jsonify({"ok": True})


@app.route("/api/camera/frame")
def api_camera_frame():
    cap = CAMERA["cap"]
    if cap is None:
        return jsonify({"error": CAMERA["error"] or "camera not open"}), 503
    ok, frame = cap.read()
    if not ok:
        return jsonify({"error": "camera frame read failed"}), 503
    return jsonify({"image": _b64(frame, max_width=760)})


@app.route("/api/camera/capture", methods=["POST"])
def api_camera_capture():
    cap = CAMERA["cap"]
    if cap is None:
        return jsonify({"error": CAMERA["error"] or "camera not open"}), 503
    ok, frame = cap.read()
    if not ok:
        return jsonify({"error": "camera frame read failed"}), 503
    data = request.get_json(silent=True) or {}
    model = data.get("model", "hog_svm")
    threshold = float(data.get("threshold", DEFAULT_THRESHOLD.get(model, 0.5)))
    reject = bool(data.get("reject", True))
    rec = _predict_record(frame, model, threshold, reject, None, "camera",
                          ood_check=bool(data.get("ood_check", True)))
    rec["input_image"] = _b64(frame, max_width=760)
    return jsonify(rec)


@app.route("/api/camera/close", methods=["POST"])
def api_camera_close():
    cap = CAMERA.get("cap")
    if cap is not None:
        cap.release()
    CAMERA["cap"] = None
    return jsonify({"ok": True})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "上传文件过大（>200 MB），请缩小批次"}), 413


if __name__ == "__main__":
    threading.Thread(target=_warmup, daemon=True).start()
    app.run(host="127.0.0.1", port=7860, debug=False, threaded=True)
