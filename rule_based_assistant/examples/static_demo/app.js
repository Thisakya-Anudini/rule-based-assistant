"use strict";

const state = {
  callId: null, turns: [], selected: -1, playing: false, speaker: "Customer",
  layaEnabled: false, layaBusy: false,
};

const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s).replace(/[&<>\"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function placeholder(msg) {
  return `<div class="placeholder">${esc(msg)}</div>`;
}

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.status + " " + res.statusText;
    try { detail = (await res.json()).error.message || detail; } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

function flash(msg) {
  const el = $("#flash");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(flash._t);
  flash._t = setTimeout(() => { el.hidden = true; }, 7000);
}

function setBusy(busy) {
  $("#send").disabled = busy;
  $("#utterance").disabled = busy;
  $("#spinner").hidden = !busy;
  renderLayaSetting();
}

function resizeMessageInput() {
  const input = $("#utterance");
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  input.style.overflowY = input.scrollHeight > 160 ? "auto" : "hidden";
}

function renderLayaSetting() {
  const button = $("#toggle-laya");
  button.textContent = state.layaEnabled ? "Disable Laya" : "Enable Laya";
  button.setAttribute("aria-pressed", String(state.layaEnabled));
  button.disabled = state.layaBusy || state.playing || $("#send").disabled;
  $("#laya-status").textContent = state.layaEnabled ? "Laya: on" : "Laya: off";
  $("#laya-status").classList.toggle("laya-on", state.layaEnabled);
}

async function loadLayaSetting() {
  state.layaBusy = true;
  renderLayaSetting();
  try {
    const setting = await api("/v1/classifier/laya");
    state.layaEnabled = setting.enabled;
  } catch (err) {
    flash("Couldn't read Laya setting: " + err.message);
  } finally {
    state.layaBusy = false;
    renderLayaSetting();
  }
}

async function toggleLaya() {
  if (state.layaBusy) return;
  state.layaBusy = true;
  renderLayaSetting();
  try {
    const setting = await api("/v1/classifier/laya", {
      method: "PUT",
      body: JSON.stringify({ enabled: !state.layaEnabled }),
    });
    state.layaEnabled = setting.enabled;
    flash(state.layaEnabled
      ? "Laya enabled. The model may download on its first classification."
      : "Laya disabled. New messages will use the rule engine only.");
  } catch (err) {
    flash("Couldn't change Laya setting: " + err.message);
  } finally {
    state.layaBusy = false;
    renderLayaSetting();
  }
}

async function createCall() {
  const { call_id } = await api("/v1/calls", { method: "POST" });
  state.callId = call_id;
  state.turns = [];
  state.selected = -1;
  $("#call-id").textContent = call_id;
}

async function newCall() {
  setBusy(true);
  try {
    await createCall();
  } catch (err) {
    flash("Couldn't start a call: " + err.message);
  } finally {
    setBusy(false);
    render();
    $("#utterance").focus();
  }
}

function setSpeaker(speaker) {
  state.speaker = speaker;
  $("#speaker-customer").classList.toggle("active", speaker === "Customer");
  $("#speaker-agent").classList.toggle("active", speaker === "Agent");
}

async function sendTurn() {
  const input = $("#utterance");
  const raw = input.value.trim();
  if (!raw || !state.callId) return;
  const stripped = TURN_RE.exec(raw);
  const text = stripped ? stripped[2].trim() : raw;
  setBusy(true);
  try {
    const view = await api(`/v1/calls/${state.callId}/turns`, {
      method: "POST",
      body: JSON.stringify({ utterance: text, speaker: state.speaker.toLowerCase() }),
    });
    state.turns.push(view);
    state.selected = state.turns.length - 1;
    input.value = "";
  } catch (err) {
    flash("Request failed: " + err.message);
  } finally {
    setBusy(false);
    resizeMessageInput();
    render();
    input.focus();
  }
}

async function submitSlotOverride(frameId, slotName, value) {
  setBusy(true);
  try {
    const view = await api(
      `/v1/calls/${state.callId}/frames/${frameId}/slots/${encodeURIComponent(slotName)}`,
      { method: "PATCH", body: JSON.stringify({ value }) },
    );
    state.turns.push(view);
    state.selected = state.turns.length - 1;
  } catch (err) {
    flash("Couldn't save correction: " + err.message);
  } finally {
    setBusy(false);
    render();
  }
}

function slotEditRowHtml(frameId, slotName, currentValue) {
  return `
    <span class="slot-name">${esc(slotName)}</span>
    <input class="slot-edit-input" type="text" value="${esc(currentValue)}" autocomplete="off" spellcheck="false" />
    <button type="button" class="slot-btn" data-action="save-slot" data-frame="${frameId}" data-slot="${esc(slotName)}">Save</button>
    <button type="button" class="slot-btn slot-btn-ghost" data-action="cancel-slot">Cancel</button>
  `;
}

function onSlotsPanelClick(e) {
  const editBtn = e.target.closest("[data-action='edit-slot']");
  if (editBtn) {
    const row = editBtn.closest(".slot");
    row.classList.add("slot-editing");
    row.innerHTML = slotEditRowHtml(editBtn.dataset.frame, editBtn.dataset.slot, editBtn.dataset.value || "");
    const input = row.querySelector("input");
    input.focus();
    input.select();
    return;
  }
  if (e.target.closest("[data-action='cancel-slot']")) {
    render();
    return;
  }
  const saveBtn = e.target.closest("[data-action='save-slot']");
  if (saveBtn) {
    const row = saveBtn.closest(".slot");
    const value = row.querySelector("input").value.trim();
    if (!value) { flash("Enter a value before saving."); return; }
    submitSlotOverride(saveBtn.dataset.frame, saveBtn.dataset.slot, value);
  }
}

function onSlotsPanelKeydown(e) {
  if (!e.target.matches(".slot-edit-input")) return;
  if (e.key === "Enter") {
    e.preventDefault();
    e.target.closest(".slot").querySelector("[data-action='save-slot']").click();
  } else if (e.key === "Escape") {
    e.preventDefault();
    render();
  }
}

const TURN_RE = /^(Customer|Agent):\s*(.*)$/i;
const CUSTOMER_DELAY_MS = 1000;
const AGENT_DELAY_MS = 500;

function parseTranscript(text) {
  const turns = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const match = TURN_RE.exec(rawLine.trim());
    if (!match) continue;
    const speaker = match[1][0].toUpperCase() + match[1].slice(1).toLowerCase();
    const utterance = match[2].trim();
    if (utterance) turns.push({ speaker, utterance });
  }
  return turns;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setPlaybackControls(playing) {
  $("#send").disabled = playing;
  $("#utterance").disabled = playing;
  $("#new-call").disabled = playing;
  $("#upload-transcript").disabled = playing;
  renderLayaSetting();
  $("#stop-playback").hidden = !playing;
}

async function playTranscript(turns) {
  state.playing = true;
  setPlaybackControls(true);
  try {
    await createCall();
    render();
    for (const { speaker, utterance } of turns) {
      if (!state.playing) break;
      await sleep(speaker === "Agent" ? AGENT_DELAY_MS : CUSTOMER_DELAY_MS);
      if (!state.playing) break;

      let view;
      try {
        view = await api(`/v1/calls/${state.callId}/turns`, {
          method: "POST",
          body: JSON.stringify({ utterance, speaker: speaker.toLowerCase() }),
        });
      } catch (err) {
        flash("Playback stopped: " + err.message);
        break;
      }
      state.turns.push(view);
      state.selected = state.turns.length - 1;
      render();
    }
  } catch (err) {
    flash("Couldn't start a call: " + err.message);
  } finally {
    state.playing = false;
    setPlaybackControls(false);
    render();
  }
}

function stopPlayback() {
  state.playing = false;
}

async function handleTranscriptFile(file) {
  if (!file) return;
  $("#transcript-file-name").textContent = `Reading ${file.name}…`;
  try {
    const text = await file.text();
    const turns = parseTranscript(text);
    if (!turns.length) {
      $("#transcript-file-name").textContent = "No valid conversation turns found. Choose another .txt file.";
      flash(`No "Customer: ..." / "Agent: ..." lines found in ${file.name}.`);
      return;
    }
    $("#transcript-file-name").textContent =
      `${file.name} · ${turns.length} ${turns.length === 1 ? "turn" : "turns"}`;
    await playTranscript(turns);
  } catch (err) {
    $("#transcript-file-name").textContent = "Could not read that file. Choose another .txt transcript.";
    flash("Couldn't read transcript: " + err.message);
  }
}

function render(preserveTranscriptScroll = false) {
  renderTranscript(preserveTranscriptScroll);
  const view = state.turns[state.selected] || null;
  renderIntent(view);
  renderSlots(view);
  renderMcp(view);
}

function renderTranscript(preserveScroll = false) {
  const box = $("#transcript");
  const scrollTop = box.scrollTop;
  box.innerHTML = "";
  if (!state.turns.length) {
    box.innerHTML = placeholder("No turns yet. Type below to start the call.");
    return;
  }
  state.turns.forEach((t, i) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "turn" + (i === state.selected ? " active" : "") + (t.speaker === "agent" ? " turn-agent" : "");
    const comparison = t.intent.model_comparison;
    const source = comparison
      ? (comparison.selected_source === "laya_fallback" ? "LAYA" : "RULE")
      : (t.intent.turn_type === "slot_override" ? "MANUAL" : "RULE");
    row.innerHTML =
      `<span class="turn-num">${t.turn_index}</span>` +
      `<span class="turn-speaker">${t.speaker === "agent" ? "Agent" : "Customer"}</span>` +
      `<span class="turn-text"></span>` +
      `<span class="turn-tag tag-${esc(t.intent.decision)}">
        <span>${esc(t.intent.decision.replace(/_/g, " "))}</span>
        <span class="turn-source">${source}</span>
      </span>`;
    row.querySelector(".turn-text").textContent = t.utterance;
    row.onclick = () => { state.selected = i; render(true); };
    box.appendChild(row);
  });
  box.scrollTop = preserveScroll ? scrollTop : box.scrollHeight;
}

