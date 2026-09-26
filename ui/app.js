const state = {
  data: null,
  branches: [],
  rooms: [],
  drafts: [],
  canon: [],
  currentDraft: null,
  busy: false,
  agentMessages: [],
};

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body && body.detail) || ("HTTP " + response.status));
  }
  return response.json();
}

async function loadProductState() {
  const results = await Promise.all([
    api("/api/dashboard?limit=80"),
    api("/api/branches"),
    api("/api/agent-rooms"),
    api("/api/narrative/drafts"),
    api("/api/narrative/canon"),
  ]);
  state.data = results[0];
  state.branches = results[1];
  state.rooms = results[2];
  state.drafts = results[3];
  state.canon = results[4];
}

function renderMetrics(summary, narrative) {
  const values = [
    ["Tick", summary.tick],
    ["Characters", summary.character_count],
    ["Relationships", summary.relationship_count],
    ["Events", summary.event_count],
    ["Pressure", Number(narrative.pressure || 0).toFixed(2)],
    ["Branch", summary.active_branch],
  ];

  $("metrics").innerHTML = values.map(([label, value]) =>
    '<div class="metric">' +
      '<div class="label">' + esc(label) + '</div>' +
      '<div class="value">' + esc(value) + '</div>' +
    '</div>'
  ).join("");

  $("subtitle").textContent =
    summary.world_id + " · " + summary.timestamp + " · branch " + summary.active_branch;
  $("pressure").textContent =
    "pressure " + Number(narrative.pressure || 0).toFixed(2);
}

function renderTimeline(events) {
  $("timeline-count").textContent = events.length + " events";
  if (!events.length) {
    $("timeline").innerHTML =
      '<div class="empty">No history yet. Advance the simulation to create history.</div>';
    return;
  }

  $("timeline").innerHTML = [...events].reverse().map(event => {
    const status = (event.action_result && event.action_result.status) || "event";
    const fact = (event.facts && event.facts[0]) || "(no fact)";
    const participants = (event.participants || []).join(" · ");
    return (
      '<article class="event">' +
        '<div class="meta">tick ' + esc(event.tick) + '<br>' + esc(status) + '</div>' +
        '<div>' +
          '<div class="fact">' + esc(fact) + '</div>' +
          '<div class="participants">' + esc(participants) + ' · ' + esc(event.location) + '</div>' +
        '</div>' +
      '</article>'
    );
  }).join("");
}

function renderCharacters(characters) {
  if (!characters.length) {
    $("characters").innerHTML = '<div class="empty">No characters.</div>';
    return;
  }
  $("characters").innerHTML = characters.map(character => {
    const goals = (character.goals || []).filter(g => g.status === "active");
    const emotions = Object.entries(character.emotions || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 2)
      .map(([name, value]) => name + " " + Number(value).toFixed(0))
      .join(" · ");

    return (
      '<article class="character">' +
        '<div class="character-name">' + esc(character.name) + '</div>' +
        '<div class="character-meta">' +
          esc(character.id) + ' · ' + esc(character.location || "unknown") +
          ' · ' + esc(character.status) +
        '</div>' +
        '<div class="character-detail">Goals: ' +
          esc(goals.map(g => g.description).join("; ") || "none") + '</div>' +
        '<div class="character-detail">Emotion: ' +
          esc(emotions || "none") + '</div>' +
      '</article>'
    );
  }).join("");
}

function graphLayout(characters) {
  const centerX = 320;
  const centerY = 180;
  const radius = Math.min(125, 45 + characters.length * 18);
  return characters.map((character, index) => {
    const angle = (-Math.PI / 2) +
      index * (2 * Math.PI / Math.max(characters.length, 1));
    return {
      character,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });
}

function renderGraph(characters, relationships) {
  const svg = $("graph");
  svg.innerHTML = "";
  if (!characters.length) {
    svg.innerHTML = '<text x="320" y="185">No characters</text>';
    return;
  }

  const nodes = graphLayout(characters);
  const lookup = Object.fromEntries(nodes.map(item => [item.character.id, item]));
  relationships.forEach(rel => {
    const a = lookup[rel.source_id];
    const b = lookup[rel.target_id];
    if (!a || !b) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", a.x);
    line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x);
    line.setAttribute("y2", b.y);
    svg.appendChild(line);
  });

  nodes.forEach(node => {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", "22");
    svg.appendChild(circle);

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", node.x);
    text.setAttribute("y", node.y + 45);
    text.textContent = node.character.name;
    svg.appendChild(text);
  });
}

