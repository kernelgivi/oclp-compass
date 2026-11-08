import { $, node, externalLink, download, options, signed, metricDescriptions } from "/dom.js";
import { createApi } from "/api.js";

// Sensitive device data is deliberately session-only: no cookies or localStorage.
const capability = location.hash.slice(1);
history.replaceState(null, "", location.pathname);
const api = createApi(capability);
const names = {
  overview: "Recommendation",
  compare: "Compare versions",
  plan: "Upgrade plan",
  hardware: "Hardware lab",
  evidence: "Owner reports",
  method: "Method & sources",
};
const priorities = {
  balanced: "Balance estimated responsiveness, a newer OS, and patch maintenance.",
  smoothness:
    "Favor lower estimated overhead. Older versions may win; verify current app availability and security updates separately.",
  apps: "Favor newer OS requirements. This does not guarantee that a particular app, GPU feature, or CPU instruction is supported.",
};
const state = {
  session: null,
  config: null,
  desired: null,
  result: null,
  page: "overview",
  comparison: null,
  plan: null,
  planTarget: null,
  confirmations: {},
};
let analysisSerial = 0;
let planSerial = 0;
let compareSerial = 0;
let scenarioSerial = 0;
let controller;
let toastTimer;

function error(message) {
  $("error-text").textContent = message;
  $("error").hidden = false;
}

function toast(message) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => {
    $("toast").hidden = true;
  }, 4500);
}

function handle(action) {
  return (...args) => {
    try {
      return Promise.resolve(action(...args)).catch((reason) => error(reason.message));
    } catch (reason) {
      error(reason.message);
    }
  };
}

function busy(value) {
  $("main").setAttribute("aria-busy", String(value));
  ["export", "export-profile"].forEach((id) => {
    $(id).disabled = value || !state.result;
  });
  $("review-plan").disabled = value || !state.result?.candidates.length;
  $("why").disabled = value || !state.result?.candidates.length;
  $("export-plan").disabled = value || !state.plan;
}

function tab(name) {
  if (!(name in names)) return;
  state.page = name;
  Object.keys(names).forEach((id) => {
    $(id).hidden = id !== name;
  });
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
    if (button.dataset.tab === name) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  $("page-name").textContent = names[name];
  if (name === "plan" && state.result && !state.plan) handle(loadPlan)();
  if (name === "compare" && state.result && !state.comparison) handle(loadComparison)();
  window.scrollTo({ top: 0, behavior: "instant" });
}

document
  .querySelectorAll("[data-tab]")
  .forEach((button) => button.addEventListener("click", () => tab(button.dataset.tab)));
document
  .querySelectorAll("[data-go]")
  .forEach((button) => button.addEventListener("click", () => tab(button.dataset.go)));
$("dismiss-error").addEventListener("click", () => {
  $("error").hidden = true;
});

function candidate(major) {
  return state.result?.candidates.find((item) => item.major === major);
}

