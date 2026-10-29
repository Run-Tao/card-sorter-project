# 附录

## 附录 A 来源清单

> 核实状态：**已打开正文** = 实际打开并阅读了 PDF/HTML/官方文档；**仅题录/摘要** = 通过 Crossref/arXiv/官方摘要页确认存在，未引用正文数字；**搜索/商品页** = 仅确认商品与价格区间，采购前需复核。完整清单见 `research/algorithms.md`、`research/hardware-bom.md`、`research/mechanical.md`。

### A.1 官方文档与一手规格

| # | 来源 | 年份 | 链接 | 支持的结论 | 核实状态 |
|---|---|---|---|---|---|
| 1 | OpenCV: VideoCapture Class Reference | 4.x | https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html | 相机属性、FOURCC、自动曝光/对焦属性可能被驱动重新解释 | 已打开正文 |
| 2 | OpenCV: Template Matching | 4.x | https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html | 模板滑窗原理、输出尺寸、6 种匹配方法 | 已打开正文 |
| 3 | OpenCV: Structural Analysis and Shape Descriptors | 4.x | https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html | findContours/approxPolyDP/minAreaRect 定义 | 已打开正文 |
| 4 | OpenCV: Geometric Transformations | 4.x | https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html | 透视变换需 4 对点、3 点不共线 | 已打开正文 |
| 5 | OpenCV: ORB | 4.x | https://docs.opencv.org/4.x/d1/d89/tutorial_py_orb.html | ORB=FAST+Harris+金字塔+steered BRIEF；SIFT/SURF 有专利、ORB 无 | 已打开正文 |
| 6 | Tesseract: Improving the quality of the output | 当前版 | https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html | ≥300 dpi、倾斜损害行分割、psm/白名单 | 已打开正文 |
| 7 | Tesseract FAQ | 当前版 | https://tesseract-ocr.github.io/tessdoc/FAQ.html | 不支持手写/条码；效果依赖输入质量 | 已打开正文 |
| 8 | ESP-IDF GPIO (ESP32-S3) | v5.5.2 | https://docs.espressif.com/projects/esp-idf/en/v5.5.2/esp32s3/api-reference/peripherals/gpio.html | S3 GPIO 数量与占用 | 已打开正文 |
| 9 | Arduino-ESP32 LEDC | 当前版 | https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html | ESP32 16 路 / S3 8 路 PWM | 已打开正文 |
| 10 | espressif/esp32-camera | 当前版 | https://github.com/espressif/esp32-camera | OV2640 上限 1600×1200；PSRAM 要求；YUV/RGB 易丢数据 | 已打开正文 |
| 11 | Raspberry Pi: Price increases for 2GB Pi 4/Pi 5 | 2026-10-01 | https://www.raspberrypi.com/news/price-increases-for-2gb-raspberry-pi-4-and-raspberry-pi-5/ | Pi 5 2GB 涨至 $77.50、Pi 4 2GB $67.50 | 已打开正文 |
| 12 | Raspberry Pi: 1GB Pi 5 at $45, memory-driven rises | 2025-12-01 | https://www.raspberrypi.com/news/1gb-raspberry-pi-5-now-available-at-45-and-memory-driven-price-rises/ | Pi 5 价格上调背景 | 已打开正文 |
| 13 | pySerial: Short introduction | 当前版 | https://pyserial.readthedocs.io/en/latest/shortintro.html | 串口打开、超时、list_ports | 已打开正文 |
| 14 | Pololu #2214 100:1 gearmotor specs | 当前版 | https://www.pololu.com/product/2214/specs | 310 rpm 空载、1.7 kg·cm 堵转 | 已打开正文 |
| 15 | Waveshare OV2710 USB camera | 当前版 | https://www.waveshare.com/product/modules/cameras-audio-video/ov2710-2mp-usb-camera-a.htm | 1/2.7" 靶面、145° DFOV、1080p | 已打开正文 |
| 16 | Astariglas 亚克力资料 | 2023 | https://astariglas.com/uploads/product-1201384217_20230418084558.pdf | 透光率约 92% | 已打开正文 |
| 17 | microsonic dbk+4 数据表 | 2026-10-17 | https://www.microsonic.de/en/sensordetail/dbk+4-3BEE-M18%20E+S/pdf | 超声双张传感器规格（工业件，超预算） | 已打开正文 |
| 18 | Engineering ToolBox: Friction Coefficients | 2004 | https://www.engineeringtoolbox.com/friction-coefficients_d_778.html | 橡胶-硬纸板 μ 0.5–0.8 | 已打开正文 |
| 19 | Condair: Printing humidification | 2026 | https://www.condair.ae/applications/industrial-manufacturing-humidification/printing-humidification-humidity-humidifier | 45–55% RH；<40% 起静电 | 已打开正文 |
| 20 | Wikipedia: Standard 52-card deck | 2026 访问 | https://en.wikipedia.org/wiki/Standard_52-card_deck | 各品牌尺寸；厚度/克重无统一规格 | 已打开正文 |