function renderThreads(narrative) {
  const threads = narrative.threads || [];
  if (!threads.length) {
    $("threads").innerHTML =
      '<div class="empty">No persistent narrative threads have emerged yet.</div>';
    return;
  }
  $("threads").innerHTML = threads.map(thread =>
    '<article class="thread">' +
      '<div class="thread-title">' + esc(thread.title) + '</div>' +
      '<div class="thread-meta">' + esc(thread.status) +
      ' · tension ' + Number(thread.tension || 0).toFixed(2) +
      ' · events ' + ((thread.event_ids && thread.event_ids.length) || 0) + '</div>' +
      '<div class="thread-question">' +
        esc(thread.unresolved_question || "No unresolved question recorded.") +
      '</div>' +
    '</article>'
  ).join("");
}

function renderDiscoveries(narrative) {
  const discoveries = narrative.discoveries || [];
  if (!discoveries.length) {
    $("discoveries").innerHTML =
      '<div class="empty">No story-bearing discovery above the observer threshold.</div>';
    return;
  }
  $("discoveries").innerHTML = discoveries.map(item =>
    '<article class="discovery">' +
      '<div class="discovery-title">' + esc(item.title || "Untitled discovery") + '</div>' +
      '<div class="discovery-meta">score ' + Number(item.score || 0).toFixed(2) +
      ' · events ' + ((item.event_ids && item.event_ids.length) || 0) + '</div>' +
      '<div class="thread-question">' + esc(item.reason || "No reason recorded.") + '</div>' +
    '</article>'
  ).join("");
}

function renderBranches() {
  if (!state.branches.length) {
    $("branches").innerHTML = '<div class="empty">No branches recorded.</div>';
    return;
  }
  const current = state.data.summary.active_branch;
  $("branches").innerHTML = state.branches.map(branch =>
    '<article class="branch ' + (branch.id === current ? "current" : "") +
    '" data-branch="' + esc(branch.id) + '">' +
      '<div class="branch-title">' + esc(branch.id) + '</div>' +
      '<div class="branch-meta">' + esc(branch.status || "active") +
      ' · tick ' + esc(branch.fork_tick ?? branch.tick ?? "") + '</div>' +
      '<div class="branch-detail">' + esc(branch.reason || "No branch reason recorded.") + '</div>' +
    '</article>'
  ).join("");

  document.querySelectorAll("[data-branch]").forEach(element => {
    element.addEventListener("click", () => selectBranch(element.dataset.branch));
  });
}

async function selectBranch(branchId) {
  try {
    const detail = await api("/api/branches/" + encodeURIComponent(branchId));
    $("branch-detail").classList.remove("empty");
    $("branch-detail").innerHTML =
      '<div><strong>' + esc(branchId) + '</strong></div>' +
      '<div class="branch-detail">tick ' + esc(detail.tick ?? "") +
      ' · ' + esc(detail.timestamp ?? "") + '</div>' +
      '<div class="branch-detail">hash ' + esc(detail.snapshot_hash || "n/a") + '</div>';
  } catch (error) {
    window.alert(error.message);
  }
}

function renderAgentRooms() {
  const selected = $("agent-select").value;
  $("agent-select").innerHTML = state.rooms.map(room =>
    '<option value="' + esc(room.agent_id) + '">' +
      esc(room.agent_id) + " · " + esc(room.role) +
    '</option>'
  ).join("");
  if (selected && state.rooms.some(room => room.agent_id === selected)) {
    $("agent-select").value = selected;
  }
}

function renderAgentMessages() {
  $("agent-messages").innerHTML = state.agentMessages.length
    ? state.agentMessages.map(item =>
        '<div class="message ' + (item.who === "user" ? "user" : "agent") + '">' +
          '<div class="message-meta">' + esc(item.who) + '</div>' +
          '<div>' + esc(item.text) + '</div>' +
        '</div>'
      ).join("")
    : '<div class="empty">Select an agent and start a conversation.</div>';
  $("agent-messages").scrollTop = $("agent-messages").scrollHeight;
}

