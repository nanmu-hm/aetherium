const state = {
  data: null,
  busy: false,
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
    throw new Error(body.detail || \`HTTP \${response.status}\`);
  }
  return response.json();
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
  $("metrics").innerHTML = values.map(([label, value]) => \`
    <div class="metric">
      <div class="label">\${esc(label)}</div>
      <div class="value">\${esc(value)}</div>
    </div>
  \`).join("");
  $("subtitle").textContent =
    \`\${summary.world_id} · \${summary.timestamp} · branch \${summary.active_branch}\`;
  $("pressure").textContent = \`pressure \${Number(narrative.pressure || 0).toFixed(2)}\`;
}

function renderTimeline(events) {
  $("timeline-count").textContent = \`\${events.length} events\`;
  if (!events.length) {
    $("timeline").innerHTML = '<div class="empty">No history yet. Advance the simulation to create history.</div>';
    return;
  }
  $("timeline").innerHTML = [...events].reverse().map(event => {
    const status = event.action_result?.status || "event";
    const fact = event.facts?.[0] || "(no fact)";
    const participants = (event.participants || []).join(" · ");
    return \`
      <article class="event">
        <div class="meta">tick \${esc(event.tick)}<br>\${esc(status)}</div>
        <div>
          <div class="fact">\${esc(fact)}</div>
          <div class="participants">\${esc(participants)} · \${esc(event.location)}</div>
        </div>
      </article>\`;
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
      .map(([name, value]) => \`\${name} \${Number(value).toFixed(0)}\`)
      .join(" · ");
    return \`
      <article class="character">
        <div class="character-name">\${esc(character.name)}</div>
        <div class="character-meta">\${esc(character.id)} · \${esc(character.location || "unknown")} · \${esc(character.status)}</div>
        <div class="character-detail">Goals: \${esc(goals.map(g => g.description).join("; ") || "none")}</div>
        <div class="character-detail">Emotion: \${esc(emotions || "none")}</div>
      </article>\`;
  }).join("");
}

function graphLayout(characters) {
  const centerX = 320;
  const centerY = 180;
  const radius = Math.min(125, 45 + characters.length * 18);
  return characters.map((character, index) => {
    const angle = (-Math.PI / 2) + index * (2 * Math.PI / Math.max(characters.length, 1));
    return { character, x: centerX + radius * Math.cos(angle), y: centerY + radius * Math.sin(angle) };
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
    $("threads").innerHTML = '<div class="empty">No persistent narrative threads have emerged yet.</div>';
    return;
  }
  $("threads").innerHTML = threads.map(thread => \`
    <article class="thread">
      <div class="thread-title">\${esc(thread.title)}</div>
      <div class="thread-meta">\${esc(thread.status)} · tension \${Number(thread.tension || 0).toFixed(2)} · events \${thread.event_ids?.length || 0}</div>
      <div class="thread-question">\${esc(thread.unresolved_question || "No unresolved question recorded.")}</div>
    </article>\`
  ).join("");
}

function renderDiscoveries(narrative) {
  const discoveries = narrative.discoveries || [];
  if (!discoveries.length) {
    $("discoveries").innerHTML = '<div class="empty">No story-bearing discovery above the observer threshold.</div>';
    return;
  }
  $("discoveries").innerHTML = discoveries.map(item => \`
    <article class="discovery">
      <div class="discovery-title">\${esc(item.title || "Untitled discovery")}</div>
      <div class="discovery-meta">score \${Number(item.score || 0).toFixed(2)} · events \${item.event_ids?.length || 0}</div>
      <div class="thread-question">\${esc(item.reason || "No reason recorded.")}</div>
    </article>\`
  ).join("");
}

function render(data) {
  state.data = data;
  renderMetrics(data.summary, data.narrative);
  renderTimeline(data.events);
  renderCharacters(data.characters);
  renderGraph(data.characters, data.relationships);
  renderThreads(data.narrative);
  renderDiscoveries(data.narrative);
}

async function refresh() {
  const data = await api("/api/dashboard?limit=80");
  render(data);
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
    body: JSON.stringify({
      max_ticks: 10,
      checkpoint_every: 5,
      checkpoint_before_run: true,
    }),
  });
}));

refresh().catch(error => window.alert(error.message));