function showDetails(item) {
  if (!item) return;
  const root = $("detail-content");
  root.replaceChildren(node("h2", `macOS ${item.name}`));
  root.append(
    node(
      "p",
      `${item.route} path · weighted fit ${item.score}/100. ${item.eligible ? "Meets the currently declared constraints." : "Excluded from recommendations."}`
    )
  );
  root.append(node("h3", "How the smoothness estimate is calculated"));
  const labels = {
    capacity: "Model prior",
    headroom: "Baseline allowance",
    ram_penalty: "Memory penalty",
    storage_penalty: "Drive penalty",
    os_load: "OS overhead",
    graphics_penalty: "Graphics penalty",
    community_adjustment: "Owner report adjustment",
  };
  const calculation = node("dl", undefined, "calculation");
  Object.entries(item.calculation).forEach(([key, value]) => {
    const display = key.endsWith("penalty") || key === "os_load" ? `−${value}` : signed(value);
    calculation.append(node("dt", labels[key] || key), node("dd", display));
  });
  calculation.append(node("dt", "Smoothness estimate"), node("dd", item.smoothness));
  root.append(
    calculation,
    node(
      "p",
      "The result is clamped to 0–100. These values are engineering assumptions, not benchmark-derived coefficients.",
      "footnote"
    )
  );
  if (item.app_checks.length) {
    root.append(node("h3", "Essential application requirements"));
    item.app_checks.forEach((app) =>
      root.append(
        node(
          "p",
          `${app.name}: ${app.status.replaceAll("_", " ")}${app.notes.length ? `. ${app.notes.join("; ")}` : " (declared minimums only; not a verified app test)."}`
        )
      )
    );
  }
  const list = node("ul");
  [...item.blocks, ...item.reasons].forEach((reason) => list.append(node("li", reason)));
  root.append(node("h3", "Constraints and caveats"), list);
  const evidence = item.evidence;
  root.append(
    node(
      "p",
      `${evidence.independent} independent exact-model report(s), effective sample ${evidence.effective_sample}; adjustment ${evidence.adjustment} points. Community confidence: ${evidence.confidence}.`
    )
  );
  if (evidence.conflicting)
    root.append(node("p", "This sample contains conflicting positive and negative outcomes."));
  root.append(
    node(
      "p",
      "Graphics rules assume the stock configuration. Check the actual GPU, original model identity, and target build before installing.",
      "footnote"
    )
  );
  if (!$("detail").open) $("detail").showModal();
}

$("close-detail").addEventListener("click", () => $("detail").close());
$("close-help").addEventListener("click", () => $("help-dialog").close());
$("why").addEventListener("click", () => showDetails(candidate(state.result?.recommendation)));
$("review-plan").addEventListener("click", () => tab("plan"));
document.querySelectorAll("[data-help]").forEach((button) =>
  button.addEventListener("click", () => {
    const metric = metricDescriptions[button.dataset.help];
    $("help-content").replaceChildren(node("h2", metric.title), node("p", metric.description));
    $("help-dialog").showModal();
  })
);

function renderModelOptions(query = "") {
  if (!state.session) return;
  const chosen = $("model-select").value || state.config.hardware.model;
  const search = query.toLowerCase().trim();
  const models = Object.entries(state.session.models);
  if (!state.session.models[state.config.hardware.model])
    models.unshift([state.config.hardware.model, { name: "Unreviewed model" }]);
  const matching = models.filter(([id, spec]) =>
    `${id} ${spec.name}`.toLowerCase().includes(search)
  );
  options(
    $("model-select"),
    matching.map(([id, spec]) => [id, `${id} · ${spec.name}`]),
    chosen
  );
  $("model-select").disabled = matching.length === 0;
}

function renderHardware() {
  const hardware = state.config.hardware;
  const spec = state.session.models[hardware.model];
  const origin =
    hardware.origin === "demo"
      ? "DEMO HARDWARE"
      : hardware.origin === "detected"
        ? "DETECTED"
        : "MANUAL PROFILE";
  $("device-name").textContent = spec?.name || hardware.model;
  $("model-id").textContent = hardware.model;
  $("origin").textContent = origin;
  $("inventory-origin").textContent = origin;
  $("ram-value").textContent = `${hardware.ram_gb} GiB`;
  $("disk-value").textContent = hardware.storage.toUpperCase();
  $("cpu-value").textContent = hardware.cores ? `${hardware.cores} cores` : "Unknown";
  $("free-value").textContent = hardware.free_gb == null ? "Unknown" : `${hardware.free_gb} GiB`;
  const inventory = [
    ["Model", hardware.model],
    ["macOS", hardware.current_os],
    ["CPU", hardware.cpu],
    ["Cores", hardware.cores ?? "Unknown"],
    ["Memory", `${hardware.ram_gb} GiB`],
    [
      "Graphics",
      hardware.gpus.length ? hardware.gpus.join(" / ") : "Unknown; stock graphics assumed",
    ],
    ["Drive", hardware.storage],
    ["Free space", hardware.free_gb == null ? "Unknown" : `${hardware.free_gb} GiB`],
    [
      "AVX2",
      hardware.avx2 === null ? "Unknown" : hardware.avx2 ? "Reported available" : "Not available",
    ],
    ["CPU arch", hardware.arch],
  ];
  $("full-inventory").replaceChildren(
    ...inventory.map(([label, value]) => {
      const row = node("div");
      row.append(node("dt", label), node("dd", value));
      return row;
    })
  );
  $("model-search").value = "";
  renderModelOptions();
  $("model-select").value = hardware.model;
  $("ram-input").value = hardware.ram_gb;
  $("disk-select").value = hardware.storage;
  $("free-input").value = hardware.free_gb ?? "";
  $("scenario-ram").value = hardware.ram_gb;
  $("scenario-drive").value = hardware.storage;
}

