(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SUIT = { S: "♠", H: "♥", D: "♦", C: "♣" };
  const RED = new Set(["H", "D"]);
  const SUITS = ["S", "H", "D", "C"];
  const RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
  const state = {
    meta: null, config: "two104", source: "synthetic",
    threshold: 0.99, reject: true, split: "jackfurby_test",
    ood: true, model: "card",
    batch: null, running: false, paused: false, auto: true,
    timer: null, lastRecord: null, mode: "模拟演示", cameraTimer: null,
    uploadFile: null, cropRect: null, modalIndex: null,
  };

  const fmt = (code) => {
    if (!code || code === "UNKNOWN" || code === "FAILED") return "?";
    const suit = code.slice(-1);
    return `${code.slice(0, -1)}${SUIT[suit] || suit}`;
  };
  const pct = (x, d = 2) => `${((Number(x) || 0) * 100).toFixed(d)}%`;
  const modelName = (m) => (state.meta?.models?.[m]?.name || m);
  const MODEL_ORDER = ["ensemble", "hog_svm", "cnn", "template"];
  const post = (url, body) => fetch(url, {
    method: "POST", headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : null,
  }).then(async (r) => {
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    return data;
  });
  let toastTimer = null;
  function toast(msg, bad = false) {
    const el = $("toast");
    el.textContent = msg;
    el.className = "toast show" + (bad ? " bad" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.className = "toast", 3000);
  }
  function setStatus(kind, text) {
    $("statusDot").className = "status-dot" + (kind === "run" ? " run" : kind === "pause" ? " pause" : "");
    $("statusText").textContent = text;
    $("modeText").textContent = state.mode;
    $("modelText").textContent = modelName(state.model);
    $("batchTypeText").textContent = configLabel();
  }
  function configLabel() {
    if (state.config === "custom") {
      return `自定义 ${$("customDecks")?.value || 2} 副 + ${$("customJokers")?.value || 0} 王/副`;
    }
    return state.meta?.configs?.[state.config]?.label || state.config;
  }

  // ---------------------------------------------------------------- init
  async function init() {
    try {
      state.meta = await (await fetch("/api/meta")).json();
    } catch (e) {
      toast("无法加载后端元数据，请确认 demo_app.py 已启动", true);
      return;
    }
    const cs = $("configSelect");
    Object.entries(state.meta.configs || {}).forEach(([key, cfg]) => {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = cfg.label;
      cs.appendChild(opt);
    });
    const custom = document.createElement("option");
    custom.value = "custom";
    custom.textContent = "自定义批次…";
    cs.appendChild(custom);
    cs.value = state.config;
    state.threshold = state.meta.default_threshold?.[state.model] ?? 0.99;
    $("thresholdRange").value = state.threshold;
    $("thresholdValue").textContent = state.threshold.toFixed(3);
    $("modelSelect").value = state.model;
    renderGallery();
    renderExperiments();
    renderEmptyDeck();
    bind();
    setStatus("", "空闲");
    await refreshState();
  }

  // ------------------------------------------------------------- gallery
  function renderGallery() {
    const g = $("gallery");
    g.innerHTML = "";
    const items = (state.meta?.samples || []).filter((s) => s.source === state.source);
    $("gallerySourceLabel").textContent = state.source === "synthetic" ? "合成" : "真实照片";
    items.forEach((s) => {
      const b = document.createElement("button");
      b.className = "sample-card";
      b.type = "button";
      b.innerHTML = `<img src="data:image/jpeg;base64,${s.thumb}" alt="${s.label}"><span>${s.label}</span>`;
      b.addEventListener("click", () => {
        stopAuto();
        document.querySelectorAll(".sample-card").forEach((x) => x.classList.toggle("active", x === b));
        predictSample(s);
      });
      g.appendChild(b);
    });
  }

  async function predictSample(s) {
    showLoading(true);
    try {
      const rec = state.model === "suit"
        ? await post("/api/suit", { sample: { source: s.source, label: s.label, file: s.file } })
        : state.model === "card"
        ? await post("/api/card", { sample: { source: s.source, label: s.label, file: s.file } })
        : await post("/api/predict", {
            model: state.model, reject: state.reject, threshold: state.threshold,
            ood_check: state.ood,
            sample: { source: s.source, label: s.label, file: s.file },
          });
      state.mode = "图片测试";
      renderRecord(rec);
      toast("单张识别完成（未计入批次）");
    } catch (e) { toast("识别失败：" + e.message, true); }
    finally { showLoading(false); }
  }

  // -------------------------------------------------------------- batch
  async function startBatch() {
    if (state.model === "suit") {
      toast("仅花色模式为单张研究模式；请切换到“数字 + 花色”或整牌模型再跑批次", true);
      return;
    }
    if (state.running) return;
    let payload = {
      model: state.model, config: state.config, source: state.source,
      reject: state.reject, threshold: state.threshold, ood_check: state.ood,
    };
    if (state.config === "custom") {
      payload.num_decks = Number($("customDecks").value) || 2;
      payload.jokers_per_deck = Number($("customJokers").value) || 0;
    }
    showLoading(true);
    try {
      const res = await post("/api/batch/start", payload);
      state.batch = res.state;
      state.running = true;
      state.paused = false;
      state.mode = "模拟演示";
      setStatus("run", "识别中");
      renderState();
      toast(`批次已开始：${state.batch.deck.expected_count} 张，${modelName(state.model)}`);
      stepLoop();
    } catch (e) { toast("无法开始批次：" + e.message, true); }
    finally { showLoading(false); }
  }

  async function stepLoop() {
    if (!state.running || state.paused) return;
    try {
      const res = await post("/api/batch/step");
      state.batch = res.state;
      if (res.record) {
        state.lastRecord = res.record;
        renderRecord(res.record);
      }
      renderState();
      if (res.done) {
        state.running = false;
        setStatus("", "批次结束");
        const st = state.batch?.deck?.status || "";
        toast(st.startsWith("COMPLETE") ? `批次完成：${st}` : `批次结束：${st}`,
              !st.startsWith("COMPLETE"));
        return;
      }
      if (!state.auto) {
        state.running = false;
        toast("单步模式：点击“继续”处理下一张");
        setStatus("pause", "已暂停");
        return;
      }
      state.timer = setTimeout(stepLoop, 420);
    } catch (e) {
      state.running = false;
      toast("批次处理失败：" + e.message, true);
      setStatus("", "异常");
    }
  }

  async function pauseBatch() {
    if (!state.batch) return;
    try {
      const res = await post("/api/batch/pause");
      state.batch = res.state;
      state.running = false; state.paused = true;
      clearTimeout(state.timer);
      setStatus("pause", "已暂停"); renderState();
    } catch (e) { toast(e.message, true); }
  }
  async function resumeBatch() {
    if (!state.batch) return;
    try {
      const res = await post("/api/batch/resume");
      state.batch = res.state;
      state.running = true; state.paused = false;
      setStatus("run", "识别中"); renderState(); stepLoop();
    } catch (e) { toast(e.message, true); }
  }
  async function stopBatch() {
    if (!state.batch) return;
    try {
      const res = await post("/api/batch/stop");
      state.batch = res.state;
      state.running = false; state.paused = false;
      clearTimeout(state.timer); setStatus("", "已停止"); renderState();
    } catch (e) { toast(e.message, true); }
  }
  async function resetBatch() {
    try {
      const res = await post("/api/batch/reset");
      state.batch = res.state; state.running = false; state.paused = false;
      state.lastRecord = null; clearTimeout(state.timer);
      clearResult(); renderState(); setStatus("", "空闲");
      toast("当前批次已重置（历史实验文件未删除）");
    } catch (e) { toast(e.message, true); }
  }
  function stopAuto() {
    state.auto = false;
    $("autoBtn").textContent = "自动演示：关";
  }
  function toggleAuto() {
    state.auto = !state.auto;
    $("autoBtn").textContent = "自动演示：" + (state.auto ? "开" : "关");
    if (state.auto && state.batch?.active && !state.running && !state.paused) resumeBatch();
  }

  // -------------------------------------------------------------- render
  function renderState() {
    const b = state.batch;
    if (!b || !b.deck) { renderEmptyDeck(); updateButtons(); return; }
    const d = b.deck;
    $("stProcessed").textContent = d.processed;
    $("stProcessedSub").textContent = `/ ${d.expected_count}`;
    $("stAccepted").textContent = d.accepted;
    $("stUnresolved").textContent = d.unresolved;
    $("stRejected").textContent = d.rejected;
    $("stFailed").textContent = d.failed;
    $("stPending").textContent = d.pending;
    $("stDuplicates").textContent = d.duplicates;
    $("stJokers").textContent = d.joker_count;
    $("stJokerSub").textContent = `/ ${d.expected_jokers}`;
    const slots = d.slots || {};
    $("slotA").textContent = slots.A ?? 0;
    $("slotB").textContent = slots.B ?? 0;
    $("slotReview").textContent = slots.REVIEW ?? 0;
    $("slotASub").textContent = `/ ${slots.expected_A ?? "—"}`;
    $("slotBSub").textContent = `/ ${slots.expected_B ?? "—"}`;
    $("batchProgress").style.width = `${Math.round((d.progress || 0) * 100)}%`;
    $("batchPercent").textContent = `${Math.round((d.progress || 0) * 100)}%`;
    $("batchSubtitle").textContent = `${b.config?.model ? modelName(b.config.model) : modelName(state.model)} · 来源 ${b.config?.source || state.source} · 阈值 ${b.config?.reject ? Number(b.config.threshold).toFixed(3) : "关闭"}`;
    renderDeck(d);
    renderRecent(b);
    renderLogs();
    const status = $("batchStatus");
    const labels = {
      IN_PROGRESS: "进行中：继续处理剩余牌",
      INCOMPLETE_UNRESOLVED: "未完成：存在拒识/失败牌，不能断言缺牌",
      DUPLICATES_FOUND: "异常：出现超出批次配置的重复牌",
      MISSING_CARDS: "未完成：存在缺牌",
    };
    let txt = labels[d.status] || (String(d.status).startsWith("COMPLETE") ? `批次完成：${d.accepted}/${d.expected_count}` : d.status);
    status.textContent = txt;
    status.className = "batch-status " + (String(d.status).startsWith("COMPLETE") ? "good" :
      d.status === "IN_PROGRESS" ? "" : "bad");
    const miss = Object.entries(d.missing || {});
    if (miss.length) {
      const shown = miss.slice(0, 18).map(([k, v]) => `${k}×${v}`).join("、");
      const prefix = d.status === "IN_PROGRESS" ? "尚未出现（处理中）："
        : d.missing_provisional ? "暂定缺牌（存在未确认牌，最终结论待定）：" : "缺牌：";
      $("missingBox").textContent = prefix + shown + (miss.length > 18 ? " …" : "");
    } else if (d.expected_jokers > d.joker_count) {
      $("missingBox").textContent = `Joker 缺 ${d.expected_jokers - d.joker_count} 张（模拟批次中会补录）`;
    } else {
      $("missingBox").textContent = "";
    }
    updateButtons();
  }

  function renderRecent(b) {
    const box = $("recentList");
    const recs = b.records || [];
    if (!recs.length) { box.innerHTML = `<p class="empty">暂无记录</p>`; return; }
    box.innerHTML = "";
    const indices = b.record_indices || [];
    [...recs].reverse().slice(0, 14).forEach((r, i) => {
      const idx = indices[indices.length - 1 - i];
      const div = document.createElement("div");
      div.className = "recent-item";
      const ok = r.accepted && r.batch_status !== "DUPLICATE";
      div.innerHTML = `<img src="${r.thumb ? "data:image/jpeg;base64," + r.thumb : ""}" alt="">
        <div><div class="r-label">${r.label || "UNKNOWN"}</div><div class="r-sub">${r.model_name || ""} · ${r.latency_ms || 0} ms</div></div>
        <span class="r-status ${ok ? "ok" : "bad"}">${ok ? "接受" : (r.batch_status || "拒识")}</span>`;
      div.addEventListener("click", () => showRecord(idx));
      box.appendChild(div);
    });
  }

  function renderDeck(d) {
    const grid = $("deckGrid");
    grid.innerHTML = "";
    const expected = d.expected_per_label || 2;
    SUITS.forEach((s) => {
      const lab = document.createElement("div");
      lab.className = "cell suit-label";
      lab.textContent = SUIT[s] + " " + s;
      grid.appendChild(lab);
      RANKS.forEach((r) => {
        const label = r + s;
        const c = d.counts?.[label] || 0;
        const cell = document.createElement("div");
        cell.className = "cell " + (c === 0 ? "absent" : c < expected ? "partial" : c === expected ? "complete" : "extra");
        cell.title = `${label}: ${c}/${expected}`;
        cell.textContent = c === 0 ? "0" : `${c}/${expected}`;
        grid.appendChild(cell);
      });
    });
    const jl = document.createElement("div");
    jl.className = "cell suit-label";
    jl.textContent = "王";
    grid.appendChild(jl);
    const jc = document.createElement("div");
    const jCount = d.joker_count || 0, jExp = d.expected_jokers || 0;
    jc.className = "cell joker " + (jCount === 0 ? "absent" : jCount < jExp ? "partial" : jCount === jExp ? "complete" : "extra");
    jc.textContent = `JOKER ${jCount}/${jExp}`;
    grid.appendChild(jc);
  }

  function renderEmptyDeck() {
    const fake = { counts: {}, expected_per_label: 2, joker_count: 0, expected_jokers: 0,
      processed: 0, accepted: 0, unresolved: 0, rejected: 0, failed: 0,
      pending: 0, duplicates: 0, expected_count: 104, progress: 0, status: "—", missing: {} };
    renderDeck(fake);
    $("batchStatus").textContent = "尚未开始批次";
    $("batchStatus").className = "batch-status";
    $("batchSubtitle").textContent = "尚未开始批次";
    ["stProcessed","stAccepted","stUnresolved","stRejected","stFailed","stPending","stDuplicates","stJokers"].forEach((id) => $(id).textContent = "0");
    $("stProcessedSub").textContent = "/ 0"; $("stJokerSub").textContent = "/ 0";
    $("slotA").textContent = "0"; $("slotB").textContent = "0"; $("slotReview").textContent = "0";
    $("slotASub").textContent = "/ 0"; $("slotBSub").textContent = "/ 0";
    $("batchProgress").style.width = "0%"; $("batchPercent").textContent = "0%";
    $("missingBox").textContent = "";
  }

  function renderRecord(rec) {
    state.lastRecord = rec;
    const suitMode = rec.model === "suit";
    const code = suitMode ? (rec.suit || "UNKNOWN") : (rec.label || rec.best_label || "UNKNOWN");
    const isU = code === "UNKNOWN" || code === "FAILED";
    const sym = $("predSymbol");
    if (suitMode) {
      sym.textContent = isU ? "?" : (SUIT[rec.suit] || "?");
      sym.className = "symbol" + (!isU && RED.has(rec.suit) ? " red" : "") + (isU ? " unknown" : "");
      $("predCode").textContent = isU ? "花色未识别" : `花色：${rec.suit_name || ""}（${rec.suit}）`;
    } else {
      sym.textContent = isU ? "?" : fmt(rec.best_label || code);
      sym.className = "symbol" + (!isU && RED.has((rec.best_label || code).slice(-1)) ? " red" : "") + (isU ? " unknown" : "");
      $("predCode").textContent = isU ? `${code} · 待确认` : `${rec.best_label || code} · ${fmt(rec.best_label || code)}`;
    }
    $("predMeta").textContent = `${rec.model_name || ""} · ${rec.detected ? "定位成功" : "定位失败"} · ${rec.detection_method || ""} · ${rec.latency_ms || 0} ms${rec.quality && rec.quality.blurry ? " · 画面偏模糊" : ""}`;
    $("recordTime").textContent = rec.time || "—";
    $("imgInput").src = rec.input_image ? `data:image/jpeg;base64,${rec.input_image}` : "";
    $("imgRect").src = rec.rectified_image ? `data:image/jpeg;base64,${rec.rectified_image}` : "";
    $("imgTL").src = rec.tl_roi ? `data:image/jpeg;base64,${rec.tl_roi}` : "";
    $("imgBR").src = rec.br_roi ? `data:image/jpeg;base64,${rec.br_roi}` : "";
    const score = Number(rec.score);
    $("scoreFill").style.width = `${isNaN(score) ? 0 : Math.max(0, Math.min(1, score)) * 100}%`;
    $("scoreValue").textContent = isNaN(score) ? "—" : score.toFixed(3);
    const badge = $("resultBadge");
    if (rec.accepted && rec.batch_status !== "DUPLICATE") {
      badge.className = "badge ok"; badge.textContent = rec.correct === false ? "接受但错误" : "已接受";
    } else {
      badge.className = "badge bad"; badge.textContent = rec.batch_status === "DUPLICATE" ? "重复异常" : "拒识/待确认";
    }
    if (rec.correct === true) badge.textContent += " · ✓";
    if (rec.correct === false) { badge.className = "badge bad"; badge.textContent = `错误 · 真实 ${rec.truth}`; }
    const dec = $("decisionBox");
    dec.className = "decision " + (rec.accepted && rec.batch_status !== "DUPLICATE" ? "ok" : "bad");
    dec.textContent = rec.accepted && rec.batch_status !== "DUPLICATE" ? `接受 · ${rec.reason}` : `待确认 · ${rec.reason}`;
    $("stageTitle").textContent = `当前牌：${rec.truth || "未知"} → ${rec.best_label || code}`;
    $("resultMeta").innerHTML = `
      <div><span>模型</span><b>${rec.model_name || "—"}</b></div>
      <div><span>定位</span><b>${rec.detected ? "成功" : "失败/回退"}</b></div>
      <div><span>耗时</span><b>${rec.latency_ms || 0} ms</b></div>
      <div><span>接受</span><b>${rec.accepted && rec.batch_status !== "DUPLICATE" ? "是" : "否"}</b></div>
      <div><span>分拣(模拟)</span><b>${rec.sort_bin_label || "复核槽"} · 模拟</b></div>
      <div><span>两副槽位</span><b>${rec.slot === "A" ? "A 槽（第一套）" : rec.slot === "B" ? "B 槽（第二套）" : "复核槽"}</b></div>
      <div><span>原因</span><b>${rec.reason || "—"}</b></div>`;
    const top = $("top5"); top.innerHTML = "";
    (rec.top5 || []).forEach(([label, sc]) => {
      const row = document.createElement("div"); row.className = "top5-row";
      const width = Math.max(0, Math.min(1, Number(sc))) * 100;
      row.innerHTML = `<span>${label}</span><span class="bar"><i style="width:${width}%"></i></span><span class="val">${Number(sc).toFixed(3)}</span>`;
      top.appendChild(row);
    });
    const steps = document.querySelectorAll(".step");
    steps.forEach((s) => s.classList.remove("done", "fail"));
    const mark = (name, ok) => { const el = document.querySelector(`.step[data-step="${name}"]`); if (el) el.classList.add(ok ? "done" : "fail"); };
    mark("input", true); mark("detect", rec.detected); mark("rectify", !!rec.rectified_image);
    mark("roi", !!rec.tl_roi); mark("classify", rec.best_label && rec.best_label !== "FAILED"); mark("decide", rec.accepted);
    $("stageNote").textContent = rec.model === "manual" ? "该记录为模拟 Joker 事件，明确不是视觉模型输出。"
      : rec.model === "corner_semantic" ? "该结果来自角标语义兜底：OCR 读点数 + 整牌模型判花色；首次使用 EasyOCR 会下载模型。"
      : "识别结果来自实际模型推理；分数不是校准概率。";
    if (rec.truth && rec.correct === false) {
      $("stageNote").textContent = `错误案例：真实 ${rec.truth}，预测 ${rec.best_label}。可在日志中复核原图与 ROI。`;
    }
    const oodBox = $("oodBox");
    oodBox.classList.toggle("hidden", !rec.ood);
    if (rec.ood) {
      $("oodReason").textContent = `模板相似度 ${Number(rec.design_similarity || 0).toFixed(3)} < 0.55；建议登记此牌面设计或人工确认，不能强行按 52 类输出。`;
      $("enrollLabel").value = "";
      $("enrollLabel").placeholder = "输入真实标签，如 7S";
    }
    if (rec.custom_match) {
      $("stageNote").textContent = "已匹配你登记的自定义模板；该结果不是 52 类通用模型的输出。";
    }
  }

  function clearResult() {
    state.lastRecord = null;
    $("predSymbol").textContent = "—"; $("predSymbol").className = "symbol";
    $("predCode").textContent = "尚未识别";
    $("predMeta").textContent = "选择批次并点击“开始识别”";
    $("imgInput").src = ""; $("imgRect").src = ""; $("imgTL").src = ""; $("imgBR").src = "";
    $("scoreFill").style.width = "0%"; $("scoreValue").textContent = "—";
    $("resultBadge").className = "badge"; $("resultBadge").textContent = "空闲";
    $("decisionBox").className = "decision"; $("decisionBox").textContent = "—";
    $("top5").innerHTML = ""; $("stageTitle").textContent = "等待开始";
    $("stageNote").textContent = "这是本地演示系统：Joker 为模拟批次事件；机械分拣未接入。";
    $("resultMeta").innerHTML = `<div><span>模型</span><b>—</b></div><div><span>定位</span><b>—</b></div><div><span>耗时</span><b>—</b></div><div><span>接受</span><b>—</b></div><div><span>分拣(模拟)</span><b>—</b></div><div><span>原因</span><b>—</b></div>`;
    $("recentList").innerHTML = `<p class="empty">暂无记录</p>`;
    document.querySelectorAll(".step").forEach((s) => s.classList.remove("done", "fail"));
  }

  function updateButtons() {
    const active = !!state.batch?.active;
    const has = !!state.batch;
    const singleResearch = state.model === "suit";
    $("startBtn").disabled = singleResearch || active || state.running;
    $("startBtn").textContent = singleResearch ? "单张研究模式（请上传）" : "▶ 开始识别";
    $("batchTypeText").textContent = singleResearch ? "单张研究" : configLabel();
    $("pauseBtn").disabled = singleResearch || !active || !state.running;
    $("resumeBtn").disabled = !active || state.running;
    $("stopBtn").disabled = !active;
    $("autoBtn").textContent = "自动演示：" + (state.auto ? "开" : "关");
    $("configSelect").disabled = active;
    $("modelSelect").disabled = active;
    $("sourceSelect").disabled = active;
    $("customDecks").disabled = active; $("customJokers").disabled = active;
  }

  // ------------------------------------------------------------- records
  async function refreshState() {
    try {
      const s = await (await fetch("/api/batch/state")).json();
      state.batch = s.active || s.records?.length ? s : null;
      if (state.batch) {
        renderState();
        if (s.current) renderRecord(s.current);
        setStatus(s.active ? (s.paused ? "pause" : "run") : "", s.active ? (s.paused ? "已暂停" : "识别中") : "批次结束");
      }
    } catch { /* backend not ready */ }
  }

  async function showRecord(index) {
    if (index === undefined || index === null) return;
    state.modalIndex = index;
    try {
      const rec = await (await fetch(`/api/batch/record/${index}`)).json();
      $("modalTitle").textContent = `记录 #${index} · ${rec.label || ""} · ${rec.time || ""}`;
      const imgs = [["modalInput", rec.input_image], ["modalRect", rec.rectified_image],
                    ["modalTL", rec.tl_roi], ["modalBR", rec.br_roi]];
      imgs.forEach(([id, b64]) => { $(id).src = b64 ? `data:image/jpeg;base64,${b64}` : ""; });
      const copy = { ...rec };
      delete copy.input_image; delete copy.rectified_image; delete copy.tl_roi; delete copy.br_roi; delete copy.thumb;
      $("modalJson").textContent = JSON.stringify(copy, null, 2);
      $("recordModal").classList.remove("hidden");
    } catch (e) { toast("无法加载记录：" + e.message, true); }
  }

  async function correctRecord() {
    if (state.modalIndex === null) return;
    const label = $("correctLabel").value.trim().toUpperCase();
    if (!/^(10|[2-9AJQK])[SHDC]|JOKER$/.test(label)) {
      return toast("请输入 52 类标签（如 7S）或 JOKER", true);
    }
    try {
      await post("/api/batch/correct", { index: state.modalIndex, label });
      $("recordModal").classList.add("hidden");
      const s = await (await fetch("/api/batch/state")).json();
      state.batch = s; renderState();
      toast("已保存人工修正");
    } catch (e) { toast("修正失败：" + e.message, true); }
  }

  function renderLogs() {
    const recs = state.batch?.records || [];
    const indices = state.batch?.record_indices || [];
    const filter = $("logFilter").value;
    const rows = recs.map((r, i) => ({ r, i: indices[i] })).filter(({ r }) => {
      if (filter === "accepted") return r.accepted;
      if (filter === "rejected") return !r.accepted && r.batch_status === "REJECTED";
      if (filter === "duplicate") return r.batch_status === "DUPLICATE";
      if (filter === "failed") return r.batch_status === "FAILED" || r.label === "FAILED";
      return true;
    });
    const tbody = $("logTable").querySelector("tbody"); tbody.innerHTML = "";
    $("logEmpty").style.display = rows.length ? "none" : "block";
    rows.forEach(({ r, i }) => {
      const tr = document.createElement("tr"); tr.className = "log-row";
      tr.innerHTML = `<td>${i + 1}</td><td>${r.time || ""}</td>
        <td>${r.thumb ? `<img src="data:image/jpeg;base64,${r.thumb}" alt="">` : "—"}</td>
        <td>${r.label || "UNKNOWN"}</td><td>${r.truth || "—"}</td><td>${r.model_name || ""}</td>
        <td>${r.score == null ? "—" : Number(r.score).toFixed(3)}</td>
        <td>${r.accepted ? "接受" : "待确认"}</td><td>${r.reason || ""}</td><td>${r.latency_ms || 0} ms</td>`;
      tr.addEventListener("click", () => showRecord(i));
      tbody.appendChild(tr);
    });
  }

  // --------------------------------------------------------- experiments
  function renderExperiments() {
    const m = state.meta?.metrics;
    if (!m) return;
    const split = state.split;
    const order = ["template", "hog_svm", "cnn"];
    const cards = $("modelCards"); cards.innerHTML = "";
    const metrics = order.map((x) => m.metrics?.[x]?.[split] || {});
    const best = metrics.reduce((bi, c, i, a) => ((c.accuracy_top1 || 0) > (a[bi].accuracy_top1 || 0) ? i : bi), 0);
    order.forEach((model, i) => {
      const d = metrics[i];
      const el = document.createElement("div");
      el.className = "model-card" + (i === best ? " best" : "");
      el.innerHTML = `<h3>${modelName(model)} <span>${i === best ? "BEST" : "MODEL"}</span></h3>
        <div class="big">${pct(d.accuracy_top1)}<small>Top-1</small></div>
        <div class="sub">F1 ${(d.macro_f1 || 0).toFixed(3)} · Top-5 ${pct(d.topk?.top5)} · ${(d.latency_ms?.mean || 0).toFixed(1)} ms</div>`;
      cards.appendChild(el);
    });
    const tb = $("compareTable").querySelector("tbody"); tb.innerHTML = "";
    order.forEach((model, i) => {
      const d = metrics[i];
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${modelName(model)}</td><td>${pct(d.accuracy_top1)}</td>
        <td>${(d.macro_precision || 0).toFixed(3)}</td><td>${(d.macro_recall || 0).toFixed(3)}</td>
        <td>${(d.macro_f1 || 0).toFixed(3)}</td><td>${pct(d.topk?.top5)}</td>
        <td>${pct(d.rank_accuracy)}</td><td>${pct(d.suit_accuracy)}</td><td>${(d.latency_ms?.mean || 0).toFixed(1)} ms</td>`;
      tb.appendChild(tr);
    });
    $("cmImage").src = `/media/eval/${$("cmModel").value}/confusion_matrix_${$("cmSplit").value}.png?${Date.now()}`;
    const calib = m.calibration || {};
    $("calibration").innerHTML = order.map((model) => {
      const c = calib[model]; if (!c) return "";
      const s = c.jackfurby_test || {}, r = c.real52_test || {};
      return `<div><b>${modelName(model)}</b> 阈值 ${Number(c.chosen_threshold || 0).toFixed(3)}：
        合成覆盖 ${pct(s.coverage)} / 准确 ${pct(s.accepted_accuracy)}；真实覆盖 ${pct(r.coverage)} / 准确 ${pct(r.accepted_accuracy)}</div>`;
    }).join("");
    const ds = m.dataset?.splits || {};
    const det = m.dataset?.detection?.real52_auto_detect || {};
    const detRate = (det.ok || 0) + (det.fallback || 0) ? (det.ok / (det.ok + det.fallback) * 100).toFixed(1) : "—";
    $("datasetInfo").innerHTML = `
      <div><span>合成 train/val/test</span><b>${ds.jackfurby_train?.num_images || "—"} / ${ds.jackfurby_val?.num_images || "—"} / ${ds.jackfurby_test?.num_images || "—"}</b></div>
      <div><span>真实测试</span><b>${ds.real52_test?.num_images || "—"} 张 / 52 类</b></div>
      <div><span>真实自动检测</span><b>${detRate}%</b></div>
      <div><span>泄漏审计</span><b>${m.integrity?.leakage_pass ? "PASS" : "FAIL"}</b></div>`;
    $("errorLinks").innerHTML = order.map((model) =>
      `<a href="/media/eval/${model}/misclassified_${split}.csv" target="_blank">${modelName(model)} 错误样本 CSV</a>`).join("") +
      `<span class="muted">（历史实验结果，实际运行日期见 outputs/eval 文件时间）</span>`;
    const ee = m.ensemble_eval?.splits;
    if (ee) {
      const syn = ee.jackfurby_test || {}, real = ee.real52_test || {};
      $("ensembleSummary").innerHTML = `集成决策树（模板+HOG+CNN+树）：合成 Top-1 ${pct(syn.accuracy)}，覆盖 ${pct(syn.coverage)}，接受准确率 ${pct(syn.accepted_accuracy)}；` +
        `真实 Top-1 ${pct(real.accuracy)}，覆盖 ${pct(real.coverage)}，接受准确率 ${pct(real.accepted_accuracy)}。` +
        ` 闭集模型在真实牌面仍不可用，优先 OOD/复核。`;
    }
  }

  // ------------------------------------------------------------- controls
  function bind() {
    document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => activateTab(t.dataset.page)));
    function activateTab(page) {
      document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.page === page));
      document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + page));
      if (page === "experiments") renderExperiments();
      if (page === "logs") renderLogs();
    }
    window.__activateTab = activateTab;
    if (location.hash) activateTab(location.hash.slice(1));

    $("configSelect").addEventListener("change", () => {
      state.config = $("configSelect").value;
      $("customConfig").classList.toggle("hidden", state.config !== "custom");
      setStatus("", $("statusText").textContent);
    });
    $("modelSelect").addEventListener("change", () => {
      state.model = $("modelSelect").value;
      state.threshold = state.meta?.default_threshold?.[state.model] ?? state.threshold;
      $("thresholdRange").value = state.threshold;
      $("thresholdValue").textContent = state.threshold.toFixed(3);
      setStatus("", $("statusText").textContent);
    });
    $("sourceSelect").addEventListener("change", () => {
      state.source = $("sourceSelect").value;
      renderGallery();
    });
    $("thresholdRange").addEventListener("input", () => {
      state.threshold = Number($("thresholdRange").value);
      $("thresholdValue").textContent = state.threshold.toFixed(3);
      if (state.batch?.active) post("/api/batch/config", { threshold: state.threshold }).catch(() => {});
    });
    $("rejectToggle").addEventListener("change", () => {
      state.reject = $("rejectToggle").checked;
      if (state.batch?.active) post("/api/batch/config", { reject: state.reject }).catch(() => {});
    });
    $("oodToggle").addEventListener("change", () => {
      state.ood = $("oodToggle").checked;
    });
    $("startBtn").addEventListener("click", startBatch);
    $("pauseBtn").addEventListener("click", pauseBatch);
    $("resumeBtn").addEventListener("click", resumeBatch);
    $("stopBtn").addEventListener("click", stopBatch);
    $("resetBtn").addEventListener("click", resetBatch);
    $("autoBtn").addEventListener("click", toggleAuto);
    $("logFilter").addEventListener("change", renderLogs);
    $("cmModel").addEventListener("change", renderExperiments);
    $("cmSplit").addEventListener("change", renderExperiments);
    document.querySelectorAll("#metricTabs button").forEach((b) => b.addEventListener("click", () => {
      state.split = b.dataset.split;
      document.querySelectorAll("#metricTabs button").forEach((x) => x.classList.toggle("active", x === b));
      renderExperiments();
    }));
    $("exportBtn").addEventListener("click", () => {
      if (!state.batch) return toast("当前没有批次可导出", true);
      window.location.href = "/api/export/batch.csv";
      toast("正在下载批次 CSV");
    });
    $("exportLogsBtn").addEventListener("click", () => {
      if (!state.batch) return toast("没有日志可导出", true);
      window.location.href = "/api/export/logs.csv";
    });
    $("exportBatchJson").addEventListener("click", () => {
      if (!state.batch) return toast("没有批次可导出", true);
      window.location.href = "/api/export/batch.json";
    });
    $("singleBtn").addEventListener("click", () => $("singleFile").click());
    $("singleFile").addEventListener("change", () => {
      const f = $("singleFile").files?.[0];
      if (f) { state.uploadFile = f; $("cropToggle").disabled = false; $("cropPanel").classList.add("hidden"); predictSingleFile(f); }
    });
    $("cropToggle").addEventListener("click", openCropEditor);
    $("cancelCropBtn").addEventListener("click", () => $("cropPanel").classList.add("hidden"));
    $("applyCropBtn").addEventListener("click", applyCrop);
    $("folderBtn").addEventListener("click", () => $("folderInput").click());
    $("folderInput").addEventListener("change", () => {
      const files = [...($("folderInput").files || [])];
      if (files.length) startUploadBatch(files);
    });
    $("injectDuplicate").addEventListener("click", () => inject("duplicate"));
    $("injectBlank").addEventListener("click", () => inject("blank"));
    $("injectJoker").addEventListener("click", () => inject("joker"));
    $("enrollBtn").addEventListener("click", enrollCurrent);
    $("modalClose").addEventListener("click", () => $("recordModal").classList.add("hidden"));
    $("recordModal").addEventListener("click", (e) => { if (e.target === $("recordModal")) $("recordModal").classList.add("hidden"); });
    $("correctBtn").addEventListener("click", correctRecord);
    bindCamera();
  }

  async function predictSingleFile(file) {
    const fd = new FormData();
    fd.append("image", file);
    fd.append("model", state.model);
    fd.append("reject", state.reject ? "1" : "0");
    fd.append("threshold", String(state.threshold));
    fd.append("ood_check", state.ood ? "1" : "0");
    showLoading(true);
    try {
      const url = state.model === "suit" ? "/api/suit" : state.model === "card" ? "/api/card" : "/api/predict";
      const r = await fetch(url, { method: "POST", body: fd });
      const rec = await r.json();
      if (!r.ok) throw new Error(rec.error || "识别失败");
      state.mode = "图片测试";
      renderRecord(rec);
      toast("单张图片识别完成（未计入批次）");
    } catch (e) { toast(e.message, true); }
    finally { showLoading(false); }
  }

  function openCropEditor() {
    if (!state.uploadFile) return toast("请先选择单张图片", true);
    state.cropRect = null;
    $("cropImg").src = URL.createObjectURL(state.uploadFile);
    $("cropBox").style.display = "none";
    $("cropPanel").classList.remove("hidden");
    const wrap = $("cropWrap");
    const box = $("cropBox");
    let start = null;
    const rel = (e) => {
      const r = $("cropImg").getBoundingClientRect();
      return { x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)),
               y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) };
    };
    wrap.onpointerdown = (e) => { e.preventDefault(); start = rel(e); box.style.display = "block"; };
    wrap.onpointermove = (e) => {
      if (!start) return;
      const p = rel(e);
      const x1 = Math.min(start.x, p.x), x2 = Math.max(start.x, p.x);
      const y1 = Math.min(start.y, p.y), y2 = Math.max(start.y, p.y);
      box.style.left = `${x1 * 100}%`; box.style.top = `${y1 * 100}%`;
      box.style.width = `${(x2 - x1) * 100}%`; box.style.height = `${(y2 - y1) * 100}%`;
      state.cropRect = [x1, y1, x2, y2];
    };
    wrap.onpointerup = () => { start = null; };
  }

  async function applyCrop() {
    if (!state.uploadFile || !state.cropRect) return toast("请拖出一个包含牌的矩形", true);
    const [, , x2, y2] = state.cropRect;
    const [x1, y1] = state.cropRect;
    if (x2 - x1 < 0.05 || y2 - y1 < 0.05) return toast("框太小，请重新拖拽", true);
    const fd = new FormData();
    fd.append("image", state.uploadFile);
    fd.append("model", state.model);
    fd.append("reject", state.reject ? "1" : "0");
    fd.append("threshold", String(state.threshold));
    fd.append("ood_check", state.ood ? "1" : "0");
    fd.append("crop", JSON.stringify(state.cropRect));
    showLoading(true);
    try {
      const r = await fetch("/api/predict", { method: "POST", body: fd });
      const rec = await r.json();
      if (!r.ok) throw new Error(rec.error || "识别失败");
      $("cropPanel").classList.add("hidden");
      state.mode = "手动框选";
      renderRecord(rec);
      toast("已按手动框选区域识别");
    } catch (e) { toast("识别失败：" + e.message, true); }
    finally { showLoading(false); }
  }

  async function startUploadBatch(files) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    fd.append("model", state.model);
    fd.append("config", state.config);
    fd.append("reject", state.reject ? "1" : "0");
    fd.append("threshold", String(state.threshold));
    fd.append("ood_check", state.ood ? "1" : "0");
    showLoading(true);
    try {
      const r = await fetch("/api/batch/start_upload", { method: "POST", body: fd });
      const res = await r.json();
      if (!r.ok) throw new Error(res.error || "上传失败");
      state.batch = res.state; state.running = true; state.paused = false;
      state.mode = "图片测试"; setStatus("run", "识别中"); renderState(); stepLoop();
    } catch (e) { toast("批量上传失败：" + e.message, true); }
    finally { showLoading(false); }
  }

  async function inject(type) {
    if (!state.batch) return toast("请先开始批次", true);
    try {
      const res = await post("/api/batch/inject", { type });
      state.batch = res.state; renderState();
      toast("异常事件已注入，继续处理即可看到效果");
      if (state.batch.active && !state.running && !state.paused) {
        state.running = true; setStatus("run", "识别中"); stepLoop();
      }
    } catch (e) { toast(e.message, true); }
  }

  async function enrollCurrent() {
    const rec = state.lastRecord;
    if (!rec) return toast("没有可登记的牌", true);
    const label = $("enrollLabel").value.trim().toUpperCase();
    if (!/^(10|[2-9AJQK])[SHDC]$/.test(label)) {
      return toast("请输入 52 类标签，例如 7S、10H、KD", true);
    }
    if (!rec.image_path) return toast("当前记录没有源图路径，请用上传图片重新识别后再登记", true);
    showLoading(true);
    try {
      const res = await post("/api/enroll", { label, image_path: rec.image_path });
      toast(`已登记 ${label}；模板验证：${res.verification_label} (${Number(res.verification_score).toFixed(3)})`);
      const newRec = await post("/api/predict", {
        model: state.model, reject: state.reject, threshold: state.threshold,
        ood_check: state.ood, image_path: rec.image_path,
      });
      renderRecord(newRec);
    } catch (e) { toast("登记失败：" + e.message, true); }
    finally { showLoading(false); }
  }

  // -------------------------------------------------------------- camera
  function bindCamera() {
    $("cameraBtn").addEventListener("click", async () => {
      try {
        const res = await post("/api/camera/open");
        if (res.error) throw new Error(res.error);
        $("cameraRow").classList.remove("hidden");
        $("cameraState").textContent = "摄像头：已打开";
        clearInterval(state.cameraTimer);
        state.cameraTimer = setInterval(async () => {
          try {
            const f = await (await fetch("/api/camera/frame")).json();
            if (f.image) $("cameraImg").src = `data:image/jpeg;base64,${f.image}`;
          } catch { /* ignore transient */ }
        }, 500);
        toast("摄像头已打开");
      } catch (e) {
        $("cameraState").textContent = "摄像头：不可用";
        toast("摄像头不可用：" + e.message, true);
      }
    });
    $("captureBtn").addEventListener("click", async () => {
      try {
        const rec = await post("/api/camera/capture", {
          model: state.model, threshold: state.threshold, reject: state.reject,
          ood_check: state.ood,
        });
        state.mode = "摄像头"; renderRecord(rec); toast("拍照识别完成");
      } catch (e) { toast("拍照识别失败：" + e.message, true); }
    });
    $("closeCameraBtn").addEventListener("click", async () => {
      clearInterval(state.cameraTimer); state.cameraTimer = null;
      try { await post("/api/camera/close"); } catch { /* ignore */ }
      $("cameraRow").classList.add("hidden");
      $("cameraState").textContent = "摄像头：未打开";
    });
  }

  function showLoading(on) { $("loading").classList.toggle("show", !!on); }

  document.addEventListener("DOMContentLoaded", init);
})();
