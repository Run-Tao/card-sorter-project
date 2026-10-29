# 无标记扑克牌自动分拣机：算法与文献调研

> **调研日期 2026-10-19 / 调研员 algo-researcher**
> 任务：`task-1`（算法与文献调研：牌面识别、物理指纹、跨品牌泛化）
> 写入范围：仅本文件 `card-sorter-project/research/algorithms.md`
> 说明：本文所有性能数字均来自文末来源表中标注"已打开正文 / 仅摘要"的条目；凡未找到可靠来源者明确写"未找到可靠来源"，不以猜测代替。

---

## 0. 证据分级约定

| 标记 | 含义 |
|---|---|
| **【已验证事实】** | 本次调研中实际打开来源（论文正文、官方文档、GitHub README、Crossref/Semantic Scholar/arXiv 元数据）并确认的内容 |
| **【工程推断】** | 由已验证的算法原理或官方文档描述推出的设计判断，来源没有直接这样表述 |
| **【待验证假设】** | 必须由本项目实测才能确认的假设，本文给出验证方法 |

核实状态另分三档：`已打开正文`（下载 PDF/GitHub/官方文档并阅读）、`仅摘要`（只读到摘要/元数据）、`仅搜索结果`（只确认条目存在）。
**本次未能打开 IEEE Xplore 正文页**（返回 HTTP 202 空页），因此若某论文只有 IEEE 版本，本文只核到"论文真实存在 + 题录信息"，不转述其正文内部数字。

---

## 1. 问题定义与一个关键的"可辨识性"切分

### 1.1 任务

- 输入：两副标准扑克牌（牌背相同）混合后的 **104 张**牌；
- 输出：分成两组，每组恰好 52 张、且 13 点数 × 4 花色各一张；
- 硬约束：**不需要判断"某张牌原本属于哪一副"**，只需要识别"点数 + 花色"，再按组合约束分组。

### 1.2 两类完全不同的问题（全文最重要的切分）

| 问题 | 目标 | 典型技术 | 本项目是否需要 |
|---|---|---|---|
| **A. 类别识别** | 这张牌是 ♠A、♥7……（52 类之一） | 角标 ROI + 分类器 / 模板匹配 / OCR | **需要，且是唯一必需项** |
| **B. 实例级 / 物理指纹识别** | 这张牌与那张牌是否"同一张纸 / 同一批 / 同一副" | 纸纹、透射纹理、PRNU、印刷随机性 | **不需要**，且工程上不可行（见第 3 节） |

题目把约束放宽为"只需识别点数+花色"，本质上就是**主动绕开问题 B**。第 3 节会论证：问题 B 不但昂贵，而且"同一张牌重复拍摄可匹配"与"判断两张牌同属一副牌"之间存在原理性鸿沟（无参考库、同批噪声、光照混淆）。

### 1.3 组合约束是一个"强先验"，应写进算法

104 张牌的识别结果必须满足：每种 (点数, 花色) 组合恰好出现 **2 次**。因此只要把 104 个预测的计数向量作为约束，就能自动发现并定位错误：

- 若某 identity 出现 1 次或 3 次 ⇒ 必然存在至少一个误识，可触发"重拍该卡 / 人工复核"；
- 在单张 top-1 准确率约 99% 量级时，104 张里期望约 1 张错，约束计数能把"系统级正确率"显著抬高——**这是【工程推断】，具体增益必须实测**（本文不编造数字）。

---

## 2. 牌面分类技术路线逐项评估

### 2.1 牌面检测与几何归一化

**做法**：灰度化/阈值 → `cv.findContours` 找外轮廓 → `cv.approxPolyDP`（Douglas–Peucker）拟合成四边形 → 按面积/长宽比过滤 → `cv.getPerspectiveTransform` + `cv.warpPerspective` 拉正为固定尺寸（如 2:3）；也可用 `cv.minAreaRect` + `cv.boxPoints` 取最小外接旋转矩形（不建模透视）。

**【已验证事实】官方文档能力边界**（均已打开）：

- `findContours` 支持 `RETR_EXTERNAL/LIST/CCOMP/TREE` 等检索模式、`CHAIN_APPROX_SIMPLE` 可把矩形轮廓压缩为 4 点：["Structural Analysis and Shape Descriptors"](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html)（OpenCV 4.13.0 文档，访问于 2026-10-19）。
- `approxPolyDP` 用 Douglas–Peucker，`epsilon` 是"原曲线与近似曲线之间的最大距离"——**epsilon 取多大直接决定能否稳定得到 4 个角点**（同上文档）。
- 透视变换 `getPerspectiveTransform` 需要 **4 对**对应点，且"这 4 点中 3 点不能共线"；`warpPerspective` 接受 3×3 矩阵：["Geometric Transformations of Images"](https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html)。
- `minAreaRect` 的输出是旋转矩形，`boxPoints` 给出 4 个顶点，顶点顺序从 y 最大者开始、顺时针——**用它做归一化时必须自己处理"哪个角是左上"**（同上 shape 文档）。

