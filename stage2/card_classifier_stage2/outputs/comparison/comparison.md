# Model comparison (same held-out splits)

| model | split | n | top-1 | macro F1 | top-5 | mean latency (ms) |
|---|---|---|---|---|---|---|
| template | jackfurby_test | 260 | 0.4154 | 0.4086 | 0.5308 | 94.0 |
| template | real52_test | 104 | 0.0000 | 0.0000 | 0.1346 | 83.8 |
| hog_svm | jackfurby_test | 260 | 1.0000 | 1.0000 | 1.0000 | 28.4 |
| hog_svm | real52_test | 104 | 0.1346 | 0.1205 | 0.3269 | 42.8 |
| cnn | jackfurby_test | 260 | 0.9808 | 0.9744 | 1.0000 | 63.0 |
| cnn | real52_test | 104 | 0.2981 | 0.2491 | 0.6635 | 61.8 |

Notes:
- jackfurby_test is synthetic (same digital design, different generated images).
- real52_test is real photographs but each class folder repeats one physical card;
  it measures cross-source robustness, not unseen-physical-card generalisation.
- Template scores are similarity values, not calibrated probabilities.
