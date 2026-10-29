# 扑克牌识别：改造后的视觉基线

## 先说明当前项目边界

本次提供的原始 `card_classifier_stage2.zip` **只有模板匹配基线**，没有 `HOG+SVM`、CNN 训练/推理代码或 `compare_models.py`。因此本次改造保留并扩展现有模板匹配入口，没有伪造或覆盖不存在的 HOG/CNN 实现。此前报告中的 HOG+SVM、CNN 数值是实验记录，不能从这个压缩包中复现。若提供完整实验代码，后续可将三种分类器接入同一预处理接口进行公平对比。

## 本次新增/修改

- `src/image_utils.py`：增加基于轮廓的四边形检测和透视校正；长边统一为竖直方向；无法检测时回退到整图缩放；保留 180° 双角标识别入口。
- `src/classifier.py`：允许同一身份有多张参考模板（如 `AS_brand1.jpg`、`AS_brand2.jpg`）；对左上/右下角分别评分；新增最低相似度与前两类分差双阈值拒识。
- `src/card_labels.py`：增加 `JOKER` 标签。这里是**53 个视觉身份标签**（52 种普通牌 + 一个通用王类）。`DeckManager` 默认按**两副 54 张 = 108 张**统计，王上限 4 张；若课程任务按两副 104 张（无王），用 `DeckManager(num_decks=2, jokers_per_deck=0)`。若验收要求区分大王和小王，需改成两类并采集相应模板。
- `src/deck_manager.py`：新增批次管理，支持**多副牌**（默认两副 108 张 / 104 张无王模式），处理重复牌、缺牌、王数量和 UNKNOWN；存在未解决牌时不会直接宣称其他牌缺失。
- `src/evaluate.py`：新增接受覆盖率、已接受样本准确率和四边形检测成功率。
- `tests/test_deck_manager.py`：增加批次逻辑测试。

## 目录约定

```text
data/templates/AS.jpg
data/templates/AS_brand2.jpg
data/templates/10H.jpg
data/templates/JOKER.jpg
data/test/AS_test_01.jpg
data/test/JOKER_test_01.jpg
```

模板文件名的第一个下划线前字段为标签。多品牌模板可以用 `AS_brand1.jpg`、`AS_brand2.jpg` 这样的文件名，但同一实体牌的模板图片不能同时进入测试集。

## 安装与运行

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

单张识别：

```powershell
python classify_one.py --image data/test/AS_test_01.jpg --templates data/templates --threshold 0.35 --margin-threshold 0.02
```

批量评估：

```powershell
python evaluate_folder.py --images data/test --templates data/templates --output outputs --threshold 0.35 --margin-threshold 0.02
```

运行批次管理单元测试：

```powershell
python -m unittest discover -s tests -v
```

## 重要限制与实验要求

1. 0.35 和 0.02 是调试起点，不是最终阈值；必须用与模板/训练数据独立的验证集调参。
2. 轮廓检测依赖卡牌边缘与背景有足够对比度；白牌白底、遮挡、复杂背景时可能回退到整图缩放。请查看 CSV 中 `quad_detected` 字段并抽查标注图。
3. 这是模板匹配基线，不等于跨品牌稳健识别模型。默认批次为两副 108 张；104 张任务请显式传 DeckManager(num_decks=2, jokers_per_deck=0)。多个模板有助于覆盖外观变化，但最大相似度可能受每类模板数量影响；尽量让各类模板数量接近。
4. 当前 `JOKER` 是一个视觉类别，批次允许计数两张。如果需要区分大王/小王，应明确标签规则并收集对应真实数据。
5. 合成图与真实照片应分别报告。数据划分按实体牌/牌组分组，不能把同一张实体牌的近似照片同时放进模板、验证和测试。
6. 本次只改造了已提供的模板匹配项目；HOG+SVM 和 CNN 代码不在当前压缩包中，尚未修改或复测。
