# 8. 软件模块、状态机与关键伪代码

> 本章给出可以直接照着写的结构。原则：**状态机显式化、每步有超时、每步有确认、异常不吞掉、数据全部落盘**。代码示例为 Python 风格伪代码，不追求可直接运行，但保留关键参数与接口。

## 8.1 软件设计目标

1. 主流程必须与题目要求的 `WAIT_CARD → FEED → DETECT → CLASSIFY → ASSIGN → DIVERT → VERIFY` 一一对应；
2. 任一状态都可以因超时/传感器异常/通信异常进入 `ERROR` 或 `PAUSE`，并支持人工恢复；
3. 每张牌的结果、图像、置信度、分配、异常原因必须可追溯；
4. 视觉模块可离线运行（用历史图像回放），不依赖机械；
5. 机械模块可脱离视觉运行（用固定测试标签），不依赖模型；
6. 代码规模控制在初学者可维护的范围：单进程、显式状态机、配置文件、无框架。

## 8.2 上位机主状态机

### 8.2.1 状态定义

| 状态 | 进入条件 | 动作 | 退出条件 | 超时/异常 |
|---|---|---|---|---|
| `IDLE` | 启动/复位 | 自检、加载配置、等待开始 | 用户点"开始"且有牌 | 自检失败 → `ERROR` |
| `WAIT_CARD` | 上一张完成 | 检查 S1 有牌、S3 无牌 | S1 有牌且 S3 空 | 无牌 30 s → 提示 |
| `FEED` | 发 FEED | 等待 ESP32 的 `AT_SCAN` 事件 | `AT_SCAN` | 5 s → `ERROR(E01)` |
| `DETECT` | 收到 `AT_SCAN` | 抓 6 帧、检测牌面/质量 | 检测成功 | 重试 2 次 → `REVIEW`/`ERROR` |
| `CLASSIFY` | 检测成功 | 两侧分类、多帧投票、置信度 | 置信度 ≥ τ | 低置信 → 重拍 1 次 → `REVIEW` |
| `ASSIGN` | 分类成功 | 查计数表，决定 A/B/REJECT | 得到分配 | 第三次出现 → `ANOMALY` |
| `DIVERT` | 分配完成 | 发 DIVERT，等舵机+出口传感器 | `DONE` | 4 s → `ERROR(E04/E05)` |
| `VERIFY` | 收到 `DONE` | 校验传感器状态、写日志、计数自增 | 记录成功 | 传感器矛盾 → `ERROR` |
| `PAUSE` | 用户/异常 | 停运动、保存现场 | 用户继续/放弃 | 超过 10 min → 建议结束 |
| `REVIEW` | 拒识/冲突 | 先由 `step_review` 把牌送复核盒，再入离线复核队列 | 人工补录/跳过 | — |
| `ERROR` | 任一错误 | 停运动、蜂鸣、记录、提示 | 人工复位 | — |
| `DONE` | 104 张处理完 | 整叠校验、输出报告 | — | — |

> 说明：题目中的 `VERIFY` 在这里实现为**两层**：单张 `VERIFY`（传感器确认这张牌确实离开且进入正确出口）+ 整叠 `VERIFY_RUN`（52 维计数校验与异常报告）。两层都必须有。

### 8.2.2 状态转移图

![主状态机](figures/fig_state_machine.png){width=100%}

```
                 ┌──────────── 自检失败 ─────────────┐
                 ▼                                   │
  ┌──────┐  开始  ┌───────────┐  S1有牌  ┌──────┐   │
  │ IDLE │──────->│ WAIT_CARD │────────->│ FEED │   │
  └──────┘       └───────────┘         └──┬───┘   │
      ▲                                   │AT_SCAN│
      │                                   ▼       │
      │                              ┌────────┐   │
      │                              │ DETECT │<-──┤ 重试
      │                              └───┬────┘   │
      │                                  │成功     │
      │                                  ▼         │
      │                              ┌──────────┐  │
      │                              │ CLASSIFY │  │
      │                              └───┬──────┘  │
      │                         低置信/冲突│         │
      │                                  ▼         │
      │                              ┌────────┐    │
      │                              │ REVIEW │────┘
      │                              └────────┘
      │                                  │成功
      │                                  ▼
      │                              ┌────────┐
      │                              │ ASSIGN │
      │                              └───┬────┘
      │                                  ▼
      │                              ┌────────┐  超时/堵转
      │                              │ DIVERT │──────────-> ERROR
      │                              └───┬────┘
      │                                  ▼
      │                              ┌────────┐
      │                              │ VERIFY │
      │                              └───┬────┘
      │                                  │ 还有牌
      └──────────────────────────────────┘
                                         │ 104张结束
                                         ▼
                                    ┌────────────┐
                                    │ VERIFY_RUN │
                                    └────────────┘
```

