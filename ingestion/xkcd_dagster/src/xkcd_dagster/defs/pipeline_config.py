import dagster as dg

COMICS_INGESTION_KEYS = [
    dg.AssetKey("raw_comics"),
    dg.AssetKey("raw_comics_v2"),
]

JAFFLE_SEEDS = [
    "raw_customers",
    "raw_orders",
    "raw_items",
    "raw_stores",
    "raw_products",
    "raw_supplies",
]

JAFFLE_INGESTION_KEYS = [dg.AssetKey(name) for name in JAFFLE_SEEDS]

# Lookup only: each job selects the keys for its own group.
INGESTION_KEYS_BY_GROUP: dict[str, list[dg.AssetKey]] = {
    "comics": COMICS_INGESTION_KEYS,
    "jaffle_shop": JAFFLE_INGESTION_KEYS,
}