| 维度 | 评估 |
|---|---|
| 输入 | 单帧 BGR 图像（建议固定工位 + 纯色背景） |
| 输出 | 4 个角点 + 拉正后的固定尺寸卡片图（如 200×300） |
| 适用条件 | 卡片与背景对比明显、不严重重叠、不反光；【已验证事实】EdjeElectronics 的 744★ 开源项目明确要求"Cards need to be placed on a dark background"（[README](https://github.com/EdjeElectronics/OpenCV-Playing-Card-Detector)） |
| 报告过的性能 | 官方文档不给精度数字；未找到"扑克牌四边形检测成功率"的同行评议量化来源 → **未找到可靠来源** |
| 实现难度 | 低（OpenCV 现成函数；难点全在阈值/光照工程） |
| 计算资源 | 极低（普通 CPU 单帧 ms 级，【工程推断】） |
| 跨品牌泛化 | 高：几何与印刷内容无关（常见标准扑克牌约 63×89 mm，**以实物实测为准**） |
| 失败模式 | 白卡压白背景、卡堆重叠、镜面反光、弯牌、部分出框、`epsilon` 不当导致角点数 ≠ 4；`minAreaRect` 不建模透视 |

**【工程推断】** 本项目 8 周内不应把"复杂分割"当主战场。更稳的做法是机械工位把牌约束到近似固定位姿，用固定 ROI + 轻量四边形校正；检测失败就以"拒识 + 重拍"处理。

---

### 2.2 模板匹配（OpenCV `matchTemplate`）

**【已验证事实】官方文档原理**（已打开）：模板匹配"把模板图像在输入图像上滑动（类似二维卷积），逐位置比较"，返回一张灰度响应图；输入 `W×H`、模板 `w×h` 时输出尺寸为 `(W-w+1, H-h+1)`；`TM_SQDIFF` 取最小值最优、其余取最大值；多目标时用阈值（例中 0.8）配合 `np.where` 提取（["Template Matching"](https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html)，OpenCV 4.13.0）。

**这套机制天然不具备旋转/尺度/透视不变性**：响应图只在"模板的固定像素排列"上滑窗，模板旋转 90° 或缩放 5% 就不再对齐——这是**从文档描述可直接推出的【工程推断】**，不是文档原话。

**【已验证事实】牌类项目的实际用法**（两条独立工程证据）：

1. EdjeElectronics/OpenCV-Playing-Card-Detector（744★，无 License 声明）：树莓派 + PiCamera/USB 摄像头，先用轮廓找牌，再对"牌角 rank/suit 图"做模板匹配；README 明确写"**The card detector will work best if you use isolated rank and suit images generated from your own cards**"，并提供 `Rank_Suit_Isolator.py` 让你拍自己的牌生成模板（[GitHub README](https://github.com/EdjeElectronics/OpenCV-Playing-Card-Detector)）。
2. Ahmad 2011（arXiv 预印本，非同行评议）：Matlab 两遍法——第一遍检测矩形并与"牌的左右边缘模板"匹配，第二遍把"左上角含点数+花色的小块"与存储的 rank/suit 模板匹配，用 if-then 规则输出；正文自述选择"最简单算法/仅用 Matlab 现成函数"、针对赌场环境（光照好、牌已知），**没有给出量化精度**（[arXiv:1109.3767](https://arxiv.org/abs/1109.3767)，已下载 PDF 读正文）。

| 维度 | 评估 |
|---|---|
| 输入 | 已归一化的角标 ROI（或整卡） |
| 输出 | 52 个模板的相似度得分/最高分类别 |
| 适用条件 | **同一品牌、同一印刷批次、固定光照、固定尺度/角度**；深色背景、无遮挡 |
| 报告过的性能 | 【已验证事实】官方文档示例用 0.8 阈值做多目标提取；**未找到"扑克牌模板匹配 top-1 准确率"的可靠量化来源**（Edje/Ahmad 均未报告系统评测）→ 不写数字 |
| 实现难度 | 低（几十行代码即可跑通） |
| 计算资源 | 低（但是 52 类 × 多尺度会线性膨胀；【工程推断】） |
| 跨品牌泛化 | **差**：模板是像素级的，字体/花色图案/墨色一变，相关系数即失去可比性（见第 4 节证据） |
| 失败模式 | 旋转、尺度、透视、光照/反光、不同品牌字体、牌面污损；`TM_CCORR` 方法在官方示例中"不如预期" |

**结论**：模板匹配适合作**角标定位的后备手段**或"同品牌同批次"的快速基线，**不能作为跨品牌主分类器**。

---

### 2.3 OCR（Tesseract）

**【已验证事实】官方文档的已知边界**（["Improving the quality of the output"](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)，[FAQ](https://tesseract-ocr.github.io/tessdoc/FAQ.html)，均已打开）：

- **分辨率**："Tesseract works best on images which have a DPI of at least 300 dpi"；
- **倾斜**："The quality of Tesseract's line segmentation reduces significantly if a page is too skewed, which severely impacts the quality of the OCR"；
- **小区域/单字**：默认按整页文本做版面分割，"If you're just seeking to OCR a small region, try a different segmentation mode, using the `--psm` argument"；`psm` 列表含 6（单一均匀文本块）、7（单行）、8（单词）、10（单字符）、11（稀疏文本）、13（原始行）等；
- **字符集**：可用 `tessedit_char_whitelist` 限定为数字（如只认 A/2–10/J/Q/K 里的数字）；
- **字体**："unless you're using a very unusual font or a new language, retraining Tesseract is unlikely to help"——反过来说，**非标准/艺术字正是 Tesseract 需要专门处理的场景**；
- **明确不支持**：手写（"won't work very well"）、条码（"No. Tesseract is for text recognition"）。

**套到扑克牌上的问题（【工程推断】+【待验证假设】）**：

1. 牌角点数/字母是**印刷体但非文档字体**（各品牌字形、笔画粗细、装饰差异大），且"10"是两位字符、J/Q/K 是字母；花色符号 ♠♥♦♣ **根本不在 OCR 字符集**里 → OCR 只能解决"点数"，花色必须另找方法。
2. 尺寸：1080p 摄像头看一张 63×88 mm 的牌，若牌约占画面 1/3 宽（约 640 px），牌角字符高度通常只有十几到二十几像素（待实测）——与"≥300 dpi 等效"差距很大（300 dpi 下 3 mm 字符约 35 px）。**必须先把角标 ROI 放大/超分再喂 OCR**。
3. **未找到**任何"用 Tesseract 识别扑克牌并报告准确率"的可靠同行评议来源 → 本文不给 OCR 的牌面准确率数字。

| 维度 | 评估 |
|---|---|
| 输入 | 拉正、放大的角标灰度图（单行或单字符） |
| 输出 | 字符/字符串（点数；花色需另做形状/模板/CNN） |
| 适用条件 | 等效 ≥300 dpi、正向、单行、限定字符集、字体接近训练字体 |
| 报告过的性能 | 仅官方文档的定性边界（见上）；**牌面场景无可靠数字** |
| 实现难度 | 中（调 psm/预处理/字符白名单；但误差不可控） |
| 计算资源 | 低（CPU 可跑） |
| 跨品牌泛化 | 差~中（字体差异是 OCR 的经典弱点，见官方文档"unusual font"表述） |
| 失败模式 | 小字符、模糊、倾斜、反光、艺术字、两位字符、花色缺失 |

**结论**：不推荐作为主分类器；至多作为"数字点数"的**独立校验通道**（psm 10 + whitelist），且需与 CNN/模板结果交叉验证。

---

### 2.4 传统特征：ORB / SIFT / SURF / LBP / GLCM

先明确一句：**这些是"图像相似度 / 纹理描述"工具，不是"同副牌判定"工具**，也不是天然的 52 类分类器。

#### 2.4.1 ORB（Rublee et al., ICCV 2011）

- **【已验证事实】论文存在**：Rublee, Rabaud, Konolige, Bradski, "ORB: An efficient alternative to SIFT or SURF", ICCV 2011, pp. 2564–2571, DOI 10.1109/ICCV.2011.6126544（Crossref + Semantic Scholar 题录核实；**IEEE 正文未取得**，未引用其内部数字）。
- **【已验证事实】OpenCV 官方教程对 ORB 的描述**（已打开）：ORB = FAST 关键点 + Harris 排序 + 图像金字塔 + 强度质心（intensity centroid）方向 + "steered BRIEF"；角度被离散为 `2π/30`（12°）的查表；默认 `nFeatures=500`、匹配用 `NORM_HAMMING`；文档称"SIFT and SURF are patented... But ORB is not"，并称 ORB 适合低功耗设备（["ORB (Oriented FAST and Rotated BRIEF)"](https://docs.opencv.org/4.x/d1/d89/tutorial_py_orb.html)）。
- **没有找到**用 ORB 做"52 类扑克牌点数/花色分类"或"纸张纹理分类"的可靠同行评议来源 → **未找到可靠来源**。
- **【工程推断】** 扑克牌角标区域纹理极稀疏（大面积白底 + 少量笔画），ORB 关键点少且重复度高；ORB 的正确用途是"同一物理对象跨视角配准/验证"，不是类别判别。

#### 2.4.2 SIFT / SURF（简述）

- **【已验证事实】题录**：Lowe, "Distinctive Image Features from Scale-Invariant Keypoints", IJCV 2004, 60(2):91–110, DOI 10.1023/B:VISI.0000029664.99615.94；Bay, Tuytelaars, Van Gool, "SURF: Speeded Up Robust Features", ECCV 2006 (LNCS 3951, pp. 404–417, DOI 10.1007/11744023_32)，期刊版 CVIU 2008, 110(3):346–359, DOI 10.1016/j.cviu.2007.09.014（Crossref 核实）。
- **【已验证事实】** OpenCV 官方文档指出 SIFT/SURF 受专利保护（同上 ORB 教程）→ 工程上应优先选 ORB 或深度模型，**避免 SURF 的许可风险**。
- 两者同样是"关键点+描述子匹配"，不是类别分类器；且计算量明显高于 ORB。

#### 2.4.3 LBP（Ojala et al., TPAMI 2002）

- **【已验证事实】题录**：Ojala, Pietikäinen, Mäenpää, "Multiresolution gray-scale and rotation invariant texture classification with local binary patterns", IEEE TPAMI 2002, 24(7):971–987, DOI 10.1109/TPAMI.2002.1017623（Crossref；**正文未取得**，不引用其内部数字）。
- **【已验证事实】LBP 用于纸张纹理的旁证（仅题录）**：Khaleefah et al., "The ideal effect of Gabor filters and Uniform Local Binary Pattern combinations on deformed scanned paper images", J. King Saud Univ. – Computer and Information Sciences, 2021, 33(10):1219–1230, DOI 10.1016/j.jksuci.2019.07.012，CC BY-NC-ND（Crossref 核实；正文未取得）。
- **【工程推断】** LBP 是"纹理描述子"，适合"纸/布/金属"这类**大面积纹理**；扑克牌正面是印刷图案，纹理信号被油墨与涂层覆盖，用 LBP 区分 52 类牌面没有证据支持。

#### 2.4.4 GLCM（Haralick et al., 1973）

- **【已验证事实】题录**：Haralick, Shanmugam, Dinstein, "Textural Features for Image Classification", IEEE Trans. SMC 1973, SMC-3(6):610–621, DOI 10.1109/TSMC.1973.4309314（Crossref 核实；下载的 PDF 为纯扫描件、无文字层，故未引用正文细节）。
- **【已验证事实】GLCM 用于纸张（不是牌面）的成功证据**：Shang, Kong, You 2011 用 **GLCM + 傅里叶频谱共 114 维特征 + SVM + 分块投票**做"复印纸品牌识别"，21 种纸/19 个品牌、每种 50 张 A4、Epson Perfection 1200 扫描仪 1200 dpi，**当分块 ≥1.5×1.5 cm² 时 21 类准确率接近 100%**；但作者也报告"同一张纸两面纹理太像时类别准确率很低"，并把"未知样本/老化"列为未来工作（[全文](https://scialert.net/fulltext/?doi=itj.2011.2112.2118)，已打开正文）。

| 方法 | 输入/输出 | 适用条件 | 报告性能（带来源） | 难度/资源 | 跨品牌 | 失败模式 |
|---|---|---|---|---|---|---|
| ORB | 图 → 关键点+二进制描述子 | 同对象跨视角匹配、低功耗 | 无牌面分类量化来源 | 低/低 | 不适用（不是分类器） | 白底弱纹理、重复图案、视角外 |
| SIFT/SURF | 图 → 关键点+浮点描述子 | 尺度/旋转不变匹配 | 无牌面分类量化来源；专利风险 | 中/中 | 不适用 | 计算量、专利、弱纹理 |
| LBP | 图 → 纹理直方图 | 大面积纹理分类 | 纸张形变扫描件有题录级旁证（Khaleefah 2021） | 低/低 | 对印刷牌面无证据 | 印刷图案/涂层淹没纹理 |
| GLCM | 图 → 共生矩阵统计量 | 纹理/纸张判别 | 纸张品牌识别近 100%（≥1.5×1.5 cm²、1200 dpi、闭集）（Shang 2011） | 低/低 | 可做"纸"不可做"牌面类别" | 分辨率不足、双面相似、未知类 |

---

### 2.5 轻量深度学习（MobileNetV3 等）

**【已验证事实】MobileNetV3 官方数据**（Howard et al., ICCV 2019, pp. 1314–1324，[CVF 开放获取页](https://openaccess.thecvf.com/content_ICCV_2019/html/Howard_Searching_for_MobileNetV3_ICCV_2019_paper.html)，已打开）：

- MobileNetV3-Large 相比 MobileNetV2：ImageNet 分类**准确率高 3.2%**，同时**延迟降低 20%**；
- MobileNetV3-Small 相比同等延迟的 MobileNetV2：**准确率高 6.6%**；
- MobileNetV3-Large 检测（COCO）在精度大致相同时**快 25% 以上**；
- 设计目标是手机 CPU，采用硬件感知 NAS + NetAdapt。

**【已验证事实】牌类检测/分类的工程证据：**

1. **YOLOv4 + 自动生成数据集（Wzorek & Kryjak, arXiv:2109.11861，已读正文）**：为桥牌转播做牌检测。数据生成流程：把单张真牌放在纯色背景上拍 30 秒视频（两盏灯改变位置/强度/颜色）→ 把牌合成到 **DTD 纹理数据集（5640 张纹理图）**背景上，随机数量/位置/旋转角度并自动标注 → 生成任意规模数据集。**YOLOv4 在该生成数据上"cards detection task 效率 99.8%"**（作者原文措辞为 "efficiency of 99.8%"，未明确是 mAP 还是准确率，引用时需保留这一歧义）。
2. **YOLOv8 + 合成/真实双数据集（TeogopK/Playing-Cards-Object-Detection，GitHub README + GitHub API 元数据，已打开）**：合成数据集 **20,000 张、52 类**（转自 Kaggle andy8744 数据集）；"真实"数据集仅 **100 张、13 类**（作者自拍自标）；训练记录（RTX A2000 8GB）：20k 合成 ×10 epochs = **2 小时**；100 张真实 ×100 epochs = **20 分钟**；100 真实 + 1000 增强/合成 ×100 epochs = **50 分钟**；数据集 CC0，仓库带实时摄像头 demo。
3. **合成数据生成开源工具（geaxgx/playing-card-detection，443★，MIT，GitHub API + README 已确认）**：README 说明用 notebook 生成带标注的扑克牌数据集（标注 52 类名称如 "2s"、"Kh" 与牌角包围框），被用于其 YOLOv3 项目。

| 维度 | 评估 |
|---|---|
| 输入 | 归一化后的角标 ROI（如 64×64 / 96×96）或整卡缩略图 |
| 输出 | 52 类概率（或 13 点数 + 4 花色两路输出） |
| 适用条件 | 有代表本副牌的标注数据；训练时覆盖光照/角度/背景变化 |
| 报告过的性能 | 【已验证事实】MobileNetV3 在 ImageNet/COCO 的相对提升（见上）；YOLOv4 牌检测 99.8%（自建合成数据，指标定义有歧义）；**未找到"两副混合实体牌、104 张全检"这一具体任务的公开准确率** → 不得编造 |
| 实现难度 | 中（数据采集/标注 > 模型代码） |
| 计算资源 | 训练：有 GPU 更现实（官方项目用 RTX A2000 8GB；20k 图 10 epochs ≈ 2 h）；纯 CPU 训练很慢但**推理**完全够用（【工程推断】，需实测） |
| 跨品牌泛化 | 中~好于模板/OCR，但**取决于训练数据是否覆盖目标品牌**（见第 4 节） |
| 失败模式 | 域偏移（合成→真实）、小样本过拟合、反光/遮挡/运动模糊、类别不平衡、置信度校准差 |

**小样本/数据增强可行性【工程推断】**：本项目只有 104 张实体牌（52 类 × 2）。可用的合法扩增：旋转（4×90° + 小角度）、缩放、透视、亮度/色温、背景替换、模糊/JPEG 压缩、局部遮挡。104 张 ×（4 方向 × 多种增强）可得到数千~数万训练块，配合在 ImageNet 上预训练的 MobileNetV3-Small 微调，是 8 周内最现实的路线；**但必须留出"未参与训练的实拍照片"作为验证集**，否则数字不可信。

---

## 3. 物理指纹 / 实例级识别专项（重点论证"为什么不做"）

> 本节结论先行：**纸张/传感器指纹可以识别"哪一张纸 / 哪一台相机"，但没有可靠证据表明它能识别"两张牌属于同一副牌"；而且其采集条件（1200 dpi 平板扫描或背光透射）与本项目 1000 元预算、普通摄像头、8 周的约束冲突。**

### 3.1 纸张表面指纹：Clarkson et al.（IEEE S&P 2009 / 2012 博士论文）

- **【已验证事实】会议论文确实存在**：Clarkson, Weyrich, Finkelstein, Heninger, Halderman, Felten, "Fingerprinting Blank Paper Using Commodity Scanners", **IEEE S&P 2009, pp. 301–314, DOI 10.1109/SP.2009.7**（Crossref 核实；IEEE 正文页被拦截；Semantic Scholar 显示出版方屏蔽了 abstract）。
- **【已验证事实】本文所用方法与数字来自同一作者的公开博士论文全文**：W. B. Clarkson, *Breaking Assumptions: Distinguishing Between Seemingly Identical Items Using Cheap Sensors*, Princeton University PhD dissertation, June 2012（[TR-921-12 PDF](https://www.cs.princeton.edu/techreports/2012/921.pdf)，已下载并用 pypdf 提取正文）。其中第 3 章标题即 "Fingerprinting Blank Paper Using Commodity Scanners"，是会议论文的扩展版。**注意**：两版数字可能略有差异，本文数字归属 2012 论文。

**方法与实验条件（【已验证事实】，论文正文）**：

- 设备：**Epson Perfection v700 平板扫描仪，1200 DPI**；测试区域为页面中心 **3×3 英寸**；
- 采集：每份文档做 **4 次扫描（0°/90°/180°/270°）**，利用扫描仪线光源方向不同来估计纸张表面法线（3D 纹理）；
- 指纹：**3200 bit** 特征向量，配 LDPC 纠错码做容错匹配；
- 样本：5 份文档 × 5 次观测 = 25 次观测，多种纸（复印纸、索引卡、信纸）。

**报告的性能（【已验证事实】，均出自该论文正文）**：

- 理想条件：同一文档两次观测的指纹平均汉明距离 **99 bit / 3200（3.1%），std 24.29**；不同文档之间平均 **1600 bit（50%），std 33.42**；
- 用维度 k=1000、N=3200 的 LDPC 码："**correctly verify all test documents, with no false positives**"；较不理想条件下 k=300/N=3200 仍可"**correctly verify 95% of all test documents, with no false positives**"；
- 非理想处理（涂抹、**印刷 12pt Times New Roman 覆盖约 13% 面积**、浸水）：同文档平均汉明距离升至约 **562–570 bit（17.6%–17.8%）**，不同文档仍约 **1600 bit（50%）**，分布仍可分；涂抹实验中判定阈值取 1130 bit 错误时，论文给出假阳/假阴概率约 **1 in 10^47**（基于分布尾部估计）；
- 章节小结原话：该方法"robust against rough treatment — such as printing or scribbling on the document or soaking it in water"，"Under normal conditions ... identify documents with near-perfect accuracy and a negligible false positive rate"。

**为什么不能直接搬来做扑克牌（【工程推断】+【待验证假设】）**：

1. **分辨率算术**：1200 dpi × 3 英寸 = **3600×3600 像素**。1080p 摄像头整帧只有 1920×1080，等效 1200 dpi 时只能覆盖约 1.6×0.9 英寸；即便只看牌面 63×88 mm，也需要单帧约 3000×4200 像素——**普通 USB 摄像头做不到**。
2. **采集方式**：需要"扫描仪移动线光源 + 4 个角度"这一特定几何；普通摄像头 + 环形光无法复现。
3. **介质**：扑克牌是**双面印刷 + 表面涂层/压纹**的卡纸，纸纤维被油墨与涂层覆盖，与"空白复印纸"差异极大；Clarkson 的"13% 油墨覆盖"实验远小于扑克牌接近 100% 的双面印刷覆盖率 → **【待验证假设】纸纹在扑克牌上可能根本不成立**。验证方法：借一台 1200 dpi 扫描仪，取 2 张同副/不同副的牌，各扫 2 次，按上述汉明距离思路对比（半天可完成）。

> 尺寸换算：1200 dpi 下，一张常见扑克牌（约 63×89 mm = 2.5×3.5 in，**以实物实测为准**）单面就需要约 **3000×4200 像素**才能达到 Clarkson 论文的分辨率。

### 3.2 透射纹理指纹：Toreini et al.（ACM TOPS 2017）

**【已验证事实】论文与数据**（arXiv 全文已下载阅读；题录经 Semantic Scholar 核实：ACM Transactions on Privacy and Security, 2017, DOI 10.1145/3092816；[arXiv:1705.02510](https://arxiv.org/abs/1705.02510)）：

- 方法：**把光源放在纸的一侧、用普通相机从另一侧拍照**，利用纸的**透射纹理**（木纤维随机交织造成的厚度/杂质不均）生成 **2048 bit** 指纹；用 Gabor 变换 + 纠错编码 + 分数汉明距离比较；
- 性能：**0% false rejection、0% false acceptance**（基于其采集数据集）；指纹含 **807 个自由度（DoF）**，对比同尺寸虹膜码的 249 DoF；
- 鲁棒性（论文自述）：对**旋转、更换光源、揉皱、浸水、加热、涂写**等非理想条件仍可用；
- 论文明确对比：Clarkson 的方法"必须从四个不同角度做多次扫描"，而本方法"**只需一张照片**"。

**对我们的意义（【工程推断】）**：这是目前"用普通相机做纸张指纹"最有力的证据，但它仍然：
1. 需要**背光透射**装置（光源在纸后），不是普通反光拍摄；
2. 解决的是"**识别某一特定纸张**"（enrollment + 1:N 匹配），不是"判断两张牌同属一副"；
3. 扑克牌为多层复合卡纸 + 黑芯 + 涂层，**透光性很可能不足** → 【待验证假设】，验证方法同上（手机手电筒从背面照一张牌，看是否能拍到纤维纹理，10 分钟即可证伪/证实）。

### 3.3 纸纹做品牌/批次判别：Shang et al. 2011（已读全文）

- **【已验证事实】** 21 种纸、19 个品牌、每种 50 张 A4；Epson Perfection 1200 @1200 dpi；每张纸切 2×2=4 块 → 每类 200 个样本；双面视为 42 个纹理类；**GLCM + 傅里叶特征共 114 维**；SVM 分类；按块投票出最终品牌；
- **【已验证事实】** "classification accuracy is close to 100% for 21 types of paper when the block size is greater than or equal to **1.5×1.5 cm²**"；块越小越差；
- **【已验证事实】** 失败条件：某些纸**两面的纹理结构太相似**（如 TANGO Blueness Sword、FORERUNNER、ACEPRINT、Double A），正反面会被互相误判；
- **【已验证事实】** 作者把"**未知样本（不在训练集里的品牌）**"和"纸张老化导致的纹理变化"列为**未来工作**——即该方法当时只做了**闭集分类**；
- **【已验证事实】** 全文使用的是"品牌"标签，**没有任何"同一副牌/同一批次"级别的实验**。

**推论【工程推断】**：纸纹可以区分"品牌"（粗粒度、闭集、需要 1200 dpi 与 ≥1.5 cm² 区域），但"同品牌不同副/不同批次"的区分难度远高于品牌区分，未见任何量化证据。**"同副牌"不是一个可测量的物理标签**，只是"同一包装内一起出厂"这一社会事实，物理上并不留下可靠标记。

### 3.4 相机传感器 PRNU（为什么更不相关）

**【已验证事实】题录**（Crossref 核实，正文未取得，不引用其内部数字）：

- Lukáš, Fridrich, Goljan, "Digital Camera Identification From Sensor Pattern Noise", IEEE TIFS 2006, 1(2):205–214, DOI 10.1109/TIFS.2006.873602；
- Chen, Fridrich, Goljan, Lukáš, "Determining Image Origin and Integrity Using Sensor Noise", IEEE TIFS 2008, 3(1):74–90, DOI 10.1109/TIFS.2007.916285。

**【已验证事实】PRNU 的鲁棒性/攻击面**（Martín-Rodríguez, arXiv:2102.09444，已下载读正文；**预印本，未核实同行评议 venue**）：

- 攻击类别包括：**加噪/改最低有效位（LSB）或 DCT 系数**、**几何攻击（像素打乱、旋转后再转回、缩放插值）**、**降噪（Wiener 滤波，含小波域实现）**、以及组合攻击；
- 评价用 PCE（Peak to Correlation Energy）与混淆矩阵错误率；4 台相机时随机识别正确率 25%（错误率 75% 才算成功攻击），6 台时对应 83%；
- 测试集：自建 4 台相机（Canon EOS 1100D、Sony A5000、Canon PowerShot SX710、Huawei P20 lite）80 张 + Dresden Image Database 36 张/6 台。

**【已验证事实】PRNU 的"唯一性"也有反例（仅摘要级）**：

- arXiv:2510.09509 "Diagonal Artifacts in Samsung Images: PRNU Challenges and Solutions"（2025）：多款 Galaxy S 机型因共同处理伪影导致**指纹碰撞**；
- arXiv:2009.04878 "A leak in PRNU based source identification. Questioning fingerprint uniqueness"（2020）：现代计算摄影的设备内处理会引入**非唯一伪影**，削弱 PRNU 区分度。

**对本项目的结论【工程推断】**：PRNU 是**相机**的指纹，不是纸/牌的指纹。它既不能回答"这张牌属于哪一副"，又对压缩、旋转、降噪敏感（见上攻击面），**完全不适合本任务**。

### 3.5 印刷/裁切的随机性、纸纹、纤维纹理作为"同厂同批"特征

- **已找到的证据**：纸张制造过程产生随机纤维纹理，可用于**单张纸**的身份识别（Clarkson 2012；Toreini 2017）；纸纹可用于**品牌级**分类（Shang 2011）。
- **未找到的证据**：**没有找到**任何论文/数据集给出"用印刷网点、裁切偏差、纸纹判断两张扑克牌是否同一副/同一批次"的准确率或可辨识性分析 → **未找到可靠来源**。原因（【工程推断】）：同一批次内这些随机量的**类内方差**可能大于"同副"与"不同副"之间的**类间差异**；且扑克牌双面满版印刷+涂层使纸纹几乎不可见。

### 3.6 必须讲清的区别：「同一张牌重复拍摄可匹配」≠「判断两张牌同属一副牌」

| 对比项 | 同一张牌重复拍摄可匹配（verification） | 判断两张牌同属一副（open-set 分组） |
|---|---|---|
| 参考数据 | 有：先给该牌建档（enrollment），再比对 | **无参考库**；"同副"没有模板 |
| 决策类型 | 1:1 或 1:N 闭集 | 无标签聚类/开集判别 |
| 信号强度 | 纸纹/透射纹理/PRNU 都有强个体特征（Clarkson：同文档 3.1% vs 不同文档 50% 汉明距离） | "同副"信号来自生产批次+包装，**物理上未被证明可测** |
| 干扰因素 | 光照/角度/压缩（可通过受控采集缓解） | 同批噪声：同品牌同批纸张的纸纹统计分布相近（Shang：双面相似即误判） |
| 失败后果 | 认错一张牌 | 整组分组错误，且**无法从数据上发现** |

**【工程推断】** 因此，即使团队愿意投入扫描仪/背光装置做"每张牌指纹建档"，也只能解决"这张牌是不是我之前见过的那张牌"，**不能解决"这两张牌原本在同一副里"**——后者在物理上不是可观测标签。项目定义"不需要判断牌原本来自哪一副"是**唯一正确的工程选择**。

### 3.7 LBP / GLCM / ORB 做纸张纹理区分的实际证据与失败条件

| 方法 | 证据 | 失败条件 |
|---|---|---|
| GLCM | **【已验证事实】** Shang 2011：GLCM+Fourier 114 维 + SVM，21 类纸张品牌 ≥1.5×1.5 cm² 时接近 100%（1200 dpi、闭集） | 分辨率不足、区域太小、双面纹理相似、未知品牌（作者列为未来工作） |
| LBP | **【仅题录】** Ojala 2002（旋转不变多分辨率纹理分类）；Khaleefah 2021 用 Gabor+ULBP 处理"形变扫描纸张图像"（正文未取得） | 印刷图案/涂层覆盖纸纹；形变/光照变化；无"同副"证据 |
| ORB | **未找到可靠来源**用于纸张纹理或纸牌实例识别 | 白底弱纹理、关键点稀疏且重复、对尺度/模糊敏感 |

---

## 4. 跨品牌泛化

### 4.1 已找到的实际证据

1. **【已验证事实】模板匹配项目要求"用你自己的牌生成模板"**：EdjeElectronics/OpenCV-Playing-Card-Detector README 原文——"The card detector will work best if you use isolated rank and suit images generated from your own cards"，并提供拍摄自家牌生成模板的脚本（[GitHub](https://github.com/EdjeElectronics/OpenCV-Playing-Card-Detector)）。这是"模板对品牌/字体敏感"的最直接工程证据。
2. **【已验证事实】真实数据稀缺且"牌组特定"**：TeogopK 项目 20,000 张合成数据是 52 类，但"真实"数据只有 **100 张、13 类**（作者自己的牌），必须靠 fine-tune 才能在实时摄像头上工作（[GitHub](https://github.com/TeogopK/Playing-Cards-Object-Detection)，README + API 元数据已核实）。
3. **【已验证事实】合成数据必须"按目标牌的外观"录制**：桥牌 YOLOv4 论文明确用**真牌**拍 30 秒视频（改变光照角度/强度/颜色）再合成到 DTD 纹理背景上，才得到 99.8% 的检测效率——说明模型外观分布由**训练时的那副牌**决定（[arXiv:2109.11861](https://arxiv.org/abs/2109.11861)，已读正文）。
4. **【已验证事实】字体是 OCR 的已知弱点**：Tesseract 官方文档以"very unusual font"作为需要特殊处理的例外（[ImproveQuality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)）。
5. **【已验证事实】不同纸/不同面都有可测差异**：Shang 2011 显示同一张纸正反两面纹理相似都会导致误判（42 类 → 忽略正反面后准确率上升）——说明"外观差异小"是这类任务的普遍困难。

### 4.2 未找到的部分（必须说明）

- **没有找到**任何同行评议论文或公开竞赛，直接量化"同一模型在不同品牌扑克牌之间的准确率下降幅度"→ **未找到可靠来源**。
- **没有找到**覆盖多品牌、带品牌标注的公开扑克牌分类数据集（现有公开数据集要么是合成渲染，要么是单一牌组实拍）。

### 4.3 对本项目的直接影响【工程推断】

- 如果**两副牌是同一品牌同一型号**（最可能的情况）：模板匹配/OCR/CNN 的品牌风险都低，甚至模板匹配可作基线；
- 如果**两副牌品牌不同**（字体、花色图案、纸张、涂层都不同）：**模板匹配基本不可用**，OCR 风险高，必须用"两副牌都采样训练"的 CNN，并让验证集包含两副牌各自的实拍；
- 因此**第 1 周就要确认两副牌的品牌/型号**，这决定后续路线（这一条应作为项目风险项立刻确认）。

---

## 5. 结论表与推荐组合

### 5.1 方法落地性总表（8 周 / 1000 元 / 普通电脑 / 经验有限）

| 方法 | 8 周可落地性 | 额外成本 | 推荐度 | 主要依据 | 备注 |
|---|---|---|---|---|---|
| 轮廓 + 四边形 + 透视归一化 | **高** | 0 | ★★★★★ 必做 | OpenCV 官方文档提供全套函数 | 固定工位 > 复杂分割 |
| 角标 ROI 定位（Rank-Suit 角） | **高** | 0 | ★★★★★ 必做 | 牌面几何标准化（标准牌约 2.5:3.5，角标位置固定，需实测标定） | 配合归一化使用 |
| 轻量 CNN（MobileNetV3-Small 微调 / 小型自定义 CNN） | **中高** | 0（用现有电脑/免费算力） | ★★★★★ 主分类器 | MobileNetV3 官方效率数据；牌类 YOLO 工程证据 | 数据采集是主要工作量 |
| 置信度拒识 + 组合计数约束 | **高** | 0 | ★★★★★ 必做 | 104 张牌"每种恰好 2 张"的强先验 | 把错误变可检测 |
| 模板匹配 | 中 | 0 | ★★☆ 仅辅助/基线 | OpenCV 文档原理；Edje 项目实践 | 仅同品牌固定光照 |
| OCR（Tesseract） | 低~中 | 0 | ★☆ 不推荐主用 | 官方文档：300 dpi、倾斜、单行 psm、非常用字体 | 花色无法 OCR |
| ORB / SIFT / SURF | 低 | 0 | ✗ 不推荐 | 它们是匹配/配准工具，不是分类器；SURF 有专利 | 可用于多帧配准 |
| LBP / GLCM | 低 | 0 | ✗ 不用于牌面类别 | 仅纸张纹理有证据（Shang 2011） | 可作为研究性实验 |
| 纸张表面指纹（Clarkson） | **低** | 需 1200 dpi 扫描仪 | ✗ 不做 | 需 4 角度扫描、3600×3600 px；卡片双面印刷+涂层 | 与预算/时间冲突 |
| 透射纹理指纹（Toreini） | **低** | 需背光装置 | ✗ 不做 | 需背光透射；扑克牌透光性未知 | 可做 10 分钟预实验证伪 |
| 相机 PRNU | 低 | 0 | ✗ 不做 | 识别相机而非纸/牌；对压缩/旋转敏感 | 与本任务无关 |

### 5.2 推荐流水线（角标 ROI + 轻量 CNN + 置信度拒识 + 计数约束）

```
[机械上料/静置]
   ↓
1) 采集：固定工位 + 漫射光 + 纯色背景（深色），1080p USB 摄像头
   ↓
2) 检测：灰度/阈值 → findContours → approxPolyDP(四边形, ε 自适应)
         → 面积/长宽比（按实测牌面比例，标准牌约 2.5:3.5）过滤
         → getPerspectiveTransform → 拉正为 200×300
   ↓
3) 角标 ROI：按实测牌面几何裁左上/右下两个 Rank-Suit 角（比例按实物标定，不写死 mm）
   ↓
4) 分类：裁剪 ROI → resize 64×64 → MobileNetV3-Small（52 类，或 13+4 双头）
         旋转 4×90° 中取最高置信度（或先检测角标朝向）
   ↓
5) 拒识：softmax 置信度 < 阈值、或 4 个方向最高分差距过小 → 判"不确定"
   ↓
6) 组合约束：统计 52 类计数，要求每类 = 2；不满足 → 标记可疑牌重拍/人工复核
   ↓
7) 分组：从 104 张中按计数约束拆成两组各 52 张（若两副同品牌，分组在物理上不可区分，
         只需输出"任意一组满足 52 张完整"的分组即可）
```

**关于第 7 步的重要提示【工程推断】**：若两副牌完全同品牌同型号，则"哪张属于哪副"**在物理上不可区分**——分拣的唯一可验证目标是"两组各自构成完整 52 张"，而不是恢复原始归属。这与题目定义一致，应在报告中明确写出。

### 5.3 8 周实施建议（算法侧）

| 周 | 目标 | 交付物 |
|---|---|---|
| W1 | 确认两副牌品牌/型号；搭固定工位；跑通轮廓+透视归一化 | 归一化后的 104 张牌图像 |
| W2 | 角标 ROI 自动裁剪 + 人工抽检；确定标注规范（52 类） | 数据集 v1（真实 104 张 ×4 方向 + 增广） |
| W3 | 训练 MobileNetV3-Small 基线；建立训练/验证"按物理牌划分"的协议 | top-1/混淆矩阵基线 |
| W4 | 加合成/增强数据；误差分析（哪些类易混：6/9、♠/♣、红/黑） | 改进模型 v2 |
| W5 | 置信度拒识阈值标定（用验证集 ROC/PR）+ 计数约束模块 | 拒识率 vs 错误率曲线 |
| W6 | 与机械/电气联调：拍照→识别→下料闭环；异常恢复（重拍） | 端到端 demo |
| W7 | 104 张全流程反复测试（≥20 轮）；记录失败模式 | 测试报告 |
| W8 | 参数冻结、复现实验、写报告 | 最终数据 |

### 5.4 关键验收指标（本项目自定目标，非文献事实）

- 单张 top-1 准确率（在"未参与训练的实拍"上）：目标 ≥99%（需实测，不能引用他人数字）；
- 104 张整组正确率（含拒识重拍）：目标 100%（靠组合约束兜底）；
- 平均单张识别耗时（普通 CPU）：目标 <100 ms（【待验证假设】）；
- 拒识率：目标 <5%（过高的拒识率会让节拍不可接受）。

---

## 6. 来源清单

> 核实状态说明：`已打开正文` = 本次实际下载并阅读 PDF/HTML/GitHub 内容；`仅摘要/元数据` = 通过 Crossref / Semantic Scholar / arXiv API / 官方摘要页确认题录；`仅搜索结果` = 只确认存在。**没有任何一条来源是凭记忆写出的。**

| # | 标题 | 作者 / 机构 | 年份 | venue | 链接 | 支持的具体结论 | 核实状态 |
|---|---|---|---|---|---|---|---|
| 1 | Fingerprinting Blank Paper Using Commodity Scanners | Clarkson, Weyrich, Finkelstein, Heninger, Halderman, Felten | 2009 | IEEE S&P 2009, pp. 301–314 | https://doi.org/10.1109/SP.2009.7 | 论文存在、题录、页码；该会议版是 #2 的先前版本 | 仅元数据（IEEE 正文被拦截，HTTP 202 空页） |
| 2 | Breaking Assumptions: Distinguishing Between Seemingly Identical Items Using Cheap Sensors（博士论文，第 3 章即上题） | William Banks Clarkson / Princeton University | 2012 | Princeton CS TR-921-12 | https://www.cs.princeton.edu/techreports/2012/921.pdf | 1200 dpi、3×3 in、4 角度扫描、3200 bit 指纹；同文档汉明距离 99/3200（3.1%，std 24.29），不同文档 1600（50%，std 33.42）；k=1000 全对无误报、k=300 达 95%；印刷 13% 油墨/涂抹/浸水后仍可分 | 已打开正文（PDF + pypdf 提取） |
| 3 | Texture to the Rescue: Practical Paper Fingerprinting based on Texture Patterns | Toreini, Shahandashti, Hao | 2017 | ACM Transactions on Privacy and Security, DOI 10.1145/3092816 | https://arxiv.org/abs/1705.02510 | 背光透射 + 普通相机单张照片；2048 bit；0% FRR / 0% FAR；807 DoF（虹膜 249）；对旋转/换光源/揉皱/浸水/加热/涂写鲁棒；对比 Clarkson 需 4 次扫描 | 已打开正文（arXiv PDF） |
| 4 | Copy Paper Brand Source Identification using Commodity Scanners | Shang, Kong, You | 2011 | Information Technology Journal 10(11):2112–2118 | https://scialert.net/fulltext/?doi=itj.2011.2112.2118 | 21 种纸/19 品牌；Epson Perfection 1200@1200 dpi；GLCM+傅里叶 114 维+SVM+投票；块 ≥1.5×1.5 cm² 时准确率接近 100%；双面相似时误判；未知样本列为未来工作 | 已打开正文 |
| 5 | ORB: An Efficient Alternative to SIFT or SURF | Rublee, Rabaud, Konolige, Bradski | 2011 | ICCV 2011, pp. 2564–2571 | https://doi.org/10.1109/ICCV.2011.6126544 | 论文存在与题录（未引用正文数字） | 仅元数据（IEEE 正文未取得） |
| 6 | OpenCV: ORB (Oriented FAST and Rotated BRIEF) | OpenCV 官方文档 | 4.13.0 | docs.opencv.org | https://docs.opencv.org/4.x/d1/d89/tutorial_py_orb.html | ORB=FAST+Harris+金字塔+强度质心+steered BRIEF；角度离散 12°；默认 500 特征；SIFT/SURF 有专利、ORB 无；适合低功耗设备 | 已打开正文（官方文档） |
| 7 | Distinctive Image Features from Scale-Invariant Keypoints | Lowe | 2004 | IJCV 60(2):91–110 | https://doi.org/10.1023/B:VISI.0000029664.99615.94 | SIFT 论文存在与题录 | 仅元数据（Crossref） |
| 8 | SURF: Speeded Up Robust Features（会议版 + 期刊版） | Bay, Tuytelaars, Van Gool | 2006 / 2008 | ECCV 2006 LNCS 3951:404–417；CVIU 110(3):346–359 | https://doi.org/10.1007/11744023_32 ；https://doi.org/10.1016/j.cviu.2007.09.014 | SURF 论文存在与题录 | 仅元数据（Crossref） |
| 9 | Multiresolution gray-scale and rotation invariant texture classification with local binary patterns | Ojala, Pietikäinen, Mäenpää | 2002 | IEEE TPAMI 24(7):971–987 | https://doi.org/10.1109/TPAMI.2002.1017623 | LBP 论文存在与题录（旋转不变多分辨率纹理分类主题） | 仅元数据（Crossref） |
| 10 | Textural Features for Image Classification | Haralick, Shanmugam, Dinstein | 1973 | IEEE Trans. SMC 3(6):610–621 | https://doi.org/10.1109/TSMC.1973.4309314 | GLCM/纹理特征论文存在与题录 | 仅元数据（Crossref；PDF 为无文字层扫描件） |
| 11 | The ideal effect of Gabor filters and Uniform Local Binary Pattern combinations on deformed scanned paper images | Khaleefah, Mostafa, Mustapha, Nasrudin | 2021 | J. King Saud Univ.–CIS 33(10):1219–1230 | https://doi.org/10.1016/j.jksuci.2019.07.012 | Gabor+ULBP 用于形变扫描纸张图像的题录存在（CC BY-NC-ND） | 仅元数据（Crossref） |
| 12 | Searching for MobileNetV3 | Howard, Sandler, Chu, et al. / Google | 2019 | ICCV 2019, pp. 1314–1324 | https://openaccess.thecvf.com/content_ICCV_2019/html/Howard_Searching_for_MobileNetV3_ICCV_2019_paper.html | Large 比 V2 准确率 +3.2% 且延迟 −20%；Small 同延迟下 +6.6%；检测 COCO 同精度快 >25% | 已打开正文（CVF 摘要页） |
| 13 | OpenCV: Template Matching | OpenCV 官方文档 | 4.13.0 | docs.opencv.org | https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html | 模板滑窗原理；输出尺寸 (W−w+1, H−h+1)；6 种方法；SQDIFF 取最小；多目标阈值示例 0.8；TM_CCORR 效果差 | 已打开正文（官方文档） |
| 14 | OpenCV: Structural Analysis and Shape Descriptors | OpenCV 官方文档 | 4.13.0 | docs.opencv.org | https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html | findContours/approxPolyDP(Douglas–Peucker, ε 为最大偏差)/minAreaRect/boxPoints/contourArea 的官方定义 | 已打开正文（官方文档） |
| 15 | OpenCV: Geometric Transformations of Images | OpenCV 官方文档 | 4.13.0 | docs.opencv.org | https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html | getPerspectiveTransform 需 4 对点、3 点不共线；warpPerspective 用 3×3 矩阵；warpAffine 用 2×3 | 已打开正文（官方文档） |
| 16 | Tesseract: Improving the quality of the output | Tesseract 官方文档 | 当前版 | tessdoc | https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html | ≥300 dpi；倾斜严重损害行分割；psm 列表（6/7/8/10/11/13）；char_whitelist；非常用字体需特殊处理 | 已打开正文（官方文档） |
| 17 | Tesseract FAQ | Tesseract 官方文档 | 当前版 | tessdoc | https://tesseract-ocr.github.io/tessdoc/FAQ.html | 不支持手写与条码；多线程/速度参数；OCR 效果依赖输入质量 | 已打开正文（官方文档） |
| 18 | Training dataset generation for automatic registration of a duplicate bridge game | Wzorek, Kryjak / AGH | 2021 | arXiv:2109.11861 | https://arxiv.org/abs/2109.11861 | 真牌 30 s 视频（两灯变角度/强度/颜色）+ DTD 5640 纹理背景合成 + 自动标注；YOLOv4 在牌检测任务"efficiency 99.8%"（指标措辞有歧义） | 已打开正文（arXiv PDF） |
| 19 | Generalised Object Detection and Semantic Analysis: Casino Example using Matlab | Othman Ahmad / UMS | 2011 | arXiv:1109.3767 | https://arxiv.org/abs/1109.3767 | 两遍法：矩形检测+边缘模板；再对左上角 rank/suit 块做模板匹配 + if-then；面向赌场良好光照、牌已知；无量化精度 | 已打开正文（arXiv PDF） |
| 20 | Playing-Cards-Object-Detection（YOLOv8 项目 + 数据集） | Teodor Kostadinov（TeogopK） | 2024–2026 | GitHub | https://github.com/TeogopK/Playing-Cards-Object-Detection | 合成 20,000 张/52 类（转自 Kaggle andy8744）；真实仅 100 张/13 类；训练时间（RTX A2000 8GB）：2 h/20 min/40 min/50 min；数据 CC0；含实时摄像头 demo | 已打开正文（README + GitHub API 元数据） |
| 21 | playing-card-detection（合成数据集生成 + YOLO v3） | geaxgx | 2019–2026 | GitHub（MIT） | https://github.com/geaxgx/playing-card-detection | 443★；notebook 生成带 52 类标注的扑克牌数据集（"2s"/"Kh" 及牌角框），用于 YOLOv3 项目 | 已打开正文（README + GitHub API 元数据） |
| 22 | OpenCV-Playing-Card-Detector（树莓派实拍） | EdjeElectronics | 2017–2026 | GitHub（无 License） | https://github.com/EdjeElectronics/OpenCV-Playing-Card-Detector | 744★；PiCamera/USB 摄像头；需深色背景；"用你自己牌生成的 rank/suit 模板效果最好"；提供模板隔离脚本 | 已打开正文（README + GitHub API 元数据） |
| 23 | Digital Camera Identification From Sensor Pattern Noise | Lukáš, Fridrich, Goljan | 2006 | IEEE TIFS 1(2):205–214 | https://doi.org/10.1109/TIFS.2006.873602 | PRNU 相机指纹论文存在与题录（未引用正文数字） | 仅元数据（Crossref） |
| 24 | Determining Image Origin and Integrity Using Sensor Noise | Chen, Fridrich, Goljan, Lukáš | 2008 | IEEE TIFS 3(1):74–90 | https://doi.org/10.1109/TIFS.2007.916285 | PRNU 用于来源取证/篡改检测的论文存在与题录 | 仅元数据（Crossref） |
| 25 | Testing Robustness of Camera Fingerprint (PRNU) Detectors | Fernando Martín-Rodríguez / Univ. of Vigo | 2021 | arXiv:2102.09444（预印本） | https://arxiv.org/abs/2102.09444 | 攻击面：LSB/DCT 加噪、几何（旋转/打乱/缩放）、Wiener 降噪、组合；PCE+混淆矩阵错误率；4 台相机随机基线 25%、6 台 83% | 已打开正文（arXiv PDF） |
| 26 | Diagonal Artifacts in Samsung Images: PRNU Challenges and Solutions | （arXiv 作者） | 2025 | arXiv:2510.09509 | https://arxiv.org/abs/2510.09509 | 多款 Galaxy S 存在共同伪影导致 PRNU 指纹碰撞 | 仅摘要（arXiv API） |
| 27 | A leak in PRNU based source identification. Questioning fingerprint uniqueness | （arXiv 作者） | 2020 | arXiv:2009.04878 | https://arxiv.org/abs/2009.04878 | 计算摄影处理引入非唯一伪影，削弱 PRNU 唯一性 | 仅摘要（arXiv API） |

**来源统计**：共 27 条，其中 `已打开正文` 15 条（含官方文档 6 条、论文/预印本 7 条、GitHub 3 条），`仅元数据/摘要` 12 条；覆盖 OpenCV/Tesseract 官方文档、4 篇经典论文原文/题录、纸张指纹 3 项独立研究、PRNU 4 条、扑克牌工程实现 3 个开源项目。满足"≥12 条可核实来源"。

---

## 7. 未核实事项、冲突与局限

### 7.1 未能核实 / 未取得正文

1. **IEEE Xplore 正文全部无法打开**（`ieeexplore.ieee.org/document/5207652` 返回 HTTP 202 空页）。因此 ORB 2011、Lukas 2006、Chen 2008、LBP 2002、Haralick 1973 均只核到题录，本文**不引用这些论文正文中的任何数字**。
2. **Clarkson 2009 会议版正文未取得**。第 3.1 节的方法与全部数字来自同一作者的 **2012 博士论文**（开放获取）。两者选题相同、后者更详细，但**具体数值可能有版本差异**；引用时应写明"据 2012 论文"。
3. **Tesseract FAQ-old 页面已 404**（`FAQ-Old.html`），"最小/最大可识别字号"的原始条目未能直接核到；本文关于小字体的判断为【工程推断】，并标注了 300 dpi 的官方表述作为依据。
4. **Kaggle 数据集页面未直接打开**（Kaggle 需要登录/JS）。TeogopK README 中"20,000 张/52 类，转自 Kaggle andy8744"属于**二手转述**，已标注来源为 README，而非 Kaggle 官方页。
5. **ORB 论文正文数字（如"比 SIFT 快两个数量级"）未核实**，本文未使用。
6. **桥牌论文的 "99.8% efficiency" 指标定义不明**（mAP？准确率？检测召回？），引用时保留了原文措辞歧义，不作为"分类准确率"使用。
7. **本地检索环境限制**：Google/Bing/DuckDuckGo 在本机不可用或返回无关结果（Bing 返回被改写的结果、DDG DNS 失败、Mojeek 403）；检索主要依赖任务提供的 web_search、arXiv API、Crossref API、Semantic Scholar API、GitHub API 与直接抓取。这记录在此以便复核。

### 7.2 来源之间的潜在冲突/差异（已处理）

- **Clarkson（表面纹理，需 4 次扫描）vs Toreini（透射纹理，单张照片）**：Toreini 论文正文明确指出 Clarkson 方法"需要从四个角度多次扫描"，而自己的方法只需一张照片。两者并不矛盾，是**不同物理信号（表面 vs 透射）**的差异；Toreini 声称透射信号更可靠（0% FRR/FAR、807 DoF），但那是其自建数据集上的结果，且需要背光装置。
- **Shang 2011（品牌近 100%）vs "纸纹不能判同副"**：不矛盾。品牌是**闭集粗分类**，同副是**开集细粒度**问题，且 Shang 自己把"未知样本"列为未来工作、并报告了双面相似导致的误判。

### 7.3 本调研的局限

- **未做任何本地实验**：本文没有训练模型、没有采集扑克牌图像、没有测过任何准确率/耗时；所有性能均为"引用"或"推断"。
- **未评估具体硬件型号/价格**：预算 1000 元内的相机、光源、扫描仪选型属于硬件调研范围，本文只给出"是否需要额外设备"的判断。
- **未找到的关键证据**（影响结论强度，需在报告中如实写出）：
  1. 没有"跨品牌扑克牌识别精度下降"的量化研究；
  2. 没有"扑克牌点数/花色 OCR"的可靠精度研究；
  3. 没有"同副牌/同批次"物理可辨识性研究；
  4. 没有"104 张实体牌混合分拣"这一完整任务的公开基准。

### 7.4 建议立即做的 3 个低成本验证实验（半天内可完成，直接决定技术路线）

| 实验 | 方法 | 判定 |
|---|---|---|
| E1 纸纹可行性 | 借 1200 dpi 扫描仪，扫同一张牌 2 次 + 不同牌各 2 次，看差异图是否有稳定纹理 | 若纹理被油墨/涂层完全掩盖 → 彻底放弃物理指纹 |
| E2 透光可行性 | 手机手电筒从牌背照，正面拍照看是否可见纤维/厚度纹理 | 不可见 → 放弃 Toreini 路线 |
| E3 角标可读性 | 固定工位 1080p 拍摄，裁角标并放大，测字符像素高度；用现成 OCR 试跑 | 字符 <20 px 或 OCR 大量失败 → 必须用 CNN/模板，不能靠 OCR |

---

## 8. 一句话总结

> 在"8 周 / 1000 元 / 普通电脑 / 经验有限 / 两副牌背相同"的约束下，**唯一值得投入的路线是"几何归一化 + 角标 ROI + 轻量 CNN（MobileNetV3-Small 微调）+ 置信度拒识 + 52 类计数约束"**；模板匹配只能做同品牌基线，OCR 只能做辅助校验，ORB/SIFT/SURF/LBP/GLCM 是匹配/纹理工具而非分类器，纸张指纹/透射纹理/PRNU 这类实例级物理指纹**在原理上解决的不是本项目的问题，在工程上也与预算和时间冲突**（Clarkson 需 1200 dpi + 4 角度扫描；Toreini 需背光装置；PRNU 识别的是相机）。题目"不需要判断牌原本来自哪一副"不是妥协，而是把不可解问题删除后的正确工程定义。
