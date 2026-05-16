const state = {
  records: [],
  specs: [],
  filtered: [],
  activeTab: "comments",
  pageSize: 80,
};

const els = {
  stock: document.querySelector("#stock-filter"),
  year: document.querySelector("#year-filter"),
  fmp: document.querySelector("#fmp-filter"),
  type: document.querySelector("#type-filter"),
  search: document.querySelector("#search-filter"),
  sort: document.querySelector("#sort-order"),
  cards: document.querySelector("#cards"),
  specs: document.querySelector("#specs"),
  shown: document.querySelector("#shown-count"),
  shownLabel: document.querySelector("#shown-label"),
  total: document.querySelector("#record-count"),
  clear: document.querySelector("#clear-filters"),
  copy: document.querySelector("#copy-link"),
  template: document.querySelector("#card-template"),
  tabs: Array.from(document.querySelectorAll(".tab-button")),
};

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((option) => option.value);
}

function fillSelect(select, values) {
  const selected = new Set(selectedValues(select));
  select.replaceChildren();
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    option.selected = selected.has(value);
    select.append(option);
  });
}

function setSelected(select, values) {
  const wanted = new Set(values);
  Array.from(select.options).forEach((option) => {
    option.selected = wanted.has(option.value);
  });
}

function uniqueSorted(values) {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

function recordText(record) {
  return `${record.stock} ${record.fmp} ${record.comment_type} ${record.section} ${record.excerpt} ${record.full_text}`.toLowerCase();
}

function specText(record) {
  return `${record.stock} ${record.fmp} ${record.area} ${record.recommendation_year} ${record.report_year} ${record.source_file} ${record.table}`.toLowerCase();
}

function currentData() {
  return state.activeTab === "specs" ? state.specs : state.records;
}

function updateFilterOptions() {
  const records = currentData();
  fillSelect(els.stock, uniqueSorted(records.map((record) => record.stock)));
  fillSelect(els.year, uniqueSorted(records.map((record) => String(state.activeTab === "specs" ? record.recommendation_year : record.year))).reverse());
  fillSelect(els.fmp, uniqueSorted(records.map((record) => record.fmp)));
  els.type.disabled = state.activeTab === "specs";
}

function applyFilters() {
  const stocks = new Set(selectedValues(els.stock));
  const years = new Set(selectedValues(els.year));
  const fmps = new Set(selectedValues(els.fmp));
  const types = new Set(selectedValues(els.type));
  const query = els.search.value.trim().toLowerCase();

  if (state.activeTab === "specs") {
    state.filtered = state.specs.filter((record) => {
      if (stocks.size && !stocks.has(record.stock)) return false;
      if (years.size && !years.has(String(record.recommendation_year))) return false;
      if (fmps.size && !fmps.has(record.fmp)) return false;
      if (query && !specText(record).includes(query)) return false;
      return true;
    });
  } else {
    state.filtered = state.records.filter((record) => {
      if (stocks.size && !stocks.has(record.stock)) return false;
      if (years.size && !years.has(String(record.year))) return false;
      if (fmps.size && !fmps.has(record.fmp)) return false;
      if (types.size && !types.has(record.comment_type)) return false;
      if (query && !recordText(record).includes(query)) return false;
      return true;
    });
  }

  sortRecords();
  render();
  writeUrlState();
}

function sortRecords() {
  const order = els.sort.value;
  state.filtered.sort((a, b) => {
    const yearA = Number(state.activeTab === "specs" ? a.recommendation_year : a.year);
    const yearB = Number(state.activeTab === "specs" ? b.recommendation_year : b.year);
    if (order === "oldest") return yearA - yearB || a.stock.localeCompare(b.stock);
    if (order === "stock") return a.stock.localeCompare(b.stock) || yearB - yearA;
    return yearB - yearA || a.stock.localeCompare(b.stock);
  });
}

function formatNumber(value) {
  if (!value) return "n/a";
  return Number(value).toLocaleString();
}

function render() {
  if (state.activeTab === "specs") {
    renderSpecs();
  } else {
    renderComments();
  }
}

function renderComments() {
  els.cards.classList.remove("hidden");
  els.specs.classList.add("hidden");
  els.cards.replaceChildren();
  els.shown.textContent = state.filtered.length.toLocaleString();
  els.shownLabel.textContent = "matching comments";

  const fragment = document.createDocumentFragment();
  state.filtered.slice(0, state.pageSize).forEach((record) => {
    const node = els.template.content.cloneNode(true);
    node.querySelector(".stock").textContent = `${record.stock} (${record.year})`;
    node.querySelector(".fmp").textContent = record.fmp;
    node.querySelector(".type").textContent = record.comment_type;
    node.querySelector(".excerpt").textContent = record.excerpt;
    node.querySelector(".full-text").textContent = record.full_text;
    node.querySelector(".source").textContent = `${record.source_file}, page ${record.page}`;
    const link = node.querySelector(".pdf-link");
    link.href = record.page_url;
    link.textContent = `Open page ${record.page}`;
    fragment.append(node);
  });

  if (state.filtered.length > state.pageSize) {
    const more = document.createElement("button");
    more.type = "button";
    more.textContent = `Show next ${Math.min(80, state.filtered.length - state.pageSize)} comments`;
    more.addEventListener("click", () => {
      state.pageSize += 80;
      renderComments();
    });
    fragment.append(more);
  }

  els.cards.append(fragment);
}

function renderSpecs() {
  els.cards.classList.add("hidden");
  els.specs.classList.remove("hidden");
  els.specs.replaceChildren();
  els.shown.textContent = state.filtered.length.toLocaleString();
  els.shownLabel.textContent = "ABC/OFL rows";

  const note = document.createElement("p");
  note.className = "spec-note";
  note.textContent = "Rows are extracted from machine-readable SSC recommendation tables; open the source page to audit the original table.";

  const table = document.createElement("table");
  table.className = "spec-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Stock</th>
        <th>FMP</th>
        <th>Area</th>
        <th>Year</th>
        <th>OFL</th>
        <th>ABC</th>
        <th>Report</th>
        <th>Source</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  state.filtered.forEach((record) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${record.stock}</td>
      <td>${record.fmp}</td>
      <td>${record.area}</td>
      <td>${record.recommendation_year}</td>
      <td class="numeric">${formatNumber(record.ofl)}</td>
      <td class="numeric">${formatNumber(record.abc)}</td>
      <td>${record.report_year}</td>
      <td><a href="${record.page_url}" target="_blank" rel="noopener">${record.source_file}, p. ${record.page}</a></td>
    `;
    tbody.append(row);
  });
  els.specs.append(note, table);
}

function writeUrlState() {
  const params = new URLSearchParams();
  params.set("tab", state.activeTab);
  const entries = [
    ["stock", selectedValues(els.stock)],
    ["year", selectedValues(els.year)],
    ["fmp", selectedValues(els.fmp)],
    ["type", selectedValues(els.type)],
  ];
  entries.forEach(([key, values]) => {
    if (values.length) params.set(key, values.join("|"));
  });
  if (els.search.value.trim()) params.set("q", els.search.value.trim());
  const next = `${location.pathname}${params.toString() ? `?${params}` : ""}`;
  history.replaceState(null, "", next);
}

function readUrlState() {
  const params = new URLSearchParams(location.search);
  state.activeTab = params.get("tab") === "specs" ? "specs" : "comments";
  updateTabButtons();
  updateFilterOptions();
  setSelected(els.stock, (params.get("stock") || "").split("|").filter(Boolean));
  setSelected(els.year, (params.get("year") || "").split("|").filter(Boolean));
  setSelected(els.fmp, (params.get("fmp") || "").split("|").filter(Boolean));
  setSelected(els.type, (params.get("type") || "").split("|").filter(Boolean));
  els.search.value = params.get("q") || "";
}

function clearFilters() {
  [els.stock, els.year, els.fmp, els.type].forEach((select) => {
    Array.from(select.options).forEach((option) => {
      option.selected = false;
    });
  });
  els.search.value = "";
  state.pageSize = 80;
  applyFilters();
}

async function copyStateLink() {
  writeUrlState();
  await navigator.clipboard.writeText(location.href);
  els.copy.textContent = "Copied";
  window.setTimeout(() => {
    els.copy.textContent = "Copy state";
  }, 1200);
}

function updateTabButtons() {
  els.tabs.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === state.activeTab);
  });
}

function setTab(tab) {
  const selected = {
    stock: selectedValues(els.stock),
    year: [],
    fmp: selectedValues(els.fmp),
  };
  state.activeTab = tab;
  state.pageSize = 80;
  updateTabButtons();
  updateFilterOptions();
  setSelected(els.stock, selected.stock);
  setSelected(els.fmp, selected.fmp);
  setSelected(els.year, selected.year);
  applyFilters();
}

async function loadSpecifications() {
  let payload = window.SSC_SPECIFICATIONS_DATA;
  if (!payload) {
    const response = await fetch("assets/specifications.json");
    payload = await response.json();
  }
  return payload.records;
}

async function init() {
  let payload = window.SSC_COMMENTS_DATA;
  if (!payload) {
    const response = await fetch("assets/comments.json");
    payload = await response.json();
  }
  state.records = payload.records;
  state.specs = await loadSpecifications();
  fillSelect(els.type, payload.filters.comment_types);
  els.total.textContent = `${state.records.length.toLocaleString()} comments; ${state.specs.length.toLocaleString()} ABC/OFL rows`;
  readUrlState();
  applyFilters();
}

[els.stock, els.year, els.fmp, els.type, els.sort].forEach((el) => {
  el.addEventListener("change", () => {
    state.pageSize = 80;
    applyFilters();
  });
});

els.tabs.forEach((button) => {
  button.addEventListener("click", () => setTab(button.dataset.tab));
});

els.search.addEventListener("input", () => {
  state.pageSize = 80;
  applyFilters();
});
els.clear.addEventListener("click", clearFilters);
els.copy.addEventListener("click", copyStateLink);

init().catch((error) => {
  els.total.textContent = "Data failed to load";
  console.error(error);
});
