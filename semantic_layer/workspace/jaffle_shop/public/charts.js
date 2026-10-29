// Chart.js bindings. Each draw function takes the rows from one tile query and
// (re)renders a single canvas. Charts are created once and updated in place.
import { dayLabel, int, mixLabel, money, moneyCompact, money0, pct, titleCase } from "./format.js";

export const COLORS = {
  brand: "#2c3e50",
  purple: "#9b59b6",
  accent: "#e74c3c",
  green: "#27ae60",
  amber: "#f39c12",
  blue: "#2980b9",
  grey: "#95a5a6",
};

const BASIC = { responsive: true, maintainAspectRatio: false, animation: { duration: 250 } };

const registry = new Map();

if (typeof window !== "undefined" && window.Chart) {
  window.Chart.defaults.font.family =
    '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif';
  window.Chart.defaults.font.size = 12;
  window.Chart.defaults.color = "#6b7683";
}

function draw(id, config) {
  const el = document.getElementById(id);
  if (!el || !window.Chart) return;
  const existing = registry.get(id);
  if (!existing) {
    registry.set(id, new window.Chart(el, config));
    return;
  }
  existing.data = config.data;
  existing.options = config.options;
  existing.update();
}

const noLegend = { legend: { display: false } };

// Item-level margin in dollars, one bar per product.
export function drawProductMargin(rows) {
  const sorted = [...rows].sort((a, b) => b.margin - a.margin);
  draw("chartProduct", {
    type: "bar",
    data: {
      labels: sorted.map((r) => r.product),
      datasets: [
        { label: "Gross margin", data: sorted.map((r) => r.margin), backgroundColor: COLORS.purple, borderRadius: 5 },
      ],
    },
    options: {
      ...BASIC,
      indexAxis: "y",
      plugins: {
        ...noLegend,
        tooltip: {
          callbacks: {
            label: (ctx) => `Margin ${money(ctx.parsed.x)} on ${int(sorted[ctx.dataIndex].items)} items`,
            afterLabel: (ctx) => `Rate ${pct(sorted[ctx.dataIndex].margin_pct)}`,
          },
        },
      },
      scales: { x: { ticks: { callback: (v) => moneyCompact(v) } } },
    },
  });
}

// Margin rate by product type. The axis is zoomed to the interesting band, so the
// panel labels it as such rather than implying a zero baseline.
export function drawTypeRate(rows) {
  const rates = rows.map((r) => Number(r.margin_pct) || 0);
  const min = rates.length ? Math.max(0, Math.floor((Math.min(...rates) - 0.02) * 100) / 100) : 0;
  const max = rates.length ? Math.min(1, Math.ceil((Math.max(...rates) + 0.02) * 100) / 100) : 1;
  draw("chartType", {
    type: "bar",
    data: {
      labels: rows.map((r) => titleCase(r.type)),
      datasets: [
        {
          label: "Margin rate",
          data: rates,
          backgroundColor: rows.map((r) => (r.type === "beverage" ? COLORS.blue : COLORS.amber)),
          borderRadius: 5,
        },
      ],
    },
    options: {
      ...BASIC,
      plugins: {
        ...noLegend,
        tooltip: {
          callbacks: {
            label: (ctx) => `Margin rate ${pct(rates[ctx.dataIndex], 2)}`,
            afterLabel: (ctx) => [
              `Share of margin ${pct(rows[ctx.dataIndex].share_of_margin)}`,
              `Items ${int(rows[ctx.dataIndex].items)}`,
            ],
          },
        },
      },
      scales: {
        y: { min, max, ticks: { callback: (v) => pct(v, 0) } },
      },
    },
  });
}

// Margin per order rises with basket size; the tooltip keeps the rate honest.
export function drawBasket(rows) {
  draw("chartBasket", {
    type: "bar",
    data: {
      labels: rows.map((r) => (Number(r.items_in_order) === 1 ? "1 item" : `${r.items_in_order} items`)),
      datasets: [
        {
          label: "Margin per order",
          data: rows.map((r) => r.margin_per_order),
          backgroundColor: COLORS.green,
          borderRadius: 5,
        },
      ],
    },
    options: {
      ...BASIC,
      plugins: {
        ...noLegend,
        tooltip: {
          callbacks: {
            label: (ctx) => `Margin per order ${money(ctx.parsed.y)}`,
            afterLabel: (ctx) => [
              `Orders ${int(rows[ctx.dataIndex].orders)}`,
              `Margin rate ${pct(rows[ctx.dataIndex].margin_pct)}`,
            ],
          },
        },
      },
      scales: { y: { ticks: { callback: (v) => moneyCompact(v) } } },
    },
  });
}

// Food-only, drink-only, and both: does adding a drink lift the order?
export function drawMix(rows) {
  const sorted = [...rows].sort((a, b) => b.margin_per_order - a.margin_per_order);
  draw("chartMix", {
    type: "bar",
    data: {
      labels: sorted.map((r) => mixLabel(r.has_food, r.has_drink)),
      datasets: [
        {
          label: "Margin per order",
          data: sorted.map((r) => r.margin_per_order),
          backgroundColor: COLORS.accent,
          borderRadius: 5,
        },
      ],
    },
    options: {
      ...BASIC,
      plugins: {
        ...noLegend,
        tooltip: {
          callbacks: {
            label: (ctx) => `Margin per order ${money(ctx.parsed.y)}`,
            afterLabel: (ctx) => [
              `Orders ${int(sorted[ctx.dataIndex].orders)}`,
              `Margin rate ${pct(sorted[ctx.dataIndex].margin_pct)}`,
            ],
          },
        },
      },
      scales: { y: { ticks: { callback: (v) => moneyCompact(v) } } },
    },
  });
}