function renderCandidates() {
  if (!state.result) return;
  let items = [...state.result.candidates];
  if (!$("show-excluded").checked) items = items.filter((item) => item.eligible);
  const sort = $("sort-options").value;
  if (sort === "newest") items.sort((a, b) => b.major - a.major);
  if (sort === "smooth") items.sort((a, b) => b.smoothness - a.smoothness);
  $("candidates").replaceChildren(
    ...items.map((item) => {
      const row = node("tr");
      if (item.major === state.result.recommendation) row.classList.add("best-row");
      if (!item.eligible) row.classList.add("excluded-row");
      const os = node("td");
      os.append(
        node("strong", item.name),
        node(
          "span",
          item.major === state.result.recommendation
            ? "RECOMMENDED"
            : !item.eligible
              ? "EXCLUDED"
              : `macOS ${item.major}`,
          "row-caption"
        )
      );
      row.append(os, node("td", item.route));
      ["smoothness", "app_recency", "maintenance"].forEach((key) => {
        const cell = node("td");
        const display = node("div", undefined, "metric-cell");
        const meter = node("meter");
        meter.min = 0;
        meter.max = 100;
        meter.value = item[key];
        meter.setAttribute(
          "aria-label",
          `${metricDescriptions[key].title}: ${item[key]} out of 100`
        );
        display.append(meter, node("span", item[key]));
        cell.append(display);
        row.append(cell);
      });
      const detail = node("td");
      const button = node("button", "↗", "row-button");
      button.setAttribute("aria-label", `Details for ${item.name}`);
      button.addEventListener("click", () => showDetails(item));
      detail.append(button);
      row.append(node("td", item.score, "score"), detail);
      return row;
    })
  );
  if (!items.length) {
    const row = node("tr");
    const cell = node(
      "td",
      "No options to display. Check exclusions or the model's review coverage."
    );
    cell.colSpan = 7;
    row.append(cell);
    $("candidates").append(row);
  }
}

function renderApps() {
  const apps = state.config.requirements;
  $("app-count").textContent = `${apps.length} ESSENTIAL APP${apps.length === 1 ? "" : "S"}`;
  $("app-list").replaceChildren(
    ...apps.map((app, index) => {
      const item = node("li");
      item.append(
        node(
          "span",
          `${app.name} · macOS ${app.min_os}+${app.avx2 ? " · AVX2" : ""}${app.metal ? " · Metal" : ""}`
        )
      );
      const remove = node("button", "Remove", "text-link");
      remove.setAttribute("aria-label", `Remove ${app.name}`);
      remove.addEventListener("click", () => {
        const next = state.desired.requirements.filter((item) => item.name !== app.name);
        analyze({ requirements: next });
      });
      item.append(remove);
      return item;
    })
  );
}

