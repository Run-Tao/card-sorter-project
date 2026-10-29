# -*- coding: utf-8 -*-
"""Smoke/unit tests for labels, image geometry, classifier interface and metrics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.card_labels import (LABELS, label_from_filename, label_to_index,
                             index_to_label, is_valid_label, parse_label)
from src.classifier import TemplateCardClassifier
from src.evaluate import evaluate_folder
from src.image_utils import (CANONICAL_SIZE, corner_roi, detect_card_quad,
                             normalize_roi, read_image, rectify_card, save_image)


def synthetic_card(label: str, size=CANONICAL_SIZE) -> np.ndarray:
    w, h = size
    img = np.full((h, w, 3), 250, np.uint8)
    cv2.rectangle(img, (2, 2), (w - 3, h - 3), (0, 0, 0), 2)
    rank = "10" if label.startswith("10") else label[0]
    suit = label[-1]
    cv2.putText(img, rank, (8, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.putText(img, suit, (8, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, rank, (w - 42, h - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.putText(img, suit, (w - 42, h - 52), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    return img


class TestLabels(unittest.TestCase):
    def test_52_unique(self):
        self.assertEqual(len(LABELS), 52)
        self.assertEqual(len(set(LABELS)), 52)

    def test_roundtrip(self):
        for i, label in enumerate(LABELS):
            self.assertEqual(label_to_index(label), i)
            self.assertEqual(index_to_label(i), label)

    def test_parse(self):
        self.assertEqual(parse_label("10H"), ("10", "H"))
        self.assertEqual(parse_label("AS"), ("A", "S"))
        self.assertEqual(parse_label("kc"), ("K", "C"))
        with self.assertRaises(ValueError):
            parse_label("11H")

    def test_filename(self):
        self.assertEqual(label_from_filename("10H_test_01.jpg"), "10H")
        with self.assertRaises(ValueError):
            label_from_filename("foo.jpg")


class TestImageUtils(unittest.TestCase):
    def test_corner_and_normalize(self):
        card = synthetic_card("AS")
        tl = corner_roi(card, "tl")
        br = corner_roi(card, "br")
        self.assertEqual(tl.shape, br.shape)
        norm = normalize_roi(tl)
        self.assertEqual(norm.shape, (128, 128))
        self.assertEqual(norm.dtype, np.uint8)

    def test_detect_quad_on_synthetic_photo(self):
        canvas = np.full((600, 500, 3), 30, np.uint8)
        pts = np.array([[100, 120], [360, 90], [390, 470], [130, 500]], np.int32)
        cv2.fillPoly(canvas, [pts], (245, 245, 245))
        quad = detect_card_quad(canvas)
        self.assertIsNotNone(quad)
        self.assertEqual(np.asarray(quad).shape, (4, 2))
        rectified, info = rectify_card(canvas)
        self.assertTrue(info["detected"])
        self.assertEqual(rectified.shape[:2], (CANONICAL_SIZE[1], CANONICAL_SIZE[0]))

    def test_read_missing(self):
        with self.assertRaises(FileNotFoundError):
            read_image("definitely_missing_file.png")


class TestClassifierAndEvaluation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.tpl = self.root / "templates"
        self.test = self.root / "test"
        self.tpl.mkdir()
        for label in ("AS", "10H", "KC"):
            save_image(self.tpl / f"{label}.png", synthetic_card(label))
        for label in ("AS", "10H", "KC"):
            d = self.test / label
            d.mkdir(parents=True)
            save_image(d / f"{label}_01.png", synthetic_card(label))

    def tearDown(self):
        self.tmp.cleanup()

    def test_template_predict(self):
        clf = TemplateCardClassifier(self.tpl, threshold=None)
        result = clf.predict(self.test / "AS" / "AS_01.png")
        self.assertEqual(result["best_label"], "AS")
        self.assertIn("top5", result)
        self.assertGreater(result["score"], 0.9)

    def test_evaluate(self):
        clf = TemplateCardClassifier(self.tpl, threshold=None)
        metrics, rows = evaluate_folder(self.test, clf, self.root / "out", "unit")
        self.assertEqual(metrics["num_images"], 3)
        self.assertEqual(metrics["accuracy_top1"], 1.0)
        self.assertTrue((self.root / "out" / "metrics_unit.json").exists())
        self.assertTrue((self.root / "out" / "predictions_unit.csv").exists())


if __name__ == "__main__":
    unittest.main()