// New vs returning: rate, with customers and revenue per customer in the tooltip.
export function drawCustomers(rows) {
  const rates = rows.map((r) => Number(r.margin_pct) || 0);
  const min = rates.length ? Math.max(0, Math.floor((Math.min(...rates) - 0.02) * 100) / 100) : 0;
  const max = rates.length ? Math.min(1, Math.ceil((Math.max(...rates) + 0.02) * 100) / 100) : 1;
  draw("chartCustomers", {
    type: "bar",
    data: {
      labels: rows.map((r) => titleCase(r.customer_type)),
      datasets: [
        {
          label: "Margin rate",
          data: rates,
          backgroundColor: COLORS.purple,
          borderRadius: 5,
        },
      ],
    },
    options: {
      ...BASIC,
      plugins: {
        ...noLegend,
        tooltip: {
          callbacks: {
            label: (ctx) => `Margin rate ${pct(rates[ctx.dataIndex], 2)}`,
            afterLabel: (ctx) => [
              `Customers ${int(rows[ctx.dataIndex].customers)}`,
              `Revenue per customer ${money(rows[ctx.dataIndex].revenue_per_customer)}`,
            ],
          },
        },
      },
      scales: { y: { min, max, ticks: { callback: (v) => pct(v, 0) } } },
    },
  });
}

// Daily revenue (bars, left axis) with the margin rate over it (line, right axis).
export function drawTrend(rows) {
  const rates = rows.map((r) => Number(r.margin_pct) || 0);
  const trendMin = rates.length ? Math.max(0, Math.floor((Math.min(...rates) - 0.03) * 100) / 100) : 0;
  const trendMax = rates.length ? Math.min(1, Math.ceil((Math.max(...rates) + 0.03) * 100) / 100) : 1;
  draw("chartTrend", {
    type: "bar",
    data: {
      labels: rows.map((r) => dayLabel(r.order_day)),
      datasets: [
        {
          label: "Revenue",
          data: rows.map((r) => r.revenue),
          backgroundColor: "rgba(155,89,182,.35)",
          borderRadius: 4,
          yAxisID: "y",
          order: 2,
        },
        {
          label: "Margin rate",
          type: "line",
          data: rows.map((r) => r.margin_pct),
          borderColor: COLORS.green,
          backgroundColor: COLORS.green,
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 3,
          yAxisID: "y1",
          order: 1,
        },
      ],
    },
    options: {
      ...BASIC,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: true, labels: { boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ctx.dataset.yAxisID === "y1"
                ? `Margin rate ${pct(ctx.parsed.y, 2)}`
                : `Revenue ${money(ctx.parsed.y)}`,
            afterBody: (items) => {
              const row = rows[items[0].dataIndex];
              return [`Orders ${int(row.orders)}`, `Margin ${money(row.margin)}`];
            },
          },
        },
      },
      scales: {
        y: { position: "left", ticks: { callback: (v) => moneyCompact(v) }, title: { display: true, text: "Revenue" } },
        y1: {
          position: "right",
          min: trendMin,
          max: trendMax,
          grid: { drawOnChartArea: false },
          ticks: { callback: (v) => pct(v, 0) },
          title: { display: true, text: "Margin rate" },
        },
        x: { ticks: { autoSkip: true, maxRotation: 0 } },
      },
    },
  });
}

// Rate against volume: high-volume, thin-rate products are where a price or cost
// change would move the most money.
export function drawVolumeRate(rows) {
  const maxMargin = Math.max(1, ...rows.map((r) => Math.abs(r.margin)));
  const byType = (type) =>
    rows
      .filter((r) => String(r.type).toLowerCase() === type)
      .map((r) => ({
        x: Number(r.items) || 0,
        y: Number(r.margin_pct) || 0,
        r: 5 + 22 * (Math.abs(r.margin) / maxMargin),
        meta: r,
      }));
  draw("chartVolume", {
    type: "bubble",
    data: {
      datasets: [
        { label: "Beverage", data: byType("beverage"), backgroundColor: "rgba(41,128,185,.55)" },
        { label: "Jaffle", data: byType("jaffle"), backgroundColor: "rgba(243,156,18,.6)" },
      ],
    },
    options: {
      ...BASIC,
      plugins: {
        legend: { display: true, labels: { boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const m = ctx.raw.meta;
              return `${m.product}: ${pct(m.margin_pct)} on ${int(m.items)} items`;
            },
            afterLabel: (ctx) => `Margin ${money(ctx.raw.meta.margin)} · bubble = margin dollars`,
          },
        },
      },
      scales: {
        x: { title: { display: true, text: "Items sold" }, ticks: { callback: (v) => int(v) } },
        y: { title: { display: true, text: "Margin rate" }, ticks: { callback: (v) => pct(v, 0) } },
      },
    },
  });
}