function renderEvidence() {
  if (!state.result) return;
  const all = state.result.candidates.flatMap((item) =>
    item.evidence.reports.map((report) => ({ report, item }))
  );
  const corpus = state.session.evidence;
  $("corpus-note").textContent =
    `${all.length} exact-model report(s) for ${state.config.hardware.model}. The ${corpus.source} corpus contains ${corpus.total} reports across ${corpus.models} model(s). This sample is not a representative community consensus. Confidence remains limited.`;
  const sentiment = $("evidence-sentiment").value;
  const os = $("evidence-os").value;
  const query = $("evidence-search").value.trim().toLowerCase();
  const filtered = all.filter(
    ({ report }) =>
      (sentiment === "all" || report.sentiment === sentiment) &&
      (os === "all" || String(report.os_major) === os) &&
      `${report.summary} ${report.os_version} ${report.author} ${report.oclp_version}`
        .toLowerCase()
        .includes(query)
  );
  $("evidence-list").replaceChildren(
    ...filtered.map(({ report, item }) => {
      const article = node("article", undefined, "panel report");
      const header = node("div", undefined, "report-header");
      header.append(
        node("span", `${report.model} / macOS ${report.os_version}`, "mono"),
        node("span", report.sentiment.toUpperCase(), `tag outcome ${report.sentiment}`)
      );
      article.append(header, node("h2", report.summary));
      article.append(
        node(
          "p",
          `${report.author} · OCLP ${report.oclp_version} · ${report.ram_gb ?? "Unknown"} GiB RAM · ${report.storage} drive`,
          "meta"
        )
      );
      article.append(
        node(
          "p",
          `Published: ${report.reported_on ?? "unknown; downweighted"} · Reviewed: ${report.reviewed_on}. ${item.evidence.conflicting ? "This OS sample contains conflicting reports." : "No consensus is inferred from this sample."}`,
          "meta"
        )
      );
      article.append(externalLink("Read the original report ↗", report.url));
      return article;
    })
  );
  if (!filtered.length)
    $("evidence-list").append(
      node(
        "div",
        all.length
          ? "No reports match these filters."
          : "No exact-model reports in this corpus. The ranking currently relies on reviewed compatibility rules and heuristic estimates.",
        "empty"
      )
    );
}

function updateSelectors() {
  const items = [...state.result.candidates].sort((a, b) => a.major - b.major);
  const choices = items.map((item) => [
    item.major,
    `${item.name}${item.eligible ? "" : " · excluded"}`,
  ]);
  const left = Number($("compare-left").value) || items[0]?.major;
  const right =
    Number($("compare-right").value) || state.result.recommendation || items.at(-1)?.major;
  options($("compare-left"), choices, left);
  options($("compare-right"), choices, right);
  if (items.length > 1 && $("compare-left").value === $("compare-right").value)
    $("compare-left").value = String(
      items.find((item) => item.major !== Number($("compare-right").value)).major
    );
  if (!candidate(state.planTarget))
    state.planTarget = state.result.recommendation ?? items[0]?.major ?? null;
  options($("plan-target"), choices, state.planTarget);
  options($("evidence-os"), [["all", "All versions"], ...choices], "all");
  ["compare-left", "compare-right", "run-compare", "plan-target"].forEach((id) => {
    $(id).disabled = !items.length;
  });
}