### 8.2.3 状态机伪代码

```python
class Sorter:
    def __init__(self, cfg, cameras, link, store):
        self.state = "IDLE"
        self.counts = {c: 0 for c in ALL_CLASSES}   # 已提交的 52 维计数
        self.pending = {c: 0 for c in ALL_CLASSES}  # 在途预占（已决定去向、未确认入盒）
        self.records = []                            # 已确认入组的每张牌
        self.review_queue = []                       # 拒识/冲突牌（实体在复核盒）
        self.inflight = None                         # 当前在途牌
        self.run_id = new_run_id()

    def processed_total(self):
        return len(self.records) + len(self.review_queue) + (1 if self.inflight else 0)

    def run(self):
        self.self_test()
        self.state = "WAIT_CARD"
        while self.state != "DONE":
            try:
                if self.state == "WAIT_CARD":  self.step_wait_card()
                elif self.state == "FEED":     self.step_feed()
                elif self.state == "DETECT":   self.step_detect()
                elif self.state == "CLASSIFY": self.step_classify()
                elif self.state == "ASSIGN":   self.step_assign()
                elif self.state == "DIVERT":   self.step_divert()
                elif self.state == "REVIEW":   self.step_review()
                elif self.state == "VERIFY":   self.step_verify()
                elif self.state == "VERIFY_RUN": self.verify_run()
                elif self.state == "PAUSE":    self.step_pause()
                elif self.state == "ERROR":    self.step_error()
            except TimeoutError as e:
                self.enter_error("TIMEOUT", str(e))
            except SerialDisconnected as e:
                self.enter_error("COMM", str(e))
            except EstopActive:
                self.enter_error("ESTOP", "急停被按下")
```

## 8.3 每个状态的实现要点

### 8.3.1 WAIT_CARD

```python
def step_wait_card(self):
    st = self.link.get_status()                    # 读传感器位图
    if st.estop:      raise EstopActive()
    if not st.s1_has_card:
        self.ui.show("请在牌仓放牌")
        return
    if st.s3_at_scan:  # 扫描位残留一张牌：必须送复核盒并记账，不能静默 eject
        self.anomalies.append(("RESIDUAL", "S3", now()))
        self.link.divert(2); self.link.eject(); self.link.wait_done(timeout=4)
        self.ui.show("扫描位残留牌已送复核盒，请检查上一张记录")
    self.state = "FEED"

def step_feed(self):
    self.link.feed(timeout_ms=5000)                # 命令下发
    ev = self.link.wait_event("AT_SCAN", timeout=5.0)
    self.t_card_at_scan = ev.timestamp
    self.state = "DETECT"
```

### 8.3.2 DETECT

```python
def step_detect(self):
    imgs = self.cameras.capture_both(frames=3)     # 上下各 3 帧
    best = None
    for side in ("top", "bottom"):
        for img in imgs[side]:
            q = quality_check(img)                 # 亮度、清晰度、过曝比例
            if not q.ok:
                continue
            card = detect_card(img)                # 四边形 + 透视校正
            if card is None:
                continue
            if best is None or card.score > best.score:
                best = card
                best.side = side
                best.image = img
    if best is None:
        self.retry_or_review("DETECT_FAIL")
        return
    self.card = best
    self.state = "CLASSIFY"
```

### 8.3.3 CLASSIFY（双面 + 多帧投票）

