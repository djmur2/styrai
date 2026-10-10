const state = {
  data: null,
  governanceData: null,
  pipelineData: { catalog: [], runs: [], latest_run: null },
  selectedPipelineId: null,
  selectedCaseId: null,
  selectedMode: null,
  selectedRunId: null,
  syntheticRecord: null,
  syntheticRecordKey: null,
  syntheticRecordRequest: 0,
  governanceScenario: "data-leak",
  governanceResult: null,
  regulationLibrary: [],
  datasetSchema: null,
  datasetGovernanceAvailable: null,
  uploadAssessment: {
    dataset: null,
    policyName: "",
    policyText: "",
    policyId: null,
    result: null,
  },
  view: "governance",
  inventoryFilter: "all",
  search: "",
};

const sampleGovernanceDatasets = {
  "credit-decisions": {
    name: "synthetic-credit-decisions.csv",
    format: "csv",
    content: `record_id,domain,risk_class,decision_mode,confidence,human_oversight_available,explanation_present,contains_personal_data,data_minimized,significant_effect,human_intervention_available,contestability_available,manual_review_completed,decision
CR-1001,finance,high,assistive,0.92,true,true,true,true,true,true,true,true,approve
CR-1002,finance,high,assistive,0.72,true,true,true,true,true,true,true,false,approve
CR-1003,finance,high,fully_automated,0.64,false,false,true,false,true,false,false,false,decline
CR-1004,finance,high,assistive,0.78,true,true,true,true,true,true,true,true,decline
CR-1005,finance,high,assistive,0.88,true,true,true,true,false,true,true,false,approve
CR-1006,finance,high,assistive,0.95,true,true,true,true,false,true,true,false,approve`,
  },
  "clinical-summaries": {
    name: "synthetic-clinical-summaries.json",
    format: "json",
    content: JSON.stringify([
      { record_id: "HC-2001", domain: "healthcare", risk_class: "high", decision_mode: "assistive", confidence: 0.94, human_oversight_available: true, explanation_present: true, contains_personal_data: true, data_minimized: true, significant_effect: false, human_intervention_available: true, contestability_available: true, manual_review_completed: true, decision: "release" },
      { record_id: "HC-2002", domain: "healthcare", risk_class: "high", decision_mode: "assistive", confidence: 0.76, human_oversight_available: true, explanation_present: true, contains_personal_data: true, data_minimized: true, significant_effect: false, human_intervention_available: true, contestability_available: true, manual_review_completed: false, decision: "release" },
      { record_id: "HC-2003", domain: "healthcare", risk_class: "high", decision_mode: "fully_automated", confidence: 0.61, human_oversight_available: false, explanation_present: false, contains_personal_data: true, data_minimized: false, significant_effect: true, human_intervention_available: false, contestability_available: false, manual_review_completed: false, decision: "hold" },
      { record_id: "HC-2004", domain: "healthcare", risk_class: "high", decision_mode: "assistive", confidence: 0.87, human_oversight_available: true, explanation_present: true, contains_personal_data: true, data_minimized: true, significant_effect: false, human_intervention_available: true, contestability_available: true, manual_review_completed: true, decision: "release" },
    ], null, 2),
  },
};

const sampleCompanyPolicy = `StyrAI Demonstration Company AI Decision Policy
Version 1.0 · Internal standard

Clause 4.2: Any AI-assisted credit recommendation with confidence below 90% must receive manual review before action.

Clause 5.1: Fully automated decisions with significant effect must be blocked when human intervention or contestability is unavailable.

Clause 6.3 — Missing evidence
Missing or ambiguous control evidence must be routed to manual review; it must never be treated as a pass.`;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const esc = (value) => String(value ?? "—")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const viewCopy = {
  governance: ["LIVE GOVERNANCE CONTROL PLANE", "AI Control Room", "Intercept AI use, monitor deployed models and turn obligations into enforceable controls."],
  execution: ["EXECUTABLE GOVERNANCE", "Pipeline Studio", "Run finance and healthcare AI workflows from source data through controlled action and evidence."],
  dashboard: ["CONTINUOUS ASSURANCE", "AI Governance Portfolio", "One operating view across models, agents, data, controls and findings."],
  inventory: ["DISCOVERY & ACCOUNTABILITY", "AI Systems", "Know every AI system, its owner, purpose, provider, risk and approval boundary."],
  monitoring: ["PRODUCTION ASSURANCE", "Model Assurance", "Detect model degradation and make thresholds trigger an accountable response."],
  "data-protection": ["DATA BEFORE DESTINATION", "AI Use Gateway", "Inspect information before it reaches a model provider or crosses a trust boundary."],
  controls: ["POLICY TO PROOF", "Policies & Obligations", "Turn internal policy and regulatory obligations into operating controls with owners and evidence."],
  automations: ["GOVERNANCE THAT RUNS", "Automation Centre", "Discover, intercept, contain, escalate and evidence continuously."],
  incidents: ["DETECTION TO CONTAINMENT", "Findings & Response", "Reconstruct what happened, what was controlled and who owns the response."],
};

