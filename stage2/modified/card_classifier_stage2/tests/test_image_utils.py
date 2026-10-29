import unittest
import cv2
import numpy as np
from src.image_utils import rectify_card, corner_roi, normalize_roi

class ImageUtilsTests(unittest.TestCase):
    def test_rectify_card_from_contrasting_background(self):
        image = np.zeros((800, 600, 3), dtype=np.uint8)
        cv2.rectangle(image, (120, 50), (480, 750), (255, 255, 255), -1)
        warped, detected = rectify_card(image)
        self.assertEqual(warped.shape[:2], (700, 500))
        self.assertTrue(detected)
        roi = normalize_roi(corner_roi(warped, "tl"))
        self.assertEqual(roi.shape, (90, 120))

    def test_fallback_when_no_card_quad(self):
        image = np.full((100, 150, 3), 120, dtype=np.uint8)
        warped, detected = rectify_card(image)
        self.assertEqual(warped.shape[:2], (700, 500))
        self.assertFalse(detected)

    def test_small_card_still_detected(self):
        # Card occupies only ~12.5% of the frame; the old 20% area cutoff would
        # have fallen back to a full-frame resize here.
        image = np.zeros((800, 600, 3), dtype=np.uint8)
        cv2.rectangle(image, (200, 250), (400, 550), (255, 255, 255), -1)
        warped, detected = rectify_card(image)
        self.assertEqual(warped.shape[:2], (700, 500))
        self.assertTrue(detected)

if __name__ == "__main__":
    unittest.main()