```python
def step_classify(self):
    results = []
    for frame in self.frames:                      # 每次运行 3 帧
        r = classify_sides(frame.top, frame.bottom) # 内部处理镜像/旋转
        results.append(r)
    vote = majority_vote(results, key=lambda r: r.label)
    p = calibrated_confidence(results, vote.label)
    if p < TAU_HIGH:
        self.recapture += 1
        if self.recapture <= 1:
            self.state = "DETECT"                  # 换曝光再拍一次
            return
        self.card.pred = vote.label
        self.card.status = "REVIEW_LOW_CONF"
        self.state = "REVIEW"                      # 先由 step_review 送复核盒，再入队
        return
    self.card.pred = vote.label
    self.card.confidence = p
    self.state = "ASSIGN"
```

**关键细节**：
- 下相机图像先水平镜像，再走与上相机相同的"两角标 + 180° 旋转"流程；
- 上下两侧都分类，取联合置信度高的一侧；若两侧都有一条读得通但结果不同，记 `SIDE_CONFLICT`，进复核；
- 多帧投票用"标签"投票，平票时取置信度最高者；平票且置信度接近 → 复核；
- **类外检测**：52 类 softmax 不会输出"大小王/广告牌"这一选项。在 52 类之前加一级"是否标准牌面"门：检查牌的长宽比、角标几何、牌背图案一致性；不通过直接进复核，避免王被高置信分到某个 52 类里。
- `p_joint = p_rank × p_suit` 是独立性假设下的乘积，**需要在验证集上单独校准**（温度缩放/直方图），不能直接用两个头的校准参数相乘。

### 8.3.4 ASSIGN

```python
def step_assign(self):
    label = self.card.pred                       # e.g. "7H"
    # 已提交计数 + 在途预占，避免"分流出错但计数已加"的假 PASS
    n = self.counts[label] + self.pending.get(label, 0)
    if n == 0:
        self.card.group = "A"
    elif n == 1:
        self.card.group = "B"
    else:
        self.card.group = "REJECT"
        self.card.status = "E2_OVERFLOW"
        self.anomalies.append(("E2", label, self.card.index))
    if self.card.group != "REJECT":
        self.pending[label] = self.pending.get(label, 0) + 1
    self.inflight = self.card
    self.state = "DIVERT"
```

> 注意：拒识牌不参与计数，因此最终 `counts` 不满足全 2 时会触发整叠异常；这是有意的——系统不会假装完整。
>
> **预占—提交**：`pending` 是"已决定去向、但尚未确认入盒"的牌；只有 `VERIFY` 成功才把它提交到 `counts` 并写入 `records`。若 DIVERT/VERIFY 失败，`enter_error` 会把 `pending` 回滚，避免"牌还在路上、计数已加"。
>
> 分配规则本身保证"A/B 每组每类至多一张"（每类第 3 张直接进异常），但 `verify_run` 仍会显式检查组大小与组内成员。

### 8.3.5 DIVERT

```python
def step_divert(self):
    target = {"A": 0, "B": 1, "REJECT": 2}[self.card.group]
    self.link.divert(target, timeout_ms=3000)
    self.link.eject(timeout_ms=4000)
    self.link.wait_done(timeout=4.0)
    self.state = "VERIFY"
```

### 8.3.5.1 REVIEW（拒识牌先物理送复核盒）

```python
def step_review(self):
    """低置信/冲突牌：先送复核盒，再加入离线复核队列。"""
    self.link.divert(2)
    self.link.eject(timeout_ms=4000)
    self.link.wait_done(timeout=4.0)
    self.card.group = "REJECT"
    self.store.append(self.card)                   # 图像与预测一并留档
    self.review_queue.append(self.card)
    self.inflight = None
    if self.processed_total() >= 104:
        self.state = "VERIFY_RUN"
    else:
        self.state = "WAIT_CARD"
```

> 人工补录是**离线动作**：操作员在界面上为复核盒中的牌指定正确牌面与目标组，系统只更新记录与计数；实体牌由人放回对应收纳盒。补录不会让机器"假装"这张牌已经被自动分拣。

