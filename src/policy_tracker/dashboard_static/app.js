const formatNumber = new Intl.NumberFormat("en-US");

const elements = {
  status: document.querySelector("#refresh-status"),
  refreshButton: document.querySelector("#refresh-button"),
  metricSources: document.querySelector("#metric-sources"),
  metricDocuments: document.querySelector("#metric-documents"),
  metricItems: document.querySelector("#metric-items"),
  metricFindings: document.querySelector("#metric-findings"),
  metricRetries: document.querySelector("#metric-retries"),
  metricWarnings: document.querySelector("#metric-warnings"),
  sourceCount: document.querySelector("#source-count"),
  sourcesBody: document.querySelector("#sources-body"),
  queueList: document.querySelector("#queue-list"),
  agendaList: document.querySelector("#agenda-list"),
  findingsList: document.querySelector("#findings-list")
};

function fmt(value) {
  return formatNumber.format(value || 0);
}

function text(value, fallback = "-") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function badge(label, tone = "") {
  return `<span class="badge ${tone}">${label}</span>`;
}

function statusTone(source) {
  if (source.has_parser_config_warning || source.manual_review_items > 0) {
    return "danger";
  }
  if (source.retry_queue_items > 0) {
    return "warning";
  }
  return "good";
}

function renderMetrics(summary) {
  elements.metricSources.textContent = `${fmt(summary.active_source_count)} / ${fmt(summary.source_count)}`;
  elements.metricDocuments.textContent = fmt(summary.structured_documents);
  elements.metricItems.textContent = fmt(summary.structured_items);
  elements.metricFindings.textContent = fmt(summary.findings);
  elements.metricRetries.textContent = fmt(summary.retry_queue_items);
  elements.metricWarnings.textContent = fmt(summary.sources_with_parser_config_warnings);
}

function renderSources(summary) {
  elements.sourceCount.textContent = `${fmt(summary.source_count)} configured`;
  elements.sourcesBody.innerHTML = summary.sources.map((source) => {
    const queueTotal = source.retry_queue_items + source.manual_review_items;
    const tone = statusTone(source);
    const status = source.status === "active" ? "Active" : text(source.status);
    return `
      <tr>
        <td>
          <span class="source-name">${text(source.source_name)}</span>
          <span class="source-id">${text(source.source_id)}</span>
        </td>
        <td>${badge(status, tone)}</td>
        <td>${text(source.latest_structured_date || source.latest_document_date)}</td>
        <td>${fmt(source.structured_documents)} / ${fmt(source.raw_documents)}</td>
        <td>${fmt(source.structured_items)}</td>
        <td>${fmt(source.findings)} (${fmt(source.high_priority_findings)} high)</td>
        <td>${fmt(queueTotal)}</td>
      </tr>
    `;
  }).join("");
}

function renderQueues(summary) {
  const queued = summary.sources
    .filter((source) => source.retry_queue_items > 0 || source.manual_review_items > 0 || source.has_parser_config_warning)
    .sort((a, b) => {
      const aTotal = a.retry_queue_items + a.manual_review_items + (a.has_parser_config_warning ? 1 : 0);
      const bTotal = b.retry_queue_items + b.manual_review_items + (b.has_parser_config_warning ? 1 : 0);
      return bTotal - aTotal;
    });

  if (queued.length === 0) {
    elements.queueList.innerHTML = `<div class="empty">No queued review items.</div>`;
    return;
  }

  elements.queueList.innerHTML = queued.map((source) => `
    <div class="queue-row">
      <div class="row-title">
        <span>${text(source.source_name)}</span>
        ${badge(source.has_parser_config_warning ? "Config warning" : "Review", source.has_parser_config_warning ? "danger" : "warning")}
      </div>
      <div class="row-meta">
        ${fmt(source.retry_queue_items)} retry items, ${fmt(source.manual_review_items)} manual review items
      </div>
    </div>
  `).join("");
}

function renderAgendas(summary) {
  if (!summary.recent_agendas.length) {
    elements.agendaList.innerHTML = `<div class="empty">No structured agendas found.</div>`;
    return;
  }

  elements.agendaList.innerHTML = summary.recent_agendas.map((agenda) => `
    <div class="agenda-row">
      <div class="row-title">
        <span>${text(agenda.body_name || agenda.source_id)}</span>
        ${badge(text(agenda.meeting_date_iso || agenda.meeting_date), "good")}
      </div>
      <div class="row-meta">
        ${text(agenda.source_id)} - ${fmt(agenda.item_count)} items - ${text(agenda.document_role)}
      </div>
    </div>
  `).join("");
}

function renderFindings(summary) {
  if (!summary.top_findings.length) {
    elements.findingsList.innerHTML = `<div class="empty">No findings generated yet.</div>`;
    return;
  }

  elements.findingsList.innerHTML = summary.top_findings.map((finding) => {
    const tone = finding.priority_level === "high" ? "danger" : finding.priority_level === "medium" ? "warning" : "good";
    return `
      <div class="finding-row">
        <div class="row-title">
          <span>${text(finding.title)}</span>
          ${badge(text(finding.priority_level), tone)}
        </div>
        <div class="row-meta">
          ${text(finding.source_id)} - ${text(finding.body_name)} - ${text(finding.meeting_date)}
        </div>
        <p class="finding-summary">${text(finding.summary_plain, "")}</p>
      </div>
    `;
  }).join("");
}

async function refreshDashboard() {
  elements.status.textContent = "Loading";
  elements.refreshButton.disabled = true;
  try {
    const response = await fetch("/api/summary", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const summary = await response.json();
    renderMetrics(summary);
    renderSources(summary);
    renderQueues(summary);
    renderAgendas(summary);
    renderFindings(summary);
    elements.status.textContent = "Current";
  } catch (error) {
    elements.status.textContent = "Error";
    elements.queueList.innerHTML = `<div class="empty">Dashboard API error: ${error.message}</div>`;
  } finally {
    elements.refreshButton.disabled = false;
  }
}

elements.refreshButton.addEventListener("click", refreshDashboard);
refreshDashboard();
