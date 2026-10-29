# 最终系统技术报告

日期：2026-10-20  
项目：扑克牌智能识别与分拣系统（工程课程演示）

## 1. 交付内容

- 可运行的 Flask Web 展示系统：`demo_app.py` + `demo/`。
- 真实 OpenCV 预处理与三种分类器（模板、HOG+SVM、CNN）。
- 单副 54 / 两副 104 / 两副 108 / 自定义批次管理；合法重复、缺牌、Joker、拒识、失败统计。
- 模拟演示流程、牌组分布、日志复核、模型实验页、CSV/JSON 导出。
- 35 个自动化测试，实际执行通过。
- 实际模型指标、混淆矩阵、错误样本和数据审计报告。
- 分拣控制抽象 `src/controller.py`（模拟实现 + 串口接口占位）。

## 2. 架构

```
浏览器 (demo/templates/index.html + static/app.js)
        │ JSON / multipart
Flask API (demo_app.py)
        ├─ /api/predict                 单张推理
        ├─ /api/batch/*                开始/步进/暂停/继续/停止/重置/注入/上传
        ├─ /api/export/*               批次/日志 CSV/JSON
        ├─ /api/camera/*               真实摄像头打开/取帧/拍照/关闭
        └─ /api/meta, /media/eval/*    实验指标与图片
        │
src/image_utils.py    OpenCV 检测、校正、ROI
src/classifier.py     模板 / HOG+SVM / CNN 统一接口
src/deck_manager.py   多副批次、Joker、重复/缺牌/未确认
src/controller.py     分拣槽位抽象（模拟）
        │
models/ + data/processed/ + outputs/eval/
```

## 3. 关键实现

### 3.1 视觉预处理
- Unicode 安全读图；210×294 标准牌面。
- 四边形检测（亮区 HSV、Otsu、Canny、自适应阈值、形状/内部亮度评分）；失败回退整图并记录 `detected=False`。
- 校正后取 TL/BR 角标；180° 方向由双角匹配/TTA 处理；透视不能自动解决方向歧义。
- 批量记录保存原图、校正图、双 ROI，供界面复核。

### 3.2 三模型统一接口
- `BaseCardClassifier.predict(image)` 返回 `label/best_label/score/second_*/margin/top5/corner/detected/quad`。
- 模板：双角 NCC，模板可多参考；分数为相似度。
- HOG：64×96 灰度 HOG，4 方向 TTA，`StandardScaler + SGDClassifier(log_loss)`。
- CNN：3×64×96 RGB，4 层卷积 + GAP + FC52，约 24.8 万参数，CPU。
- 阈值只在 val 上选；界面可关闭拒识做完整批次演示。

### 3.3 批次管理
- 普通牌容量 = 副数；Joker 容量 = 副数×每副王数。
- 两副同标签第二张合法，第三张才重复。
- unresolved = 拒识 + 失败；存在 unresolved 时不作最终缺牌断言。
- 完成状态仅当 processed/expected、accepted、missing、duplicates 全部满足。

### 3.3.1 决策树集成
- `ensemble` 对三个模型的候选标签做 stacking：候选在各模型的分数/排名/分差、投票数、模板设计相似度、质量。
- 浅层决策树预测“候选是否正确”；低概率/票数不足拒识；设计相似度高且 HOG 高置信时回退 HOG。
- 实测：合成 Top-1 100%、覆盖 100%、接受准确率 100%；真实 Top-1 5.77%、覆盖 14.4%、接受准确率 40%。
- 结论：集成用于投票/拒识，不掩盖真实域偏移。

### 3.3.2 两副牌两槽分离
- `TwoDeckSorter`：同标签第一次确认→A，第二次→B，第三次/UNKNOWN→复核。
- 两副 104 实测 A=52/52、B=52/52；两副 108 实测 A=54/54、B=54/54（4 Joker）。
- 关键限制：无标记混洗无法恢复物理来源；A/B 是按出现顺序重建的两套，不是“原副识别”。

### 3.4 Joker 策略
- 无 Joker 训练数据，分类器**不输出 JOKER**。
- Joker 只是批次标签；单副/两副含王演示中由“模拟 Joker”事件补足，记录明确标注 `manual / simulated`，不计入模型准确率。
- 若未来采集红/黑王数据，可扩展为两个视觉类别，同时保持批次计数逻辑。

### 3.5 未知牌面（OOD）与自定义模板
- 每次推理同时计算模板相似度作为设计是否见过的检查；<0.55 且非已登记模板时输出 `UNKNOWN`。
- 界面可输入真实标签，把当前校正图登记为 `data/templates/<label>_custom_*.png`；模板分类器重载后可识别该设计。
- 样例（三国杀 7♠）：登记前 UNKNOWN/OOD（0.341），登记后 7S（1.000，custom_match=True）。
- 这解决的是“少量带标签样本适配新设计”，不是任意牌面零样本识别；没有 OCR/目标域角标模型时，系统选择拒识而不是高置信度误判。

### 3.6 界面
- 顶部状态；左侧控制与示例；中央 6 步视觉流水线 + 4 图 + Top-5；右侧结果/最近记录；底部件数统计 + 104 格牌组 + 缺牌；独立实验页/日志页/说明页。
- 所有按钮连接真实 API：开始/暂停/继续/停止/重置、模型切换、阈值、上传、摄像头、异常注入、导出。
- 耗时任务在服务端逐张执行，前端轮询步进；没有伪造实时画面。

## 4. 实际测试证据

```text
python -m unittest discover -s tests -v
Ran 35 tests in 2.339s
OK
```

端到端（真实 API 调用）：

```text
two104 reject=False → COMPLETE_104 / 104 accepted
two108 reject=False → COMPLETE_108 / 108 accepted / 4 Joker simulated
single54             → COMPLETE_54 / 54 accepted / 2 Joker simulated
two104 + duplicate   → DUPLICATES_FOUND / duplicates=1
batch CSV export     → HTTP 200, real file
single image predict → real model output (label/score/images)
camera open/frame    → actual device read (on this machine)
```

## 5. 实际指标（outputs/eval）

| 模型 | 合成 test Top-1 | 真实 test Top-1 | 合成 F1 | 真实 F1 |
|---|---|---|---|---|
| 模板 | 41.54% | 0.00% | 0.409 | 0.000 |
| HOG+SVM | 100.00% | 13.46% | 1.000 | 0.121 |
| CNN | 98.08% | 29.81% | 0.974 | 0.249 |

合成 = 与训练同数字牌面；真实 = 另一套牌设计、每类同一实体牌重复。真实 29.81% 证明跨设计域偏移严重，不可直接用于实体机。

## 6. 未完成/未验证

- 真实多品牌、多实体牌泛化：**未验证**。
- Joker 视觉识别：**未实现**（无数据），仅批次模拟。
- 机械/ESP32 分拣：**未接入**；只有接口抽象和模拟状态。
- 原始图直接分类 vs 固定 ROI vs 透视校正的完整消融：**未全部完成**。
- 概率校准/OOD：**未实现**。
- 摄像头：本机实测可读帧；不同机器需现场检查。

## 7. 结论

系统已能按 README 启动，界面真实可交互，能对图片执行实际视觉处理与识别，支持 54/104/108 批次、拒识与异常、模拟演示、实验展示与导出。真实牌泛化与机械控制是下一阶段工作，报告中未将其伪称为已完成。
