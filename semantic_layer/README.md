# Malloy semantic layer

This directory is the source of truth for the Malloy packages served by both
Credible and the self-hosted Malloy Publisher.

## Packages

| Package | Folder | Tables |
|---|---|---|
| `comics` | `packages/comics/` | `marts.comics`, `marts.calendar` |
| `jaffle_shop` | `packages/jaffle_shop/` | `marts.cafe_customers`, `marts.cafe_locations`, `marts.cafe_order_items`, `marts.cafe_orders`, `marts.cafe_products`, `marts.cafe_supplies` |

Each package directory is the publishable unit. It must contain `publisher.json`;
`semantic_layer/publisher.config.json` is only a local Publisher configuration
and is never uploaded to Credible.

## MotherDuck dependency

The sources read from MotherDuck database `data_warehouse_demo`, schema `marts`.
The following tables must exist before Publisher can load or query the packages:

- `marts.calendar`
- `marts.comics`
- `marts.cafe_customers`
- `marts.cafe_locations`
- `marts.cafe_order_items`
- `marts.cafe_orders`
- `marts.cafe_products`
- `marts.cafe_supplies`

The MotherDuck token belongs in the repository-root `.env` as
`MOTHERDUCK_TOKEN`. Never commit the token or a populated Publisher config.

## Local Publisher

From this directory:

```bash
set -a
source ../.env
set +a

npx --yes @malloy-publisher/server@0.0.244 \
  --server_root . \
  --config ./publisher.config.json \
  --port 4000 \
  --init
```

Open `http://localhost:4000`, confirm both packages load without errors, and
query `comics` and `cafe_orders` to verify MotherDuck connectivity. Stop the
server with `Ctrl+C`.

## Credible publishing

Credible packages are published from `main` by the GitHub Actions workflow using
`cred publish`. The workflow bumps the package patch version for every changed
package because published versions are immutable. Do not publish manually from
a laptop once CI/CD owns the package; a manual publish consumes the version and
forces the next automated publish to use a higher one.

A package is owned by either CI/CD or git-backed modeling, never both. Do not
enroll a package in git-backed modeling while the workflow publishes it.

## No cross-repository symlinks

Do not symlink packages from another repository. Docker build contexts and the
deployed Cloud Run image contain only the Publisher repository, so a symlink to
a sibling checkout is outside the context and will be missing or dangling.
Keep the canonical package files in this repository and copy or mirror them into
the Publisher deployment.