function render() {
  const result = state.result;
  renderHardware();
  renderApps();
  renderCandidates();
  updateSelectors();
  renderEvidence();
  const best = candidate(result.recommendation);
  $("best-name").textContent = best?.name || "No reviewed fit";
  $("fit-value").textContent = best ? String(best.score) : "—";
  $("best-route").textContent = best
    ? best.route === "Native"
      ? "Apple native"
      : "OCLP"
    : "No route selected";
  $("patch-description").textContent = best
    ? best.graphics_patches
      ? "Graphics root patches expected"
      : "No stock graphics patches expected"
    : "Review the constraints";
  $("report-count").textContent = best
    ? `${best.evidence.independent} report${best.evidence.independent === 1 ? "" : "s"}`
    : "—";
  $("best-evidence").textContent = best
    ? best.evidence.independent
      ? "Limited anecdotal evidence"
      : "No exact-model reports"
    : "No recommendation issued";
  $("best-description").textContent = best
    ? best.route === "Native"
      ? `${best.name} ranks highest for your current priorities and has a native route for this model. Check its current app and security-update coverage before choosing it.`
      : `${best.name} ranks highest for your current priorities. It requires OCLP on this model, so review patch maintenance and test the apps you depend on.`
    : result.warnings.at(-1) || "No reviewed option satisfies the declared requirements.";
  $("priority-description").textContent = priorities[state.config.priority];
  $("min-os").value = String(state.config.min_os);
  document.querySelectorAll("[data-priority]").forEach((button) => {
    const selected = button.dataset.priority === state.config.priority;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  $("warnings").replaceChildren(...result.warnings.map((warning) => node("li", warning)));
  $("warning-count").textContent = `${result.warnings.length} NOTES +`;
  $("weights").textContent = Object.entries(result.weights)
    .map(
      ([key, value]) =>
        `${Math.round(value * 100)}% ${metricDescriptions[key === "app_recency" ? "app_recency" : key]?.title.toLowerCase() || key}`
    )
    .join(" + ");
  $("policy-date").textContent =
    `Reviewed ${result.policy.reviewed} · ${result.stale ? "stale snapshot" : `${result.policy_age_days} days old`}`;
  $("sources").replaceChildren(
    ...result.policy.sources.map((source) => externalLink(`${source.title} ↗`, source.url))
  );
  $("glossary").replaceChildren(
    ...Object.values(metricDescriptions).map((metric) => {
      const article = node("article", undefined, "panel");
      article.append(node("h2", metric.title), node("p", metric.description));
      return article;
    })
  );
}

async function analyze(patch = {}) {
  if (!state.desired) return;
  state.desired = { ...state.desired, ...patch };
  const requested = structuredClone(state.desired);
  const serial = ++analysisSerial;
  controller?.abort();
  controller = new AbortController();
  planSerial++;
  compareSerial++;
  scenarioSerial++;
  busy(true);
  $("error").hidden = true;
  try {
    const result = await api("/api/recommend", requested, controller.signal);
    if (serial !== analysisSerial) return;
    state.config = { ...requested, hardware: result.hardware };
    state.desired = structuredClone(state.config);
    state.result = result;
    state.plan = null;
    state.comparison = null;
    state.confirmations = {};
    $("comparison-result").replaceChildren();
    $("plan-content").replaceChildren();
    $("scenario-result").replaceChildren();
    $("plan-state").textContent = "Select or review this target";
    if ($("detail").open) $("detail").close();
    render();
    if (state.page === "compare") handle(loadComparison)();
    if (state.page === "plan") handle(loadPlan)();
  } catch (reason) {
    if (serial !== analysisSerial) return;
    state.desired = state.config ? structuredClone(state.config) : requested;
    error(
      `${reason.message}${state.result ? " The previous valid analysis is still displayed." : ""}`
    );
  } finally {
    if (serial === analysisSerial) {
      busy(false);
      $("loading").hidden = true;
    }
  }
}

document
  .querySelectorAll("[data-priority]")
  .forEach((button) =>
    button.addEventListener("click", () => analyze({ priority: button.dataset.priority }))
  );
$("min-os").addEventListener("change", () => analyze({ min_os: Number($("min-os").value) }));
$("show-excluded").addEventListener("change", renderCandidates);
$("sort-options").addEventListener("change", renderCandidates);
["evidence-sentiment", "evidence-os"].forEach((id) =>
  $(id).addEventListener("change", renderEvidence)
);
$("evidence-search").addEventListener("input", renderEvidence);

async function loadComparison() {
  if (!state.result?.candidates.length) {
    $("comparison-result").replaceChildren(
      node("div", "No reviewed versions are available for this model.", "empty")
    );
    return;
  }
  const serial = ++compareSerial;
  const analysis = analysisSerial;
  const response = await api("/api/compare", {
    ...state.config,
    left: Number($("compare-left").value),
    right: Number($("compare-right").value),
  });
  if (serial !== compareSerial || analysis !== analysisSerial) return;
  state.comparison = response;
  const root = $("comparison-result");
  root.replaceChildren();
  const heading = node("div", undefined, "comparison-heading");
  [response.left, response.right].forEach((item, index) => {
    const column = node("div");
    column.append(
      node("span", `OPTION ${index === 0 ? "A" : "B"} / macOS ${item.major}`, "kicker"),
      node("h2", item.name),
      node("span", item.eligible ? "MEETS DECLARED CONSTRAINTS" : "EXCLUDED", "tag"),
      node("p", `${item.route} · ${item.evidence.independent} independent owner report(s)`)
    );
    heading.append(column);
  });
  root.append(heading);
  const wrap = node("div", undefined, "table-scroll comparison-metrics");
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "region");
  wrap.setAttribute("aria-label", "Version comparison table");
  const table = node("table");
  const head = node("thead");
  const header = node("tr");
  ["Preference metric", response.left.name, response.right.name, "B minus A"].forEach((label) =>
    header.append(node("th", label))
  );
  head.append(header);
  const body = node("tbody");
  response.metrics.forEach((metric) => {
    const row = node("tr");
    row.append(
      node("td", metric.label),
      node("td", metric.left),
      node("td", metric.right),
      node(
        "td",
        `${signed(metric.delta)} points`,
        `delta ${metric.delta > 0 ? "positive" : metric.delta < 0 ? "negative" : ""}`
      )
    );
    body.append(row);
  });
  table.append(head, body);
  wrap.append(table);
  root.append(wrap);
  const notes = node("section", undefined, "panel comparison-notes");
  notes.append(node("h2", "What changes between these versions"));
  const list = node("ul");
  response.differences.forEach((difference) => list.append(node("li", difference)));
  if (!response.differences.length)
    list.append(
      node(
        "li",
        "These versions share the same installation route, stock graphics patch expectation, and evidence count. Their OS overhead and recency scores still differ."
      )
    );
  notes.append(
    list,
    node("p", response.note, "footnote"),
    node(
      "p",
      response.preferred
        ? `${candidate(response.preferred).name} has the higher eligible fit for your selected priorities.`
        : "Neither option meets the declared constraints.",
      "status-line"
    )
  );
  root.append(notes);
}

$("run-compare").addEventListener("click", handle(loadComparison));

async function loadPlan() {
  if (state.planTarget === null || !state.result?.candidates.length) {
    $("plan-content").replaceChildren(
      node("div", "No reviewed installation plan is available for this model.", "empty")
    );
    return;
  }
  const serial = ++planSerial;
  const analysis = analysisSerial;
  const confirmations = state.confirmations[state.planTarget] || {};
  const response = await api("/api/plan", {
    ...state.config,
    target: state.planTarget,
    confirmations,
  });
  if (serial !== planSerial || analysis !== analysisSerial) return;
  state.plan = response;
  $("plan-state").textContent = response.label;
  $("plan-route").textContent =
    `${response.route.toUpperCase()} / ${response.direction.replaceAll("_", " ").toUpperCase()}`;
  $("export-plan").disabled = false;
  const focusedId = document.activeElement?.id;
  const root = $("plan-content");
  root.replaceChildren();
  const grid = node("div", undefined, "plan-grid");
  const review = node("section", undefined, "panel review-panel");
  review.append(node("h2", "Review before changing anything"));
  response.checks.forEach((check) => {
    const row = node("div", undefined, "check-row");
    row.append(node("span", check.status.toUpperCase(), `check-status ${check.status}`));
    const content = node("div");
    if (["backup", "identity", "apps", "recovery"].includes(check.id)) {
      const label = node("label");
      const input = node("input");
      input.type = "checkbox";
      input.id = `confirm-${check.id}`;
      input.checked = !!confirmations[check.id];
      input.addEventListener("change", () => {
        state.confirmations[state.planTarget] = {
          ...(state.confirmations[state.planTarget] || {}),
          [check.id]: input.checked,
        };
        handle(loadPlan)();
      });
      label.append(input, node("span", check.label));
      content.append(label);
    } else content.append(node("strong", check.label));
    content.append(node("p", check.description));
    row.append(content);
    review.append(row);
  });
  grid.append(review);
  const phases = node("div");
  response.phases.forEach((phase, index) => {
    const section = node("section", undefined, "panel phase");
    const h = node("h2");
    h.append(
      node("span", String(index + 1).padStart(2, "0"), "phase-number"),
      node("span", phase.title)
    );
    const steps = node("ol");
    phase.steps.forEach((step) => steps.append(node("li", step)));
    section.append(h, steps);
    phases.append(section);
  });
  grid.append(phases);
  root.append(grid);
  if (response.cautions.length) {
    const caution = node("section", undefined, "panel comparison-notes");
    const list = node("ul", undefined, "caution-list");
    response.cautions.forEach((message) => list.append(node("li", message)));
    caution.append(node("h2", "Target-specific caveats"), list);
    root.append(caution);
  }
  root.append(node("p", response.disclaimer, "footnote"));
  if (focusedId?.startsWith("confirm-")) $(focusedId)?.focus({ preventScroll: true });
}

$("plan-target").addEventListener(
  "change",
  handle(async () => {
    state.planTarget = Number($("plan-target").value);
    await loadPlan();
  })
);

$("model-search").addEventListener("input", () => renderModelOptions($("model-search").value));
$("model-select").addEventListener("change", () => {
  if ($("model-select").value !== state.config.hardware.model) $("free-input").value = "";
});
$("hardware-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!$("model-select").value)
    return error("Choose a reviewed model. No models match the current search.");
  const changed = $("model-select").value !== state.config.hardware.model;
  const hardware = {
    ...state.config.hardware,
    model: $("model-select").value,
    ram_gb: Number($("ram-input").value),
    storage: $("disk-select").value,
    free_gb: $("free-input").value === "" ? null : Number($("free-input").value),
    origin: "manual",
    notes: ["Configuration selected manually. Confirm actual hardware before installation."],
  };
  if (changed)
    Object.assign(hardware, {
      cpu: "Not detected",
      cores: null,
      gpus: [],
      avx2: null,
      current_os: "Unknown",
    });
  analyze({ hardware });
});
$("restore").addEventListener("click", () =>
  analyze({ hardware: structuredClone(state.session.hardware) })
);
$("rescan").addEventListener(
  "click",
  handle(async () => {
    $("rescan").disabled = true;
    try {
      const response = await api("/api/rescan", {});
      state.session.hardware = response.hardware;
      await analyze({ hardware: response.hardware });
      toast("Hardware inventory refreshed. Existing plan confirmations were cleared.");
    } finally {
      $("rescan").disabled = false;
    }
  })
);