function renderIntent(view) {
  const el = $("#panel-intent .panel-body");
  if (!view) { el.innerHTML = placeholder("Pick a speaker and type a turn to begin."); return; }
  const it = view.intent;

  const cands = it.candidates.map((c) => {
    const pct = Math.max(0, Math.min(100, c.score * 100)).toFixed(0);
    return `<div class="cand">
      <span class="cand-name">${esc(c.intent)}</span>
      <span class="cand-bar"><span style="width:${pct}%"></span></span>
      <span class="cand-score">${c.score.toFixed(3)}</span>
    </div>`;
  }).join("");

  const flags = it.heuristic_flags
    .map((f) => `<span class="chip">${esc(f)}</span>`)
    .join("");

  let clarificationBlock = "";
  if (it.clarification) {
    clarificationBlock = `<div class="esc">
      <div class="esc-head">Rule-based clarification</div>
      <div class="esc-reason">${esc(it.clarification.reason || "")}</div>
      <div class="esc-note">${esc(String(it.clarification.message || "Please clarify your request."))}</div>
    </div>`;
  }

  const score = it.top_score != null ? ` &middot; top score ${it.top_score.toFixed(3)}` : "";
  const msgBlock = it.message ? `<div class="blocked-msg">${esc(it.message)}</div>` : "";
  const comparison = it.model_comparison;
  let sourceBlock = "";
  if (comparison) {
    const selectedByLaya = comparison.selected_source === "laya_fallback";
    const sourceTitle = selectedByLaya ? "Laya selected the intent" : "Rule engine selected the intent";
    const statusText = {
      disabled: "Laya is off. Only the rule engine was used.",
      compared: comparison.agreement
        ? "Both classifiers agree. The rule engine remains in control."
        : "Both classifiers were checked.",
      disagreement_rules_won: "The predictions disagreed, so the rule engine was kept.",
      laya_fallback: "The rules found no intent; Laya supplied a confident fallback.",
      below_confidence_threshold: "Laya was below the confidence threshold; no Laya intent was used.",
      invalid_intent: "Laya returned an unsupported intent; the rule result was kept.",
      error: "Laya could not classify this message; the rule result was kept.",
    }[comparison.status] || "Classification details";
    const layaValue = comparison.laya_intent
      ? `${esc(comparison.laya_intent)} <span class="source-confidence">${Number(comparison.laya_confidence).toFixed(3)} confidence</span>`
      : comparison.status === "error" ? "Unavailable" : "Not run";
    sourceBlock = `
      <section class="decision-source ${selectedByLaya ? "source-laya" : "source-rules"}"
               aria-label="Classification source">
        <div class="decision-source-head">
          <span class="source-kicker">DECISION SOURCE</span>
          <strong>${sourceTitle}</strong>
        </div>
        <p class="source-explanation">${statusText}</p>
        <div class="prediction-grid">
          <div class="prediction">
            <span class="prediction-label">Rule engine</span>
            <strong>${esc(comparison.rule_intent || "unknown_intent")}</strong>
            <span class="source-confidence">rule score ${Number(comparison.rule_score || 0).toFixed(3)}</span>
          </div>
          <div class="prediction">
            <span class="prediction-label">Laya</span>
            <strong>${layaValue}</strong>
          </div>
        </div>
      </section>`;
  }
  el.innerHTML = `
    <div class="headline">
      <span class="badge badge-${esc(it.decision)}">${esc(it.decision.replace(/_/g, " "))}</span>
      <span class="sel-intent">${esc(it.selected_intent || "—")}</span>
    </div>
    <div class="sub">turn_type <code>${esc(it.turn_type)}</code>${score}</div>
    ${sourceBlock}
    ${flags ? `<div class="chips">${flags}</div>` : ""}
    ${msgBlock}
    <div class="cands">${cands}</div>
    ${clarificationBlock}
  `;
}