### 8.3.6 VERIFY

```python
def step_verify(self):
    st = self.link.get_status()
    if st.s3_at_scan or st.s2_blocked:
        raise RuntimeError("卡片未离开扫描位")
    if not st.s4_exit_pulse_seen:
        raise RuntimeError("出口传感器未确认")
    self.card.timestamp = now()
    # 提交预占：只有确认入盒后才计入 counts
    if self.card.group in ("A", "B"):
        self.counts[self.card.pred] += 1
        self.pending[self.card.pred] -= 1
    self.records.append(self.card)
    self.store.append(self.card)                   # 立即落盘（崩溃安全）
    self.inflight = None
    self.retry = 0
    if self.processed_total() >= 104:
        self.state = "VERIFY_RUN"
    else:
        self.state = "WAIT_CARD"
```

> `processed_total() = len(records) + len(review_queue) + (1 if inflight else 0)`，保证 104 张不会重复计数。

### 8.3.7 整叠校验

```python
def verify_run(self):
    n_total = self.processed_total()
    missing = [c for c, n in self.counts.items() if n == 0]
    extra   = [c for c, n in self.counts.items() if n >= 3]
    bad     = [c for c, n in self.counts.items() if n not in (0, 2)]

    # 唯一的 PASS 条件：A/B 各 52 张、每组每类恰好 1 张、counts 全为 2
    members = {"A": [], "B": []}
    for r in self.records:
        if r.group in members:
            members[r.group].append(r.pred)
    group_dup, group_missing = {}, {}
    for g in ("A", "B"):
        seen = {}
        for c in members[g]:
            seen[c] = seen.get(c, 0) + 1
        group_dup[g] = [c for c, n in seen.items() if n > 1]
        group_missing[g] = [c for c in ALL_CLASSES if seen.get(c, 0) != 1]
    sizes = {g: len(members[g]) for g in members}

    ok = (n_total == 104
          and sizes["A"] == 52 and sizes["B"] == 52
          and not missing and not extra and not bad
          and not any(group_dup.values())
          and not any(group_missing.values())
          and not self.review_queue and not self.anomalies)
    report = {
        "run_id": self.run_id, "total": n_total, "counts": self.counts,
        "group_sizes": sizes, "group_dup": group_dup, "group_missing": group_missing,
        "missing": missing, "extra": extra,
        "review": len(self.review_queue), "anomalies": self.anomalies,
        "verdict": "PASS" if ok else "ANOMALY",
    }
    self.store.write_summary(report)
    self.ui.show_report(report)
    self.state = "DONE" if ok else "PAUSE"
```

> 这段校验是"假 PASS"的最后一道防线：即使 `counts` 全为 2，只要 A/B 组大小不是 52/52 或某组缺/重一张，就判 ANOMALY。

### 8.3.8 异常、暂停与人工恢复

```python
def enter_error(self, kind, detail):
    self.link.stop()                               # 立即停
    self.link.set_output(buzzer=True, led="red")
    # 回滚在途预占：牌没确认入盒，就不能占着 counts
    if self.inflight and self.inflight.group in ("A", "B"):
        self.pending[self.inflight.pred] -= 1
    self.store.event("ERROR", kind=kind, detail=detail, state=self.state,
                     card=self.inflight, pending=dict(self.pending))
    self.ui.show_error(kind, detail)
    self.state = "ERROR"

def resume_from_error(self):
    st = self.link.get_status()
    if st.estop:              raise RuntimeError("请先复位急停")
    if st.card_in_path:
        self.ui.show("请人工取出卡住的牌；若牌面可辨认，请放回复核队列")
        self.inflight.status = "JAM_REMOVED"
        self.store.append(self.inflight)           # 留档，不占 counts
        self.review_queue.append(self.inflight)
        self.inflight = None
    self.link.home()
    self.state = "WAIT_CARD"

def manual_complete(self, card_index, label, group):
    """人工复核：指定正确牌面与目标组；实体牌由操作员放回对应盒。"""
    rec = self.card_by_index(card_index)
    if group not in ("A", "B"):
        raise ValueError("group 必须是 A 或 B")
    rec.pred, rec.group, rec.status, rec.manual = label, group, "MANUAL", True
    self.review_queue.remove(rec)
    self.records.append(rec)                       # 必须进入分组成员表
    self.counts[label] += 1
    self.store.append(rec)
    self.ui.refresh_counts()
```

