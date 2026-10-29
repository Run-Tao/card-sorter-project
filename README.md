# 无标记扑克牌自动分拣机（视觉识别 + 工程实现）

两副**牌背相同**的标准扑克牌混合成 104 张，由机器逐张识别（52 类：13 点数 × 4 花色），
并按「每类恰好两张、分别进入 A/B 两组」的计数约束自动分流为两组各 52 张；
无法确定的牌进入复核流程并如实报告异常，而不是猜测后强行分流。

> 本仓库是**代码与技术文档**版本。完整数据集、UI 冒烟测试缓存与打包产物体积过大，
> 未纳入 git（原因见下），保留在本地交付包中。

## 目录结构

| 路径 | 内容 |
|---|---|
| `report/` | 工程实施方案（Markdown/DOCX/PDF）、分节源文件 `sections/`、独立审查记录 `review_notes.md`、BOM 与图表工具 |
| `research/` | 算法、硬件、机械三份调研（过程稿，以主报告为准） |
| `tools/` | 图表生成、BOM 生成、报告一致性检查脚本 |
| `stage2/card_classifier_stage2/` | 分类器与演示系统：`src/`、`tests/`、`models/`、`outputs/eval/`（真实评测指标）、`demo_app.py`（Flask 本地 Web 演示） |
| `stage2/modified/` | 模板匹配分支的历史修正版本（自述无数据/模型，仅代码参考） |

## 快速开始（stage2 演示）

```powershell
cd stage2\card_classifier_stage2
python -m pip install -r requirements.txt
python demo_app.py            # 打开 http://127.0.0.1:7860
python -m unittest discover -s tests -v
```

> `StartPokerSystem.exe` 只是调用本机 Python 的启动器（非独立可执行包）；
> 完整 PyInstaller 打包因 PyQt/PySide 与 torch 冲突未成功，详见 `NEXT_PLAN.md`。

## 未入库内容（及原因）

| 内容 | 大小 | 原因 |
|---|---|---|
| `stage2/card_classifier_stage2/data/` | ~949 MB | 超出 GitHub 仓库建议体积；本地保留，可按 `data/README.md` 重新生成 |
| `stage2/card_classifier_stage2/outputs/edge_*` | ~218 MB | UI 冒烟测试的浏览器缓存，无工程价值 |
| `*.zip`（交付包/备份） | 58–112 MB | 单文件超过 GitHub 100 MB 硬限制 |
| `build/`、`dist/`、`*.exe` | ~19 MB | 可重新生成的构建产物 |

## 重要说明

- 报告中的性能数字大多标注为**项目目标值/待验证假设**，并非实测结果；实测数据见 `outputs/eval/`
  与 `outputs/calibration/`。
- 本项目不解决「牌组归属（哪张牌属于原来哪一副）」：题目只要求两组各成完整一套，
  且同品牌同批次、无参考样本时该归属不可靠可辨识。详见报告第 1 章。
- 代码与文档为课程项目产出，未附带开源许可证；如需引用请联系作者。