$("scenario-form").addEventListener(
  "submit",
  handle(async (event) => {
    event.preventDefault();
    if (!state.result) return;
    const serial = ++scenarioSerial;
    const analysis = analysisSerial;
    const response = await api("/api/simulate", {
      ...state.config,
      ram_gb: Number($("scenario-ram").value),
      storage: $("scenario-drive").value,
    });
    if (serial !== scenarioSerial || analysis !== analysisSerial) return;
    const root = $("scenario-result");
    root.replaceChildren();
    const before = candidate(response.recommendation_before)?.name || "No eligible option";
    const after = candidate(response.recommendation_after)?.name || "No eligible option";
    root.append(
      node(
        "p",
        `Highest-ranked option: ${before} → ${after}. The active hardware profile has not changed.`,
        "scenario-summary"
      )
    );
    const wrap = node("div", undefined, "table-scroll");
    wrap.tabIndex = 0;
    wrap.setAttribute("role", "region");
    wrap.setAttribute("aria-label", "Hypothetical hardware comparison table");
    const table = node("table");
    const head = node("thead");
    const h = node("tr");
    ["macOS", "Current fit", "Hypothetical fit", "Change", "Eligibility"].forEach((label) =>
      h.append(node("th", label))
    );
    head.append(h);
    const body = node("tbody");
    response.changes.forEach((change) => {
      const row = node("tr");
      row.append(
        node("td", change.name),
        node("td", change.before),
        node("td", change.after),
        node("td", `${signed(change.delta)} points`, "delta"),
        node("td", change.eligible_after ? "Meets constraints" : "Excluded")
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    root.append(wrap, node("p", response.note, "footnote"));
  })
);

$("app-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!state.desired) return;
  const name = $("app-name").value.trim();
  if (!name) return;
  if (state.desired.requirements.some((app) => app.name.toLowerCase() === name.toLowerCase()))
    return error("This app is already in your essential-app list.");
  const next = [
    ...state.desired.requirements,
    {
      name,
      min_os: Number($("app-min").value),
      avx2: $("app-avx").checked,
      metal: $("app-metal").checked,
    },
  ];
  analyze({ requirements: next });
  $("app-form").reset();
});

async function exportReport(includePlan = false) {
  if (!state.result) return;
  const filename = `compass-${state.config.hardware.model.replace(",", "-")}`;
  if (!includePlan && $("export-format").value === "json") {
    download(`${filename}.json`, JSON.stringify(state.result, null, 2), "application/json");
  } else {
    const request = { ...state.config };
    if (state.planTarget !== null)
      Object.assign(request, {
        target: state.planTarget,
        confirmations: state.confirmations[state.planTarget] || {},
      });
    const response = await api("/api/report", request);
    download(
      `${filename}${includePlan ? "-plan" : "-report"}.md`,
      response.markdown,
      "text/markdown;charset=utf-8"
    );
  }
  toast("Report exported. Review it before sharing.");
}
$("export").addEventListener(
  "click",
  handle(() => exportReport())
);
$("export-plan").addEventListener(
  "click",
  handle(() => exportReport(true))
);
$("export-profile").addEventListener("click", () => {
  if (!state.config) return;
  download(
    `compass-${state.config.hardware.model.replace(",", "-")}-profile.json`,
    JSON.stringify(state.config.hardware, null, 2),
    "application/json"
  );
  toast("Hardware profile exported. Use Load profile or the CLI --profile option to reopen it.");
});
$("import-profile").addEventListener(
  "change",
  handle(async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      if (file.size > 12288)
        throw new Error(
          "Hardware profiles must be at most 12 KiB. Choose a profile export, not a full analysis report."
        );
      const value = JSON.parse(await file.text());
      if (!value || typeof value !== "object" || Array.isArray(value))
        throw new Error("Expected a hardware profile JSON object.");
      await analyze({ hardware: { ...value, origin: "manual" } });
    } finally {
      event.target.value = "";
    }
  })
);

