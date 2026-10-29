# 修改版审查与修复记录

审查对象：`C:\Users\Taoli\Downloads\card_classifier_stage2_modified.zip`  
审查日期：2026-10-20

## 结论

上传版本是在**最初模板匹配基线**上改的，不是当前 `card_classifier_stage2`
增强版（没有 `data/`、模型、HOG+SVM、CNN、评估结果和展示界面）。它的 6 个测试
能通过，但有 3 个会直接影响验收的逻辑问题；本次已修复并补测。

## 发现并修复的问题

### P0-1 批次管理按“一副 54 张”写死

原 `DeckManager` 每张普通牌上限 1 张，`AS` 第二张会被判 `DUPLICATE`，
因此两副牌（104 张或 108 张）永远无法通过。

修复：`DeckManager(num_decks=2, jokers_per_deck=2)` 默认两副 108 张；
104 张无王模式用 `DeckManager(num_decks=2, jokers_per_deck=0)`。
每张普通牌上限 = `num_decks`，王上限 = `num_decks * jokers_per_deck`。

### P0-2 JOKER 别名与测试“假通过”

原 `normalize_label("JOKER_RED")` 返回 `JOKER_RED`（非法标签），但测试却断言
它等于 `JOKER_RED`，所以测试通过而实际把红王判成未知。

修复：`JOKER_RED`、`JOKER_BLACK`、`REDJOKER`、`BLACKJOKER`、`RED_JOKER`、
`BLACK_JOKER`、`JK`、`JR`、`JB`、`JOKER1/2` 全部归一到 `JOKER`；测试改为
断言归一化结果。

### P0-3 模板只存左上角，模板本身倒置时失效

原 `_load_templates` 只存 TL 角；如果模板图是 180° 方向，查询时 TL/BR 都对不上。
修复：每个模板同时存 TL 和旋转后的 BR 两个角，查询取最大相似度。

### P1 小牌检测回退

原四边形检测要求牌面 > 图像面积 20%，真实照片中牌小就回退整图。
修复：阈值降到 3%，并新增 12.5% 小牌测试。

### P1 单候选崩溃

`classify_one.py` 在只有 1 个类别模板时对 `None` 做 `:.4f` 格式化会崩溃；
已增加保护。

## 验证

```powershell
cd card_classifier_stage2
python -m unittest discover -s tests -v
```

实际结果：

```
Ran 10 tests in 0.023s
OK
```

新增测试覆盖：两副 108、104 无王、单副 54 兼容、第三张重复、王别名、王数量上限、
12.5% 小牌检测。

## 仍未解决的问题（不是本次能伪造的）

1. 该压缩包仍**没有真实数据、模板、模型**，无法给出准确率；需要按 README 的
   目录约定放 `data/templates` 与 `data/test` 后运行 `evaluate_folder.py`。
2. 它只有模板匹配，不含 HOG+SVM/CNN；增强版 `card_classifier_stage2` 才包含
   三种模型、公开数据、混淆矩阵和展示界面。
3. `JOKER` 目前是一个视觉类别；若要区分大王/小王，必须拆成两个标签并采集模板。
4. 模板分数是 NCC 相似度，不是概率；0.35/0.02 仍是调试起点，必须用独立验证集校准。
