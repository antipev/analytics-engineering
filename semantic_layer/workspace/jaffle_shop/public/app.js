// Jaffle Shop profitability app: runs every tile query against the curated
// cafe_bridge_explore, then renders KPIs, charts and the product table.
import { TILES, MODEL, DATA_WINDOW } from "./tiles.js";
import {
  csvEscape,
  int,
  isDayInput,
  money,
  money0,
  pct,
  titleCase,
} from "./format.js";
import {
  drawBasket,
  drawCustomers,
  drawMix,
  drawProductMargin,
  drawTrend,
  drawTypeRate,
  drawVolumeRate,
} from "./charts.js";

const state = {
  start: DATA_WINDOW.start,
  end: DATA_WINDOW.end,
  topN: 10,
  data: {},
  lastLoaded: null,
};

const els = {
  status: document.getElementById("status"),
  start: document.getElementById("start"),
  end: document.getElementById("end"),
  topn: document.getElementById("topn"),
  kpis: document.getElementById("kpis"),
  substrip: document.getElementById("substrip"),
  table: document.querySelector("#productTable tbody"),
  typeNote: document.getElementById("typeNote"),
  customerNote: document.getElementById("customerNote"),
  supply: document.getElementById("supply"),
  csvBtn: document.getElementById("csvBtn"),
  resetBtn: document.getElementById("resetBtn"),
};

