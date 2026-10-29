# Data sources, licenses and limitations

This project downloads **small subsets** of two public Hugging Face datasets.
Run:

```powershell
python tools/download_datasets.py --out data --jackfurby-train 20 --jackfurby-val 5 --drfarid 2 --drfarid-candidates 8
python prepare_data.py --data data --overwrite
```

## 1. JackFurby/playing-cards — synthetic, MIT

- URL: https://huggingface.co/datasets/JackFurby/playing-cards
- License: **MIT** (dataset card)
- Content: 4 × 10,000 machine-generated images of playing cards on random
  backgrounds; the `single/` split has one card per image.
- Labels: 52 classes, official `train.json` / `val.json` splits and 4 card
  corners per image (`card_points`).
- Used here: `train`/`val` are taken from the official **train** split;
  `test` is taken from the official **val** split. The baseline does not train
  on the official val images.
- Important: **synthetic**. High accuracy here does not prove real-card
  performance.

## 2. drFarid/French-Playing-Cards — real photographs, MIT

- URL: https://huggingface.co/datasets/drFarid/French-Playing-Cards
- License: **MIT** (dataset card)
- Content: 1,877 real photos in 52 French-named class folders
  (`Coeur`=H, `Carreau`=D, `Pique`=S, `Trefle`=C; `Valet`=J, `Dame`=Q, `Roi`=K,
  `1`=A).
- Used here: only as a **cross-source test set** (6 photos/class), never for
  training or threshold tuning.
- Important: each class folder appears to contain repeated photos of **one
  physical card**. The set therefore measures robustness to capture conditions,
  **not** generalisation to an unseen physical card. There is no card-identity
  metadata, so a leak-free train/test split within this dataset is impossible.

## Not used / rejected

- Kaggle `andy8744/playing-cards-*` and Roboflow exports require an account/API
  key and are large; not downloaded in this session.
- `F1nn21/playing-cards` (54 single PNGs) has license `other` and no explicit
  permission statement; not redistributed or used as the main dataset.
- No public dataset with multiple physical decks and card identity was
  downloaded. Cross-brand / unseen-card generalisation is therefore
  **unverified** and must be tested by the team with their own 2–3 decks.

## How to add your own real photos

1. Put one folder per label under `data/external_mydeck/<LABEL>/`.
2. Take **multiple photos of each physical card** (different lighting, angle,
   background) and record which photos belong to the same physical card.
3. Split by **physical card identity / capture session**, not by random photo.
4. Run `python evaluate_folder.py --images data/external_mydeck --model template`
   (or `--model hog/cnn`) and report the result separately from the synthetic
   benchmark.