$("text-size").addEventListener("click", () => {
  const large = document.documentElement.dataset.textSize !== "large";
  document.documentElement.dataset.textSize = large ? "large" : "standard";
  $("text-size").setAttribute("aria-pressed", String(large));
  $("text-size").textContent = large ? "Standard text" : "Larger text";
});
$("theme-toggle").addEventListener("click", () => {
  const light = document.documentElement.dataset.theme !== "light";
  document.documentElement.dataset.theme = light ? "light" : "dark";
  $("theme-toggle").setAttribute("aria-pressed", String(light));
  $("theme-toggle").textContent = light ? "Dark mode" : "Light mode";
});

function commands() {
  return [
    ...Object.entries(names).map(([id, label]) => ({ label, run: () => tab(id) })),
    { label: "Export analysis report", run: () => handle(exportReport)() },
    { label: "Save hardware profile", run: () => $("export-profile").click() },
    { label: "Toggle larger text", run: () => $("text-size").click() },
    { label: "Toggle light / dark mode", run: () => $("theme-toggle").click() },
  ];
}
function renderCommands() {
  const query = $("command-search").value.trim().toLowerCase();
  const matching = commands().filter((command) => command.label.toLowerCase().includes(query));
  $("command-list").replaceChildren(
    ...matching.map((command) => {
      const button = node("button", command.label);
      button.addEventListener("click", () => {
        $("command-dialog").close();
        command.run();
      });
      return button;
    })
  );
  if (!matching.length) $("command-list").append(node("p", "No matching commands.", "footnote"));
}
function openCommands() {
  $("command-search").value = "";
  renderCommands();
  if (!$("command-dialog").open) $("command-dialog").showModal();
  $("command-search").focus();
}
$("open-command").addEventListener("click", openCommands);
$("command-search").addEventListener("input", renderCommands);
$("command-search").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    $("command-list").querySelector("button")?.click();
  }
});
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openCommands();
  }
});

async function boot() {
  if (!capability) {
    $("loading").hidden = true;
    error(
      "Missing session key. Reopen the complete URL printed in Terminal, including the # fragment. The key is removed from the address bar for privacy after opening."
    );
    return;
  }
  try {
    state.session = await api("/api/session", {});
    state.desired = {
      hardware: state.session.hardware,
      requirements: state.session.requirements,
      priority: "balanced",
      min_os: 11,
    };
    await analyze();
  } catch (reason) {
    $("loading").hidden = true;
    error(reason.message);
  }
}
boot();
