# Shopify B2B ERP Integration

A production-oriented integration between a NetSuite ERP system and Shopify B2B using the Shopify Admin GraphQL API. The integration runs on AWS Lambda, triggered by NetSuite webhooks via API Gateway.

---

## Overview

Most B2B businesses run an ERP system that holds negotiated pricing, company accounts, and shipping locations. This integration keeps that data in sync with Shopify B2B so that each buyer sees their correct prices and locations automatically at checkout, without manual data entry on the Shopify side.

The GraphQL API acts as the communication layer between the Lambda middleware and the Shopify store. Every company record, location, contact, price list, and catalog in Shopify is created and maintained through GraphQL mutations fired from within the Lambda function.

---

## Assumptions

1. The client is on Shopify Plus. B2B GraphQL mutations such as `companyCreate`, `priceListCreate`, and `catalogCreate` are only available on Plus. Without it the integration cannot run.

2. The Shopify store already has products and variants loaded. Price list sync depends on Shopify variant GIDs existing before any pricing data is pushed. If variants are missing, `priceListFixedPricesAdd` will fail.

3. NetSuite is the ERP. The integration is designed around NetSuite's webhook structure, which fires HTTP POST requests with JSON payloads on record create and update events. ERP systems that do not support webhooks would require a polling-based architecture instead.

4. The ERP is the single source of truth. Any data conflict between NetSuite and Shopify is resolved in favour of NetSuite. Changes made directly in the Shopify admin will be overwritten on the next sync.

5. Each company belongs to exactly one pricing tier. The integration maps one company to one catalog and one price list. Companies with location-specific pricing that differs by branch would require an extended catalog model not covered here.

6. AWS Lambda is the integration middleware. NetSuite webhooks hit an API Gateway endpoint which triggers a Lambda function. Inside that Lambda function the Shopify GraphQL mutations are constructed and fired. Lambda is used because it is serverless, event-driven, and scales automatically with the volume of incoming ERP changes.

7. The Shopify Admin API token is already issued and scoped. The token requires read and write access to companies, customers, catalogs, and price lists. Without the correct scopes every mutation returns an authorization error.

---

## Architecture

```
NetSuite (ERP)
    |
    | webhook — HTTP POST JSON payload
    v
AWS API Gateway
    |
    v
AWS Lambda (middleware)
    |
    | GraphQL mutations
    v
Shopify Admin API
    |
    v
Shopify B2B Store
```

The Lambda function also writes to a mapping table after every successful create or update. The mapping table is the bridge between ERP IDs and Shopify GIDs and is the mechanism that makes all syncs idempotent.

---



## What Each Step Does

### Step A — Syncing ERP stored company data

Covers the full flow from receiving a NetSuite webhook to having a Company, its Locations, and its Contacts live in Shopify B2B.

- Performs an idempotency check by querying Shopify via `externalId` before creating anything, preventing duplicate records if a webhook fires more than once.
- Creates the Company using `companyCreate` and immediately writes the returned GID to the mapping table.
- Creates each shipping address as a `CompanyLocation` using `companyLocationCreate`, scoped under the Company GID.
- Creates a Shopify Customer record for each ERP contact and links them to the company using `companyAssignCustomerAsContact` with either an ADMIN or MEMBER role.
- For address changes, uses `companyLocationAssignAddress` rather than deleting and recreating. Deleting a location that has open draft orders causes errors and breaks those orders. Before any address update where the zip code changes, the integration checks for active draft orders on that location and logs a warning, since address changes in a different tax jurisdiction trigger tax recalculation on Shopify's side.

### Step B — Customer specific price list

Covers creating customer-specific pricing in Shopify and routing it to the correct buyers at checkout.

