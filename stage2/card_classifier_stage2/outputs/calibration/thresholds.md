# Rejection threshold calibration

Threshold chosen on `jackfurby_val` for 95% coverage, then applied unchanged.

| model | threshold | val cov | val accepted acc | synthetic cov | synthetic acc | real cov | real acc |
|---|---|---|---|---|---|---|---|
| template | 0.6279 | 0.950 | 0.4494 | 0.969 | 0.4286 | 0.000 | 0.0000 |
| hog_svm | 0.9947 | 0.950 | 1.0000 | 0.950 | 1.0000 | 0.788 | 0.1585 |
| cnn | 0.2701 | 0.950 | 0.9798 | 0.942 | 0.9796 | 0.702 | 0.3151 |

Scores are similarity/softmax values, not calibrated probabilities.
Coverage = fraction of cards accepted; rejected cards should go to a review bin.