### A.2 论文与学术来源

| # | 来源 | 年份 | 链接 | 支持的结论 | 核实状态 |
|---|---|---|---|---|---|
| 21 | Clarkson et al., Fingerprinting Blank Paper Using Commodity Scanners | 2009 | https://doi.org/10.1109/SP.2009.7 | 论文存在；会议版正文被 IEEE 拦截 | 仅题录 |
| 22 | Clarkson, Breaking Assumptions（Princeton TR-921，第 3 章即上题扩展版） | 2012 | https://www.cs.princeton.edu/techreports/2012/921.pdf | 1200 dpi、4 角度、3200 bit；同文档 99/3200 vs 不同文档 1600/3200；k=1000 全对无误报 | 已打开正文 |
| 23 | Toreini et al., Texture to the Rescue（ACM TOPS） | 2017 | https://arxiv.org/abs/1705.02510 | 背光透射 + 单张照片；2048 bit；0% FRR/FAR（自建数据集） | 已打开正文 |
| 24 | Shang et al., Copy Paper Brand Source Identification | 2011 | https://scialert.net/fulltext/?doi=itj.2011.2112.2118 | 1200 dpi + GLCM/傅里叶 114 维 + SVM；21 类品牌近 100%；双面相似误判 | 已打开正文 |
| 25 | Howard et al., Searching for MobileNetV3 | 2019 | https://openaccess.thecvf.com/content_ICCV_2019/html/Howard_Searching_for_MobileNetV3_ICCV_2019_paper.html | Large 比 V2 +3.2% 准确率、−20% 延迟；Small 同延迟 +6.6% | 已打开正文 |
| 26 | Rublee et al., ORB: An Efficient Alternative to SIFT or SURF | 2011 | https://doi.org/10.1109/ICCV.2011.6126544 | 题录（未引用正文数字） | 仅题录 |
| 27 | Ojala et al., Multiresolution Gray-Scale and Rotation Invariant LBP | 2002 | https://doi.org/10.1109/TPAMI.2002.1017623 | 题录 | 仅题录 |
| 28 | Haralick et al., Textural Features for Image Classification | 1973 | https://doi.org/10.1109/TSMC.1973.4309314 | GLCM 题录 | 仅题录 |
| 29 | Lukáš et al., Digital Camera Identification From Sensor Pattern Noise | 2006 | https://doi.org/10.1109/TIFS.2006.873602 | PRNU 是相机指纹 | 仅题录 |
| 30 | Chen et al., Determining Image Origin and Integrity Using Sensor Noise | 2008 | https://doi.org/10.1109/TIFS.2007.916285 | PRNU 用于来源取证 | 仅题录 |
| 31 | Martín-Rodríguez, Testing Robustness of PRNU Detectors | 2021 | https://arxiv.org/abs/2102.09444 | PRNU 对压缩/几何/去噪敏感 | 已打开正文 |
| 32 | Wzorek & Kryjak, Training dataset generation for duplicate bridge | 2021 | https://arxiv.org/abs/2109.11861 | 真牌视频 + 纹理合成自动数据集；YOLOv4 牌检测（指标定义有歧义） | 已打开正文 |

### A.3 开源项目、专利与商品来源