- Creates a `PriceList` per ERP pricing tier with a base percentage discount.
- Pushes per-variant negotiated prices using `priceListFixedPricesAdd` in batches of up to 250 prices per call. Shopify supports a maximum of 250 prices per mutation call, so catalogs with more SKUs are chunked automatically.
- For very large catalogs in the tens of thousands of SKUs, uses `stagedUploadsCreate` to upload a JSONL file and triggers a bulk operation that Shopify processes asynchronously in the background. This avoids exhausting the rate limit budget that batching alone would cause at that scale.
- Creates a `Catalog` per tier and assigns it to all matching company location GIDs from the mapping table. Once assigned, Shopify automatically routes the correct price list to the correct buyer at checkout with no further intervention.

### Step C — Data Consistency

Covers keeping Shopify in sync with the ERP over time as data changes.

- Each price list in the ERP carries a version timestamp. On every sync the Lambda compares the incoming version against the version stored in the mapping table. If they match, the sync is skipped entirely and zero API calls are made. If they differ, a delta update runs.
- The delta comparison checks each incoming variant price against the currently live Shopify price and only pushes the variants that actually changed. This prevents unnecessary writes and keeps API usage within rate limit budgets.
- A nightly reconciliation job runs independently of the event-driven sync as a safety net. It fetches all companies from Shopify using paginated queries, compares them against the full ERP dataset, and triggers a re-sync for any company that is missing. This catches records that were dropped due to Lambda timeouts or silent webhook failures.
- Location updates always use `companyLocationUpdate` rather than delete and recreate to preserve all existing relationships — open orders, catalog assignments, and price list links — that Shopify has already built around that location GID.

---

## ID Mapping Table

The mapping table is the most critical component of the integration. It stores the relationship between every ERP ID and its corresponding Shopify GID, along with the last known state of the record and the timestamp of the last successful sync.

| Column | Description |
|---|---|
| erp_id | The internal ID from NetSuite |
| shopify_gid | The Global ID returned by Shopify after creation |
| last_known_state | Snapshot of the record at last sync — used for diffing |
| last_synced_at | UTC timestamp of the last successful sync |
| price_version | For price list rows — the ERP version string used for drift detection |

In production this table lives in a persistent datastore such as DynamoDB or RDS. In the demo it is an in-memory dictionary in `id_map.py`.

---

## Key GraphQL Mutations Used

| Mutation | Purpose |
|---|---|
| `companyCreate` | Creates a new B2B company in Shopify |
| `companyUpdate` | Updates an existing company record |
| `companyLocationCreate` | Creates a shipping or billing location under a company |
| `companyLocationUpdate` | Updates a location in place without breaking existing relationships |
| `companyLocationAssignAddress` | Updates shipping and billing addresses with tax awareness |
| `companyAssignCustomerAsContact` | Links a Shopify customer to a company with a role |
| `customerCreate` | Creates a Shopify customer record for a contact |
| `priceListCreate` | Creates a price list with a base discount |
| `priceListFixedPricesAdd` | Writes per-variant fixed prices to a price list in batches of up to 250 |
| `catalogCreate` | Creates a catalog and assigns it to company locations |
| `stagedUploadsCreate` | Obtains a staging URL for bulk JSONL file upload |
| `bulkOperationRunMutation` | Triggers async bulk processing for very large price catalogs |

---

## Setup

```bash
pip install requests rich
```

Set the following in each script:

```python
SHOPIFY_STORE  = "your-store.myshopify.com"
SHOPIFY_TOKEN  = "your-admin-api-token"
```



## Pitfalls

- Shopify has no native upsert. Always query by `externalId` before creating or you will get duplicate company records.
- A `CompanyLocation` can only be assigned to one catalog at a time. If the same location needs to be in multiple catalogs, the architecture needs to be redesigned before implementation.
- Deleting a company location that has open draft orders will throw an error. Always update in place.
- Address changes that cross tax jurisdiction boundaries trigger tax recalculation. Check for open orders before proceeding and notify the finance team.
- The Admin API token must be rotated before expiry. A lapsed token causes all mutations to fail silently if there is no error handling on the HTTP 401 response.
- Webhook delivery from NetSuite is not guaranteed. The nightly reconciliation job exists specifically to catch records that were dropped due to failed or timed-out Lambda executions.