function renderSlots(view) {
  const el = $("#panel-slots .panel-body");
  if (!view) { el.innerHTML = placeholder("No frames yet."); return; }
  const frames = view.slots.frames;
  if (!frames.length) {
    el.innerHTML = placeholder("No intent identified — no frame opened.");
    return;
  }
  el.innerHTML = frames.map((f) => {
    let rows;
    if (f.required.length === 0) {
      rows = `<div class="slot slot-none">no slots required &rarr; fires immediately</div>`;
    } else {
      const editable = f.status !== "REVERTED";
      rows = f.required.map((name) => {
        const filled = Object.prototype.hasOwnProperty.call(f.slots, name);
        const justNow = f.filled_this_turn.includes(name);
        const rawVal = filled ? String(f.slots[name]) : "";
        const val = filled ? esc(rawVal) : "waiting…";
        const editBtn = editable
          ? `<button type="button" class="slot-edit-btn" data-action="edit-slot"
               data-frame="${f.id}" data-slot="${esc(name)}" data-value="${esc(rawVal)}"
               title="${filled ? "Correct this value" : "Fill in this value manually"}">&#9998;</button>`
          : "";
        return `<div class="slot ${filled ? "slot-filled" : "slot-missing"}${justNow ? " slot-new" : ""}"
             data-frame="${f.id}" data-slot="${esc(name)}">
          <span class="slot-name">${esc(name)}</span>
          <span class="slot-val">${val}</span>
          ${justNow ? `<span class="slot-flag">filled this turn</span>` : ""}
          ${editBtn}
        </div>`;
      }).join("");
    }
    const origin = f.initiated_by === "agent"
      ? `<span class="frame-origin">opened by agent</span>` : "";
    return `<div class="frame frame-${esc(f.status)}">
      <div class="frame-head">
        <span class="frame-id">Frame #${f.id}</span>
        <span class="frame-intent">${esc(f.intent)}</span>
        <span class="frame-status">${esc(f.status)}</span>
        ${origin}
      </div>
      ${rows}
    </div>`;
  }).join("");
}

