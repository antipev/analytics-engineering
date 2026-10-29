// Pure formatting helpers for the Jaffle Shop profitability app.
// No DOM access here so the functions stay easy to reason about and test.

export const money = (n, digits = 2) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return "$" + Number(n).toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
};

export const money0 = (n) => money(n, 0);

export const moneyCompact = (n) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  if (Math.abs(v) >= 1000) return "$" + (v / 1000).toFixed(1) + "k";
  return "$" + v.toFixed(0);
};

export const int = (n) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("en-US");
};

export const pct = (n, digits = 1) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  return (Number(n) * 100).toFixed(digits) + "%";
};

// Publisher returns dates as ISO strings, plain Date objects, or typed cells.
// Normalise all three shapes to a YYYY-MM-DD string.
export const isoDay = (v) => {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v.slice(0, 10);
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  if (typeof v === "object") {
    const inner = v.value ?? v.date_value ?? v.string_value ?? v.time_value;
    if (inner !== undefined && inner !== null) return isoDay(inner);
  }
  return String(v);
};

export const dayLabel = (v) => {
  const iso = isoDay(v);
  const d = new Date(iso + "T00:00:00Z");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
};

export const isDayInput = (s) => typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s);

// The food/drink mix arrives as two booleans; readers want one phrase.
export const mixLabel = (hasFood, hasDrink) => {
  if (hasFood && hasDrink) return "Food + drink";
  if (hasFood) return "Food only";
  if (hasDrink) return "Drink only";
  return "Neither";
};

export const titleCase = (s) =>
  typeof s === "string" && s.length ? s.charAt(0).toUpperCase() + s.slice(1) : String(s ?? "");

export const csvEscape = (c) => '"' + String(c).replace(/"/g, '""') + '"';