| # | 来源 | 类型 | 链接 | 用途 |
|---|---|---|---|---|
| 33 | TeogopK/Playing-Cards-Object-Detection | 开源（CC0 数据） | https://github.com/TeogopK/Playing-Cards-Object-Detection | 合成 20,000 张/52 类；真实仅 100 张/13 类；数据采集是主要工作量 |
| 34 | geaxgx/playing-card-detection | 开源（MIT） | https://github.com/geaxgx/playing-card-detection | 52 类合成数据集生成 + YOLO v3 |
| 35 | EdjeElectronics/OpenCV-Playing-Card-Detector | 开源 | https://github.com/EdjeElectronics/OpenCV-Playing-Card-Detector | 同品牌模板匹配基线；需深色背景 |
| 36 | BBG TCG Sorter | 开源社区（AGPLv3） | https://itsn80.github.io/bbg-tcg-sorter/ | DIY 分卡机：步进送牌 + 舵机翻板 + IR |
| 37 | Canon US20080309001A1 | 专利 | https://patents.google.com/patent/US20080309001A1/en | 分离垫弹簧压力"降噪 vs 双张"两难 |
| 38 | Seiko Epson US20110236113A1 | 专利 | https://patents.google.com/patent/US20110236113A1/en | 高摩擦垫、倾斜面分离、取纸轮抬起/释放 |
| 39 | Murata US20030047860A1 | 专利 | https://patents.google.com/patent/US20030047860A1/en | 延迟辊 + 扭矩限制器 |
| 40 | Nisca US7425001B2 | 专利 | https://patents.google.com/patent/US7425001B2/en | 超声双张检测 + 对齐辊 loop |
| 41 | Fuji Xerox JP5354454B2 | 专利 | https://patents.google.com/patent/JP5354454B2/en | 辊位移测厚 → 双张检测 |
| 42 | GRG Huitong EP3021260A1 | 专利 | https://patents.google.com/patent/EP3021260A1/en | 重力自适应浮动分卡 |
| 43 | 深圳天腾 CN223956082U | 专利 | https://patents.google.com/patent/CN223956082U/en | 分卡通道间距 ≥1 张且 <2 张卡厚 |
| 44 | iCEasy 树莓派品牌页 | 商品页 | https://www.iceasy.com/brand/7490 | Pi 4B 4GB 标价 ¥590（库存 0 需询价） |
| 45 | DFRobot 28BYJ-48 驱动模块 | 商品页 | https://www.dfrobot.com.cn/search.php?keywords=28BYJ-48 | ¥40（品牌溢价参考） |
| 46 | 米思米 2020 铝型材 | 商品页 | https://www.misumi.com.cn/pr/vona/mech/arumi201907/ | ¥14.44/米起（未税） |
| 47 | 汇率 API（2026-10-19） | 数据 | https://open.er-api.com/v6/latest/USD | USD→CNY 6.6927 |

**未找到可靠来源的问题（必须在报告中如实写出）**：
1. 没有"跨品牌扑克牌识别精度下降"的量化研究；
2. 没有"扑克牌点数/花色 OCR"的可靠精度研究；
3. 没有"同副牌/同批次"物理可辨识性研究；
4. 没有"104 张实体牌混合分拣"这一完整任务的公开基准；
5. 淘宝/京东实时到手价无法批量核实（页面反爬），BOM 中约一半为区间估算。

## 附录 B 术语表

| 术语 | 含义 |
|---|---|
| 牌面类别（class） | 52 种（点数 × 花色）之一 |
| 多重集（multiset） | 允许重复元素的集合；本项目中"每类恰好 2 张" |
| 静默错误（silent error） | 系统给出错误结果且未察觉 |
| 拒识（reject） | 系统主动拒绝给出类别，转入复核 |
| 覆盖率（coverage） | 1 − 拒识率，即被接受样本的比例 |
| Top-1 准确率 | 排名第一的预测正确的比例 |
| FMR / FNMR / EER | 误匹配率 / 漏匹配率 / 等错误率 |
| 留出品牌（held-out brand） | 完全不参与训练、只用于测试的品牌 |
| 数据泄漏 | 同一实例/同一来源同时出现在训练与测试中，导致评估虚高 |
| 停机拍摄（stop-and-scan） | 牌停稳后再曝光，避免运动模糊与卷帘畸变 |
| 角标 ROI | 牌角"点数 + 花色"所在的小区域 |
| 透视校正 | 用 4 对点把倾斜拍摄的牌面变换到标准矩形 |
| PRNU | 相机传感器光响应非均匀性，是"相机指纹"不是"纸指纹" |
| 纸纹/透射指纹 | 纸张纤维/厚度的随机纹理，用于纸张个体识别 |
| 双张（double feed） | 一次进牌进入两张或以上 |
| 卡牌（jam） | 牌在纸路中卡住 |
| 端到端成功率 | 一次完整运行"两组都完整"的比例 |
| 失效安全（fail-safe） | 故障时进入安全状态（停机、拒识、不输出错误结果） |

## 附录 C 默认参数（config.yaml 建议初值）

