# -*- coding: utf-8 -*-
"""Tests for the simulated sorting controller and Flask API."""

import unittest
from pathlib import Path

import demo_app
from src.controller import SortingController

ROOT = Path(__file__).resolve().parents[1]


class TestSortingController(unittest.TestCase):
    def test_suit_bins(self):
        c = SortingController()
        self.assertEqual(c.command("AS").bin, "BIN_SPADE")
        self.assertEqual(c.command("10H").bin, "BIN_HEART")
        self.assertEqual(c.command("QD").bin, "BIN_DIAMOND")
        self.assertEqual(c.command("7C").bin, "BIN_CLUB")

    def test_joker_and_unknown_review(self):
        c = SortingController()
        self.assertEqual(c.command("JOKER").bin, "REVIEW")
        self.assertEqual(c.command("UNKNOWN").bin, "REVIEW")
        self.assertTrue(c.execute(c.command("AS"))["simulated"])


class TestWebApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = demo_app.app.test_client()

    def tearDown(self):
        self.client.post("/api/batch/reset")
        self.client.post("/api/camera/close")

    def test_meta(self):
        r = self.client.get("/api/meta")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(len(data["labels"]), 52)
        self.assertIn("two104", data["configs"])

    def test_start_step_and_export(self):
        r = self.client.post("/api/batch/start", json={
            "model": "hog_svm", "config": "two104", "source": "synthetic",
            "reject": False, "threshold": 0.99})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r = self.client.post("/api/batch/step")
        self.assertEqual(r.status_code, 200)
        rec = r.get_json()["record"]
        self.assertTrue(rec["best_label"])
        self.assertEqual(r.get_json()["state"]["deck"]["processed"], 1)
        csv_resp = self.client.get("/api/export/batch.csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("truth", csv_resp.get_data(as_text=True).splitlines()[0])

    def test_pause_resume_stop(self):
        self.client.post("/api/batch/start", json={
            "model": "hog_svm", "config": "two104", "source": "synthetic"})
        self.assertEqual(self.client.post("/api/batch/pause").status_code, 200)
        self.assertTrue(self.client.get("/api/batch/state").get_json()["paused"])
        self.assertEqual(self.client.post("/api/batch/resume").status_code, 200)
        self.assertFalse(self.client.get("/api/batch/state").get_json()["paused"])
        self.assertEqual(self.client.post("/api/batch/stop").status_code, 200)
        self.assertTrue(self.client.get("/api/batch/state").get_json()["stopped"])

    def test_invalid_config(self):
        r = self.client.post("/api/batch/start", json={"config": "nope"})
        self.assertEqual(r.status_code, 400)

    def test_manual_crop_and_correction(self):
        image = ROOT / "data" / "processed" / "jackfurby" / "test" / "AS" / "9942.png"
        with image.open("rb") as f:
            r = self.client.post("/api/predict", data={
                "image": (f, image.name), "model": "hog_svm",
                "reject": "0", "threshold": "0.99", "ood_check": "0",
                "crop": "[0.0,0.0,1.0,1.0]",
            }, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(r.get_json()["manual_crop"])
        self.client.post("/api/batch/start", json={
            "model": "hog_svm", "config": "two104", "source": "synthetic",
            "reject": False, "ood_check": False})
        step = self.client.post("/api/batch/step").get_json()
        old = step["record"]["label"]
        r = self.client.post("/api/batch/correct", json={"index": 0, "label": "7S"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        data = r.get_json()
        self.assertEqual(data["record"]["label"], "7S")
        self.assertEqual(data["state"]["deck"]["processed"], 1)
        self.assertNotEqual(old, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
