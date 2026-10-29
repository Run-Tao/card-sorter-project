# Error analysis

## template/jackfurby_test

- n=260, top-1=0.4077, rank=0.5385, suit=0.7846
- top confusions: 10D->10S (4), 3C->3S (4), 3D->3S (4), 4S->8S (4), 7S->9S (4), 10C->10S (3), 10H->8H (3), 2D->2S (3)

## template/real52_test

- n=104, top-1=0.0000, rank=0.0288, suit=0.3654
- top confusions: 3C->JC (2), 3H->AS (2), 3S->JC (2), 4D->JD (2), 6D->JD (2), 7C->JC (2), 8C->JC (2), 9H->JD (2)

## hog_svm/jackfurby_test

- n=260, top-1=0.9885, rank=0.9923, suit=0.9923
- top confusions: 2S->2H (1), AC->7C (1), JC->2H (1)

## hog_svm/real52_test

- n=104, top-1=0.1346, rank=0.1923, suit=0.3750
- top confusions: 2D->JC (2), 2H->JC (2), 2S->JC (2), 3D->JC (2), 8D->JS (2), 9S->JS (2), AH->KC (2), JC->KC (2)

## cnn/jackfurby_test

- n=260, top-1=0.9692, rank=0.9731, suit=0.9885
- top confusions: 9H->10H (5), 2S->AH (1), AC->AH (1), JC->AD (1)

## cnn/real52_test

- n=104, top-1=0.2981, rank=0.3942, suit=0.6731
- top confusions: 10C->9C (2), 4C->2C (2), 5C->3C (2), JC->QD (2), JD->QD (2), JH->QD (2), JS->KC (2), KS->KC (2)

## template/real52_detection_fallback

- n=8, top-1=0.0000, rank=0.0000, suit=0.3750
- top confusions: 10H->JS (1), 3H->AS (1), 4D->JD (1), 6S->3S (1), 7D->JC (1), 7H->3S (1), 7S->3S (1), QD->KH (1)

## hog_svm/real52_detection_fallback

- n=8, top-1=0.0000, rank=0.0000, suit=0.1250
- top confusions: 10H->JS (1), 3H->JS (1), 4D->JS (1), 6S->KC (1), 7D->JS (1), 7H->JS (1), 7S->JS (1), QD->JS (1)

## cnn/real52_detection_fallback

- n=8, top-1=0.0000, rank=0.1250, suit=0.5000
- top confusions: 10H->8D (1), 3H->3D (1), 4D->8D (1), 6S->9S (1), 7D->QD (1), 7H->8D (1), 7S->KC (1), QD->8D (1)