function mcpBlock(call, result) {
  const envelope = {
    method: "tools/call",
    params: { name: call.tool, arguments: call.arguments },
  };
  const resultBlock = result != null
    ? `<div class="mcp-result">
        <div class="mcp-result-head">&#9664; RESPONSE FROM MCP</div>
        <pre>${esc(JSON.stringify(result, null, 2))}</pre>
      </div>`
    : "";
  return `<div class="mcp-call live">
    <div class="mcp-call-head">&#9654; CALL SENT TO MCP</div>
    <pre>${esc(JSON.stringify(envelope, null, 2))}</pre>
    ${resultBlock}
  </div>`;
}

function resultForCall(view, call) {
  const frame = (view.slots.frames || []).find(
    (f) => f.tool_call && JSON.stringify(f.tool_call) === JSON.stringify(call)
  );
  return frame ? frame.tool_result : null;
}

function renderMcp(view) {
  const el = $("#panel-mcp .panel-body");
  if (!view) { el.innerHTML = placeholder("No MCP calls yet."); return; }

  const fired = view.mcp.fired_this_turn || [];
  const now = fired.length
    ? fired.map((call) => mcpBlock(call, resultForCall(view, call))).join("")
    : `<div class="mcp-idle">No MCP call this turn &mdash; a frame fires only once every required slot is filled.</div>`;

  const all = view.mcp.all_calls || [];
  const history = all.length
    ? `<div class="mcp-history-head">All calls this session (${all.length})</div>` +
      all.map((c) =>
        `<div class="mcp-hist">Frame #${c.frame} &middot; <code>${esc(c.tool)}</code>(${esc(JSON.stringify(c.arguments))})</div>`
      ).join("")
    : "";

  el.innerHTML = now + history;
}

window.addEventListener("DOMContentLoaded", () => {
  $("#send").onclick = sendTurn;
  $("#speaker-customer").onclick = () => setSpeaker("Customer");
  $("#speaker-agent").onclick = () => setSpeaker("Agent");
  $("#new-call").onclick = newCall;
  $("#stop-playback").onclick = stopPlayback;
  $("#toggle-laya").onclick = toggleLaya;
  $("#upload-transcript").onclick = () => $("#transcript-file").click();
  $("#transcript-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    handleTranscriptFile(file);
  });
  $("#utterance").addEventListener("input", resizeMessageInput);
  $("#utterance").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendTurn(); }
  });
  const slotsBody = $("#panel-slots .panel-body");
  slotsBody.addEventListener("click", onSlotsPanelClick);
  slotsBody.addEventListener("keydown", onSlotsPanelKeydown);
  loadLayaSetting();
  newCall();
  resizeMessageInput();
});