**恢复原则**：
- 任何异常都先停运动、保存现场（图像、传感器状态、状态机状态）；
- 不允许"自动跳过错误牌继续"，因为会破坏 104 张的计数语义；
- **在途牌必须结清**：要么回滚预占后重试，要么人工取出并记入复核队列，不能悬空；
- 人工补录必须指定目标组并写入 `records`，否则 `verify_run` 的组大小/成员校验会失败——这是有意设计，防止"补录后假 PASS"；
- 人工补录必须记录操作员、时间、原预测、最终标签，便于报告分析。

## 8.4 ESP32 子状态机

```
IDLE ──FEED──-> FEEDING ──S2/S3──-> AT_SCAN ──DIVERT──-> DIVERTING
  ▲                │ 超时             │                    │
  │                ▼                  │                    ▼
  └──────────── ERROR <-───────────────┴────────────── EJECTING
                                ▲                         │
                                └──── 超时/堵转/急停 ──────┘
```

**ESP32 固件伪代码（节选）**：

```cpp
void loop() {
  protocol.poll();                 // 解析串口帧、喂心跳
  safety.check();                  // 急停/心跳/超时
  switch (state) {
    case IDLE:      motors.stop(); break;
    case FEEDING:   feedMotor.run(); if (sensor.atScan()) { stopFeed(); sendEvent(AT_SCAN); state = AT_SCAN; } break;
    case AT_SCAN:   if (hostCommand == DIVERT) { servo.to(target); state = DIVERTING; } break;
    case DIVERTING: if (servo.atTarget() || timeout()) { ejectMotor.run(); state = EJECTING; } break;
    case EJECTING:  if (sensor.exited()) { stopAll(); servo.home(); sendDone(); state = IDLE; } break;
    case ERROR_ST:  stopAll(); break;
  }
}
```

**ESP32 侧的关键实现点**：
- 步进电机加减速曲线（梯形），避免丢步与卡牌冲击；
- 传感器 5～10 ms 去抖，用边沿中断记录时间戳；
- 双张判定：S2 到 S3 的遮挡时长显著大于单张阈值（需标定），或 S2/S3 同时被遮挡；
- 舵机用"到位时间 + 电流/堵转"判断，不假设"发角度就一定到位"；
- 看门狗定时器必须喂；任何阻塞等待都要有超时。

## 8.5 通信协议实现（Python 端）

```python
def encode(seq, cmd, payload=b""):
    body = bytes([seq, cmd]) + payload            # SEQ + CMD + PAYLOAD
    frame_body = bytes([len(body)]) + body        # LEN + SEQ + CMD + PAYLOAD
    return b"\xAA\x55" + frame_body + struct.pack("<H", crc16(frame_body))

def decode(buf):
    if len(buf) < 7: return None                  # 最小帧：AA 55 LEN SEQ CMD CRC16
    if buf[0:2] != b"\xAA\x55": return None
    ln = buf[2]
    frame_body = buf[2:3+ln]                      # CRC 覆盖 LEN..PAYLOAD（与 5.5.1 一致）
    body = buf[3:3+ln]
    crc = struct.unpack("<H", buf[3+ln:5+ln])[0]
    if crc != crc16(frame_body): raise BadCRC()
    return body[0], body[1], body[2:]

def command(self, cmd, payload=b"", timeout=1.0, retries=2):
    for _ in range(retries + 1):
        seq = self.next_seq()
        self.write(encode(seq, cmd, payload))
        resp = self.read_frame(timeout)
        if resp and resp.seq == seq:
            return resp
    raise TimeoutError(f"cmd {cmd:#x} no response")
```

## 8.6 模块依赖与目录结构

