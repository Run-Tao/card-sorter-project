# Dataset report

## Splits

| split | images | classes | per-class min/max | missing |
|---|---|---|---|---|
| jackfurby_train | 780 | 52 | 15/15 | 0 |
| jackfurby_val | 260 | 52 | 5/5 | 0 |
| jackfurby_test | 260 | 52 | 5/5 | 0 |
| real52_test | 104 | 52 | 2/2 | 0 |

## Card detection on real photos

- auto-detected quad: 96
- fallback full-image resize: 8

## Known limitations

- JackFurby images are synthetic (one openclipart deck rendered on random backgrounds).
- drFarid real photos are per-class repeats of presumably one physical card each; splitting within a class would leak card identity, so the whole set is used only as a test set.
- No public dataset with multiple physical decks and card identity was downloaded; cross-brand / unseen-card generalisation remains unverified.
