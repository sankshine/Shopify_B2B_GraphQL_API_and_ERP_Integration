import json

# For very large catalogs — tens of thousands of SKUs —
# batched mutations become too slow and too expensive on rate limits
# The Shopify Bulk Operations API handles this via a JSONL file upload

# Step 1: Request a staged upload URL from Shopify
staged_upload = """
mutation StagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets {
      url
      resourceUrl
      parameters {
        name
        value
      }
    }
    userErrors { field message }
  }
}
"""
result  = graphql(staged_upload, {
    "input": [{
        "resource":   "BULK_MUTATION_VARIABLES",
        "filename":   "price_list_bulk.jsonl",
        "mimeType":   "text/jsonl",
        "httpMethod": "POST",
    }]
})
target      = result["data"]["stagedUploadsCreate"]["stagedTargets"][0]
upload_url  = target["url"]
resource_url = target["resourceUrl"]
params      = {p["name"]: p["value"] for p in target["parameters"]}

print(f"Staged upload URL obtained: {upload_url[:60]}...")

# Step 2: Build the JSONL file — one JSON object per line, one price per line
# This is how Shopify expects bulk operation variables
large_price_catalog = [
    {
        "variantId": f"gid://shopify/ProductVariant/{1000 + i}",
        "price": {
            "amount":       str(round(10.00 + i * 0.10, 2)),
            "currencyCode": "USD",
        }
    }
    for i in range(5000)   # 5,000 SKUs — too large for batched mutations
]

jsonl_lines = "\n".join(
    json.dumps({"priceListId": pl_gid, "prices": [price]})
    for price in large_price_catalog
)

# Step 3: Upload the JSONL file to the staged URL
import requests as req
upload_response = req.post(upload_url, data=params, files={"file": ("price_list_bulk.jsonl", jsonl_lines)})
print(f"File uploaded: HTTP {upload_response.status_code}")

# Step 4: Trigger the bulk operation using the uploaded file URL
bulk_mutation = """
mutation BulkOperationRun($mutation: String!, $stagedUploadPath: String!) {
  bulkOperationRunMutation(
    mutation: $mutation
    stagedUploadPath: $stagedUploadPath
  ) {
    bulkOperation {
      id
      status
    }
    userErrors { field message }
  }
}
"""
result = graphql(bulk_mutation, {
    "mutation": """
        mutation AddPrices($priceListId: ID!, $prices: [PriceListPriceInput!]!) {
          priceListFixedPricesAdd(priceListId: $priceListId, prices: $prices) {
            prices { variant { id } price { amount } }
            userErrors { field message }
          }
        }
    """,
    "stagedUploadPath": resource_url,
})
bulk_op = result["data"]["bulkOperationRunMutation"]["bulkOperation"]
print(f"Bulk operation started:")
print(f"  ID:     {bulk_op['id']}")
print(f"  Status: {bulk_op['status']}")

# Step 5: Poll until the bulk operation completes
poll_status = """
query {
  currentBulkOperation {
    id
    status
    errorCode
    objectCount
    url
  }
}
"""
import time
while True:
    result = graphql(poll_status)
    op     = result["data"]["currentBulkOperation"]
    print(f"  Polling: status={op['status']} objects_processed={op['objectCount']}")

    if op["status"] in ("COMPLETED", "FAILED"):
        break
    time.sleep(5)

if op["status"] == "COMPLETED":
    print(f"\nBulk operation complete:")
    print(f"  {op['objectCount']} prices written to Shopify")
    print(f"  Results available at: {op['url']}")
else:
    print(f"Bulk operation failed: {op['errorCode']}")

