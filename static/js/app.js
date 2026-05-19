const Portal = (() => {
  const fmt = (n) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n || 0);

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `Request failed (${res.status})`);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDate(iso) {
    if (!iso) return "Never";
    return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
  }

  const ACCOUNT_CATEGORIES = [
    { value: "retirement_c1", label: "Client 1 — Retirement" },
    { value: "retirement_c2", label: "Client 2 — Retirement" },
    { value: "non_retirement", label: "Non-Retirement" },
    { value: "trust", label: "Trust / Residence" },
    { value: "liability", label: "Liability" },
  ];

  async function renderClientList() {
    const el = document.getElementById("client-list");
    try {
      const clients = await api("/api/clients");
      if (!clients.length) {
        el.innerHTML = `<div class="empty-state card"><p>No clients yet.</p><a href="/clients/new" class="btn btn-primary">Add your first client</a></div>`;
        return;
      }
      el.innerHTML = clients
        .map(
          (c) => `
        <article class="client-card">
          <h3>${escapeHtml(c.display_name)}</h3>
          <p class="meta">${c.is_married ? "Married" : "Single"} · Last report: ${formatDate(c.last_report_at)}</p>
          <div class="btn-group">
            <a href="/clients/${c.id}" class="btn btn-primary btn-sm">Open</a>
            <a href="/clients/${c.id}/report" class="btn btn-sm">Generate Report</a>
          </div>
        </article>`
        )
        .join("");
    } catch (err) {
      el.innerHTML = `<p class="alert alert-error">${escapeHtml(err.message)}</p>`;
    }
  }

  function accountRowTemplate(account = {}, index = 0) {
    const cat = account.category || "retirement_c1";
    const isTrust = cat === "trust";
    const isLiability = cat === "liability";
    return `
      <div class="account-row" data-index="${index}">
        <button type="button" class="btn btn-sm btn-danger remove-btn" data-action="remove-account">×</button>
        <div class="form-grid">
          <div class="form-group">
            <label>Category</label>
            <select name="accounts[${index}][category]" data-field="category">
              ${ACCOUNT_CATEGORIES.map((o) => `<option value="${o.value}" ${o.value === cat ? "selected" : ""}>${o.label}</option>`).join("")}
            </select>
          </div>
          <div class="form-group">
            <label>Account Type</label>
            <input name="accounts[${index}][account_type]" value="${escapeHtml(account.account_type || "")}" placeholder="IRA, Roth IRA, Mortgage…" required />
          </div>
          <div class="form-group">
            <label>Label</label>
            <input name="accounts[${index}][label]" value="${escapeHtml(account.label || "")}" required />
          </div>
          <div class="form-group">
            <label>Last 4 of Account #</label>
            <input name="accounts[${index}][account_last_four]" value="${escapeHtml(account.account_last_four || "")}" maxlength="4" />
          </div>
          <div class="form-group liability-field" style="display:${isLiability ? "flex" : "none"}">
            <label>Interest Rate (%)</label>
            <input type="number" step="0.01" name="accounts[${index}][interest_rate]" value="${account.interest_rate ?? ""}" />
          </div>
          <div class="form-group trust-field" style="display:${isTrust ? "flex" : "none"}">
            <label>Property Address</label>
            <input name="accounts[${index}][property_address]" value="${escapeHtml(account.property_address || "")}" />
          </div>
        </div>
      </div>`;
  }

  function personFields(person = {}, role = "client1", required = true) {
    return `
      <div class="form-section">
        <h2>${role === "client1" ? "Client 1" : "Client 2"}</h2>
        <input type="hidden" name="persons[${role}][role]" value="${role}" />
        <div class="form-grid">
          <div class="form-group">
            <label>Full Name</label>
            <input name="persons[${role}][full_name]" value="${escapeHtml(person.full_name || "")}" ${required ? "required" : ""} />
          </div>
          <div class="form-group">
            <label>Date of Birth</label>
            <input type="date" name="persons[${role}][date_of_birth]" value="${escapeHtml(person.date_of_birth || "")}" ${required ? "required" : ""} />
          </div>
          <div class="form-group">
            <label>SSN (last 4)</label>
            <input name="persons[${role}][ssn_last_four]" value="${escapeHtml(person.ssn_last_four || "")}" maxlength="4" pattern="\\d{4}" ${required ? "required" : ""} />
          </div>
        </div>
      </div>`;
  }

  async function initClientForm(clientId) {
    const form = document.getElementById("client-form");
    let data = {
      display_name: "",
      is_married: true,
      monthly_inflow: 15000,
      monthly_outflow: 11000,
      insurance_deductibles: 2500,
      schwab_label: "Schwab Investment Account",
      persons: [],
      accounts: [],
    };

    if (clientId) {
      document.getElementById("form-title").textContent = "Edit Client";
      const bundle = await api(`/api/clients/${clientId}`);
      data = { ...bundle.client, persons: bundle.persons, accounts: bundle.accounts, id: clientId };
    }

    const p1 = data.persons.find((p) => p.role === "client1") || {};
    const p2 = data.persons.find((p) => p.role === "client2") || {};
    const accounts = data.accounts.length ? data.accounts : defaultAccounts(data.is_married);

    form.innerHTML = `
      <div id="form-error"></div>
      <div class="form-section">
        <h2>Household</h2>
        <div class="form-grid">
          <div class="form-group">
            <label>Display Name</label>
            <input name="display_name" value="${escapeHtml(data.display_name)}" required />
          </div>
          <div class="checkbox-row">
            <input type="checkbox" id="is_married" name="is_married" ${data.is_married ? "checked" : ""} />
            <label for="is_married">Married (Client 1 &amp; Client 2)</label>
          </div>
        </div>
      </div>
      <div id="person-client1">${personFields(p1, "client1")}</div>
      <div id="person-client2" style="display:${data.is_married ? "block" : "none"}">${personFields(p2, "client2", false)}</div>
      <div class="form-section">
        <h2>SACS — Static Cashflow</h2>
        <div class="form-grid">
          <div class="form-group">
            <label>Monthly Inflow (after tax)</label>
            <input type="number" name="monthly_inflow" value="${data.monthly_inflow}" required />
          </div>
          <div class="form-group">
            <label>Monthly Outflow (expense budget)</label>
            <input type="number" name="monthly_outflow" value="${data.monthly_outflow}" required />
          </div>
          <div class="form-group">
            <label>Insurance Deductibles (total)</label>
            <input type="number" name="insurance_deductibles" value="${data.insurance_deductibles}" />
          </div>
          <div class="form-group">
            <label>Schwab Account Label</label>
            <input name="schwab_label" value="${escapeHtml(data.schwab_label)}" />
          </div>
        </div>
      </div>
      <div class="form-section">
        <h2>Account Structure</h2>
        <div id="accounts-container">${accounts.map((a, i) => accountRowTemplate(a, i)).join("")}</div>
        <button type="button" class="btn" id="add-account">+ Add Account</button>
      </div>
      <div class="btn-group">
        <button type="submit" class="btn btn-primary">Save Client</button>
        <a href="${clientId ? `/clients/${clientId}` : "/"}" class="btn">Cancel</a>
      </div>`;

    const marriedToggle = form.querySelector("#is_married");
    marriedToggle.addEventListener("change", () => {
      form.querySelector("#person-client2").style.display = marriedToggle.checked ? "block" : "none";
    });

    form.querySelector("#add-account").addEventListener("click", () => {
      const container = form.querySelector("#accounts-container");
      const idx = container.children.length;
      container.insertAdjacentHTML("beforeend", accountRowTemplate({}, idx));
      bindAccountRows(form);
    });

    bindAccountRows(form);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = form.querySelector("#form-error");
      errEl.innerHTML = "";
      try {
        const payload = collectClientForm(form, clientId);
        if (clientId) {
          await api(`/api/clients/${clientId}`, { method: "PUT", body: JSON.stringify(payload) });
          window.location.href = `/clients/${clientId}`;
        } else {
          const res = await api("/api/clients", { method: "POST", body: JSON.stringify(payload) });
          window.location.href = `/clients/${res.id}`;
        }
      } catch (err) {
        errEl.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
      }
    });
  }

  function defaultAccounts(isMarried) {
    const base = [
      { category: "retirement_c1", account_type: "IRA", label: "Traditional IRA" },
      { category: "retirement_c1", account_type: "Roth IRA", label: "Roth IRA" },
      { category: "non_retirement", account_type: "Brokerage", label: "Joint Brokerage" },
      { category: "trust", account_type: "Residence", label: "Primary Residence", property_address: "" },
      { category: "liability", account_type: "Mortgage", label: "Home Mortgage", interest_rate: 3.25 },
    ];
    if (isMarried) {
      base.splice(2, 0, { category: "retirement_c2", account_type: "IRA", label: "Spouse IRA" });
    }
    return base;
  }

  function bindAccountRows(form) {
    form.querySelectorAll("[data-action='remove-account']").forEach((btn) => {
      btn.onclick = () => btn.closest(".account-row").remove();
    });
    form.querySelectorAll("[data-field='category']").forEach((sel) => {
      sel.onchange = () => {
        const row = sel.closest(".account-row");
        const val = sel.value;
        row.querySelector(".trust-field").style.display = val === "trust" ? "flex" : "none";
        row.querySelector(".liability-field").style.display = val === "liability" ? "flex" : "none";
      };
    });
  }

  function collectClientForm(form, clientId) {
    const fd = new FormData(form);
    const persons = [];
    for (const role of ["client1", "client2"]) {
      const name = fd.get(`persons[${role}][full_name]`);
      if (!name && role === "client2") continue;
      persons.push({
        role,
        full_name: name,
        date_of_birth: fd.get(`persons[${role}][date_of_birth]`),
        ssn_last_four: fd.get(`persons[${role}][ssn_last_four]`),
      });
    }

    const accounts = [];
    form.querySelectorAll(".account-row").forEach((row, index) => {
      const get = (field) => row.querySelector(`[name='accounts[${index}][${field}]']`)?.value;
      const category = row.querySelector("[data-field='category']").value;
      accounts.push({
        category,
        account_type: get("account_type"),
        label: get("label"),
        account_last_four: get("account_last_four"),
        interest_rate: get("interest_rate") ? parseFloat(get("interest_rate")) : null,
        property_address: get("property_address") || null,
      });
    });

    return {
      id: clientId || undefined,
      display_name: fd.get("display_name"),
      is_married: form.querySelector("#is_married").checked,
      monthly_inflow: parseFloat(fd.get("monthly_inflow")),
      monthly_outflow: parseFloat(fd.get("monthly_outflow")),
      insurance_deductibles: parseFloat(fd.get("insurance_deductibles") || 0),
      schwab_label: fd.get("schwab_label"),
      persons,
      accounts,
    };
  }

  async function renderClientDetail(clientId) {
    const el = document.getElementById("client-detail");
    try {
      const bundle = await api(`/api/clients/${clientId}`);
      const { client, persons, accounts, reports } = bundle;
      const target = 6 * client.monthly_outflow + parseFloat(client.insurance_deductibles);

      el.innerHTML = `
        <section class="page-header">
          <div>
            <h1>${escapeHtml(client.display_name)}</h1>
            <p class="muted">${client.is_married ? "Married household" : "Single client"} · Private reserve target: ${fmt(target)}</p>
          </div>
          <div class="btn-group">
            <a href="/clients/${clientId}/report" class="btn btn-primary">Generate Report</a>
            <a href="/clients/${clientId}/edit" class="btn">Edit Profile</a>
          </div>
        </section>
        <div class="card">
          <h2>Cashflow (SACS static)</h2>
          <div class="form-grid">
            <div><span class="muted">Inflow</span><br><strong>${fmt(client.monthly_inflow)}/mo</strong></div>
            <div><span class="muted">Outflow</span><br><strong>${fmt(client.monthly_outflow)}/mo</strong></div>
            <div><span class="muted">Excess</span><br><strong>${fmt(client.monthly_inflow - client.monthly_outflow)}/mo</strong></div>
          </div>
        </div>
        <div class="card">
          <h2>People</h2>
          ${persons.map((p) => `<p><strong>${escapeHtml(p.full_name)}</strong> — Age ${p.age}, DOB ${p.date_of_birth}, SSN …${p.ssn_last_four}</p>`).join("")}
        </div>
        <div class="card">
          <h2>Accounts (${accounts.length})</h2>
          <ul>${accounts.map((a) => `<li><span class="badge">${a.category}</span> ${escapeHtml(a.label)} (${escapeHtml(a.account_type)})</li>`).join("")}</ul>
        </div>
        <div class="card">
          <h2>Report History</h2>
          ${
            reports.length
              ? `<ul class="history-list">${reports
                  .map(
                    (r) => `
                <li>
                  <span>${escapeHtml(r.quarter_label)} — ${r.report_date}</span>
                  <a href="/clients/${clientId}/reports/${r.id}" class="btn btn-sm">View / Download</a>
                </li>`
                  )
                  .join("")}</ul>`
              : `<p class="muted">No reports yet. Generate your first quarterly report.</p>`
          }
        </div>`;
    } catch (err) {
      el.innerHTML = `<p class="alert alert-error">${escapeHtml(err.message)}</p>`;
    }
  }

  async function initReportEntry(clientId) {
    const el = document.getElementById("report-entry");
    const bundle = await api(`/api/clients/${clientId}`);
    const { client, accounts, previous_balances: prev } = bundle;
    const quarterDefault = `Q${Math.ceil((new Date().getMonth() + 1) / 3)} ${new Date().getFullYear()}`;

    const balanceField = (key, label, lastVal, isCash = false) => {
      const incomplete = lastVal === undefined ? "field-incomplete" : "";
      return `
        <div class="form-group ${incomplete}" data-balance-key="${key}">
          <label>${escapeHtml(label)}</label>
          <input type="number" step="0.01" name="balance_${key}" data-key="${key}" value="" />
          ${
            prev[key] !== undefined
              ? `<div class="last-value">Last quarter: ${fmt(prev[key])}
              <button type="button" data-use-last="${key}" data-value="${prev[key]}">Use last value</button></div>`
              : ""
          }
        </div>
        ${
          isCash
            ? `
        <div class="form-group" data-balance-key="${key}_cash">
          <label>Cash portion</label>
          <input type="number" step="0.01" data-key="${key}_cash" value="" />
        </div>`
            : ""
        }`;
    };

    el.innerHTML = `
      <section class="page-header">
        <div>
          <h1>Generate Report</h1>
          <p class="muted">${escapeHtml(client.display_name)} — enter quarterly balances</p>
        </div>
        <a href="/clients/${clientId}" class="btn">← Back</a>
      </section>
      <div id="report-error"></div>
      <form id="quarterly-form" class="report-layout">
        <div>
          <div class="card">
            <h2>Report Period</h2>
            <div class="form-grid">
              <div class="form-group">
                <label>Quarter Label</label>
                <input name="quarter_label" value="${quarterDefault}" required />
              </div>
              <div class="form-group">
                <label>Report Date</label>
                <input type="date" name="report_date" value="${new Date().toISOString().slice(0, 10)}" />
              </div>
            </div>
          </div>
          <div class="card">
            <h2>SACS — Balances</h2>
            <p class="muted">Inflow ${fmt(client.monthly_inflow)} · Outflow ${fmt(client.monthly_outflow)} (from profile)</p>
            <div class="form-grid">
              ${balanceField("private_reserve", "Private Reserve Balance", prev.private_reserve)}
              ${balanceField("schwab_investment", client.schwab_label || "Schwab Investment", prev.schwab_investment)}
            </div>
          </div>
          <div class="card">
            <h2>TCC — Account Balances</h2>
            ${accounts
              .map((a) => {
                const key = String(a.id);
                const isInv = ["retirement_c1", "retirement_c2", "non_retirement"].includes(a.category);
                return `
                <h3 style="margin-top:1rem;font-size:0.95rem;color:#1e4d8c">${escapeHtml(a.label)} <span class="badge">${a.category}</span></h3>
                <div class="form-grid">
                  ${balanceField(key, "Balance", prev[key], isInv)}
                </div>`;
              })
              .join("")}
          </div>
        </div>
        <aside class="calc-panel" id="live-calc">
          <h3>Live Calculations</h3>
          <p class="muted">Totals update as you type</p>
        </aside>
        <div style="grid-column:1/-1" class="btn-group">
          <button type="submit" class="btn btn-primary">Save &amp; Generate PDFs</button>
        </div>
      </form>`;

    el.querySelectorAll("[data-use-last]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.useLast;
        el.querySelector(`[data-key="${key}"]`).value = btn.dataset.value;
        refreshPreview(clientId, el);
      });
    });

    el.querySelector("#quarterly-form").addEventListener("input", () => refreshPreview(clientId, el));
    el.querySelector("#quarterly-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const err = el.querySelector("#report-error");
      err.innerHTML = "";
      try {
        const payload = collectBalances(el);
        const res = await api(`/api/clients/${clientId}/reports`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        window.location.href = `/clients/${clientId}/reports/${res.id}?new=1`;
      } catch (ex) {
        err.innerHTML = `<div class="alert alert-error">${escapeHtml(ex.message)}</div>`;
      }
    });

    refreshPreview(clientId, el);
  }

  function collectBalances(el) {
    const form = el.querySelector("#quarterly-form");
    const balances = {};
    el.querySelectorAll("[data-key]").forEach((input) => {
      if (input.value !== "") balances[input.dataset.key] = parseFloat(input.value);
    });
    return {
      quarter_label: form.querySelector("[name='quarter_label']").value,
      report_date: form.querySelector("[name='report_date']").value,
      balances,
    };
  }

  async function refreshPreview(clientId, el) {
    const panel = el.querySelector("#live-calc");
    try {
      const { calculations: calc, missing } = await api(`/api/clients/${clientId}/preview`, {
        method: "POST",
        body: JSON.stringify(collectBalances(el)),
      });
      const s = calc.sacs;
      const t = calc.tcc;
      panel.innerHTML = `
        <h3>Live Calculations</h3>
        ${missing.length ? `<p class="alert alert-error" style="font-size:0.8rem">Missing: ${missing.join(", ")}</p>` : ""}
        <p><strong>SACS</strong></p>
        <div class="calc-row"><span>Excess</span><strong>${fmt(s.excess)}</strong></div>
        <div class="calc-row"><span>Reserve Target</span><strong>${fmt(s.private_reserve_target)}</strong></div>
        <p style="margin-top:1rem"><strong>TCC</strong></p>
        <div class="calc-row"><span>C1 Retirement</span><strong>${fmt(t.client1_retirement_total)}</strong></div>
        <div class="calc-row"><span>C2 Retirement</span><strong>${fmt(t.client2_retirement_total)}</strong></div>
        <div class="calc-row"><span>Non-Retirement</span><strong>${fmt(t.non_retirement_total)}</strong></div>
        <div class="calc-row"><span>Trust</span><strong>${fmt(t.trust_value)}</strong></div>
        <div class="calc-row grand"><span>Grand Total</span><strong>${fmt(t.grand_total)}</strong></div>
        <div class="calc-row"><span>Liabilities (separate)</span><strong>${fmt(t.liabilities_total)}</strong></div>`;

      el.querySelectorAll("[data-balance-key]").forEach((group) => {
        const key = group.dataset.balanceKey;
        const input = group.querySelector(`[data-key="${key}"]`);
        if (!input) return;
        group.classList.toggle("field-incomplete", !input.value && missing.some((m) => group.textContent.includes(m) || key === m));
      });
    } catch {
      /* ignore preview errors while typing */
    }
  }

  async function renderReportComplete(clientId, reportId) {
    const el = document.getElementById("report-complete");
    const payload = await api(`/api/reports/${reportId}`);
    const { report, client, persons, accounts: profileAccounts } = payload;
    const calc = report.calculations || {};
    const s = calc.sacs || {};
    const t = calc.tcc || {};
    const balances = report.balances || {};
    const accountDetails = calc.accounts || profileAccounts || [];

    const isNew = new URLSearchParams(window.location.search).get("new") === "1";

    const groupByCategory = (cat) => accountDetails.filter((a) => a.category === cat);
    const c1Accounts = groupByCategory("retirement_c1");
    const c2Accounts = groupByCategory("retirement_c2");
    const nonRet = groupByCategory("non_retirement");
    const trust = groupByCategory("trust");
    const liabilities = groupByCategory("liability");

    const accountRow = (a) => {
      const last4 = a.account_last_four ? `…${escapeHtml(a.account_last_four)}` : "—";
      const cashHtml = a.cash_balance
        ? `<span class="muted" style="margin-left:0.5rem">(cash: ${fmt(a.cash_balance)})</span>`
        : "";
      const extra = a.property_address
        ? `<div class="muted" style="font-size:0.8rem">${escapeHtml(a.property_address)}</div>`
        : a.interest_rate != null
        ? `<div class="muted" style="font-size:0.8rem">@ ${a.interest_rate}%</div>`
        : "";
      return `
        <li class="report-item">
          <div>
            <strong>${escapeHtml(a.label || a.account_type)}</strong>
            <span class="muted" style="margin-left:0.4rem">${escapeHtml(a.account_type)} · ${last4}</span>
            ${extra}
          </div>
          <div><strong>${fmt(a.balance || 0)}</strong>${cashHtml}</div>
        </li>`;
    };

    const groupCard = (title, items, totalLabel, totalValue) => {
      if (!items.length) return "";
      return `
        <div class="card">
          <h2>${escapeHtml(title)}</h2>
          <ul class="report-items">${items.map(accountRow).join("")}</ul>
          ${
            totalLabel
              ? `<div class="calc-row grand"><span>${escapeHtml(totalLabel)}</span><strong>${fmt(totalValue || 0)}</strong></div>`
              : ""
          }
        </div>`;
    };

    el.innerHTML = `
      <section class="page-header">
        <div>
          <h1>Report — ${escapeHtml(report.quarter_label)}</h1>
          <p class="muted">${escapeHtml(client.display_name)} · ${escapeHtml(report.report_date || "")}</p>
        </div>
        <a href="/clients/${clientId}" class="btn">← Client</a>
      </section>
      ${isNew ? `<div class="alert alert-success">Report saved. Download polished PDFs below.</div>` : ""}
      <div class="btn-group" style="margin-bottom:1rem">
        <a href="/api/reports/${reportId}/pdf/sacs" class="btn btn-primary">Download SACS PDF</a>
        <a href="/api/reports/${reportId}/pdf/tcc" class="btn btn-primary">Download TCC PDF</a>
      </div>

      <div class="card">
        <h2>SACS — Cashflow</h2>
        <div class="calc-row"><span>Monthly Inflow</span><strong>${fmt(s.inflow)}</strong></div>
        <div class="calc-row"><span>Monthly Outflow</span><strong>${fmt(s.outflow)}</strong></div>
        <div class="calc-row grand"><span>Monthly Excess</span><strong>${fmt(s.excess)}</strong></div>
        <div class="calc-row"><span>Private Reserve Balance</span><strong>${fmt(s.private_reserve_balance)}</strong></div>
        <div class="calc-row"><span>${escapeHtml(client.schwab_label || "Investment Account")} Balance</span><strong>${fmt(s.schwab_balance)}</strong></div>
        <div class="calc-row"><span>Private Reserve Target</span><strong>${fmt(s.private_reserve_target)}</strong></div>
      </div>

      ${groupCard(
        client.is_married ? "Client 1 — Retirement" : "Retirement",
        c1Accounts,
        client.is_married ? "Client 1 Retirement Total" : "Retirement Total",
        t.client1_retirement_total,
      )}
      ${client.is_married ? groupCard("Client 2 — Retirement", c2Accounts, "Client 2 Retirement Total", t.client2_retirement_total) : ""}
      ${groupCard("Trust / Residence", trust, "Trust Value", t.trust_value)}
      ${groupCard("Non-Retirement Accounts", nonRet, "Non-Retirement Total", t.non_retirement_total)}
      ${groupCard("Liabilities (not in net worth)", liabilities, "Liabilities Total", t.liabilities_total)}

      <div class="card">
        <h2>Grand Total Net Worth</h2>
        <div class="calc-row grand"><span>C1 + C2 + Non-Retirement + Trust</span><strong>${fmt(t.grand_total)}</strong></div>
        <p class="muted" style="font-size:0.85rem;margin-top:0.5rem">Liabilities are tracked separately and not subtracted from net worth (per PRD).</p>
      </div>`;
  }

  return {
    renderClientList,
    initClientForm,
    renderClientDetail,
    initReportEntry,
    renderReportComplete,
  };
})();
