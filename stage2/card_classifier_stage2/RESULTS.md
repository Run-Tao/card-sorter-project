# 最终结果速览

完整说明见 `README.md` 与 `REPORT.md`。本文件只记录最终可核对的数字。

## 界面

- 启动：`python demo_app.py` 或 `run.bat`
- 地址：http://127.0.0.1:7860
- 实际浏览器冒烟测试（Edge/CDP，`tools/ui_smoke_test.py`）：
  - 页面标题正确
  - 开始按钮可点击，状态变为“识别中”，processed 增加
  - 暂停/继续/停止/重置均生效，重置后 processed=0
  - “模型实验”“日志与导出”页可切换并渲染

## 模型指标（`outputs/eval`，2026-10-20 重跑）

| 模型 | 合成 test Top-1 | 真实 test Top-1 | 合成 Macro F1 | 真实 Macro F1 |
|---|---|---|---|---|
| 模板 | 41.54% | 0.00% | 0.409 | 0.000 |
| HOG+SVM | 100.00% | 13.46% | 1.000 | 0.121 |
| CNN | 98.08% | 29.81% | 0.974 | 0.249 |

合成 = 与训练同数字牌面；真实 = 另一套牌设计、每类同一实体牌重复拍摄。真实 29.81% 不代表可上实体机。

## OOD / 未知设计（`outputs/ood_eval.md`）

| 数据 | n | 相似度中位数 | OOD 拒识率 |
|---|---|---|---|
| 合成同设计 | 260 | 0.958 | 1.5%（误拒） |
| 真实另一设计 | 104 | 0.428 | 90.4%（符合预期） |

三国杀 7♠：登记前 UNKNOWN/OOD（0.341），登记后 7S（1.000，custom_match）。
单张手动框选、批次人工修正均已实现并测试。

## 决策树集成 / 两槽分离

| 项目 | 结果 |
|---|---|
| 集成模型（合成） | Top-1 100%，覆盖 100%，接受准确率 100% |
| 集成模型（真实） | Top-1 5.77%，覆盖 14.4%，接受准确率 40%（OOD 会先拒识） |
| 两副 104 两槽 | A=52/52，B=52/52，review=0 |
| 两副 108 两槽 | A=54/54，B=54/54，review=0，Joker=4/4 |

> A/B 是按同一标签出现顺序重建的两套，不是物理来源识别。

## 批次端到端（真实 API 调用）

```text
two104 104 步 → COMPLETE_104，accepted=104/104
two108 108 步 → COMPLETE_108，accepted=108/108，Joker=4/4（模拟事件）
single54 54 步 → COMPLETE_54，accepted=54/54，Joker=2/2（模拟事件）
two104 完成后注入重复 → DUPLICATES_FOUND，duplicates=1
/api/export/batch.csv → HTTP 200，真实 CSV
/api/export/logs.json → HTTP 200，真实 JSON
/api/predict JSON reject 开关 → 验证 UNKNOWN/AS 两种结果
```

## 自动化测试

```text
python -m unittest discover -s tests -v
Ran 35 tests ... OK
```

## 未验证

- Joker 视觉识别（无训练数据；仅批次模拟）
- 跨品牌/多实体牌真实泛化
- 机械/ESP32 分拣（仅 `src/controller.py` 接口与模拟）
- 原始图直接分类 vs 固定 ROI vs 透视校正的完整消融