```
project/
├─ app.py                 # 入口
├─ config.yaml            # 相机索引、ROI、阈值、串口、机械参数
├─ requirements.txt
├─ models/
│  ├─ rank_suit.onnx
│  └─ labels.json
├─ sorter/
│  ├─ camera.py
│  ├─ detect.py
│  ├─ classify.py
│  ├─ side.py
│  ├─ decision.py
│  ├─ serial_link.py
│  ├─ orchestrator.py
│  ├─ store.py
│  ├─ ui.py
│  └─ replay.py
├─ tools/
│  ├─ collect_cards.py    # 采集 3 品牌牌面扫描图
│  ├─ train.py            # 训练/导出 ONNX
│  ├─ evaluate.py         # 混淆矩阵/置信度曲线
│  └─ calibrate.py        # 工位标定
├─ firmware/              # ESP32 PlatformIO 工程
├─ data/
│  ├─ raw/                # 3 品牌扫描图
│  ├─ augmented/
│  └─ splits.json         # 按卡片实例划分，防泄漏
└─ runs/                  # 每次运行的图像与日志
```

## 8.7 适合初学者的开发顺序（建议按此顺序，每周有可见成果）

| 步骤 | 目标 | 验收 | 预计时间 |
|---|---|---|---|
| 1 | 相机 Hello World：打开双相机、锁定曝光、保存图像 | 两张清晰的牌面图 | 0.5 天 |
| 2 | 离线分类基线：采集 1 品牌 52 张，模板匹配分类 | 单品牌测试集 ≥95% | 2 天 |
| 3 | 数据采集 3 品牌 + 增强 + 训练小 CNN | 留出品牌 ≥90%（目标） | 3 天 |
| 4 | 串口 Hello：PING/PONG、LED、心跳 | 串口日志稳定 | 0.5 天 |
| 5 | 电机点动：手动触发进牌、传感器打印 | 单张牌能到扫描位 | 1 天 |
| 6 | 机械闭环（假分类）：固定标签，跑 20 张 | 20 张无卡牌 | 1 天 |
| 7 | 视觉接入：单张完整流程 | 10 张全流程正确 | 1 天 |
| 8 | 整叠 + 校验 + 异常 + 日志 + 界面 | 3 次 104 张完整运行 | 3 天 |
| 9 | 回放/回归：用 runs 目录复现问题 | 可定位任意失败样本 | 1 天 |

> 关键：第 2～3 步（离线视觉）与第 4～6 步（机械/电控）**可以并行**，由不同成员负责，在第 7 步汇合。这样 8 周计划才排得开。

## 8.8 测试桩与离线调试

- **假 MCU**：`serial_link` 支持 `--fake`，用本地模拟器返回传感器事件，用于无硬件时调试状态机；
- **回放模式**：把 `runs/<id>/` 的图像喂给视觉管线，重算预测与分配，对比当时日志，定位是图像问题还是决策问题；
- **单元测试**：detect（给定图返回四边形）、decision（给定标签序列返回 A/B/异常）、protocol（编码/解码/CRC/重发）；
- **集成测试**：用预录的 104 张图跑完整状态机，要求输出与手工标注一致。

## 8.9 代码与配置规范

- 配置与代码分离（YAML），阈值不写死在代码里；
- 所有时间戳统一本地时区 ISO8601，日志用 UTF-8；
- 每张牌记录 `run_id + card_index`，图像命名对应；
- 模型、配置、数据、日志分目录，Git 忽略大文件；
- 每次改算法先跑回归集（固定 104 张回放），防止"修好一个坏三个"。

## 8.10 本章结论

1. 状态机必须覆盖 `WAIT_CARD/FEED/DETECT/CLASSIFY/ASSIGN/DIVERT/VERIFY`，并显式实现 `REVIEW/PAUSE/ERROR`；
2. `VERIFY` 分单张传感器确认与整叠计数校验两层，缺一不可；
3. 拒识牌不参与计数、不强行修复，最终以异常报告结束——这是"不输出错误结果"的工程实现；
4. 通信必须带 CRC、序号、ACK、心跳与超时；
5. 开发顺序按"离线视觉"与"机械电控"两条线并行，第 7 步汇合，符合 8 周节奏。