function renderDrafts() {
  const selected = state.currentDraft ? state.currentDraft.id : $("draft-select").value;
  $("draft-select").innerHTML =
    '<option value="">Select draft…</option>' +
    state.drafts.map(draft =>
      '<option value="' + esc(draft.id) + '">' +
        esc(draft.title || draft.id) + " · v" + esc(draft.version) +
        " · " + esc(draft.status) +
      '</option>'
    ).join("");
  if (selected && state.drafts.some(draft => draft.id === selected)) {
    $("draft-select").value = selected;
  }
}

function renderScenes() {
  const selected = $("scene-select").value;
  const scenes = state.data.narrative.scenes || [];
  $("scene-select").innerHTML =
    '<option value="">Select scene…</option>' +
    scenes.map(scene =>
      '<option value="' + esc(scene.id) + '">' +
        esc(scene.id) + " · events " + scene.event_ids.length +
      '</option>'
    ).join("");
  if (selected && scenes.some(scene => scene.id === selected)) {
    $("scene-select").value = selected;
  }
}

function renderCurrentDraft() {
  const draft = state.currentDraft;
  const disabled = !draft;
  $("draft-title").disabled = disabled;
  $("draft-prose").disabled = disabled;
  $("save-draft").disabled = disabled || draft.status !== "pending";
  $("approve-draft").disabled = disabled || draft.status !== "pending";
  $("reject-draft").disabled = disabled || draft.status !== "pending";
  $("draft-status").textContent = draft
    ? draft.status + " · v" + draft.version
    : "no draft selected";

  if (!draft) {
    $("draft-title").value = "";
    $("draft-prose").value = "";
    $("draft-provenance").innerHTML = '<div class="empty">No draft selected.</div>';
    return;
  }

  $("draft-title").value = draft.title;
  $("draft-prose").value = draft.prose;
  $("draft-provenance").innerHTML =
    '<div>Scene: ' + esc(draft.scene_id) + '</div>' +
    '<div>Branch: ' + esc(draft.branch_id) + ' · tick ' + esc(draft.tick) + '</div>' +
    '<div>Viewpoint: ' + esc(draft.viewpoint_character_id || "not specified") + '</div>' +
    '<div>Participants: ' + esc((draft.participant_ids || []).join(", ")) + '</div>' +
    '<div>Source events:</div>' +
    '<div>' + esc((draft.source_event_ids || []).join(", ")) + '</div>';
}

function renderCanon() {
  $("canon-list").innerHTML = state.canon.length
    ? state.canon.map(entry =>
        '<article class="canon-item">' +
          '<div class="canon-title">' + esc(entry.title || entry.scene_id) + '</div>' +
          '<div class="canon-meta">v' + esc(entry.version) +
          ' · ' + esc(entry.branch_id) + ' · ' + esc(entry.approved_by) + '</div>' +
          '<div class="canon-prose">' + esc(entry.prose) + '</div>' +
        '</article>'
      ).join("")
    : '<div class="empty">No approved narrative canon yet.</div>';
}

async function openDraft(draftId) {
  if (!draftId) {
    state.currentDraft = null;
    renderCurrentDraft();
    return;
  }
  state.currentDraft = await api("/api/narrative/drafts/" + encodeURIComponent(draftId));
  renderCurrentDraft();
}

async function refresh() {
  await loadProductState();
  renderMetrics(state.data.summary, state.data.narrative);
  renderTimeline(state.data.events);
  renderCharacters(state.data.characters);
  renderGraph(state.data.characters, state.data.relationships);
  renderThreads(state.data.narrative);
  renderDiscoveries(state.data.narrative);
  renderBranches();
  renderAgentRooms();
  renderScenes();
  renderDrafts();
  renderCanon();
  if (state.currentDraft) {
    const refreshed = state.drafts.find(item => item.id === state.currentDraft.id);
    state.currentDraft = refreshed ? await api("/api/narrative/drafts/" + encodeURIComponent(refreshed.id)) : null;
  }
  renderCurrentDraft();
  renderAgentMessages();
}

