import math

# ERP sends 600 SKU-level prices for Acme — too many for one call
# Shopify supports up to 250 prices per priceListFixedPricesAdd call
# So we chunk into batches of 250 and call three times

all_erp_prices = [
    {
        "variantId": f"gid://shopify/ProductVariant/{1000 + i}",
        "price": {
            "amount":       str(round(10.00 + i * 0.50, 2)),
            "currencyCode": "USD",
        }
    }
    for i in range(600)   # simulating 600 SKUs from ERP
]

BATCH_SIZE   = 250
total_prices = len(all_erp_prices)
num_batches  = math.ceil(total_prices / BATCH_SIZE)

print(f"Total prices to sync: {total_prices}")
print(f"Batch size:           {BATCH_SIZE}")
print(f"Number of batches:    {num_batches}\n")

add_prices = """
mutation AddFixedPrices($priceListId: ID!, $prices: [PriceListPriceInput!]!) {
  priceListFixedPricesAdd(priceListId: $priceListId, prices: $prices) {
    prices {
      variant { id }
      price   { amount }
    }
    userErrors { field message }
  }
}
"""
for batch_num in range(num_batches):
    start = batch_num * BATCH_SIZE
    end   = start + BATCH_SIZE
    batch = all_erp_prices[start:end]

    result  = graphql(add_prices, {"priceListId": pl_gid, "prices": batch})
    payload = result["data"]["priceListFixedPricesAdd"]

    if payload["userErrors"]:
        print(f"Batch {batch_num + 1} errors: {payload['userErrors']}")
    else:
        print(f"Batch {batch_num + 1}/{num_batches}: "
              f"{len(payload['prices'])} prices written "
              f"(variants {start + 1}–{min(end, total_prices)})")