const kpiCard = (label, value, sub = "") =>
  `<div class="kpi"><div class="lbl">${label}</div><div class="val">${value}</div>${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;

const setStatus = (kind, text) => {
  els.status.className = "badge" + (kind === "loading" ? " loading" : kind === "error" ? " error" : "");
  els.status.textContent = text;
};

const row = (id) => (state.data[id] || [])[0] || {};
const rows = (id) => state.data[id] || [];

const windowLabel = () => {
  const { start, end } = state.lastLoaded || {};
  const from = isDayInput(start) ? start : "first date";
  const to = isDayInput(end) ? end : "last date";
  return `${from} → ${to}`;
};

function renderKpis() {
  const t = row("totals");
  const it = row("itemTotals");
  const supplyShare = t.revenue ? t.supply_cost / t.revenue : null;

  els.kpis.innerHTML =
    kpiCard("Orders", int(t.orders), `${int(t.items)} items · ${(Number(t.items_per_order) || 0).toFixed(2)} per order`) +
    kpiCard("Revenue", money(t.revenue), `includes ${money(t.tax_paid)} tax`) +
    kpiCard("Supply cost", money(t.supply_cost), `${pct(supplyShare)} of revenue`) +
    kpiCard("Gross margin", money(t.margin), `${pct(t.margin_pct)} of revenue`) +
    kpiCard("Average order value", money(t.aov), `${money(t.subtotal)} pre-tax`) +
    kpiCard("Item-level margin", money(it.margin), `${pct(it.margin_pct)} on ${money(it.revenue)} pre-tax`);

  els.substrip.innerHTML = t.orders
    ? `Item-level basis (pre-tax): <b>${int(it.items)}</b> items · <b>${money(it.revenue)}</b> revenue · ` +
      `<b>${money(it.supply_cost)}</b> supply cost · <b>${money(it.margin)}</b> margin at <b>${pct(it.margin_pct)}</b>. ` +
      `Order-level margin is ${money(t.margin)} at ${pct(t.margin_pct)}, higher only because order revenue carries tax.`
    : `<span class="empty">No orders in this date range.</span>`;
}

function renderProductTable(products) {
  if (!products.length) {
    els.table.innerHTML = `<tr><td colspan="7" class="empty">No products sold in this date range.</td></tr>`;
    return;
  }
  els.table.innerHTML = products
    .map((p) => {
      const rate = Number(p.margin_pct) || 0;
      const cls = rate < 0.7 ? "low" : rate < 0.8 ? "mid" : "high";
      return `<tr>
        <td>${p.product.trim()}</td>
        <td>${titleCase(p.type)}</td>
        <td class="num">${int(p.items)}</td>
        <td class="num">${money(p.revenue)}</td>
        <td class="num">${money(p.supply_cost)}</td>
        <td class="num">${money(p.margin)}</td>
        <td class="num rate ${cls}">${pct(rate)}</td>
      </tr>`;
    })
    .join("");
}

function renderSupply() {
  const s = row("supplies");
  const cards = [
    ["Supplies", int(s.supplies)],
    ["Total unit cost", money(s.total_supply_cost)],
    ["Average unit cost", money(s.average_supply_cost, 3)],
    ["Perishable", `${int(s.perishable_supplies)} · ${pct(s.perishable_rate)}`],
  ];
  els.supply.innerHTML = cards
    .map(([k, v]) => `<div><div class="k">${k}</div><div class="v">${v}</div></div>`)
    .join("");
}

function renderNotes() {
  const types = rows("typeMix");
  if (types.length) {
    const best = [...types].sort((a, b) => b.margin_pct - a.margin_pct)[0];
    const volume = [...types].sort((a, b) => b.items - a.items)[0];
    els.typeNote.textContent =
      `${titleCase(best.type)} earns the higher rate (${pct(best.margin_pct)}) and carries ${pct(best.share_of_margin)} of margin dollars; ` +
      `${titleCase(volume.type)} sells more items (${int(volume.items)}). Axis does not start at zero.`;
  }

  const customers = rows("customers");
  if (customers.length) {
    els.customerNote.textContent = customers
      .map(
        (c) =>
          `${titleCase(c.customer_type)}: ${int(c.customers)} customers, ${int(c.orders)} orders, ` +
          `${money(c.revenue_per_customer)} revenue each`
      )
      .join(" · ");
  }
}

function render() {
  const products = rows("products");
  const shown = products.slice(0, state.topN);

  renderKpis();
  drawProductMargin(shown);
  drawTypeRate(rows("typeMix"));
  drawVolumeRate(products);
  renderProductTable(products);
  drawBasket(rows("basket"));
  drawMix(rows("mix"));
  drawCustomers(rows("customers"));
  drawTrend(rows("trend"));
  renderSupply();
  renderNotes();
}

async function loadAll() {
  if (typeof Publisher === "undefined" || typeof Publisher.query !== "function") {
    setStatus("error", "Publisher runtime missing — this page must be served by Malloy Publisher.");
    return;
  }

  const filters = { start: els.start.value, end: els.end.value };
  if (filters.start && filters.end && filters.start > filters.end) {
    setStatus("error", "The 'from' date is after the 'to' date.");
    return;
  }

  document.body.classList.add("is-busy");
  setStatus("loading", "Querying cafe_bridge_explore…");

  try {
    const results = await Promise.all(TILES.map((tile) => Publisher.query(MODEL, tile.query(filters))));
    TILES.forEach((tile, i) => {
      state.data[tile.id] = Array.isArray(results[i]) ? results[i] : [];
    });
    state.lastLoaded = filters;
    render();

    const totals = row("totals");
    setStatus(
      "ok",
      totals.orders
        ? `${windowLabel()} · ${int(totals.orders)} orders · ${money(totals.revenue)} revenue · ${pct(totals.margin_pct)} margin`
        : `${windowLabel()} · no orders in this range`
    );
  } catch (err) {
    console.error(err);
    setStatus("error", err && err.message ? String(err.message) : "Query failed.");
  } finally {
    document.body.classList.remove("is-busy");
  }
}

function downloadCsv() {
  const products = rows("products");
  if (!products.length) {
    alert("Nothing to download for this date range.");
    return;
  }
  const header = ["Product", "Type", "Items", "Item revenue (pre-tax)", "Supply cost", "Gross margin", "Margin rate"];
  const body = products.map((p) => [
    p.product.trim(),
    p.type,
    p.items,
    Number(p.revenue).toFixed(2),
    Number(p.supply_cost).toFixed(2),
    Number(p.margin).toFixed(2),
    (Number(p.margin_pct) * 100).toFixed(2) + "%",
  ]);
  const csv = [header, ...body].map((r) => r.map(csvEscape).join(",")).join("\n");
  const stamp = `${state.lastLoaded?.start || "all"}_${state.lastLoaded?.end || "all"}`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `jaffle_shop_profitability_${stamp}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

function reset() {
  els.start.value = DATA_WINDOW.start;
  els.end.value = DATA_WINDOW.end;
  els.topn.value = "10";
  state.topN = 10;
  loadAll();
}

[els.start, els.end].forEach((el) => el.addEventListener("change", loadAll));
els.topn.addEventListener("change", () => {
  state.topN = Number(els.topn.value) || 10;
  render();
});
els.csvBtn.addEventListener("click", downloadCsv);
els.resetBtn.addEventListener("click", reset);

loadAll();