async function perform(button, fn) {
  if (state.busy) return;
  state.busy = true;
  button.disabled = true;
  try {
    await fn();
    await refresh();
  } catch (error) {
    window.alert(error.message);
  } finally {
    state.busy = false;
    button.disabled = false;
  }
}

$("refresh").addEventListener("click", () => perform($("refresh"), refresh));
$("step-one").addEventListener("click", () => perform($("step-one"), async () => {
  await api("/api/simulation/step", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ticks: 1}),
  });
}));
$("run-ten").addEventListener("click", () => perform($("run-ten"), async () => {
  await api("/api/simulation/run", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({max_ticks: 10, checkpoint_every: 5, checkpoint_before_run: true}),
  });
}));

$("agent-inspect").addEventListener("click", async () => {
  const id = $("agent-select").value;
  if (!id) return;
  try {
    const result = await api("/api/agents/" + encodeURIComponent(id) + "/inspect", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({mode: "interactive"}),
    });
    state.agentMessages.push({who: id + " / inspect", text: result.result.response || (result.result.diagnostics || []).join(" ")});
    renderAgentMessages();
  } catch (error) {
    window.alert(error.message);
  }
});

$("agent-send").addEventListener("click", async () => {
  const message = $("agent-message").value.trim();
  const id = $("agent-select").value;
  if (!message || !id) return;
  $("agent-message").value = "";
  state.agentMessages.push({who: "user", text: message});
  renderAgentMessages();
  try {
    const result = await api("/api/agents/" + encodeURIComponent(id) + "/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: message, mode: "interactive"}),
    });
    state.agentMessages.push({who: id, text: result.result.response || (result.result.diagnostics || []).join(" ")});
    renderAgentMessages();
  } catch (error) {
    window.alert(error.message);
  }
});

$("draft-select").addEventListener("change", () => openDraft($("draft-select").value));

$("create-draft").addEventListener("click", async () => {
  const sceneId = $("scene-select").value;
  if (!sceneId) return window.alert("Select a narrative scene first.");
  try {
    const draft = await api("/api/narrative/drafts", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({scene_id: sceneId}),
    });
    state.currentDraft = draft;
    await refresh();
    $("draft-select").value = draft.id;
    renderCurrentDraft();
  } catch (error) {
    window.alert(error.message);
  }
});

$("save-draft").addEventListener("click", async () => {
  if (!state.currentDraft) return;
  try {
    const draft = await api("/api/narrative/drafts/" + encodeURIComponent(state.currentDraft.id) + "/revise", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        title: $("draft-title").value,
        prose: $("draft-prose").value,
        edited_by: "workbench",
      }),
    });
    state.currentDraft = draft;
    await refresh();
  } catch (error) {
    window.alert(error.message);
  }
});

$("approve-draft").addEventListener("click", async () => {
  if (!state.currentDraft) return;
  try {
    await api("/api/narrative/drafts/" + encodeURIComponent(state.currentDraft.id) + "/approve", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({version: state.currentDraft.version, approved_by: "workbench"}),
    });
    await refresh();
  } catch (error) {
    window.alert(error.message);
  }
});

$("reject-draft").addEventListener("click", async () => {
  if (!state.currentDraft) return;
  try {
    await api("/api/narrative/drafts/" + encodeURIComponent(state.currentDraft.id) + "/reject", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({version: state.currentDraft.version}),
    });
    await refresh();
  } catch (error) {
    window.alert(error.message);
  }
});

loadProductState()
  .then(() => {
    renderMetrics(state.data.summary, state.data.narrative);
    renderTimeline(state.data.events);
    renderCharacters(state.data.characters);
    renderGraph(state.data.characters, state.data.relationships);
    renderThreads(state.data.narrative);
    renderDiscoveries(state.data.narrative);
    renderBranches();
    renderAgentRooms();
    renderScenes();
    renderDrafts();
    renderCanon();
    renderCurrentDraft();
    renderAgentMessages();
  })
  .catch(error => window.alert(error.message));