function titleCase(value) {
  return String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function number(value) {
  return Number(value || 0).toLocaleString("en-NO");
}

function nok(value) {
  return new Intl.NumberFormat("en-NO", { style: "currency", currency: "NOK", maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatAmount(value, currency = "NOK") {
  return new Intl.NumberFormat("en-NO", {
    style: "currency",
    currency: currency || "NOK",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function when(value, withTime = false) {
  if (!value || value === "Never" || value === "Immediate") return value || "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], withTime
    ? { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }
    : { year: "numeric", month: "short", day: "numeric" });
}

function short(value, length = 16) {
  const text = String(value ?? "—");
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function decisionClass(value) {
  if (["allowed", "allow", "approved", "effective", "healthy", "verified", "resolved", "authorized", "executed", "complete", "validation_passed"].includes(value)) return "authorized";
  if (["allow_with_redaction", "pending_approval", "waiting_approval", "watch", "guarded", "approved_with_conditions", "review_required", "action_required", "improvement", "created", "source_loaded", "input_controlled", "model_completed", "ready", "pending"].includes(value)) return "review";
  return "blocked";
}

function showToast(message, error = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 3000);
}

const INCOMPATIBLE_SERVER_MESSAGE = "This page is connected to an older or incompatible StyrAI service. Reload the page or contact the staging owner. Your CSV or JSON file is not the cause.";

function incompatibleServerMessage(status) {
  return status ? `${INCOMPATIBLE_SERVER_MESSAGE} (Server response ${status}.)` : INCOMPATIBLE_SERVER_MESSAGE;
}

async function request(url, options = {}) {
  let response;
  try {
    const { headers: suppliedHeaders = {}, ...fetchOptions } = options;
    const headers = new Headers(suppliedHeaders);
    const method = String(fetchOptions.method || "GET").toUpperCase();
    if (method === "POST") headers.set("X-StyrAI-Request", "1");
    if (fetchOptions.body != null && !(fetchOptions.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    response = await fetch(url, {
      credentials: "same-origin",
      ...fetchOptions,
      headers,
    });
  } catch (_error) {
    throw new Error("The StyrAI service could not be reached. Reload the page or contact the staging owner; the uploaded file has not been evaluated.");
  }

  let responseText;
  try {
    responseText = await response.text();
  } catch (_error) {
    throw new Error("StyrAI could not read the service response. Reload the page or contact the staging owner; the uploaded file has not been evaluated.");
  }

  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  const trimmedResponse = responseText.trim();
  const looksLikeHtml = contentType.includes("text/html") || /^<!doctype\s+html/i.test(trimmedResponse) || /^<html[\s>]/i.test(trimmedResponse);
  const looksLikeJson = contentType.includes("application/json") || contentType.includes("+json") || /^[\[{]/.test(trimmedResponse);

  if (looksLikeHtml || (trimmedResponse && !looksLikeJson)) {
    throw new Error(incompatibleServerMessage(response.status));
  }
  if (!trimmedResponse) {
    if (!response.ok) throw new Error(`The StyrAI server could not complete this request (response ${response.status}).`);
    return null;
  }

  let payload;
  try {
    payload = JSON.parse(trimmedResponse);
  } catch (_error) {
    throw new Error(incompatibleServerMessage(response.status));
  }
  if (!response.ok) throw new Error(payload?.error || payload?.message || `The StyrAI server could not complete this request (response ${response.status}).`);
  return payload;
}

async function requestOptional(url) {
  try {
    return await request(url);
  } catch (_error) {
    return null;
  }
}

function supportsDatasetGovernance(schema) {
  return Boolean(
    schema
    && typeof schema === "object"
    && schema.schema === "styrai.synthetic-ai-outcomes.v1"
    && Array.isArray(schema.formats)
    && schema.formats.includes("csv")
    && schema.formats.includes("json"),
  );
}

function parseCsv(content) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < content.length; index += 1) {
    const character = content[index];
    if (character === '"' && quoted && content[index + 1] === '"') {
      field += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === "," && !quoted) {
      row.push(field.trim());
      field = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && content[index + 1] === "\n") index += 1;
      row.push(field.trim());
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }
  row.push(field.trim());
  if (row.some((value) => value !== "")) rows.push(row);
  if (rows.length < 2) throw new Error("The CSV must contain a header and at least one data row.");
  const headers = rows[0].map((header, index) => header || `column_${index + 1}`);
  if (new Set(headers).size !== headers.length) throw new Error("CSV column names must be unique.");
  return rows.slice(1).map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""])));
}

function parseDatasetContent(content, format) {
  if (format === "json") {
    const parsed = JSON.parse(content);
    const records = Array.isArray(parsed) ? parsed : parsed.records;
    if (!Array.isArray(records) || !records.length) throw new Error("JSON must be a non-empty array or an object containing a non-empty records array.");
    if (records.some((record) => !record || typeof record !== "object" || Array.isArray(record))) throw new Error("Every JSON record must be an object.");
    return records;
  }
  return parseCsv(content);
}

function datasetColumns(records) {
  return [...new Set(records.flatMap((record) => Object.keys(record)))];
}

function datasetFormat(name, mimeType = "") {
  if (name.toLowerCase().endsWith(".json") || mimeType.includes("json")) return "json";
  if (name.toLowerCase().endsWith(".csv") || mimeType.includes("csv")) return "csv";
  return null;
}

function loadDataset({ name, format, content }) {
  const limits = state.datasetSchema?.limits || { characters: 512000, records: 500, columns: 100 };
  if (content.length > limits.characters) throw new Error(`Choose a CSV or JSON file no larger than ${number(limits.characters)} characters.`);
  const records = parseDatasetContent(content, format);
  const columns = datasetColumns(records);
  if (records.length > limits.records) throw new Error(`Choose a dataset with no more than ${number(limits.records)} records.`);
  if (columns.length > limits.columns) throw new Error(`Choose a dataset with no more than ${number(limits.columns)} columns.`);
  state.uploadAssessment.dataset = { name, format, content, records, columns };
  state.uploadAssessment.result = null;
  renderUploadAssessment();
}

function schemaSampleDataset(sampleName) {
  const examples = state.datasetSchema?.examples || {};
  if (sampleName === "credit-decisions" && examples.finance_csv) {
    return { name: "synthetic-credit-decisions.csv", format: "csv", content: examples.finance_csv };
  }
  if (sampleName === "clinical-summaries" && examples.healthcare_json) {
    return { name: "synthetic-clinical-summaries.json", format: "json", content: JSON.stringify(examples.healthcare_json, null, 2) };
  }
  return sampleGovernanceDatasets[sampleName];
}

function clearUploadAssessment() {
  state.uploadAssessment.dataset = null;
  state.uploadAssessment.policyName = "";
  state.uploadAssessment.policyText = "";
  state.uploadAssessment.policyId = null;
  state.uploadAssessment.result = null;
  const datasetInput = $("#governance-dataset-file");
  const policyInput = $("#company-policy-file");
  if (datasetInput) datasetInput.value = "";
  if (policyInput) policyInput.value = "";
  if ($("#company-policy-text")) $("#company-policy-text").value = "";
  renderUploadAssessment();
}

function renderDatasetPreview(dataset) {
  const inspection = $("#dataset-inspection");
  if (!inspection) return;
  inspection.hidden = !dataset;
  if (!dataset) return;
  $("#dataset-inspection-count").textContent = `${number(dataset.records.length)} record${dataset.records.length === 1 ? "" : "s"} · ${dataset.columns.length} fields`;
  $("#dataset-schema").innerHTML = dataset.columns.map((column) => `<span>${esc(column)}</span>`).join("");
  const displayedColumns = dataset.columns.slice(0, 8);
  const displayedRecords = dataset.records.slice(0, 5);
  $("#dataset-preview-head").innerHTML = `<tr>${displayedColumns.map((column) => `<th scope="col">${esc(column)}</th>`).join("")}</tr>`;
  $("#dataset-preview-body").innerHTML = displayedRecords.map((record) => `<tr>${displayedColumns.map((column) => `<td>${esc(record[column] === "" ? "Empty" : record[column])}</td>`).join("")}</tr>`).join("");
  const limits = [];
  if (dataset.records.length > displayedRecords.length) limits.push(`first ${displayedRecords.length} of ${number(dataset.records.length)} records shown`);
  if (dataset.columns.length > displayedColumns.length) limits.push(`first ${displayedColumns.length} of ${dataset.columns.length} fields shown`);
  $("#dataset-preview-note").textContent = limits.length ? `Preview only: ${limits.join("; ")}. The run evaluates the complete uploaded dataset.` : "All loaded records and fields are shown. The run evaluates this complete dataset.";
}

function renderUploadAssessment() {
  const controlsExist = $("#assessment-workbench");
  if (!controlsExist) return;
  const upload = state.uploadAssessment;
  const dataset = upload.dataset;
  const result = upload.result;
  const fileSummary = $("#dataset-file-summary");
  if (dataset) {
    fileSummary.classList.add("loaded");
    fileSummary.innerHTML = `<span class="empty-file-icon" aria-hidden="true">✓</span><div><strong>${esc(dataset.name)}</strong><small>${number(dataset.records.length)} parsed records · ${dataset.columns.length} detected fields · ${dataset.format.toUpperCase()}</small></div>`;
  } else {
    fileSummary.classList.remove("loaded");
    fileSummary.innerHTML = '<span class="empty-file-icon" aria-hidden="true">▦</span><div><strong>No dataset selected</strong><small>Statistics will be calculated from the rows you load—not from pre-populated figures.</small></div>';
  }
  renderDatasetPreview(dataset);
  const policyText = upload.policyText.trim();
  $("#policy-source-status").innerHTML = policyText
    ? `<strong>${esc(upload.policyName || "Pasted company policy")}</strong><small>${number(policyText.split(/\s+/).filter(Boolean).length)} words ready for clause extraction and cross-reference.</small>`
    : "<strong>No internal policy added</strong><small>The regulatory baseline can still run by itself.</small>";
  $("#active-policy-reference").textContent = policyText ? (upload.policyName || "Pasted company policy") : "No policy loaded";
  $("#active-policy-detail").textContent = policyText ? "Will be evaluated separately from regulatory obligations." : "Upload or paste a policy to add stricter clauses to this run.";
  const runButton = $("#run-dataset-assessment");
  if (state.datasetGovernanceAvailable === false) {
    $("#assessment-run-readiness").textContent = "Updated governance engine required";
    $("#assessment-run-readiness-detail").textContent = "This page is connected to an older StyrAI service. Reload the page or contact the staging owner. Any loaded CSV or JSON was parsed correctly and is not the cause.";
    runButton.disabled = true;
    runButton.title = "Reload the updated StyrAI service to enable dataset governance runs.";
  } else {
    $("#assessment-run-readiness").textContent = dataset ? `${number(dataset.records.length)} records ready to evaluate` : "Add a dataset to begin";
    $("#assessment-run-readiness-detail").textContent = dataset
      ? `${policyText ? "Regulation and internal policy will run as separate layers." : "Regulatory screen only; add a company policy for a separate internal layer."}`
      : "The run button activates after StyrAI can parse at least one record.";
    runButton.disabled = !dataset || state.datasetGovernanceAvailable !== true;
    runButton.removeAttribute("title");
  }
  $("#assessment-results").hidden = !result;
  if (result) renderAssessmentResults(result);
}

const fallbackRegulationLibrary = [
  {
    id: "EU-AIA-ART14",
    authority: "EU AI Act",
    provision: "Article 14(1) and 14(4)",
    requirement: "High-risk systems must support effective human oversight and enable appropriate intervention or interruption.",
    official_source: "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
    version: "Regulation (EU) 2024/1689 · OJ 12 July 2024",
    applicability: "Applicability depends on system classification; Annex III high-risk readiness tracked for 2 December 2027.",
    controls: ["Human review evidence", "Override capability"],
    authority_type: "regulation",
    evaluation_scope: "library_reference_only",
  },
  {
    id: "GDPR-ART22",
    authority: "GDPR",
    provision: "Article 22(1)–(3)",
    requirement: "Screen decisions based solely on automated processing for significant effects and applicable safeguards.",
    official_source: "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
    version: "Regulation (EU) 2016/679 · consolidated text",
    applicability: "Applicable since 25 May 2018; case-specific lawful-basis and exception analysis required.",
    controls: ["Automation scope", "Human intervention", "Explanation evidence"],
    authority_type: "regulation",
    evaluation_scope: "current_law_proxy",
  },
];

function normalizeRegulationLibrary(payload) {
  const entries = Array.isArray(payload) ? payload : (payload?.sources || payload?.regulations || payload?.provisions || payload?.items || []);
  return entries.map((entry, index) => ({
    id: entry.source_id || entry.id || entry.regulation_id || entry.provision_id || `REF-${index + 1}`,
    authority: entry.authority || entry.framework || entry.source_title || entry.regulation || "Regulatory source",
    provision: entry.provision || entry.article || entry.citation || entry.reference || "Provision not specified",
    requirement: entry.requirement || entry.requirement_summary || entry.summary || entry.text || "Requirement summary unavailable",
    official_source: entry.official_url || entry.official_source || entry.source_url || entry.url || "",
    version: entry.version || entry.source_version || entry.last_updated || "Version recorded in demonstration library",
    applicability: entry.application_or_review_date || entry.applicability || entry.applicability_date || entry.effective_date || "Applicability review required",
    controls: entry.controls || entry.affected_controls || entry.control_ids || [entry.control_id, entry.control_proxy].filter(Boolean),
    authority_type: entry.authority_type || entry.type || "regulation",
    evaluation_scope: entry.evaluation_scope || "current_law_proxy",
  }));
}

function renderRegulationLibrary() {
  const target = $("#regulation-library-grid");
  if (!target) return;
  const entries = state.regulationLibrary.length ? state.regulationLibrary : fallbackRegulationLibrary;
  $("#regulation-library-count").textContent = `${entries.length} exact provision${entries.length === 1 ? "" : "s"} loaded`;
  target.innerHTML = entries.map((entry) => `<article class="regulation-reference-card">
    <header><span class="reference-kind ${esc(entry.authority_type === "advisory" || entry.evaluation_scope === "library_reference_only" ? "advisory" : entry.evaluation_scope === "future_readiness" ? "readiness" : "regulation")}">${esc(entry.authority_type === "advisory" ? "ADVISORY" : entry.evaluation_scope === "library_reference_only" ? "LIBRARY REFERENCE" : entry.evaluation_scope === "future_readiness" ? "FUTURE READINESS" : "CURRENT-LAW PROXY")}</span><strong>${esc(entry.authority)} · ${esc(entry.provision)}</strong></header>
    <p>${esc(entry.requirement)}</p>
    <dl><div><dt>Source/version</dt><dd>${esc(entry.version)}</dd></div><div><dt>Applicability</dt><dd>${esc(entry.applicability)}</dd></div><div><dt>Affected controls</dt><dd>${esc((Array.isArray(entry.controls) ? entry.controls : [entry.controls]).join(" · ") || "Applicability mapping")}</dd></div></dl>
    ${entry.official_source ? `<a href="${esc(entry.official_source)}" target="_blank" rel="noopener noreferrer">Open official source <span aria-hidden="true">↗</span></a>` : ""}
  </article>`).join("");
}

function numericValue(object, keys, fallback = 0) {
  for (const key of keys) {
    if (object?.[key] !== undefined && object?.[key] !== null) return Number(object[key]) || 0;
  }
  return fallback;
}

function normalizeAssessmentFinding(finding, index) {
  const citation = finding.citation || {};
  const authority = finding.source_authority || finding.authority_type || finding.layer;
  const rawResult = finding.result_status || finding.result || finding.outcome || finding.status || finding.decision || "Review required";
  const readableResult = rawResult === "fail" && authority === "law" ? "Potential gap" : rawResult === "manual_review" ? "Manual review" : titleCase(rawResult);
  const readinessFinding = ["readiness_gap", "future_readiness"].includes(rawResult) || String(finding.finding_type || "").includes("future_readiness");
  const citationReference = [citation.source_id, citation.provision, citation.source_version, citation.source_clause ? `“${citation.source_clause}”` : ""].filter(Boolean).join(" · ");
  return {
    record_id: finding.record_id || finding.case_id || finding.row_id || finding.row || `Finding ${index + 1}`,
    layer: readinessFinding ? "Future readiness" : authority === "law" ? "Current-law proxy" : authority === "internal_policy" ? "Internal policy" : (authority || finding.source_type || finding.rule_layer || "Governance"),
    result: readableResult,
    reference: finding.exact_reference || finding.reference || citationReference || finding.provision || finding.policy_clause || finding.control_id || "Reference not supplied",
    evidence: finding.evidence || finding.observation || finding.reason || finding.message || "Evidence recorded by the run",
    action: finding.required_action || finding.action || finding.remediation || finding.next_step || (readinessFinding ? "Assign a readiness owner; this is not a current-law failure." : authority === "law" ? "Send to compliance/legal review; no legal violation is asserted." : "Complete the required internal review before action."),
    official_url: citation.official_url || "",
  };
}

function evidenceSummary(evidence) {
  if (!evidence || typeof evidence !== "object") return String(evidence || "");
  const conditions = Array.isArray(evidence.conditions)
    ? evidence.conditions.map((item) => `${item.field}=${item.observed ?? "missing"}`).join("; ")
    : "";
  const direct = Object.entries(evidence)
    .filter(([key]) => key !== "conditions")
    .map(([key, value]) => `${key}=${value ?? "missing"}`)
    .join("; ");
  return [conditions, direct].filter(Boolean).join("; ");
}

function normalizeAssessmentResult(payload, dataset) {
  const root = payload?.run || payload?.result || payload || {};
  const summary = root.summary || root.statistics || root.counts || {};
  const regulation = root.regulatory || root.regulatory_summary || root.regulation || summary.regulatory_controls || summary.regulatory || summary.regulation || {};
  const policy = root.internal_policy || root.policy_summary || root.policy || summary.internal_policy_controls || summary.internal_policy || summary.policy || {};
  const readiness = root.future_readiness || summary.future_readiness_controls || {};
  const rowResults = root.row_results || root.results || [];
  const rawFindings = root.findings || root.row_findings || rowResults.flatMap((row) => row.findings || []) || [];
  const total = numericValue(root, ["records_evaluated", "record_count", "rows_evaluated", "total_records"], numericValue(root.dataset, ["records_evaluated", "record_count"], numericValue(summary, ["records_evaluated", "record_count", "total"], dataset.records.length)));
  const normalized = {
    run_id: root.run_id || root.id || payload?.run_id || "Recorded run",
    created_at: root.created_at || root.completed_at || payload?.created_at || new Date().toISOString(),
    records_evaluated: total,
    records_uploaded: numericValue(root, ["records_uploaded", "records_received"], dataset.records.length),
    regulatory: {
      pass: numericValue(regulation, ["pass", "passed", "passes"]),
      fail: numericValue(regulation, ["fail", "failed", "failures"]),
      potential_gap: numericValue(regulation, ["potential_gap", "potential_gaps", "gaps"]),
      insufficient_evidence: numericValue(regulation, ["insufficient_evidence", "insufficient", "unknown"]),
      not_applicable: numericValue(regulation, ["not_applicable", "na", "not_evaluated"]),
      tested: numericValue(regulation, ["tested", "total"]),
      applicable: numericValue(regulation, ["applicable"]),
      total_checks: numericValue(regulation, ["total_checks", "total"]),
    },
    future_readiness: {
      ready: numericValue(readiness, ["ready", "passed"]),
      readiness_gaps: numericValue(readiness, ["readiness_gaps", "gaps", "failed"]),
      insufficient_evidence: numericValue(readiness, ["insufficient_evidence", "insufficient"]),
      not_applicable: numericValue(readiness, ["not_applicable", "na"]),
      tested: numericValue(readiness, ["tested"]),
      applicable: numericValue(readiness, ["applicable"]),
      total_checks: numericValue(readiness, ["total_checks", "total"]),
    },
    internal_policy: {
      pass: numericValue(policy, ["pass", "passed", "passes"]),
      fail: numericValue(policy, ["fail", "failed", "block", "blocked"]),
      manual_review: numericValue(policy, ["manual_review", "manual_reviews", "review_required", "reviews"]),
      insufficient_evidence: numericValue(policy, ["insufficient_evidence", "insufficient", "unknown"]),
      not_evaluated: numericValue(policy, ["not_evaluated", "not_applicable", "na"]),
      tested: numericValue(policy, ["tested", "total"]),
      applicable: numericValue(policy, ["applicable"]),
      total_checks: numericValue(policy, ["total_checks", "total"]),
    },
    findings: rawFindings.map((finding, index) => {
      const normalizedFinding = normalizeAssessmentFinding(finding, index);
      const row = rowResults.find((item) => String(item.record_id) === String(normalizedFinding.record_id));
      const control = (row?.control_results || []).find((item) => item.control_id === finding.control_id);
      const observedEvidence = evidenceSummary(control?.evidence);
      if (observedEvidence) normalizedFinding.evidence = observedEvidence;
      return normalizedFinding;
    }),
    engine: root.engine || root.evaluation_engine || root.rule_set?.engine_version || "StyrAI demonstration governance engine",
    policy_interpretation: root.policy_interpretation || root.policy_method || (root.rule_set?.internal_policies?.length ? "Activated deterministic policy clauses" : "No internal policy activated"),
    dataset_hash: root.dataset_hash || root.input_hash || root.dataset?.sha256 || "Metadata recorded",
    overall_disposition: summary.overall_disposition || root.overall_disposition || "",
    regulation_pass_internal_review: numericValue(summary, ["regulation_pass_internal_review"]),
    statistics_definition: summary.statistics_definition || "Explicit record-by-control counts; no percentage is treated as legal compliance.",
    model_statistics: root.model_statistics || {},
    legal_determination: false,
  };
  const regulationCount = Object.values(normalized.regulatory).reduce((sum, value) => sum + value, 0);
  const policyCount = Object.values(normalized.internal_policy).reduce((sum, value) => sum + value, 0);
  if (!regulationCount && !policyCount && !normalized.findings.length) throw new Error("The governance API returned no evaluable control results.");
  return normalized;
}

function resultTone(result) {
  if (result.overall_disposition === "not_assessed") return { value: "pending", label: "Not assessed" };
  if (result.overall_disposition === "allow_with_controls") return { value: "review_required", label: "Allow with controls" };
  if (result.overall_disposition === "action_required") return { value: "review_required", label: "Action required" };
  if (result.overall_disposition === "insufficient_evidence") return { value: "review_required", label: "Evidence required" };
  if (result.overall_disposition === "manual_review") return { value: "review_required", label: "Manual review required" };
  if (result.internal_policy.fail > 0) return { value: "blocked", label: "Internal policy block" };
  if (result.regulatory.fail + result.regulatory.potential_gap > 0 || result.internal_policy.manual_review > 0 || result.regulatory.insufficient_evidence > 0) return { value: "review_required", label: "Manual review required" };
  if ((result.regulatory.applicable || 0) === 0 && (result.internal_policy.applicable || 0) === 0) return { value: "pending", label: "Not evaluated" };
  return { value: "approved", label: "No issue detected by tested controls" };
}

function renderCountLine(label, value, total, tone = "neutral", unit = "checks") {
  return `<li class="${esc(tone)}"><span>${esc(label)}</span><strong>${number(value)} of ${number(total)} ${esc(unit)}</strong></li>`;
}

function renderModelStatistics(statistics = {}) {
  const confidence = statistics.confidence || {};
  const error = statistics.observed_error_rate || {};
  const groups = statistics.group_adverse_action_rates || {};
  const psi = statistics.population_stability_index || {};
  const unavailable = (label, metric) => `<article class="model-stat-card unavailable"><span>${esc(label)}</span><strong>Not calculated</strong><small>${esc(metric.reason || "Required fields were not supplied in this dataset.")}</small></article>`;
  const cards = [];
  cards.push(confidence.status === "calculated" ? `<article class="model-stat-card"><span>Confidence values</span><strong>Mean ${Number(confidence.mean).toFixed(3)}</strong><dl><div><dt>Denominator</dt><dd>${number(confidence.denominator)} non-empty values</dd></div><div><dt>Range</dt><dd>${Number(confidence.minimum).toFixed(3)}–${Number(confidence.maximum).toFixed(3)}</dd></div></dl><small>${esc(confidence.definition)}</small></article>` : unavailable("Confidence values", confidence));
  cards.push(error.status === "calculated" ? `<article class="model-stat-card"><span>Observed prediction errors</span><strong>${number(error.errors)} of ${number(error.denominator)} labelled records</strong><dl><div><dt>Formula</dt><dd>predicted_label ≠ actual_label</dd></div></dl><small>${esc(error.definition)}</small></article>` : unavailable("Observed prediction errors", error));
  cards.push(groups.status === "calculated" ? `<article class="model-stat-card"><span>Adverse actions by supplied group</span><strong>${number(groups.eligible_records)} eligible records</strong><dl>${(groups.groups || []).map((group) => `<div><dt>${esc(group.group)}</dt><dd>${number(group.adverse_actions)} of ${number(group.records)} records</dd></div>`).join("")}</dl><small>${esc(groups.definition)}</small></article>` : unavailable("Adverse actions by supplied group", groups));
  cards.push(psi.status === "calculated" ? `<article class="model-stat-card"><span>Population Stability Index</span><strong>${Number(psi.value).toFixed(4)}</strong><dl><div><dt>Baseline</dt><dd>${number(psi.baseline_denominator)} score rows</dd></div><div><dt>Current</dt><dd>${number(psi.current_denominator)} score rows</dd></div></dl><small>${esc(psi.definition)}</small></article>` : unavailable("Population Stability Index", psi));
  $("#model-statistics-grid").innerHTML = cards.join("");
}

function renderAssessmentResults(result) {
  const total = Math.max(0, result.records_evaluated);
  const regulatoryTotal = result.regulatory.total_checks || result.regulatory.pass + result.regulatory.fail + result.regulatory.potential_gap + result.regulatory.insufficient_evidence + result.regulatory.not_applicable;
  const regulatoryApplicable = result.regulatory.applicable ?? regulatoryTotal - result.regulatory.not_applicable;
  const readinessTotal = result.future_readiness?.total_checks || result.future_readiness?.ready + result.future_readiness?.readiness_gaps + result.future_readiness?.insufficient_evidence + result.future_readiness?.not_applicable || 0;
  const readinessApplicable = result.future_readiness?.applicable ?? readinessTotal - (result.future_readiness?.not_applicable || 0);
  const policyTotal = result.internal_policy.total_checks || result.internal_policy.pass + result.internal_policy.fail + result.internal_policy.manual_review + result.internal_policy.insufficient_evidence + result.internal_policy.not_evaluated;
  const policyApplicable = result.internal_policy.applicable ?? policyTotal - result.internal_policy.not_evaluated;
  const tone = resultTone(result);
  const overall = $("#assessment-overall-status");
  overall.className = `status-pill ${decisionClass(tone.value)}`;
  overall.textContent = tone.label;
  $("#assessment-results-subtitle").textContent = `${state.uploadAssessment.dataset?.name || "Uploaded dataset"} · completed ${when(result.created_at, true)} · no legal determination asserted`;
  $("#assessment-divergence-title").textContent = result.regulation_pass_internal_review ? "Regulatory proxy pass + stricter policy review" : "Two separate decisions";
  $("#assessment-divergence-detail").textContent = result.regulation_pass_internal_review
    ? `${number(result.regulation_pass_internal_review)} of ${number(total)} records satisfied every applicable current-law control proxy but still require manual review under the activated company policy. This is the intended authority hierarchy—not a contradictory score.`
    : "Current-law proxies, future-readiness checks and company policy remain separate. A proxy pass means no issue was detected by the rules tested—not a legal opinion.";
  $("#assessment-stat-grid").innerHTML = [
    ["Records evaluated", `${number(total)} of ${number(result.records_uploaded)} uploaded`, "Every uploaded record included in the completed run."],
    ["Current-law control checks", number(regulatoryTotal), `${number(regulatoryApplicable)} applicable checks across ${number(total)} records; ${number(result.regulatory.not_applicable)} not applicable.`],
    ["Future-readiness checks", number(readinessTotal), `${number(readinessApplicable)} applicable forward-looking checks; kept outside current-law results.`],
    ["Internal-policy control checks", number(policyTotal), policyTotal ? `${number(policyApplicable)} applicable checks across ${number(total)} records.` : "No active company policy was included in this run."],
    ["Row-level findings", number(result.findings.length), "Findings can exceed records because one record may trigger multiple rules."],
  ].map(([label, value, detail]) => `<article><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></article>`).join("");
  $("#assessment-stat-definition").textContent = result.statistics_definition;
  $("#assessment-layer-grid").innerHTML = `<article class="assessment-layer-card regulatory-layer">
    <header><div><span>CURRENT-LAW CONTROL PROXIES</span><strong>Regulatory screen</strong></div>${status(!regulatoryApplicable ? "pending" : result.regulatory.fail + result.regulatory.potential_gap || result.regulatory.insufficient_evidence ? "review_required" : "approved", !regulatoryApplicable ? "Not evaluated" : result.regulatory.fail + result.regulatory.potential_gap ? "Potential gap" : result.regulatory.insufficient_evidence ? "Evidence needed" : "Control proxies satisfied")}</header>
    <p>Operational rules were cross-referenced to exact provisions. This is a screening result, not certification.</p>
    <ul>${renderCountLine("Control proxy satisfied", result.regulatory.pass, regulatoryApplicable, "pass", "applicable")}${renderCountLine("Potential gap", result.regulatory.fail + result.regulatory.potential_gap, regulatoryApplicable, "fail", "applicable")}${renderCountLine("Insufficient evidence", result.regulatory.insufficient_evidence, regulatoryApplicable, "review", "applicable")}${renderCountLine("Not applicable", result.regulatory.not_applicable, regulatoryTotal, "neutral", "total")}</ul>
  </article><article class="assessment-layer-card readiness-layer">
    <header><div><span>FORWARD-LOOKING REQUIREMENTS</span><strong>Future readiness</strong></div>${status(!readinessApplicable ? "pending" : result.future_readiness.readiness_gaps || result.future_readiness.insufficient_evidence ? "review_required" : "approved", !readinessApplicable ? "Not evaluated" : result.future_readiness.readiness_gaps ? "Readiness gap" : result.future_readiness.insufficient_evidence ? "Evidence needed" : "Ready")}</header>
    <p>Readiness checks anticipate staged obligations and are explicitly excluded from current-law proxy pass/fail.</p>
    <ul>${renderCountLine("Ready", result.future_readiness.ready, readinessApplicable, "pass", "applicable")}${renderCountLine("Readiness gap", result.future_readiness.readiness_gaps, readinessApplicable, "fail", "applicable")}${renderCountLine("Insufficient evidence", result.future_readiness.insufficient_evidence, readinessApplicable, "review", "applicable")}${renderCountLine("Not applicable", result.future_readiness.not_applicable, readinessTotal, "neutral", "total")}</ul>
  </article><article class="assessment-layer-card policy-layer">
    <header><div><span>COMPANY AUTHORITY</span><strong>Internal policy</strong></div>${status(!policyTotal || !policyApplicable ? "pending" : result.internal_policy.fail ? "blocked" : result.internal_policy.manual_review || result.internal_policy.insufficient_evidence ? "review_required" : "approved", !policyTotal || !policyApplicable ? "Not evaluated" : result.internal_policy.fail ? "Block" : result.internal_policy.manual_review ? "Manual review" : result.internal_policy.insufficient_evidence ? "Evidence needed" : "Pass")}</header>
    <p>A stricter policy decision remains binding even when the regulatory screen passes.</p>
    <ul>${renderCountLine("Pass", result.internal_policy.pass, policyApplicable, "pass", "applicable")}${renderCountLine("Fail / block", result.internal_policy.fail, policyApplicable, "fail", "applicable")}${renderCountLine("Manual review", result.internal_policy.manual_review, policyApplicable, "review", "applicable")}${renderCountLine("Insufficient evidence", result.internal_policy.insufficient_evidence, policyApplicable, "review", "applicable")}${renderCountLine("Not applicable / not evaluated", result.internal_policy.not_evaluated, policyTotal, "neutral", "total")}</ul>
  </article><article class="assessment-layer-card advisory-layer">
    <header><div><span>ADVISORY FRAMEWORK</span><strong>NIST AI RMF mapping</strong></div>${status("pending", "Not scored")}</header>
    <p>Advisory mappings can guide remediation, but are never mixed into regulatory or internal-policy denominators.</p>
    <ul>${renderCountLine("Scored as legal compliance", 0, 0, "neutral", "checks")}${renderCountLine("Scored as internal policy", 0, 0, "neutral", "checks")}</ul>
  </article>`;
  renderModelStatistics(result.model_statistics);
  $("#assessment-findings-count").textContent = `${result.findings.length} finding${result.findings.length === 1 ? "" : "s"}`;
  $("#assessment-findings-body").innerHTML = result.findings.length ? result.findings.map((finding) => `<tr><td><strong>${esc(finding.record_id)}</strong></td><td><span class="finding-layer ${String(finding.layer).toLowerCase().includes("policy") ? "policy" : String(finding.layer).toLowerCase().includes("readiness") ? "readiness" : "regulation"}">${esc(finding.layer)}</span></td><td>${status(String(finding.result).toLowerCase().includes("pass") ? "approved" : String(finding.result).toLowerCase().includes("fail") || String(finding.result).toLowerCase().includes("block") ? "blocked" : "review_required", finding.result)}</td><td><strong>${esc(finding.reference)}</strong>${finding.official_url ? `<a class="finding-source-link" href="${esc(finding.official_url)}" target="_blank" rel="noopener noreferrer">Official source ↗</a>` : ""}</td><td>${esc(finding.evidence)}</td><td>${esc(finding.action)}</td></tr>`).join("") : '<tr><td colspan="6" class="assessment-no-findings"><strong>No row-level issue was detected by the rules evaluated.</strong><span>This does not constitute a legal-compliance opinion.</span></td></tr>';
  $("#assessment-run-provenance").innerHTML = `<div><span>Run ID</span><strong>${esc(result.run_id)}</strong></div><div><span>Evaluation engine</span><strong>${esc(result.engine)}</strong></div><div><span>Policy interpretation</span><strong>${esc(result.policy_interpretation)}</strong></div><div><span>Dataset evidence</span><strong>${esc(result.dataset_hash || "Recorded")}</strong></div><div><span>Legal determination</span><strong>Not asserted</strong></div>`;
}

async function createActivePolicy(name, text) {
  if (!text.trim()) return null;
  const draft = await request("/api/governance/policies/drafts", {
    method: "POST",
    body: JSON.stringify({ name, filename: "synthetic-company-policy.txt", text, synthetic_policy_confirmed: true }),
  });
  const policyId = draft.policy_id || draft.id || draft.policy?.policy_id || draft.policy?.id;
  if (!policyId) throw new Error("The policy draft was created without an identifier.");
  const extractedRules = draft.rules || draft.policy?.rules || [];
  const unparsedClauses = draft.unparsed_clauses || draft.policy?.unparsed_clauses || [];
  if (!extractedRules.length) throw new Error("No enforceable rule was extracted. Revise the policy wording and review the retained draft before running it.");
  const reviewLines = extractedRules.length
    ? extractedRules.map((rule, index) => `${index + 1}. ${rule.clause_id || rule.rule_id}: ${rule.source_clause || rule.description || "Extracted rule"}\n   Enforced as: ${rule.description || "Mapped deterministic rule"}`)
    : ["No enforceable rules were extracted."];
  const approved = window.confirm([
    "Review the deterministic policy extraction before activation:",
    "",
    ...reviewLines,
    "",
    `${unparsedClauses.length} clause${unparsedClauses.length === 1 ? "" : "s"} could not be parsed and will not be enforced.`,
    "",
    "Activate all listed rules for this synthetic run?",
  ].join("\n"));
  if (!approved) throw new Error("Policy activation cancelled. The extracted draft remains inactive and the dataset was not evaluated.");
  await request(`/api/governance/policies/${encodeURIComponent(policyId)}/activate`, {
    method: "POST",
    body: JSON.stringify({ approved_by: "Demo policy owner", rationale: "Activated for this synthetic demonstration.", approve_all_extracted_rules: true }),
  });
  return policyId;
}

async function runUploadAssessment(button) {
  const dataset = state.uploadAssessment.dataset;
  if (!dataset) return;
  if (state.datasetGovernanceAvailable !== true) {
    renderUploadAssessment();
    showToast(INCOMPATIBLE_SERVER_MESSAGE, true);
    return;
  }
  button.disabled = true;
  button.textContent = "Evaluating records…";
  try {
    const policyText = state.uploadAssessment.policyText.trim();
    let policyId = state.uploadAssessment.policyId;
    if (policyText && !policyId) {
      policyId = await createActivePolicy(state.uploadAssessment.policyName || "Uploaded company policy", policyText);
      state.uploadAssessment.policyId = policyId;
    }
    const response = await request("/api/governance/dataset-runs", {
      method: "POST",
      body: JSON.stringify({
        name: dataset.name,
        filename: dataset.name,
        format: dataset.format,
        content: dataset.content,
        synthetic_data_confirmed: true,
        model_id: dataset.name.toLowerCase().includes("clinical") ? "healthcare-summary-prod" : "finance-credit-risk-prod",
        policy_ids: policyId ? [policyId] : [],
      }),
    });
    state.uploadAssessment.result = normalizeAssessmentResult(response, dataset);
    renderUploadAssessment();
    $("#assessment-results").scrollIntoView({ behavior: "smooth", block: "start" });
    showToast("Dataset evaluation completed with separate regulatory and internal-policy results.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = !state.uploadAssessment.dataset || state.datasetGovernanceAvailable !== true;
    button.textContent = "Run governance assessment";
  }
}

function assetById(id) {
  return state.data?.assets.find((asset) => asset.asset_id === id);
}

function setView(name) {
  if (!viewCopy[name]) return;
  state.view = name;
  $$("[data-view-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.viewPanel === name));
  $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
  const [eyebrow, title, subtitle] = viewCopy[name];
  $("#page-eyebrow").textContent = eyebrow;
  $("#page-title").textContent = title;
  $("#page-subtitle").textContent = subtitle;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function entity(asset) {
  const icon = asset.asset_type.includes("agent") || asset.asset_type.includes("Agent") ? "AG" : asset.asset_type === "Shadow AI" ? "?" : "ML";
  return `<div class="entity"><span class="entity-icon">${icon}</span><div><strong>${esc(asset.name)}</strong><small>${esc(asset.asset_type)} · ${esc(asset.business_unit)}</small></div></div>`;
}

function status(value, label = null) {
  return `<span class="status-pill ${esc(decisionClass(value))}">${esc(label || titleCase(value))}</span>`;
}

function list(value) {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== "object") return [];
  return Object.values(value);
}

function first(object, keys, fallback = null) {
  for (const key of keys) {
    const value = object?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return fallback;
}

function pipelineCatalog(payload = state.pipelineData) {
  const raw = payload?.catalog?.pipelines || payload?.catalog || payload?.pipelines || [];
  return list(raw).flatMap((item) => item?.pipelines ? list(item.pipelines) : [item]).filter((item) => item && typeof item === "object");
}

function pipelineRuns(payload = state.pipelineData) {
  return list(payload?.runs).filter((item) => item && typeof item === "object");
}

function pipelineId(pipeline) {
  return String(first(pipeline, ["pipeline_id", "id", "slug"], ""));
}

function runPipelineId(run) {
  return String(first(run, ["pipeline_id", "pipeline", "catalog_id"], ""));
}

function pipelineCases(pipeline) {
  return list(pipeline?.cases);
}

function pipelineModes(pipeline) {
  const modes = list(pipeline?.modes);
  return modes.length ? modes : [
    { id: "controlled", label: "Controlled path", kind: "controlled" },
    { id: "negative", label: "Negative control test", kind: "negative" },
  ];
}

function currentPipeline() {
  return pipelineCatalog().find((item) => pipelineId(item) === state.selectedPipelineId) || pipelineCatalog()[0] || null;
}

function currentCase(pipeline = currentPipeline()) {
  const cases = pipelineCases(pipeline);
  return cases.find((item) => String(first(item, ["case_id", "id"], "")) === state.selectedCaseId) || cases[0] || null;
}

function currentPipelineRun() {
  const runs = pipelineRuns();
  const run = runs.find((item) => item.run_id === state.selectedRunId)
    || (state.pipelineData?.latest_run?.run_id === state.selectedRunId ? state.pipelineData.latest_run : null)
    || null;
  return run && runPipelineId(run) === state.selectedPipelineId ? run : null;
}

function industryOf(item) {
  const value = String(first(item, ["industry", "domain", "sector"], "finance")).toLowerCase();
  return value.includes("health") ? "healthcare" : "finance";
}

function industryLabel(item) {
  return industryOf(item) === "healthcare" ? "Healthcare" : "Financial services";
}

function industryIcon(item) {
  return industryOf(item) === "healthcare" ? "+" : "₣";
}

function initialisePipelineSelection(payload) {
  const catalog = pipelineCatalog(payload);
  if (!catalog.length) return;
  const latest = payload.latest_run;
  const selectedExists = catalog.some((item) => pipelineId(item) === state.selectedPipelineId);
  if (!selectedExists) state.selectedPipelineId = runPipelineId(latest) || pipelineId(catalog[0]);
  const pipeline = catalog.find((item) => pipelineId(item) === state.selectedPipelineId) || catalog[0];
  const cases = pipelineCases(pipeline);
  const selectedCaseExists = cases.some((item) => String(first(item, ["case_id", "id"], "")) === state.selectedCaseId);
  if (!selectedCaseExists) state.selectedCaseId = String(first(cases[0], ["case_id", "id"], ""));
  const modes = pipelineModes(pipeline);
  if (!modes.some((item) => String(first(item, ["id", "mode"], "")) === state.selectedMode)) {
    state.selectedMode = String(first(modes[0], ["id", "mode"], "controlled"));
  }
  const knownRuns = pipelineRuns(payload);
  const runExists = knownRuns.some((item) => item.run_id === state.selectedRunId);
  if (state.selectedRunId !== "" && !runExists) state.selectedRunId = latest?.run_id || knownRuns[0]?.run_id || null;
}

function runStatusCopy(run) {
  if (!run) return ["idle", "Ready to start", "Choose a fictional case and start a governed run."];
  const copy = {
    created: ["ready", "Run created", "The source record is ready for the first controlled stage."],
    source_loaded: ["ready", "Source context loaded", "Advance to inspect and minimise the outbound data."],
    input_controlled: ["ready", "Input controls passed", "The approved model route can now be invoked."],
    model_completed: ["ready", "Model output generated", "The output must pass domain-specific validation."],
    validation_passed: ["ready", "Validation passed", "Advance to the independent human review gate."],
    waiting_approval: ["waiting_approval", "Human decision required", "The proposed downstream action remains locked."],
    authorized: ["authorized", "Authorised—not executed", "A bound receipt permits only the reviewed action."],
    executed: ["executed", "Execution reconciled", "The simulated adapter outcome is sealed into the evidence chain."],
    blocked: ["blocked", "Pipeline stopped safely", "A control prevented further execution and linked the response evidence."],
    denied: ["denied", "Reviewer denied the action", "No downstream system was invoked."],
  };
  return copy[run.status] || [run.status || "ready", titleCase(run.status || "In progress"), "The governed pipeline state has advanced."];
}

function stageControlText(stage) {
  const raw = stage?.control_ids || stage?.controls || stage?.control_id;
  const controls = Array.isArray(raw) ? raw : raw ? [raw] : [];
  return controls.map(String).join(" · ");
}

function executionStep(step) {
  const stepStatus = step?.status || "pending";
  const symbol = { complete: "✓", waiting: "…", ready: "→", blocked: "×", denied: "×", pending: "⌁", locked: "⌁", skipped: "–" }[stepStatus] || "·";
  const controls = stageControlText(step);
  return `<div class="execution-step ${esc(stepStatus)}"><span class="step-icon">${symbol}</span><div><strong>${esc(first(step, ["label", "title"], "Pipeline stage"))}</strong><small>${esc(first(step, ["detail", "description"], titleCase(stepStatus)))}</small></div>${controls ? `<code>${esc(controls)}</code>` : ""}</div>`;
}

function renderPipelineCatalog(catalog) {
  $("#pipeline-catalog").innerHTML = catalog.map((pipeline) => {
    const id = pipelineId(pipeline);
    const active = id === state.selectedPipelineId;
    const stages = list(pipeline.stages);
    const cases = pipelineCases(pipeline);
    return `<button class="pipeline-card ${industryOf(pipeline)} ${active ? "active" : ""}" data-pipeline-id="${esc(id)}">
      <span class="pipeline-card-icon">${industryIcon(pipeline)}</span>
      <span class="pipeline-card-copy"><small>${esc(industryLabel(pipeline))} pipeline</small><strong>${esc(first(pipeline, ["title", "name"], titleCase(id)))}</strong><span>${esc(first(pipeline, ["description", "summary"], "Execute the complete governed workflow using synthetic data."))}</span></span>
      <span class="pipeline-card-meta"><b>${stages.length}</b> stages · <b>${cases.length}</b> cases <i>${active ? "Selected" : "Open"} →</i></span>
    </button>`;
  }).join("") || '<article class="panel pipeline-empty"><strong>Pipeline catalogue unavailable</strong><p>The shared synthetic demonstration has not returned any workflows.</p></article>';
}

function renderPipelineSelectors(pipeline) {
  const catalog = pipelineCatalog();
  $("#pipeline-select").innerHTML = catalog.map((item) => `<option value="${esc(pipelineId(item))}" ${pipelineId(item) === state.selectedPipelineId ? "selected" : ""}>${esc(industryLabel(item))} — ${esc(first(item, ["title", "name"], titleCase(pipelineId(item))))}</option>`).join("");
  const cases = pipelineCases(pipeline);
  $("#pipeline-case-select").innerHTML = cases.map((item) => {
    const id = String(first(item, ["case_id", "id"], ""));
    return `<option value="${esc(id)}" ${id === state.selectedCaseId ? "selected" : ""}>${esc(first(item, ["title", "name"], id))}</option>`;
  }).join("");
  const modes = pipelineModes(pipeline);
  $("#pipeline-mode-select").innerHTML = modes.map((item) => {
    const id = String(first(item, ["id", "mode"], "controlled"));
    return `<option value="${esc(id)}" ${id === state.selectedMode ? "selected" : ""}>${esc(first(item, ["label", "title"], titleCase(id)))}</option>`;
  }).join("");
  $("#pipeline-config-title").textContent = first(pipeline, ["title", "name"], "Choose a shared synthetic demonstration");
  const selectedCase = currentCase(pipeline);
  $("#pipeline-config-help").textContent = first(selectedCase, ["subtitle", "description"], "Synthetic case data; no external model or system is connected.");
}

function renderPipelinePassport(pipeline, run) {
  const passport = run?.passport || pipeline?.passport || {};
  const model = run?.model || pipeline?.model || {};
  const name = first(passport, ["system_name", "name", "model_id"], first(model, ["model_id", "asset_id"], "Approved model passport"));
  const facts = [
    ["Owner", first(passport, ["owner", "business_owner"], "Assigned at run time")],
    ["Approved model", [first(passport, ["model_id"], first(model, ["model_id"], null)), first(passport, ["version"], first(model, ["version"], null))].filter(Boolean).join(" · ") || "Verified at run time"],
    ["Provider", first(passport, ["provider", "boundary", "region"], "Approved simulation route")],
    ["Risk tier", titleCase(first(passport, ["risk_tier", "risk"], first(pipeline, ["risk_tier"], "Governed")))],
  ];
  const passportStatus = first(passport, ["status"], run ? "verified" : "pending");
  $("#pipeline-passport").innerHTML = `<div class="passport-title"><span class="entity-icon">${industryOf(pipeline) === "healthcare" ? "HC" : "FS"}</span><div><small>GOVERNANCE PASSPORT</small><strong>${esc(name)}</strong></div></div>${facts.map(([label, value]) => `<div><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`).join("")}${status(passportStatus, run ? titleCase(passportStatus) : "Loads on start")}`;
}

function renderPipelineStages(pipeline, run) {
  const stages = list(run?.stages).length ? list(run.stages) : list(pipeline?.stages).map((item, index) => ({ ...item, status: index === 0 ? "ready" : "pending" }));
  $("#pipeline-stages").style.setProperty("--stage-count", Math.max(stages.length, 1));
  $("#pipeline-stages").innerHTML = stages.map((stage, index) => `<li class="${esc(stage.status || "pending")}"><span>${stage.status === "complete" ? "✓" : index + 1}</span><div><small>${esc(stageControlText(stage) || `STAGE ${index + 1}`)}</small><strong>${esc(first(stage, ["label", "title"], `Stage ${index + 1}`))}</strong></div></li>`).join("");
}

function flattenDisplayFacts(value, prefix = "", depth = 0) {
  if (!value || typeof value !== "object" || depth > 1) return [];
  return Object.entries(value).flatMap(([key, item]) => {
    if (["prompt", "task", "description", "notes", "model_output", "provider_payload"].includes(key)) return [];
    const label = [prefix, titleCase(key)].filter(Boolean).join(" · ");
    if (item && typeof item === "object" && !Array.isArray(item)) return flattenDisplayFacts(item, label, depth + 1);
    if (Array.isArray(item)) return item.length ? [[label, item.map((part) => typeof part === "object" ? JSON.stringify(part) : String(part)).join(", ")]] : [];
    return item === null || item === undefined || item === "" ? [] : [[label, String(item)]];
  });
}

function syntheticRecordKey(pipeline = currentPipeline(), selectedCase = currentCase(pipeline)) {
  if (!pipeline || !selectedCase) return null;
  const caseId = String(first(selectedCase, ["case_id", "id"], ""));
  return caseId ? `${pipelineId(pipeline)}/${caseId}` : null;
}

function renderSyntheticLabel(record, detail = "Shared synthetic demonstration") {
  return `<div class="synthetic-data-banner"><span class="synthetic-data-badge">FICTIONAL · SYNTHETIC DATA</span><span>${esc(detail)}</span><strong>No external system is contacted</strong></div>`;
}

function operationalStatus(value) {
  const normalised = String(value || "pending");
  const tone = normalised.includes("released") || normalised.includes("signed") ? "verified" : "pending";
  return status(tone, titleCase(normalised));
}

function renderFinanceRecord(record) {
  const currency = record.currency || "NOK";
  const payments = list(record.payments);
  return `<article class="synthetic-record finance-record">
    <header class="synthetic-record-heading"><div><small>FINANCE SOURCE RECORD</small><h3>${esc(record.title || "Synthetic payment batch")}</h3><p>${esc(record.subtitle || record.case_id)}</p></div>${operationalStatus(record.operational_status)}</header>
    <div class="synthetic-record-metrics">
      <div><span>Declared total</span><strong>${esc(formatAmount(record.declared_total, currency))}</strong></div>
      <div><span>Ledger total</span><strong>${esc(formatAmount(record.ledger_total, currency))}</strong></div>
      <div><span>Record version</span><strong>v${esc(record.record_version)}</strong></div>
      <div><span>Reconciliation reference</span><strong>${esc(record.reconciliation_reference)}</strong></div>
    </div>
    <div class="synthetic-table-wrap"><table class="synthetic-table"><thead><tr><th>Payment</th><th>Fictional beneficiary</th><th>Amount</th><th>Sanctions screen</th><th>Duplicate</th></tr></thead><tbody>${payments.map((payment) => `<tr><td><strong>${esc(payment.payment_id)}</strong></td><td>${esc(payment.beneficiary)}</td><td>${esc(formatAmount(payment.amount, currency))}</td><td>${status(payment.sanctions_result === "clear" ? "effective" : "blocked", titleCase(payment.sanctions_result))}</td><td>${payment.duplicate ? status("blocked", "Flagged") : status("effective", "No")}</td></tr>`).join("")}</tbody></table></div>
    <footer class="synthetic-record-footer"><span>Source system: ${esc(record.source_system)}</span><span>Classification: ${esc(titleCase(record.classification))}</span><span>${payments.length} payments</span></footer>
  </article>`;
}

function renderHealthcareRecord(record) {
  const patient = record.patient || {};
  const encounter = record.encounter || {};
  const observations = Object.entries(encounter.observations || {});
  const medications = list(encounter.medications);
  const allergies = list(encounter.allergies);
  const instructions = list(encounter.instructions);
  return `<article class="synthetic-record healthcare-record">
    <header class="synthetic-record-heading"><div><small>HEALTHCARE SOURCE RECORD</small><h3>${esc(record.title || "Synthetic patient encounter")}</h3><p>${esc(record.subtitle || record.case_id)}</p></div>${operationalStatus(record.operational_status)}</header>
    <div class="patient-identity"><span class="patient-avatar">HC</span><div><small>FICTIONAL PATIENT</small><strong>${esc(patient.display_name)}</strong><p>${esc(patient.medical_record_number)} · Born ${esc(patient.date_of_birth)}</p></div><div class="record-version"><span>Record version</span><strong>v${esc(record.record_version)}</strong></div></div>
    <div class="encounter-grid">
      <section><small>RECORDED DIAGNOSIS</small><strong>${esc(encounter.diagnosis)}</strong><p>${esc(encounter.follow_up)}</p></section>
      <section><small>OBSERVATIONS</small>${observations.length ? `<dl>${observations.map(([label, value]) => `<div><dt>${esc(titleCase(label))}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>` : "<p>None recorded</p>"}</section>
      <section><small>MEDICINES</small><div class="record-tags">${medications.length ? medications.map((item) => `<span>${esc(item)}</span>`).join("") : "<span>None recorded</span>"}</div><small>ALLERGIES</small><div class="record-tags warning">${allergies.length ? allergies.map((item) => `<span>${esc(item)}</span>`).join("") : "<span>None recorded</span>"}</div></section>
      <section><small>PATIENT INSTRUCTIONS</small><ul>${instructions.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></section>
    </div>
    <footer class="synthetic-record-footer"><span>Source system: ${esc(record.source_system)}</span><span>Classification: ${esc(titleCase(record.classification))}</span><span>Secure portal queue: ${list(record.portal_queue).length}</span></footer>
  </article>`;
}

function renderExecutionStateCard(record, pipeline, phase) {
  const healthcare = industryOf(pipeline) === "healthcare";
  const release = record.release || null;
  const summary = record.signed_summary || null;
  const portalQueue = list(record.portal_queue);
  const actionDetail = healthcare
    ? (summary
      ? `<div class="state-action-result"><small>SIGNED VISIT SUMMARY</small><strong>${esc(summary.diagnosis || "Summary signed")}</strong><p>${esc(summary.summary || summary.follow_up || "The approved summary was written to the simulated EHR.")}</p><span>Portal queue: ${portalQueue.length ? esc(titleCase(portalQueue[0].status)) : "Empty"}</span></div>`
      : '<div class="state-action-empty"><strong>No signed summary</strong><span>Secure portal queue is empty</span></div>')
    : (release
      ? `<div class="state-action-result"><small>SIMULATED PAYMENT RELEASE</small><strong>${esc(formatAmount(release.amount, release.currency || record.currency))}</strong><p>Released into the shared synthetic demonstration.</p><span>External side effect: ${release.external_side_effect ? "Yes" : "No"}</span></div>`
      : '<div class="state-action-empty"><strong>No payment released</strong><span>Batch remains held for review</span></div>');
  return `<article class="execution-state-card ${phase.toLowerCase()}"><header><span>${esc(phase)}</span>${operationalStatus(record.operational_status)}</header><div class="execution-state-facts"><div><small>Status</small><strong>${esc(titleCase(record.operational_status))}</strong></div><div><small>Record version</small><strong>v${esc(record.record_version)}</strong></div></div>${actionDetail}</article>`;
}

function renderExecutionComparison(pipeline, run) {
  const before = run?.execution?.before_record;
  const after = run?.execution?.after_record;
  if (!before || !after) return "";
  return `<section class="execution-comparison"><header><div><small>EXECUTION OUTCOME</small><h3>Authoritative source state changed exactly once</h3><p>The approved action is reconciled against the shared synthetic demonstration.</p></div>${status("verified", "Reconciled")}</header><div class="execution-comparison-grid">${renderExecutionStateCard(before, pipeline, "Before")}<div class="comparison-arrow" aria-hidden="true">→</div>${renderExecutionStateCard(after, pipeline, "After")}</div></section>`;
}

function renderSyntheticRecordPanel(pipeline = currentPipeline(), run = currentPipelineRun()) {
  const content = $("#synthetic-record-content");
  const recordStatus = $("#synthetic-record-status");
  if (!content || !recordStatus) return;
  const expectedKey = syntheticRecordKey(pipeline);
  const record = state.syntheticRecordKey === expectedKey ? state.syntheticRecord : null;
  if (!record) {
    recordStatus.innerHTML = status("pending", "Loading synthetic record");
    content.innerHTML = `${renderSyntheticLabel({}, "Shared synthetic demonstration")}<div class="synthetic-record-loading"><span></span><div><strong>Loading the full fictional source record</strong><p>The record will appear here before any governed run begins.</p></div></div>`;
    return;
  }
  recordStatus.innerHTML = `${status("verified", "Synthetic record loaded")}<small>${esc(record.case_id)} · v${esc(record.record_version)}</small>`;
  const recordView = industryOf(pipeline) === "healthcare" ? renderHealthcareRecord(record) : renderFinanceRecord(record);
  content.innerHTML = `${renderSyntheticLabel(record)}${recordView}${renderExecutionComparison(pipeline, run)}`;
}

async function refreshSyntheticRecord({ force = false } = {}) {
  const pipeline = currentPipeline();
  const selectedCase = currentCase(pipeline);
  const key = syntheticRecordKey(pipeline, selectedCase);
  if (!key) return;
  if (!force && state.syntheticRecord && state.syntheticRecordKey === key) {
    renderSyntheticRecordPanel(pipeline, currentPipelineRun());
    return;
  }
  const requestNumber = ++state.syntheticRecordRequest;
  state.syntheticRecord = null;
  state.syntheticRecordKey = key;
  renderSyntheticRecordPanel(pipeline, currentPipelineRun());
  try {
    const record = await request(`/api/demo-records/${encodeURIComponent(pipelineId(pipeline))}/${encodeURIComponent(first(selectedCase, ["case_id", "id"], ""))}`);
    if (requestNumber !== state.syntheticRecordRequest || key !== syntheticRecordKey()) return;
    state.syntheticRecord = record;
    state.syntheticRecordKey = key;
    renderSyntheticRecordPanel(currentPipeline(), currentPipelineRun());
  } catch (error) {
    if (requestNumber !== state.syntheticRecordRequest) return;
    const content = $("#synthetic-record-content");
    const recordStatus = $("#synthetic-record-status");
    if (recordStatus) recordStatus.innerHTML = status("blocked", "Record unavailable");
    if (content) content.innerHTML = `${renderSyntheticLabel({}, "Shared synthetic demonstration")}<div class="synthetic-record-error"><strong>The fictional record could not be loaded.</strong><p>${esc(error.message)}</p></div>`;
  }
}

function renderSourceApplication(pipeline, run) {
  const selectedCase = run?.case || currentCase(pipeline) || {};
  const snapshot = run?.source_snapshot || selectedCase?.source_snapshot || selectedCase?.data || { key_facts: selectedCase.key_facts };
  const source = pipeline?.source_application || pipeline?.source_system || snapshot?.application || {};
  const sourceName = typeof source === "string" ? source : first(source, ["name", "application", "title"], industryOf(pipeline) === "healthcare" ? "Clinical Workspace" : "Lending Workspace");
  const organisation = first(snapshot, ["organisation", "organization", "tenant", "provider"], industryOf(pipeline) === "healthcare" ? "Northstar Health · fictional" : "Nordic Lending Group · fictional");
  const caseId = first(selectedCase, ["case_id", "id"], "Case not selected");
  const caseTitle = first(selectedCase, ["title", "name", "subject"], first(snapshot, ["subject_name", "patient_name", "applicant_name"], "Fictional case"));
  const subtitle = first(selectedCase, ["subtitle", "description"], first(snapshot, ["encounter", "case_type", "request"], "Synthetic source record"));
  const classification = first(selectedCase, ["classification"], first(snapshot, ["classification", "data_class"], "Confidential"));
  const facts = flattenDisplayFacts(snapshot).filter(([label]) => !/organisation|organization|application/i.test(label)).slice(0, 9);
  const output = run?.model_output;
  const validation = run?.validation;
  const checks = list(validation?.checks);
  const workState = !run
    ? '<div class="pipeline-source-empty"><span>✦</span><strong>Pipeline ready</strong><p>Start the selected case to load its synthetic source record and controlled task.</p></div>'
    : `<div class="pipeline-source-flow">
        <div class="source-flow-card"><small>CURRENT PIPELINE STATE</small><strong>${esc(titleCase(run.status))}</strong><p>${esc(first(list(run.stages).find((item) => item.status === "ready" || item.status === "waiting"), ["detail"], "Advance the governed pipeline when ready."))}</p></div>
        ${run.provider_payload ? `<details class="pipeline-detail"><summary>Governance-safe provider payload</summary><pre>${esc(typeof run.provider_payload === "string" ? run.provider_payload : JSON.stringify(run.provider_payload, null, 2))}</pre></details>` : ""}
        ${output ? `<div class="source-output"><small>SIMULATED MODEL OUTPUT</small><p>${esc(typeof output === "string" ? output : JSON.stringify(output, null, 2))}</p></div>` : ""}
        ${validation ? `<div class="validation-summary"><div><small>OUTPUT VALIDATION</small>${status(validation.status || (checks.every((item) => item.passed) ? "effective" : "blocked"))}</div>${checks.map((check) => `<span class="validation-check ${check.passed ? "passed" : "failed"}"><b>${check.passed ? "✓" : "×"}</b>${esc(first(check, ["label", "check_id"], "Validation check"))}</span>`).join("")}</div>` : ""}
      </div>`;
  $("#pipeline-source").innerHTML = `<header class="workbench-header"><div class="workbench-brand"><span>${industryOf(pipeline) === "healthcare" ? "EHR" : "FIN"}</span><div><strong>${esc(sourceName)}</strong><small>${esc(organisation)}</small></div></div><div class="protected-badge"><span>✓</span><div><strong>Protected by StyrAI</strong><small>Enforcement active</small></div></div></header>
    <div class="workbench-body pipeline-workbench-body"><aside class="case-sidebar pipeline-case-sidebar"><p class="mini-label">FICTIONAL SOURCE CASE</p><div class="customer-avatar">${industryOf(pipeline) === "healthcare" ? "HC" : "FS"}</div><h3>${esc(caseTitle)}</h3><p class="case-id">${esc(caseId)} · ${esc(subtitle)}</p><dl>${facts.map(([label, value]) => `<div><dt>${esc(label)}</dt><dd>${esc(short(value, 80))}</dd></div>`).join("")}<div><dt>Data class</dt><dd>${status(classification)}</dd></div></dl><div class="source-boundary"><span>⌂</span><p><strong>Source boundary</strong>Synthetic data stays inside this StyrAI demonstration environment.</p></div></aside><section class="copilot-workspace pipeline-copilot"><div class="copilot-heading"><div><span class="copilot-mark">✦</span><div><strong>${esc(first(pipeline, ["title", "name"], "Governed AI pipeline"))}</strong><small>${esc(industryLabel(pipeline))} · shared synthetic demonstration</small></div></div><span class="model-chip">${esc(first(run?.model || {}, ["version", "adapter"], "Not invoked"))}</span></div><div class="conversation pipeline-conversation">${workState}</div></section></div>`;
}

function renderPipelineOverlay(pipeline, run) {
  const [statusClass, heading, detail] = runStatusCopy(run);
  const steps = list(run?.stages).length ? list(run.stages) : list(pipeline?.stages).map((item) => ({ ...item, status: "pending", detail: first(item, ["detail"], "Waiting for the governed run.") }));
  const incidentIds = list(run?.linked_incident_ids);
  const automationIds = list(run?.linked_automation_run_ids);
  const runtime = run?.runtime_event || {};
  const intervention = run ? `<div class="overlay-card ${["blocked", "denied"].includes(run.status) ? "block-card" : ""}"><h4>${esc(heading)}</h4><p>${esc(detail)}</p><div class="overlay-facts"><div class="overlay-fact"><span>Provider invoked</span><strong>${run.provider_invoked ? "Yes · simulated" : "No"}</strong></div><div class="overlay-fact"><span>Downstream invoked</span><strong>${run.downstream_invoked ? "Yes · simulated" : "No"}</strong></div><div class="overlay-fact"><span>Runtime decision</span><strong>${esc(titleCase(first(runtime, ["decision", "status"], run.status)))}</strong></div><div class="overlay-fact"><span>Raw source in evidence</span><strong>No</strong></div>${incidentIds.length ? `<div class="overlay-fact"><span>Linked incidents</span><strong>${esc(incidentIds.join(", "))}</strong></div>` : ""}${automationIds.length ? `<div class="overlay-fact"><span>Automations</span><strong>${esc(automationIds.join(", "))}</strong></div>` : ""}</div>${run.reconciliation ? `<div class="provider-payload"><strong>Reconciliation</strong><br>${esc(typeof run.reconciliation === "string" ? run.reconciliation : JSON.stringify(run.reconciliation, null, 2))}</div>` : ""}</div>` : '<div class="overlay-card"><h4>Controls are ready</h4><p>Start a run to execute identity, data, model, validation, human-oversight and action controls.</p><div class="overlay-facts"><div class="overlay-fact"><span>Unknown routes</span><strong>Fail closed</strong></div><div class="overlay-fact"><span>External connections</span><strong>None</strong></div><div class="overlay-fact"><span>Environment</span><strong>Shared synthetic demonstration</strong></div></div></div>';
  $("#pipeline-overlay").innerHTML = `<header class="overlay-header"><div><span class="overlay-mark">S</span><div><strong>StyrAI runtime</strong><small>${esc(industryLabel(pipeline))} enforcement overlay</small></div></div><span class="overlay-connection"><i></i> Demonstration runtime</span></header><div class="overlay-status ${esc(statusClass)}"><div class="overlay-status-line"><span class="overlay-status-label">${esc(run ? titleCase(run.status) : "ENFORCEMENT READY")}</span>${run ? status(run.status) : '<span class="status-pill authorized">Ready</span>'}</div><h3>${esc(heading)}</h3><p>${esc(detail)}</p></div><div class="overlay-timeline">${steps.map(executionStep).join("")}</div><div class="overlay-intervention">${intervention}</div>`;
}

function renderPipelineActionDock(run, pipeline) {
  const dock = $("#pipeline-action-dock");
  if (!run) {
    dock.innerHTML = '<div class="pipeline-dock-copy"><span class="handoff-icon blue">▶</span><div><p class="eyebrow">NEXT ACTION</p><h3>Start the selected governed run</h3><p>The pipeline will pause at each executable control boundary.</p></div></div><button class="button primary pipeline-start-secondary">Start governed run</button>';
    return;
  }
  const terminal = ["executed", "blocked", "denied"].includes(run.status);
  const review = run.status === "waiting_approval";
  const authorised = run.status === "authorized";
  const canAdvance = !terminal && !review && !authorised;
  const [, heading, statusDetail] = runStatusCopy(run);
  const approvedBy = list(run.governed_action?.approved_by);
  const requiredApprovals = Number(run.governed_action?.decision?.required_approvals || 1);
  const detail = review ? `${approvedBy.length} of ${requiredApprovals} required approvals recorded. ${statusDetail}` : statusDetail;
  const approvers = list(pipeline?.approvers);
  const usedDemonstrationApprovers = list(run.approval_contexts).map((item) => item.demonstration_approver_id);
  const availableApprovers = approvers.filter((item) => !usedDemonstrationApprovers.includes(first(item, ["approver_id", "id"], "")));
  const reviewerControl = availableApprovers.length
    ? `<select id="pipeline-reviewer">${availableApprovers.map((item) => `<option value="${esc(first(item, ["approver_id", "id"], ""))}">${esc(first(item, ["label", "name"], first(item, ["approver_id", "id"], "Reviewer")))}</option>`).join("")}</select>`
    : `<input id="pipeline-reviewer" value="${industryOf(run) === "healthcare" ? "attending-clinician-demo" : "payments-manager-demo"}" />`;
  const reviewForm = review ? `<div class="pipeline-review-form"><label>Demonstration reviewer role${reviewerControl}</label><label>Rationale<textarea id="pipeline-rationale" rows="2">Reviewed the fictional record, model output and validation results.</textarea></label></div>` : "";
  dock.innerHTML = `<div class="pipeline-dock-head"><div><p class="eyebrow">VALID NEXT ACTION</p><h3>${esc(heading)}</h3><p>${esc(detail)}</p></div>${status(run.status)}</div>${reviewForm}<div class="pipeline-dock-actions">
    <button class="button secondary pipeline-advance-next" ${canAdvance ? "" : "disabled"}>Step next</button>
    <button class="button primary pipeline-advance-review" ${canAdvance ? "" : "disabled"}>Run to review</button>
    <button class="button approve-button pipeline-decision" data-approved="true" ${review ? "" : "disabled"}>Approve</button>
    <button class="button deny-button pipeline-decision" data-approved="false" ${review ? "" : "disabled"}>Deny</button>
    <button class="button execute-button pipeline-execute" ${authorised ? "" : "disabled"}>Execute authorised action</button>
    <span class="dock-divider"></span>
    <button class="small-button danger pipeline-inject" data-kind="drift" ${terminal ? "disabled" : ""}>Inject drift</button>
    <button class="small-button danger pipeline-inject" data-kind="version" ${terminal ? "disabled" : ""}>Inject version change</button>
  </div>`;
}

function renderPipelineProof(run) {
  $("#pipeline-correlation").textContent = run?.run_id || "Not started";
  const action = run?.governed_action || {};
  const execution = run?.execution || {};
  const runtime = run?.runtime_event || {};
  const model = run?.model || {};
  const facts = run ? [
    ["Correlation ID", run.run_id],
    ["Runtime event", first(runtime, ["event_id", "runtime_event_id", "id"], "Not created")],
    ["Model", [first(model, ["model_id", "asset_id"], "Not invoked"), first(model, ["version"], null)].filter(Boolean).join(" · ")],
    ["Action", first(action?.action || action, ["action_id", "id"], first(action, ["action_id"], "Not created"))],
    ["Authorisation", first(action, ["authorization_receipt", "authorisation_receipt", "receipt"], "Not issued")],
    ["Execution receipt", first(execution, ["adapter_receipt", "delivery_receipt", "execution_receipt", "receipt", "receipt_id"], run.downstream_invoked ? "Recorded" : "Not executed")],
    ["Incidents", list(run.linked_incident_ids).join(", ") || "None"],
    ["Audit integrity", state.data?.audit?.valid ? "Chain verified" : "Review required"],
  ] : [
    ["Correlation ID", "Created when the run starts"], ["Runtime event", "Not started"], ["Model", "Not invoked"], ["Action", "Not proposed"], ["Authorisation", "Not issued"], ["Execution receipt", "Not executed"], ["Incidents", "None"], ["Audit integrity", state.data?.audit?.valid ? "Chain verified" : "Ready"],
  ];
  $("#pipeline-proof").innerHTML = facts.map(([label, value]) => `<div class="proof-fact"><span>${esc(label)}</span><strong title="${esc(value)}">${esc(short(value, 42))}</strong></div>`).join("");
  $("#download-execution-evidence").disabled = !run;
}

function renderPipelineHistory(runs, catalog) {
  const container = $("#pipeline-run-history");
  if (!runs.length) {
    container.innerHTML = '<div class="empty-list">Start a finance or healthcare pipeline to create correlated run history.</div>';
    return;
  }
  container.innerHTML = runs.slice(0, 12).map((run) => {
    const pipeline = catalog.find((item) => pipelineId(item) === runPipelineId(run)) || run;
    const selected = run.run_id === state.selectedRunId;
    return `<div class="pipeline-history-row ${selected ? "selected" : ""}"><span class="pipeline-history-icon ${industryOf(pipeline)}">${industryIcon(pipeline)}</span><div><strong>${esc(first(run, ["title"], first(pipeline, ["title", "name"], "Governed pipeline")))}</strong><small>${esc(first(run.case || {}, ["title", "case_id"], first(run, ["case_id"], "Fictional case")))}</small></div><div><strong>${esc(when(run.started_at, true))}</strong><small>${esc(run.run_id)}</small></div><div>${status(run.status)}<small>${esc(titleCase(first(run, ["current_stage"], "Complete")))}</small></div><button class="small-button pipeline-open-run" data-run-id="${esc(run.run_id)}">${selected ? "Viewing" : "Open run"}</button></div>`;
  }).join("");
}

function renderExecution(payload) {
  state.pipelineData = payload || { catalog: [], runs: [], latest_run: null };
  initialisePipelineSelection(state.pipelineData);
  const catalog = pipelineCatalog();
  const pipeline = currentPipeline();
  if (!pipeline) {
    renderPipelineCatalog([]);
    $("#pipeline-workspace").classList.add("hidden");
    renderPipelineHistory([], []);
    return;
  }
  $("#pipeline-workspace").classList.remove("hidden");
  const run = currentPipelineRun();
  renderPipelineCatalog(catalog);
  renderPipelineSelectors(pipeline);
  renderPipelinePassport(pipeline, run);
  renderPipelineStages(pipeline, run);
  renderSyntheticRecordPanel(pipeline, run);
  renderSourceApplication(pipeline, run);
  renderPipelineOverlay(pipeline, run);
  renderPipelineActionDock(run, pipeline);
  renderPipelineProof(run);
  renderPipelineHistory(pipelineRuns(), catalog);
}

const governanceScenarioCopy = {
  "data-leak": {
    title: "Corporate AI use · outbound data control",
    summary: "A fictional employee attempts to paste client information and a credential into an unapproved public AI service.",
    runLabel: "Intercept outbound AI request",
  },
  "model-drift": {
    title: "Financial services · production model monitoring",
    summary: "A synthetic population-shift signal pushes a deployed credit-risk model beyond its approved drift threshold.",
    runLabel: "Inject and contain drift",
  },
  "regulatory-gap": {
    title: "Healthcare · regulatory and policy assessment",
    summary: "StyrAI evaluates a deployed clinical summarisation model against its internal passport and applicable governance obligations.",
    runLabel: "Assess deployed AI system",
  },
};

function governanceAsset(assetId, data = state.data) {
  return data?.assets?.find((asset) => asset.asset_id === assetId) || null;
}

function governanceModel(modelId, data = state.governanceData) {
  return data?.models?.find((model) => model.model_id === modelId) || null;
}

function governanceControlCheck(symbol, title, detail, tone = "") {
  return `<div class="control-check ${esc(tone)}"><span>${esc(symbol)}</span><div><strong>${esc(title)}</strong><small>${esc(detail)}</small></div></div>`;
}

function renderGovernanceInput(data, governance = state.governanceData) {
  const scenario = state.governanceScenario;
  if (scenario === "data-leak") {
    return `<div class="governance-object">
      <div class="governance-object-head"><span class="governance-object-icon">EMP</span><div><strong>Employee research workspace</strong><small>Fictional treasury analyst · browser-based AI use</small></div></div>
      <dl class="governance-fact-list"><div><dt>Destination</dt><dd>Unapproved public AI</dd></div><div><dt>Declared class</dt><dd>Internal</dd></div><div><dt>Trust boundary</dt><dd>External provider</dd></div></dl>
      <div class="synthetic-prompt"><small>FICTIONAL INPUT · NEVER TRANSMITTED</small>Summarise the Aurora Energy plan for anna.demo@example.test, account NO93 8601 1117 947. api_key=demo-secret-do-not-send</div>
    </div>`;
  }
  if (scenario === "model-drift") {
    const asset = governanceModel("finance-credit-risk-prod", governance);
    return `<div class="governance-object">
      <div class="governance-object-head"><span class="governance-object-icon">ML</span><div><strong>${esc(asset?.name || "Retail Credit Risk Model")}</strong><small>${esc(asset?.model_name || "Predictive model")} · production</small></div></div>
      <dl class="governance-fact-list"><div><dt>Version</dt><dd>${esc(asset?.version || "12.4")}</dd></div><div><dt>Owner</dt><dd>${esc(asset?.owner || "Credit Risk Models")}</dd></div><div><dt>Approved use</dt><dd>Analyst decision support</dd></div><div><dt>Observed drift</dt><dd>${Number(asset?.metrics?.drift_score ?? .06).toFixed(2)}</dd></div></dl>
    </div>`;
  }
  const asset = governanceModel("healthcare-summary-prod", governance);
  return `<div class="governance-object">
    <div class="governance-object-head"><span class="governance-object-icon">HC</span><div><strong>${esc(asset?.name || "Healthcare Visit Summary Copilot")}</strong><small>${esc(asset?.model_name || "Clinical summary model")} · deployed</small></div></div>
    <dl class="governance-fact-list"><div><dt>Risk tier</dt><dd>${esc(titleCase(asset?.risk_class || "high impact"))}</dd></div><div><dt>Observed version</dt><dd>${esc(asset?.version || "2026.08.2")}</dd></div><div><dt>Approved version</dt><dd>${esc(asset?.approved_version || "2026.08.2")}</dd></div><div><dt>Data handled</dt><dd>Restricted health information</dd></div><div><dt>Jurisdiction</dt><dd>${esc(asset?.region || "EU / Norway")}</dd></div></dl>
  </div>`;
}

function renderGovernanceTrace() {
  const scenario = state.governanceScenario;
  const completed = state.governanceResult?.scenario === scenario;
  if (scenario === "data-leak") {
    return `<div class="control-trace">
      ${governanceControlCheck(completed ? "×" : "1", "Registry and destination", completed ? "Public AI destination is not registered or approved." : "Verify the model, provider, region and contract.", completed ? "fail" : "")}
      ${governanceControlCheck(completed ? "!" : "2", "Sensitive-data inspection", completed ? "Credential, email and bank-account patterns detected." : "Classify the prompt before it crosses the boundary.", completed ? "warn" : "")}
      ${governanceControlCheck(completed ? "×" : "3", "Outbound data policy DATA-001", completed ? "DATA-001 requires a fail-closed decision." : "Apply internal policy to the effective data class.", completed ? "fail" : "")}
      ${governanceControlCheck(completed ? "✓" : "4", "Evidence and response", completed ? "Create metadata-only evidence and notify the owner." : "Prepare the incident and evidence workflow.")}
    </div>`;
  }
  if (scenario === "model-drift") {
    return `<div class="control-trace">
      ${governanceControlCheck(completed ? "!" : "1", "Continuous telemetry", completed ? "Population drift reached 0.27; threshold is 0.15." : "Measure drift, quality, errors and latency continuously.", completed ? "warn" : "")}
      ${governanceControlCheck(completed ? "✓" : "2", "Model passport", "Match production version 12.4 to its approved use and owner.")}
      ${governanceControlCheck(completed ? "×" : "3", "Monitoring policy MON-001", completed ? "Operating threshold breached; normal routing is no longer permitted." : "Compare observed metrics with approved limits.", completed ? "fail" : "")}
      ${governanceControlCheck(completed ? "✓" : "4", "Automated containment", completed ? "Route to fallback, open validation and alert accountable owners." : "Prepare a response before the incident occurs.")}
    </div>`;
  }
  const findings = state.governanceResult?.response?.findings || [];
  return `<div class="control-trace">
    ${governanceControlCheck(findings.length ? "!" : "1", "Risk and use classification", findings.length ? "High-impact healthcare use requires enhanced governance review." : "Determine role, intended use, affected people and risk tier.", findings.length ? "warn" : "")}
    ${governanceControlCheck(findings.length ? "!" : "2", "EU AI Act readiness", findings.length ? "Controls were checked against the staged timeline; legal applicability still requires review." : "Track a potential Annex III readiness horizon of 2 Dec 2027 and confirm applicability with legal owners.", findings.length ? "warn" : "")}
    ${governanceControlCheck(findings.length ? "×" : "3", "Internal policy controls", findings.length ? `${findings.length} control gap${findings.length === 1 ? "" : "s"} require owner action; legal review remains separate.` : "Test the live model passport against company policy.", findings.length ? "fail" : "")}
    ${governanceControlCheck(findings.length ? "✓" : "4", "Evidence and ownership", findings.length ? "Create a reviewable finding with control owner and remediation path." : "Prepare a traceable assessment record.")}
  </div>`;
}

function renderGovernanceOutcome() {
  const result = state.governanceResult;
  if (!result || result.scenario !== state.governanceScenario) {
    return `<div class="governance-pending"><span>◈</span><strong>Ready to enforce</strong><p>Run the test to show the decision, automated action and evidence created by StyrAI.</p></div>`;
  }
  if (result.scenario === "data-leak") {
    const event = result.response.event || {};
    return `<div class="governance-result"><div class="governance-result-banner"><small>RUNTIME DECISION</small><strong>BLOCKED BEFORE PROVIDER</strong></div><p class="decision-reason">${esc(event.reason || "Sensitive information cannot be transmitted to this destination.")}</p><div class="governance-result-list"><div><span>Detected</span><strong>${esc((event.detected_types || []).map(titleCase).join(" · ") || "Restricted data")}</strong></div><div><span>Transmission</span><strong>${event.transmission_prevented === false ? "Allowed" : "Prevented"}</strong></div><div><span>External model invoked</span><strong>${result.response.external_provider_invoked ? "Yes" : "No"}</strong></div><div><span>Raw prompt stored</span><strong>${result.response.raw_input_stored ? "Yes" : "No"}</strong></div><div><span>Incident</span><strong>${esc(result.response.incident?.incident_id || "Created")}</strong></div></div></div>`;
  }
  if (result.scenario === "model-drift") {
    const response = result.response;
    return `<div class="governance-result"><div class="governance-result-banner contained"><small>MONITORING DECISION</small><strong>MODEL CONTAINED</strong></div><p class="decision-reason">Population drift exceeded the approved 0.15 operating threshold. This is a confirmed internal policy breach—not a legal determination.</p><div class="governance-result-list"><div><span>Drift score</span><strong>${Number(response.before_metrics?.drift_score ?? result.before?.drift_score ?? .06).toFixed(2)} → ${Number(response.after_metrics?.drift_score ?? .27).toFixed(2)}</strong></div><div><span>Production state</span><strong>${esc(titleCase(response.model?.status || "guarded"))}</strong></div><div><span>Write-capable calls</span><strong>Routed to fallback</strong></div><div><span>Policy breach</span><strong>${esc(response.policy_breach || "MON-001")}</strong></div><div><span>Incident</span><strong>${esc(response.incident?.incident_id || "Created")}</strong></div></div></div>`;
  }
  const assessment = result.response.assessment || {};
  const findings = result.response.findings || [];
  const critical = findings.filter((finding) => ["critical", "high"].includes(String(finding.severity).toLowerCase())).length;
  return `<div class="governance-result"><div class="governance-result-banner review"><small>ASSURANCE DECISION</small><strong>${findings.length} GAP${findings.length === 1 ? "" : "S"} FLAGGED</strong></div><p class="decision-reason">A synthetic unreviewed model version created a confirmed internal policy breach and potential regulatory obligations at risk. Compliance or legal review is still required.</p><div class="governance-result-list"><div><span>High-priority findings</span><strong>${critical}</strong></div><div><span>Assessment result</span><strong>${esc(titleCase(assessment.result || "review required"))}</strong></div><div><span>Observed version</span><strong>${esc(result.response.version_observation?.model?.version || "2026.09-unreviewed")}</strong></div><div><span>Approved version</span><strong>${esc(result.response.version_observation?.model?.approved_version || "2026.08.2")}</strong></div><div><span>Potential Annex III horizon</span><strong>2 Dec 2027 · applicability review</strong></div><div><span>Legal violation confirmed</span><strong>No</strong></div><div><span>Assessment</span><strong>${esc(assessment.assessment_id || "Recorded")}</strong></div></div></div>`;
}

function renderGovernanceEvidence(data) {
  const target = $("#governance-evidence");
  const badge = $("#governance-evidence-status");
  const result = state.governanceResult;
  if (!result || result.scenario !== state.governanceScenario) {
    badge.textContent = "Ready";
    badge.className = "panel-badge";
    target.innerHTML = '<div class="governance-empty-state"><strong>No test has run yet</strong><p>Choose a scenario and run it to create a policy decision, incident response and reconstructable evidence.</p></div>';
    return;
  }
  badge.textContent = "Evidence created";
  badge.className = "panel-badge green";
  let facts = [];
  if (result.scenario === "data-leak") {
    const event = result.response.event || {};
    facts = [["Runtime event", event.event_id], ["Evidence", result.response.evidence_id], ["Prompt hash", short(event.prompt_hash, 22)], ["Policies", (event.policy_ids || []).join(" · ")], ["Finding", result.response.finding?.finding_id], ["Incident", result.response.incident?.incident_id], ["Raw input", "Not retained"], ["Audit chain", data.audit?.valid ? "Verified" : "Review required"]];
  } else if (result.scenario === "model-drift") {
    facts = [["Model", result.response.model?.model_id], ["Observed version", result.response.model?.version], ["Control", result.response.policy_breach || "MON-001"], ["Finding", result.response.finding?.finding_id], ["Incident", result.response.incident?.incident_id], ["Evidence", result.response.evidence_id], ["Audit chain", data.audit?.valid ? "Verified" : "Review required"]];
  } else {
    const assessment = result.response.assessment || {};
    facts = [["Assessment", assessment.assessment_id], ["System", assessment.model_id || "healthcare-summary-prod"], ["Findings", (result.response.findings || []).length], ["Policy breaches", (result.response.policy_breaches || []).join(" · ")], ["Obligations at risk", (result.response.regulatory_obligations_at_risk || []).join(" · ")], ["Owner", result.response.owner || "Director of Clinical Informatics"], ["Legal violation", result.response.legal_violation_confirmed ? "Confirmed" : "Not asserted"], ["Audit chain", data.audit?.valid ? "Verified" : "Review required"]];
  }
  target.innerHTML = `<div class="governance-evidence-grid">${facts.map(([label, value]) => `<div><span>${esc(label)}</span><strong>${esc(value || "Recorded")}</strong></div>`).join("")}</div>`;
}

function renderGovernanceEstate(data, governance = state.governanceData) {
  const preferred = ["finance-credit-risk-prod", "healthcare-summary-prod", "corporate-copilot-external", "shadow-consumer-ai"];
  const models = preferred.map((id) => governanceModel(id, governance)).filter(Boolean);
  $("#governance-estate").innerHTML = `<div class="governance-estate-list">${models.map((model) => `<div class="governance-estate-row"><span>${model.model_id === "shadow-consumer-ai" ? "?" : model.model_name.toLowerCase().includes("language") ? "AG" : "ML"}</span><div><strong>${esc(model.name)}</strong><small>${esc(titleCase(model.domain))} · ${esc(model.version)}</small></div>${status(model.status)}</div>`).join("")}</div>`;
}

function renderGovernance(data, governance = state.governanceData) {
  const copy = governanceScenarioCopy[state.governanceScenario] || governanceScenarioCopy["data-leak"];
  $$('[data-governance-scenario]').forEach((button) => {
    const active = button.dataset.governanceScenario === state.governanceScenario;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  $("#governance-input").innerHTML = renderGovernanceInput(data, governance);
  $("#governance-control-trace").innerHTML = renderGovernanceTrace();
  $("#governance-outcome").innerHTML = renderGovernanceOutcome();
  $("#governance-scenario-summary").innerHTML = `<strong>${esc(copy.title)}</strong><span>${esc(copy.summary)}</span>`;
  $("#run-governance-scenario").textContent = copy.runLabel;
  $("#governance-system-count").textContent = governance?.models?.length || data.metrics.ai_systems;
  $("#nav-inventory-count").textContent = governance?.models?.length || data.metrics.ai_systems;
  $("#nav-incident-count").textContent = governance?.metrics?.open_incidents ?? data.metrics.open_incidents;
  const deployed = governance?.metrics?.deployed_models ?? data.metrics.production_systems;
  const monitored = governance?.models?.filter((model) => model.environment === "production" && model.monitoring_enabled).length ?? deployed;
  $("#governance-monitoring-coverage").textContent = `${monitored} / ${deployed}`;
  $("#governance-blocked-count").textContent = governance?.metrics?.prevented_transmissions ?? data.metrics.blocked_sensitive_events;
  renderGovernanceEvidence(data);
  renderGovernanceEstate(data, governance);
}

function renderMetrics(data) {
  const { metrics, audit } = data;
  const effectiveControls = data.controls.filter((control) => control.status === "effective").length;
  const productionAssets = data.assets.filter((asset) => asset.environment === "production");
  const monitoredProduction = productionAssets.filter((asset) => asset.monitoring_enabled).length;
  $("#nav-inventory-count").textContent = metrics.ai_systems;
  $("#nav-incident-count").textContent = metrics.open_incidents;
  $("#sidebar-audit").textContent = audit.valid ? "Chain verified" : "Integrity review required";
  $("#sidebar-records").textContent = number(audit.record_count);
  $("#updated-at").textContent = `Updated ${when(data.generated_at, true)}`;
  $("#hero-coverage").textContent = `${effectiveControls}/${data.controls.length}`;
  $("#hero-integrity").textContent = audit.valid ? "Chain verified" : "Review required";
  $("#metric-systems").textContent = metrics.ai_systems;
  $("#metric-production").textContent = metrics.production_systems;
  $("#metric-monitoring").textContent = `${monitoredProduction} / ${productionAssets.length}`;
  $("#metric-calls").textContent = number(metrics.model_calls_24h);
  $("#metric-spend").textContent = `${nok(metrics.model_spend_24h_nok)} spend through governed routes`;
  $("#metric-blocked").textContent = metrics.blocked_sensitive_events;
  $("#metric-incidents").textContent = metrics.open_incidents;
}

function renderDashboard(data) {
  const production = data.assets.filter((asset) => asset.environment === "production");
  $("#dashboard-assets").innerHTML = production.map((asset) => `
    <tr>
      <td>${entity(asset)}</td>
      <td><strong>${esc(asset.owner)}</strong><small>${esc(asset.business_unit)}</small></td>
      <td><span class="risk-pill ${esc(asset.risk_tier)}">${esc(asset.risk_tier)}</span></td>
      <td><strong>${esc(asset.version)}</strong><small>Approved ${esc(asset.approved_version)}</small></td>
      <td><span class="health-dot ${esc(asset.health.status)}"></span>${esc(titleCase(asset.health.status))}</td>
      <td><strong>${number(asset.health.calls_24h)}</strong><small>${number(asset.health.blocked_24h)} controlled</small></td>
    </tr>`).join("");

  const domains = ["Inventory", "Data protection", "Model monitoring", "Evidence"];
  const legend = domains.map((domain) => {
    const controls = data.controls.filter((control) => control.domain === domain);
    const effective = controls.filter((control) => control.status === "effective").length;
    const attention = controls.length - effective;
    return `<div class="coverage-line"><span>${esc(domain)}</span><strong>${effective} effective · ${attention} attention</strong></div>`;
  }).join("");
  const effectiveControls = data.controls.filter((control) => control.status === "effective").length;
  $("#coverage-value").textContent = `${effectiveControls}/${data.controls.length}`;
  $("#coverage-ring").style.setProperty("--coverage", Math.round(100 * effectiveControls / Math.max(1, data.controls.length)));
  $("#coverage-legend").innerHTML = legend;

  $("#dashboard-events").innerHTML = data.events.slice(0, 5).map((event) => `
    <div class="runtime-item">
      <span class="runtime-symbol">${event.decision === "blocked" ? "×" : "✓"}</span>
      <div><strong>${esc(event.asset_name)}</strong><small>${esc(event.actor)} · ${when(event.timestamp, true)}</small></div>
      <div><strong>${esc(titleCase(event.effective_classification))}</strong><small>${esc(event.detected_data_types.join(", ") || "No sensitive pattern")}</small></div>
      <div><strong>${esc(short(event.destination, 26))}</strong><small>${event.latency_ms} ms · ${event.estimated_tokens} tokens</small></div>
      ${status(event.decision)}
    </div>`).join("");

  const open = data.incidents.filter((incident) => incident.status === "open").slice(0, 3);
  $("#dashboard-incidents").innerHTML = open.length ? open.map((incident) => `
    <div class="mini-incident"><div class="mini-incident-head"><strong>${esc(incident.title)}</strong><span class="risk-pill ${esc(incident.severity)}">${esc(incident.severity)}</span></div><p>${esc(incident.summary)}</p></div>`).join("") : '<div class="empty-list">No open incidents.</div>';
  $("#automation-count").textContent = data.automations.filter((rule) => rule.enabled).length;
  $("#automation-runs").textContent = number(data.automations.reduce((total, rule) => total + rule.runs, 0));
}

function inventoryMatches(asset) {
  const term = state.search.toLowerCase();
  const matchesSearch = !term || [asset.name, asset.owner, asset.provider, asset.business_unit, asset.intended_use].join(" ").toLowerCase().includes(term);
  const filters = {
    all: true,
    production: asset.environment === "production",
    high: ["high", "critical"].includes(asset.risk_tier),
    attention: !["approved"].includes(asset.status) || !["healthy"].includes(asset.health.status),
  };
  return matchesSearch && filters[state.inventoryFilter];
}

function renderInventory(data) {
  $("#inventory-total").textContent = data.assets.length;
  const rows = data.assets.filter(inventoryMatches);
  $("#inventory-table").innerHTML = rows.length ? rows.map((asset) => `
    <tr>
      <td>${entity(asset)}</td>
      <td><strong>${esc(asset.owner)}</strong><small>${esc(asset.business_unit)}</small></td>
      <td><strong>${esc(asset.provider)}</strong><small>${esc(asset.region)} · ${asset.external_provider ? "External" : "Customer boundary"}</small></td>
      <td class="usage-copy">${esc(asset.intended_use)}</td>
      <td><span class="risk-pill ${esc(asset.risk_tier)}">${esc(asset.risk_tier)}</span></td>
      <td>${status(asset.status)}</td>
      <td><strong>${esc(when(asset.next_review))}</strong><small>${esc(asset.contract_status)} terms</small></td>
    </tr>`).join("") : '<tr><td colspan="7"><div class="empty-list">No AI systems match this view.</div></td></tr>';
}

function sparkline(values) {
  const width = 150;
  const height = 34;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const points = values.map((value, index) => `${(index / Math.max(1, values.length - 1)) * width},${height - 3 - ((value - min) / span) * (height - 6)}`).join(" ");
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" aria-label="Recent quality trend"><polyline fill="none" stroke="#315efb" stroke-width="2" points="${points}"/><polyline fill="none" stroke="rgba(49,94,251,.13)" stroke-width="7" points="${points}"/></svg>`;
}

function renderMonitoring(data) {
  const monitored = data.assets.filter((asset) => asset.monitoring_enabled);
  $("#healthy-models").textContent = `${monitored.filter((asset) => asset.health.status === "healthy").length} / ${monitored.length}`;
  $("#model-grid").innerHTML = monitored.map((asset) => `
    <article class="panel model-card" data-asset-id="${esc(asset.asset_id)}">
      <div class="model-card-head"><div class="model-card-title"><span class="entity-icon">${asset.asset_type.toLowerCase().includes("agent") ? "AG" : "ML"}</span><div><strong>${esc(asset.name)}</strong><small>${esc(asset.model)} · ${esc(asset.version)} · ${esc(asset.owner)}</small></div></div>${status(asset.health.status)}</div>
      <div class="model-health-grid">
        <div class="health-metric"><span>Groundedness</span><strong>${Math.round(asset.health.groundedness * 100)}%</strong><small>Threshold ≥ 80%</small></div>
        <div class="health-metric"><span>Drift score</span><strong>${asset.health.drift_score.toFixed(2)}</strong><small>Threshold ≤ 0.15</small></div>
        <div class="health-metric"><span>Error rate</span><strong>${(asset.health.error_rate * 100).toFixed(1)}%</strong><small>Threshold ≤ 3%</small></div>
        <div class="health-metric"><span>P95 latency</span><strong>${number(asset.health.p95_latency_ms)} ms</strong><small>Threshold ≤ 2,000</small></div>
      </div>
      <div class="sparkline-wrap"><div><strong>${number(asset.health.calls_24h)} calls · ${nok(asset.health.cost_24h_nok)}</strong><small>Recent groundedness trend</small></div>${sparkline(asset.health.history)}</div>
      <div class="model-actions"><button class="small-button health-button" data-breach="quality">Simulate quality breach</button><button class="small-button health-button" data-breach="drift">Simulate drift</button><button class="small-button health-button" data-breach="latency">Simulate latency</button><button class="small-button danger version-button">Simulate version change</button></div>
    </article>`).join("");
}

function renderDataProtection(data) {
  $("#sim-asset").innerHTML = data.assets.map((asset) => `<option value="${esc(asset.asset_id)}">${esc(asset.name)} — ${esc(asset.provider)}</option>`).join("");
  $("#data-events").innerHTML = data.events.map((event) => `
    <tr><td>${esc(when(event.timestamp, true))}</td><td><strong>${esc(event.asset_name)}</strong><small>${esc(event.actor)}</small></td><td>${esc(titleCase(event.effective_classification))}</td><td>${esc(event.detected_data_types.map(titleCase).join(", ") || "None")}</td><td>${esc(short(event.destination, 30))}</td><td>${status(event.decision)}</td><td><strong>${esc(short(event.prompt_hash, 12))}</strong><small>Metadata only</small></td></tr>`).join("");
}

function renderDecision(result) {
  const event = result.event;
  $("#empty-decision").classList.add("hidden");
  const panel = $("#decision-result");
  panel.classList.remove("hidden");
  panel.innerHTML = `
    <div class="decision-hero ${esc(event.decision)}"><span>Runtime policy decision</span><strong>${esc(titleCase(event.decision))}</strong></div>
    <p class="decision-reason">${esc(event.reason)}</p>
    <div class="decision-facts">
      <div class="decision-fact"><span>Effective class</span><strong>${esc(titleCase(event.effective_classification))}</strong></div>
      <div class="decision-fact"><span>Detected patterns</span><strong>${esc(event.detected_data_types.map(titleCase).join(", ") || "None")}</strong></div>
      <div class="decision-fact"><span>Destination</span><strong>${esc(event.destination)}</strong></div>
      <div class="decision-fact"><span>Controls applied</span><strong>${esc(event.controls_applied.join(", "))}</strong></div>
      <div class="decision-fact"><span>Raw input retained</span><strong>${result.raw_input_stored ? "Yes" : "No"}</strong></div>
      <div class="decision-fact"><span>Evidence ID</span><strong>${esc(event.event_id)}</strong></div>
    </div>
    <div class="redacted-preview"><strong>Governance-safe preview</strong><br />${esc(event.redacted_preview)}</div>`;
}

function renderControls(data) {
  $("#control-total").textContent = data.controls.length;
  const frameworks = ["EU AI Act", "DORA", "ISO 42001", "NIST AI RMF"];
  $("#framework-grid").innerHTML = frameworks.map((framework) => {
    const mapped = data.controls.filter((control) => control.frameworks.includes(framework));
    const effective = mapped.filter((control) => control.status === "effective").length;
    const watch = mapped.filter((control) => control.status === "watch").length;
    const improvement = mapped.filter((control) => control.status === "improvement").length;
    return `<article class="panel framework-card"><div class="framework-card-head"><span>${esc(framework)}</span><strong>${effective}/${mapped.length} effective</strong></div><div class="framework-status-counts"><span>${watch} watch</span><span>${improvement} improvement</span></div><small>${mapped.length} technical controls mapped · not a certification</small></article>`;
  }).join("");
  $("#control-table").innerHTML = data.controls.map((control) => `
    <tr><td><strong>${esc(control.control_id)} · ${esc(control.title)}</strong><small>${esc(control.objective)}</small></td><td>${esc(control.domain)}</td><td>${esc(titleCase(control.mode))}</td><td>${control.automated ? status("effective", "Automated") : status("improvement", "Human-led")}</td><td>${status(control.status)}</td><td><strong>${number(control.evidence_count)} records</strong></td><td><strong>${esc(when(control.last_tested))}</strong></td><td>${esc(control.owner)}</td></tr>`).join("");
}

function renderAutomations(data) {
  $("#automation-total").textContent = data.automations.filter((rule) => rule.enabled).length;
  $("#automation-grid").innerHTML = data.automations.map((rule) => `
    <article class="panel automation-card" data-rule-id="${esc(rule.rule_id)}">
      <div class="automation-card-head"><span class="automation-icon">↻</span><span class="automation-mode">${esc(rule.mode)} · ${rule.enabled ? "on" : "off"}</span></div>
      <h3>${esc(rule.name)}</h3><p>${esc(rule.description)}</p>
      <div class="automation-trigger"><span>Trigger</span><strong>${esc(rule.trigger)}</strong></div>
      <div class="automation-actions-list">${rule.actions.map((action) => `<span>${esc(action)}</span>`).join("")}</div>
      <div class="automation-footer"><small>${number(rule.runs)} runs · ${esc(rule.last_result)}</small><button class="small-button run-automation">Run now</button></div>
    </article>`).join("");
  $("#automation-history").innerHTML = data.automation_runs.length ? data.automation_runs.map((run) => `
    <div class="run-item"><time>${esc(when(run.timestamp, true))}</time><div><strong>${esc(run.rule_name)}</strong><small>${esc(run.trigger)}</small></div><div><strong>${esc(run.result)}</strong><small>${esc(run.actions_taken.join(" · "))}</small></div>${status("effective", "Completed")}</div>`).join("") : '<div class="empty-list">Run an automation to see execution evidence.</div>';
}

function renderIncidents(data) {
  const open = data.incidents.filter((incident) => incident.status === "open");
  $("#incident-open-total").textContent = open.length;
  $("#incident-list").innerHTML = data.incidents.length ? data.incidents.map((incident) => {
    const asset = assetById(incident.asset_id);
    return `<div class="incident-row" data-incident-id="${esc(incident.incident_id)}"><span class="severity-icon">!</span><div><strong>${esc(incident.title)}</strong><small>${esc(incident.incident_id)} · ${esc(incident.category)}</small></div><div class="incident-summary"><strong>${esc(incident.summary)}</strong><small>${esc(incident.automated_actions.join(" · "))}</small></div><div><strong>${esc(asset?.name || "Platform")}</strong><small>${esc(incident.owner)}</small></div><div><span class="risk-pill ${esc(incident.severity)}">${esc(incident.severity)}</span><small>${esc(when(incident.created_at, true))}</small></div><div class="incident-actions">${status(incident.status)}${incident.status === "open" ? '<button class="small-button resolve-incident">Resolve</button>' : ""}</div></div>`;
  }).join("") : '<div class="empty-list">No governance incidents.</div>';
  $("#pack-list").innerHTML = data.evidence_packs.length ? data.evidence_packs.map((pack) => `
    <div class="pack-row" data-pack-id="${esc(pack.pack_id)}"><span class="pack-icon">✓</span><div><strong>${esc(pack.name)}</strong><small>${esc(pack.pack_id)} · ${esc(when(pack.generated_at, true))}</small></div><div><strong>${pack.control_count} controls · ${pack.event_count} events</strong><small>${esc(pack.frameworks.join(" · "))}</small></div><div>${status(pack.status)}<small>Chain ${pack.audit_chain_valid ? "verified" : "review required"}</small></div><button class="small-button download-pack">Download JSON</button></div>`).join("") : '<div class="empty-list">Generate an evidence pack to create an assurance-ready export.</div>';
}

function render(data) {
  state.data = data;
  renderMetrics(data);
  renderDashboard(data);
  renderInventory(data);
  renderMonitoring(data);
  renderDataProtection(data);
  renderControls(data);
  renderAutomations(data);
  renderIncidents(data);
}

async function refresh() {
  const [platform, pipelines, governance, regulations, datasetSchema] = await Promise.all([
    request("/api/platform"),
    request("/api/pipelines"),
    request("/api/governance"),
    requestOptional("/api/governance/regulations"),
    requestOptional("/api/governance/dataset-schema"),
  ]);
  state.governanceData = governance;
  state.regulationLibrary = normalizeRegulationLibrary(regulations);
  state.datasetSchema = datasetSchema;
  state.datasetGovernanceAvailable = supportsDatasetGovernance(datasetSchema);
  render(platform);
  renderGovernance(platform, governance);
  renderRegulationLibrary();
  renderUploadAssessment();
  renderExecution(pipelines);
  await refreshSyntheticRecord({ force: true });
}

async function withAction(button, action, success) {
  if (button) button.disabled = true;
  try {
    await action();
    await refresh();
    showToast(success);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    if (button) button.disabled = false;
  }
}

async function generateEvidence(button) {
  await withAction(button, () => request("/api/automations/AUTO-EVIDENCE/run", { method: "POST", body: "{}" }), "Verified evidence pack generated.");
  setView("incidents");
}

async function downloadPack(packId) {
  try {
    const evidence = await request(`/api/packs/${encodeURIComponent(packId)}`);
    const blob = new Blob([JSON.stringify(evidence, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `styrai-${packId.toLowerCase()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast("Evidence pack downloaded.");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function startPipelineRun(button) {
  const pipeline = currentPipeline();
  const selectedCase = currentCase(pipeline);
  if (!pipeline || !selectedCase) {
    showToast("Choose a pipeline and fictional case first.", true);
    return;
  }
  await withAction(
    button,
    async () => {
      const run = await request("/api/pipeline-runs", {
        method: "POST",
        body: JSON.stringify({
          pipeline_id: pipelineId(pipeline),
          case_id: first(selectedCase, ["case_id", "id"], ""),
          mode: state.selectedMode,
        }),
      });
      state.selectedRunId = run.run_id;
      return run;
    },
    "Governed run created. The first executable stage is ready."
  );
  setView("execution");
  $("#pipeline-workspace").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function advancePipeline(button, until) {
  const run = currentPipelineRun();
  if (!run) return;
  await withAction(
    button,
    () => request(`/api/pipeline-runs/${encodeURIComponent(run.run_id)}/advance`, {
      method: "POST",
      body: JSON.stringify({ until }),
    }),
    until === "review" ? "Pipeline advanced to its next human or terminal control gate." : "The next governed stage executed."
  );
}

async function decidePipeline(button, approved) {
  const run = currentPipelineRun();
  if (!run) return;
  const approver = $("#pipeline-reviewer")?.value?.trim() || "";
  const rationale = $("#pipeline-rationale")?.value?.trim() || "";
  if (!approver || !rationale) {
    showToast("Reviewer and rationale are required.", true);
    return;
  }
  await withAction(
    button,
    () => request(`/api/pipeline-runs/${encodeURIComponent(run.run_id)}/decision`, {
      method: "POST",
      body: JSON.stringify({ demo_approver_id: approver, approved, rationale }),
    }),
    approved
      ? "Independent approval recorded; the reviewed action is authorised."
      : "Action denied; no downstream system was invoked."
  );
}

async function executePipeline(button) {
  const run = currentPipelineRun();
  if (!run) return;
  await withAction(
    button,
    () => request(`/api/pipeline-runs/${encodeURIComponent(run.run_id)}/execute`, {
      method: "POST",
      body: "{}",
    }),
    "Authorised action executed in the shared synthetic demonstration and reconciled."
  );
}

async function injectPipelineFailure(button, kind) {
  const run = currentPipelineRun();
  if (!run) return;
  await withAction(
    button,
    () => request(`/api/pipeline-runs/${encodeURIComponent(run.run_id)}/inject`, {
      method: "POST",
      body: JSON.stringify({ kind }),
    }),
    kind === "drift"
      ? "Drift injected; the monitoring response and containment evidence were created."
      : "Version change injected; the model gate evaluated the unapproved version."
  );
}

async function downloadExecutionEvidence() {
  const run = currentPipelineRun();
  if (!run) return;
  try {
    const evidence = await request(`/api/pipeline-runs/${encodeURIComponent(run.run_id)}/evidence`);
    const blob = new Blob([JSON.stringify(evidence, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `styrai-pipeline-${run.run_id.toLowerCase()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast("Correlated execution evidence downloaded.");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function runGovernanceScenario(button) {
  if (button) button.disabled = true;
  const scenario = state.governanceScenario;
  try {
    let response;
    let before = null;
    if (scenario === "data-leak") {
      response = await request("/api/governance/inspect", {
        method: "POST",
        body: JSON.stringify({
          model_id: "shadow-consumer-ai",
          actor: "treasury-analyst-demo",
          use_case: "unknown",
          classification: "internal",
          prompt: "Summarise the Aurora Energy plan for anna.demo@example.test, account NO93 8601 1117 947. api_key=demo-secret-do-not-send",
        }),
      });
    } else if (scenario === "model-drift") {
      const model = governanceModel("finance-credit-risk-prod");
      before = { ...(model?.metrics || {}) };
      response = await request("/api/governance/models/finance-credit-risk-prod/monitor", {
        method: "POST",
        body: JSON.stringify({ metric: "drift_score", value: 0.27 }),
      });
    } else {
      const versionObservation = await request("/api/governance/models/healthcare-summary-prod/observe-version", {
        method: "POST",
        body: JSON.stringify({ observed_version: "2026.09-unreviewed" }),
      });
      const assessment = await request("/api/governance/models/healthcare-summary-prod/assess", {
        method: "POST",
        body: "{}",
      });
      response = { ...assessment, version_observation: versionObservation };
    }
    state.governanceResult = { scenario, response, before, completedAt: new Date().toISOString() };
    await refresh();
    showToast(scenario === "data-leak"
      ? "Sensitive data was blocked before the public AI provider."
      : scenario === "model-drift"
        ? "Model drift was contained and an incident was opened."
        : "Policy and regulatory readiness gaps were recorded for review.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    if (button) button.disabled = false;
  }
}

async function resetGovernanceDemo(button) {
  if (button) button.disabled = true;
  try {
    await request("/api/governance/reset", { method: "POST", body: "{}" });
    state.governanceResult = null;
    await refresh();
    showToast("AI governance demonstration reset to its baseline.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    if (button) button.disabled = false;
  }
}

const presenterScenarios = {
  "finance-success": {
    pipelineId: "finance-material-payment",
    caseId: "FIN-PAY-8842",
    mode: "standard",
    title: "Finance · successful controlled release",
    outcome: "Two independent reviewers authorise the exact payment batch before a simulated release.",
    steps: [
      "Review the fictional payment batch and confirm that the declared and ledger totals match.",
      "Select Start governed run, then Run to review to execute the automated control stages.",
      "Approve once as the payments manager and again as the treasury controller.",
      "Select Execute authorised action and show the reconciled before-and-after ledger state.",
    ],
  },
  "finance-blocked": {
    pipelineId: "finance-material-payment",
    caseId: "FIN-PAY-9917",
    mode: "mismatch",
    title: "Finance · blocked control test",
    outcome: "A deterministic amount mismatch is stopped before approval or payment execution.",
    steps: [
      "Review the fictional two-payment batch and its authoritative ledger total.",
      "Select Start governed run, then Run to review.",
      "Point out the failed validation, linked incident and absence of any downstream invocation.",
      "Use the evidence panel to show that the system failed closed.",
    ],
  },
  "healthcare-success": {
    pipelineId: "healthcare-visit-summary",
    caseId: "HC-VISIT-204",
    mode: "standard",
    title: "Healthcare · successful clinical summary",
    outcome: "A fictional encounter is checked against source facts before clinician approval and a simulated EHR write.",
    steps: [
      "Review the fictional patient, encounter, medicines, allergy and follow-up plan.",
      "Select Start governed run, then Run to review to generate and validate the summary.",
      "Approve as the attending clinician.",
      "Select Execute authorised action and show the signed summary and secure portal queue.",
    ],
  },
};

function clearSelectedExecution() {
  state.selectedRunId = null;
  state.syntheticRecord = null;
  state.syntheticRecordKey = null;
  state.syntheticRecordRequest += 1;
}

function updatePresenterGuide(scenarioId) {
  const guide = $("#presenter-guide");
  const scenario = presenterScenarios[scenarioId];
  if (!guide || !scenario) return;
  guide.innerHTML = `<div class="presenter-guide-heading"><small>PRESENTER PATH · SHARED SYNTHETIC DEMONSTRATION</small><h3>${esc(scenario.title)}</h3><p>${esc(scenario.outcome)}</p></div><ol>${scenario.steps.map((step) => `<li>${esc(step)}</li>`).join("")}</ol><div class="presenter-guide-note"><strong>Say this clearly:</strong> All people, organisations and records are fictional. The governance workflow is functional; model and downstream-system adapters are simulated in this demonstration environment.</div>`;
  $$("[data-presenter-scenario]").forEach((button) => {
    button.classList.toggle("active", button.dataset.presenterScenario === scenarioId);
    button.setAttribute("aria-pressed", button.dataset.presenterScenario === scenarioId ? "true" : "false");
  });
}

function focusPresenterPanel() {
  const panel = $("#presenter-panel") || $(".presenter-console");
  if (!panel) return;
  panel.setAttribute("tabindex", "-1");
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
  window.setTimeout(() => panel.focus({ preventScroll: true }), 350);
}

async function selectPresenterScenario(button, scenarioId) {
  const scenario = presenterScenarios[scenarioId];
  if (!scenario) return;
  if (button) button.disabled = true;
  try {
    await request("/api/platform/reset", { method: "POST", body: "{}" });
    const [platform, pipelines] = await Promise.all([
      request("/api/platform"),
      request("/api/pipelines"),
    ]);
    render(platform);
    state.pipelineData = pipelines;
    clearSelectedExecution();
    state.selectedPipelineId = scenario.pipelineId;
    state.selectedCaseId = scenario.caseId;
    state.selectedMode = scenario.mode;
    state.selectedRunId = "";
    renderExecution(pipelines);
    await refreshSyntheticRecord({ force: true });
    updatePresenterGuide(scenarioId);
    setView("execution");
    focusPresenterPanel();
    showToast(`${scenario.title} is reset and ready.`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    if (button) button.disabled = false;
  }
}

document.addEventListener("click", async (event) => {
  const governanceScenarioButton = event.target.closest("[data-governance-scenario]");
  if (governanceScenarioButton) {
    state.governanceScenario = governanceScenarioButton.dataset.governanceScenario;
    state.governanceResult = null;
    renderGovernance(state.data, state.governanceData);
    return;
  }

  const runGovernanceButton = event.target.closest("#run-governance-scenario");
  if (runGovernanceButton) {
    await runGovernanceScenario(runGovernanceButton);
    return;
  }

  const resetGovernanceButton = event.target.closest("#reset-governance-demo");
  if (resetGovernanceButton) {
    await resetGovernanceDemo(resetGovernanceButton);
    return;
  }

  const presenterButton = event.target.closest("[data-presenter-scenario]");
  if (presenterButton) {
    await selectPresenterScenario(presenterButton, presenterButton.dataset.presenterScenario);
    return;
  }

  const viewButton = event.target.closest("[data-view], [data-go-view]");
  if (viewButton) {
    event.preventDefault();
    setView(viewButton.dataset.view || viewButton.dataset.goView);
    return;
  }

  const pipelineCard = event.target.closest("[data-pipeline-id]");
  if (pipelineCard) {
    state.selectedPipelineId = pipelineCard.dataset.pipelineId;
    state.selectedCaseId = null;
    state.selectedMode = null;
    state.selectedRunId = "";
    state.syntheticRecord = null;
    state.syntheticRecordKey = null;
    initialisePipelineSelection(state.pipelineData);
    renderExecution(state.pipelineData);
    await refreshSyntheticRecord({ force: true });
    $("#pipeline-workspace").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  const pipelineStart = event.target.closest("#pipeline-start, .pipeline-start-secondary");
  if (pipelineStart) {
    await startPipelineRun(pipelineStart);
    return;
  }

  const pipelineAdvanceNext = event.target.closest(".pipeline-advance-next");
  if (pipelineAdvanceNext) {
    await advancePipeline(pipelineAdvanceNext, "next");
    return;
  }

  const pipelineAdvanceReview = event.target.closest(".pipeline-advance-review");
  if (pipelineAdvanceReview) {
    await advancePipeline(pipelineAdvanceReview, "review");
    return;
  }

  const pipelineDecision = event.target.closest(".pipeline-decision");
  if (pipelineDecision) {
    await decidePipeline(pipelineDecision, pipelineDecision.dataset.approved === "true");
    return;
  }

  const pipelineExecute = event.target.closest(".pipeline-execute");
  if (pipelineExecute) {
    await executePipeline(pipelineExecute);
    return;
  }

  const pipelineInject = event.target.closest(".pipeline-inject");
  if (pipelineInject) {
    await injectPipelineFailure(pipelineInject, pipelineInject.dataset.kind);
    return;
  }

  const openRun = event.target.closest(".pipeline-open-run");
  if (openRun) {
    const run = pipelineRuns().find((item) => item.run_id === openRun.dataset.runId);
    if (!run) return;
    state.selectedPipelineId = runPipelineId(run);
    state.selectedCaseId = String(first(run.case || run, ["case_id"], state.selectedCaseId || ""));
    state.selectedMode = run.mode || state.selectedMode;
    state.selectedRunId = run.run_id;
    renderExecution(state.pipelineData);
    $("#pipeline-workspace").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  const promptButton = event.target.closest("[data-prompt-scenario]");
  if (promptButton) {
    const prompts = {
      safe: "Summarise our standard mortgage procedure for an advisor.",
      confidential: "Customer anna.demo@example.test asks about account NO93 8601 1117 947. Mark confidential.",
      secret: "api_key=demo-secret-do-not-send",
    };
    $("#sim-prompt").value = prompts[promptButton.dataset.promptScenario];
    $("#sim-classification").value = promptButton.dataset.promptScenario === "safe" ? "internal" : "confidential";
    return;
  }

  const modelCard = event.target.closest("[data-asset-id]");
  if (modelCard && event.target.closest(".health-button")) {
    const button = event.target.closest(".health-button");
    await withAction(button, () => request(`/api/models/${encodeURIComponent(modelCard.dataset.assetId)}/health-breach`, { method: "POST", body: JSON.stringify({ breach: button.dataset.breach }) }), "Threshold breach contained; incident and validation task created.");
    return;
  }
  if (modelCard && event.target.closest(".version-button")) {
    const button = event.target.closest(".version-button");
    await withAction(button, () => request(`/api/models/${encodeURIComponent(modelCard.dataset.assetId)}/version-change`, { method: "POST", body: "{}" }), "Unapproved model version contained and sent for revalidation.");
    return;
  }

  const automationCard = event.target.closest("[data-rule-id]");
  if (automationCard && event.target.closest(".run-automation")) {
    const button = event.target.closest(".run-automation");
    await withAction(button, () => request(`/api/automations/${encodeURIComponent(automationCard.dataset.ruleId)}/run`, { method: "POST", body: "{}" }), "Governance automation completed and evidence recorded.");
    return;
  }

  const incidentRow = event.target.closest("[data-incident-id]");
  if (incidentRow && event.target.closest(".resolve-incident")) {
    const button = event.target.closest(".resolve-incident");
    await withAction(button, () => request(`/api/incidents/${encodeURIComponent(incidentRow.dataset.incidentId)}/resolve`, { method: "POST", body: "{}" }), "Incident resolved with an audit record.");
    return;
  }

  const packRow = event.target.closest("[data-pack-id]");
  if (packRow && event.target.closest(".download-pack")) await downloadPack(packRow.dataset.packId);
});

$("#pipeline-select").addEventListener("change", async (event) => {
  state.selectedPipelineId = event.target.value;
  state.selectedCaseId = null;
  state.selectedMode = null;
  state.selectedRunId = "";
  state.syntheticRecord = null;
  state.syntheticRecordKey = null;
  initialisePipelineSelection(state.pipelineData);
  renderExecution(state.pipelineData);
  await refreshSyntheticRecord({ force: true });
});

$("#pipeline-case-select").addEventListener("change", async (event) => {
  state.selectedCaseId = event.target.value;
  state.selectedRunId = "";
  state.syntheticRecord = null;
  state.syntheticRecordKey = null;
  renderExecution(state.pipelineData);
  await refreshSyntheticRecord({ force: true });
});

$("#pipeline-mode-select").addEventListener("change", (event) => {
  state.selectedMode = event.target.value;
  state.selectedRunId = "";
  renderExecution(state.pipelineData);
});

$("#call-simulator").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type='submit']");
  button.disabled = true;
  try {
    const result = await request("/api/simulate/call", {
      method: "POST",
      body: JSON.stringify({
        asset_id: $("#sim-asset").value,
        classification: $("#sim-classification").value,
        actor: $("#sim-actor").value,
        prompt: $("#sim-prompt").value,
      }),
    });
    renderDecision(result);
    await refresh();
    renderDecision(result);
    showToast(result.event.decision === "blocked" ? "Transmission blocked and incident opened." : "Call controlled and evidence recorded.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
});

async function handleDatasetFile(file) {
  if (!file) return;
  try {
    const format = datasetFormat(file.name, file.type);
    if (!["csv", "json"].includes(format)) throw new Error("Choose a CSV or JSON dataset.");
    loadDataset({ name: file.name, format, content: await file.text() });
    showToast(`${file.name} loaded and ready to inspect.`);
  } catch (error) {
    showToast(error.message, true);
  }
}

$("#governance-dataset-file").addEventListener("change", async (event) => handleDatasetFile(event.target.files?.[0]));
$("#company-policy-file").addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    if (text.length > 20000) throw new Error("Choose a written policy no longer than 20,000 characters for this demonstration.");
    state.uploadAssessment.policyName = file.name;
    state.uploadAssessment.policyText = text;
    state.uploadAssessment.policyId = null;
    state.uploadAssessment.result = null;
    $("#company-policy-text").value = text;
    renderUploadAssessment();
    showToast(`${file.name} loaded as the internal-policy layer.`);
  } catch (error) {
    showToast(error.message, true);
  }
});
$("#company-policy-text").addEventListener("input", (event) => {
  state.uploadAssessment.policyText = event.target.value;
  state.uploadAssessment.policyName = event.target.value.trim() ? "Pasted company policy" : "";
  state.uploadAssessment.policyId = null;
  state.uploadAssessment.result = null;
  renderUploadAssessment();
});
$("#load-sample-policy").addEventListener("click", () => {
  const policyText = state.datasetSchema?.policy_extractor_example?.text || sampleCompanyPolicy;
  state.uploadAssessment.policyName = "StyrAI Demonstration Company AI Decision Policy v1.0";
  state.uploadAssessment.policyText = policyText;
  state.uploadAssessment.policyId = null;
  state.uploadAssessment.result = null;
  $("#company-policy-text").value = policyText;
  renderUploadAssessment();
  showToast("Stricter sample policy loaded. It requires review even for some regulatory passes.");
});
$$('[data-sample-dataset]').forEach((button) => button.addEventListener("click", () => {
  try {
    loadDataset(schemaSampleDataset(button.dataset.sampleDataset));
    showToast("Synthetic sample loaded. Inspect its schema before running the assessment.");
  } catch (error) {
    showToast(error.message, true);
  }
}));
$("#reset-dataset-run").addEventListener("click", () => {
  clearUploadAssessment();
  showToast("Uploaded dataset, policy and run result cleared.");
});
$("#run-dataset-assessment").addEventListener("click", (event) => runUploadAssessment(event.currentTarget));
const datasetDropzone = $("#dataset-dropzone");
["dragenter", "dragover"].forEach((type) => datasetDropzone.addEventListener(type, (event) => {
  event.preventDefault();
  datasetDropzone.classList.add("dragging");
}));
["dragleave", "drop"].forEach((type) => datasetDropzone.addEventListener(type, (event) => {
  event.preventDefault();
  datasetDropzone.classList.remove("dragging");
}));
datasetDropzone.addEventListener("drop", (event) => handleDatasetFile(event.dataTransfer?.files?.[0]));

$("#inventory-search").addEventListener("input", (event) => {
  state.search = event.target.value;
  renderInventory(state.data);
});

$(".filter-pills").addEventListener("click", (event) => {
  const button = event.target.closest("[data-inventory-filter]");
  if (!button) return;
  state.inventoryFilter = button.dataset.inventoryFilter;
  $$("[data-inventory-filter]").forEach((item) => item.classList.toggle("active", item === button));
  renderInventory(state.data);
});

$("#generate-evidence").addEventListener("click", (event) => generateEvidence(event.currentTarget));
$("#generate-evidence-secondary").addEventListener("click", (event) => generateEvidence(event.currentTarget));
$("#download-execution-evidence").addEventListener("click", downloadExecutionEvidence);
$$('[data-governance-scenario]').forEach((button) => button.addEventListener("click", (event) => {
  event.stopPropagation();
  state.governanceScenario = button.dataset.governanceScenario;
  state.governanceResult = null;
  renderGovernance(state.data, state.governanceData);
}));
$("#run-governance-scenario").addEventListener("click", async (event) => {
  event.stopPropagation();
  await runGovernanceScenario(event.currentTarget);
});
$("#reset-governance-demo").addEventListener("click", async (event) => {
  event.stopPropagation();
  await resetGovernanceDemo(event.currentTarget);
});
$("#reset-platform").addEventListener("click", async (event) => {
  await withAction(event.currentTarget, async () => {
    await request("/api/platform/reset", { method: "POST", body: "{}" });
    clearSelectedExecution();
    state.governanceResult = null;
    $("#decision-result").classList.add("hidden");
    $("#empty-decision").classList.remove("hidden");
  }, "Shared synthetic demonstration reset to its governed baseline.");
});

refresh()
  .then(() => {
    if (new URLSearchParams(window.location.search).get("presentation") === "1") {
      setView("governance");
    }
  })
  .catch((error) => showToast(error.message, true));