```yaml
camera:
  index_top: 0
  index_bottom: 1
  backend: DSHOW
  fourcc: MJPG
  width: 1920
  height: 1080
  fps: 15
  autofocus: 0
  auto_exposure: 0.25     # 不同后端语义不同，必须读回验证
  lock_white_balance: true

geometry:
  fov_width_mm: 180.0     # 16:9 推荐；4:3 可用 130
  fov_height_mm: 101.3
  rectify_width: 600
  rectify_height: 840
  corner_roi_tl: [8, 8, 120, 150]      # x1,y1,x2,y2（校正后）
  corner_roi_br_rotated: true
  bottom_mirror: true

classifier:
  model: rank_suit.onnx
  input_size: 96
  frames_per_capture: 3
  tau_high: 0.98          # 需在验证集上校准
  tau_low: 0.80
  template_fallback: true
  vote: majority

decision:
  expected_total: 104
  expected_per_class: 2
  classes: 52
  reject_group: REVIEW

motion:
  feed_speed_mm_s: 100
  feed_timeout_ms: 5000
  at_scan_timeout_ms: 3000
  divert_timeout_ms: 2000
  eject_timeout_ms: 4000
  steps_per_mm: 40.8      # NEMA17 200 步 ×16 细分 / (π×25 mm)，以实测为准

serial:
  port: AUTO              # 按 VID/PID 枚举，不写死 COM3
  baud: 115200
  heartbeat_ms: 500
  heartbeat_timeout_ms: 2000
  retries: 3

logging:
  run_root: runs/
  save_images: true
  save_frames: 3
```

## 附录 D 检查清单

### D.1 采购到货检查
- [ ] ESP32-S3 能被 esptool 识别，Flash/PSRAM 容量与标称一致；
- [ ] 两个相机都能在 OpenCV 中读到 1920×1080，FOURCC 读回为 MJPG；
- [ ] 相机手动对焦/曝光可锁定（读回值验证）；
- [ ] 电源空载 12V，带载压降 <5%；
- [ ] 舵机独立供电，堵转不导致 ESP32 复位；
- [ ] 传感器 5V 输出经电平转换后接 ESP32。

### D.2 装配检查
- [ ] 牌仓内高 36 mm，104 张可放入且压板行程足够；
- [ ] 限高唇口可换 0.35/0.45/0.55 mm 垫片；
- [ ] 导槽单边间隙 0.3–0.5 mm 可调；
- [ ] 双轮同轴，无单边驱动；
- [ ] 扫描窗平整、无划痕，可 30 s 拆换；
- [ ] 掀盖能释放分离垫；断电可手动反转取牌；
- [ ] 滑槽断电靠自重回 B 盒。

### D.3 调试检查（第 2 周）
- [ ] 单张进牌 ≥95%，双张 ≤5%，卡牌 ≤2%；
- [ ] 偏斜 ≤3°；
- [ ] 停位重复性 ±1 mm；
- [ ] 角标字符 ≥50 px；
- [ ] 3 种光照下图像质量可接受。

### D.4 答辩前检查
- [ ] 连续 3 次 104 张运行记录完整；
- [ ] 异常演示（缺牌/多牌/王/双张/低置信）各 1 次；
- [ ] 视频备份可播放；
- [ ] BOM 实际支出与预算对比表；
- [ ] 所有性能数字有测试方法、样本量、置信区间；
- [ ] 报告中"目标值/实测值"标注清楚。

## 附录 E 变更记录与文件清单

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1 | 2026-10-19 | 完成问题定义、算法比较、BOM、机械、软件、计划、测试、MVP、答辩框架 |
| v1.0 | 2026-10-19 | 合并三份调研（算法 27 源、硬件 BOM、机械 27 源）、生成 4 张图与 BOM 表、统一预算与参数 |
| v1.1 | 2026-10-19 | 按独立审查修改：验收目标改为概率自洽（0.04%/0.2%、全自动 ≥50%）、整叠校验防"假 PASS"、REVIEW 物理路径、H3 改为同品牌两副、节拍口径统一、BOM 补镜头/分离垫/5 副牌（956 元）、工时与降级表重算 |

**工程文件结构**：

```
card-sorter-project/
├─ report/
│  ├─ 无标记扑克牌自动分拣机_工程实施方案.md / .docx
│  ├─ BOM_预算表.xlsx
│  ├─ sections/           # 分节源文件（可单独修改）
│  └─ figures/            # 架构图、状态机、机械布局、乘积效应
├─ research/
│  ├─ algorithms.md       # 算法/文献调研（27 源）
│  ├─ hardware-bom.md     # 硬件/价格调研
│  └─ mechanical.md       # 机械/专利/计算调研（27 源）
└─ tools/
   ├─ make_figures.py
   └─ make_bom_xlsx.py
```

**说明**：`report/sections/` 是分节源文件，修改后重新合并即可更新主报告；`tools/` 中的脚本可复现图表与 BOM 表。`research/` 下的三份调研是**过程稿**，保留原始检索与核实状态；若其中个别表述（如早期版本的价格、相机视场、电机选型）与主报告冲突，**以主报告为准**。
