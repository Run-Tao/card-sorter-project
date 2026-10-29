# 外部新牌面测试记录

## 数据来源

- [mavjav-edu/playing-cards](https://github.com/mavjav-edu/playing-cards)（MIT License，Howard Yeh）
- 下载 13 张 PNG 到 `data/external_cards/mavjav/`，**不参与训练/调参**，只做外部测试。
- 这些 PNG 是透明背景卡面；旧代码按 `IMREAD_COLOR` 读取会把透明区变黑，导致定位失败。
  现已改为 alpha 合成白底（`read_image` / 上传解码），透明 PNG 可正常定位。

## 测试结果（当前版本）

| 真值 | 预测 | 定位 | 说明 |
|---|---|---|---|
| AS | AS | quad | ✓ |
| 2H | 2H | quad | ✓ |
| 3D | 3D | full_frame_closeup | ✓ |
| 4C | 4C | quad | ✓ |
| 5S | 5S | full_frame_closeup | ✓ |
| 6H | 6H | full_frame_closeup | ✓ |
| 7D | 7D | full_frame_closeup | ✓ |
| 8C | 8C | quad | ✓ |
| 9S | 9S | quad | ✓ |
| 10H | AH | quad | ✗ 数字 10→A |
| JD | 7D | quad | ✗ 数字 J→7 |
| QC | 6S | quad | ✗ 数字 Q→6，花色 C→S |
| KH | KH | quad | ✓ |

**组合正确 10/13（76.9%）；花色正确 12/13（92.3%）；定位状态均给出。**

## 失败原因

1. **数字头对 J/Q/10 的角标字形识别弱**：EasyOCR 在 222×323 小图上读不准 J/Q/10；
   这些牌的角标较小，部分窗口被花色/边框干扰。
2. **花色头在 QC 上误判为黑桃**：C 与 S 同属黑色，形状模板区分不足。
3. **定位**：部分牌填满画面，只能给 `full_frame_closeup` 整图兜底，不是精确 quad。

## 下一步（优先）

1. 用多字体/多设计 rank 角标数据训练 13 类 rank 头；不要继续依赖通用 OCR。
2. 花色增加 S/C 形状判别数据，或训练 4 类小 CNN。
3. 对近拍图做白卡区域分割，输出精确 quad；再重测定位成功率。
4. 每新增一个外部设计，先作为验证集跑一遍，不允许把测试图加入训练/登记集。

## 复现

```powershell
python -c "from src.card_reader import CardReader; ..."
# 或网页上传 data/external_cards/mavjav/*.png
```
