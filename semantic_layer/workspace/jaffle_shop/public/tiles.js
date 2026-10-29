// Every tile the app shows is declared here as data: an id, the tile's copy, and a
// query builder that turns filter state into Malloy source.
//
// One model, one explore. Each query pins `Stage` on cafe_bridge_explore and then
// reaches measures through that stage's refinement, so the app reads exactly the
// measures the profitability notebook reads.
import { isDayInput } from "./format.js";

export const MODEL = "3_explores/cafe_bridge_explore.malloy";

// Date bounds as exposed by the data. Used to seed the date inputs and to state
// the window in the UI.
export const DATA_WINDOW = { start: "2016-09-01", end: "2016-09-16" };

// Both stages carry Order_date; supplies and locations do not, so they are not filtered.
function stageFilter(stage, { start, end }) {
  const parts = [`Stage = '${stage}'`];
  if (isDayInput(start)) parts.push(`${stage}.Order_date >= @${start}`);
  if (isDayInput(end)) parts.push(`${stage}.Order_date <= @${end}`);
  return parts.join(" and ");
}

const orders = (f) => stageFilter("cafe_orders", f);
const items = (f) => stageFilter("cafe_order_items", f);

export const TILES = [
  {
    id: "totals",
    title: "Order-level totals",
    basis: "revenue includes tax",
    query: (f) => `run: cafe_bridge_explore -> {
  where: ${orders(f)}
  aggregate:
    orders is cafe_orders.Order_Count
    revenue is cafe_orders.Total_Revenue
    subtotal is cafe_orders.Total_Subtotal
    tax_paid is cafe_orders.Total_Tax_Paid
    supply_cost is cafe_orders.Total_Order_Cost
    margin is cafe_orders.Gross_Margin
    margin_pct is cafe_orders.Gross_Margin / cafe_orders.Total_Revenue
    aov is cafe_orders.Total_Revenue / cafe_orders.Order_Count
    items is cafe_orders.Total_Items
    items_per_order is cafe_orders.Total_Items / cafe_orders.Order_Count
}`,
  },
  {
    id: "itemTotals",
    title: "Item-level totals",
    basis: "revenue is pre-tax",
    query: (f) => `run: cafe_bridge_explore -> {
  where: ${items(f)}
  aggregate:
    items is cafe_order_items.Order_Item_Count
    revenue is cafe_order_items.Item_Revenue
    supply_cost is cafe_order_items.Total_Supply_Cost
    margin is cafe_order_items.Item_Gross_Margin
    margin_pct is cafe_order_items.Item_Gross_Margin / cafe_order_items.Item_Revenue
}`,
  },
  {
    id: "products",
    title: "Product detail",
    query: (f) => `run: cafe_bridge_explore -> {
  where: ${items(f)}
  group_by:
    type is cafe_order_items.cafe_products.Product_type
    product is cafe_order_items.Product_name
  aggregate:
    items is cafe_order_items.Order_Item_Count
    revenue is cafe_order_items.Item_Revenue
    supply_cost is cafe_order_items.Total_Supply_Cost
    margin is cafe_order_items.Item_Gross_Margin
    margin_pct is cafe_order_items.Item_Gross_Margin / cafe_order_items.Item_Revenue
  order_by: margin desc
}`,
  },
  {
    id: "typeMix",
    title: "Margin rate by product type",
    query: (f) => `run: cafe_bridge_explore -> {
  where: ${items(f)}
  group_by: type is cafe_order_items.cafe_products.Product_type
  aggregate:
    items is cafe_order_items.Order_Item_Count
    margin is cafe_order_items.Item_Gross_Margin
    share_of_margin is cafe_order_items.Item_Gross_Margin / all(cafe_order_items.Item_Gross_Margin)
    margin_pct is cafe_order_items.Item_Gross_Margin / cafe_order_items.Item_Revenue
  order_by: margin desc
}`,
  },
  {
    id: "basket",
    title: "Margin per order by basket size",
    query: (f) => `run: cafe_bridge_explore -> {
  where: ${orders(f)}
  group_by: items_in_order is cafe_orders.Count_order_items
  aggregate:
    orders is cafe_orders.Order_Count
    revenue is cafe_orders.Total_Revenue
    margin is cafe_orders.Gross_Margin
    margin_per_order is cafe_orders.Gross_Margin / cafe_orders.Order_Count
    margin_pct is cafe_orders.Gross_Margin / cafe_orders.Total_Revenue
  order_by: items_in_order
}`,
  },
  {
    id: "mix",
    title: "Food and drink mix",
    query: (f) => `run: cafe_bridge_explore -> {
  where: ${orders(f)}
  group_by:
    has_food is cafe_orders.Is_food_order
    has_drink is cafe_orders.Is_drink_order
  aggregate:
    orders is cafe_orders.Order_Count
    revenue is cafe_orders.Total_Revenue
    margin is cafe_orders.Gross_Margin
    margin_per_order is cafe_orders.Gross_Margin / cafe_orders.Order_Count
    margin_pct is cafe_orders.Gross_Margin / cafe_orders.Total_Revenue
}`,
  },
  {
    id: "customers",
    title: "New vs returning customers",
    query: (f) => `run: cafe_bridge_explore -> {
  where: ${orders(f)}
  group_by: customer_type is cafe_customers.Customer_type
  aggregate:
    orders is cafe_orders.Order_Count
    customers is cafe_customers.Customer_Count
    revenue is cafe_orders.Total_Revenue
    margin is cafe_orders.Gross_Margin
    margin_pct is cafe_orders.Gross_Margin / cafe_orders.Total_Revenue
    revenue_per_customer is cafe_orders.Total_Revenue / cafe_customers.Customer_Count
  order_by: margin desc
}`,
  },
  {
    id: "trend",
    title: "Daily margin rate against revenue",
    query: (f) => `run: cafe_bridge_explore -> {
  where: ${orders(f)}
  group_by: order_day is cafe_orders.Order_date
  aggregate:
    orders is cafe_orders.Order_Count
    revenue is cafe_orders.Total_Revenue
    margin is cafe_orders.Gross_Margin
    margin_pct is cafe_orders.Gross_Margin / cafe_orders.Total_Revenue
  order_by: order_day
}`,
  },
  {
    id: "supplies",
    title: "Supply base",
    query: () => `run: cafe_bridge_explore -> {
  where: Stage = 'cafe_supplies'
  aggregate:
    supplies is cafe_supplies.Supply_Count
    total_supply_cost is cafe_supplies.Total_Supply_Cost
    average_supply_cost is cafe_supplies.Average_Supply_Cost
    perishable_supplies is cafe_supplies.Perishable_Supply_Count
    perishable_rate is cafe_supplies.Perishable_Supply_Rate
}`,
  },
];

export const tileById = (id) => TILES.find((t) => t.id === id);
