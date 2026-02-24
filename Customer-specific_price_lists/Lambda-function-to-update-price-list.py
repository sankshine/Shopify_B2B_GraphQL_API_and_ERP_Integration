# ── Push Acme's negotiated prices for each product variant ──────────────────
add_prices = """
mutation AddFixedPrices($priceListId: ID!, $prices: [PriceListPriceInput!]!) {
  priceListFixedPricesAdd(priceListId: $priceListId, prices: $prices) {
    prices {
      variant { id }
      price   { amount currencyCode }
    }
    userErrors { field message }
  }
}
"""
prices_payload = [
    {
        "variantId": line["shopify_variant_id"],
        "price": {
            "amount":       line["agreedPrice"],
            "currencyCode": erp_payload["currency"],
        }
    }
    for line in erp_payload["lines"]
]

result = graphql(add_prices, {
    "priceListId": pl_gid,
    "prices":      prices_payload,
})

print("Fixed prices written:")
for p in result["data"]["priceListFixedPricesAdd"]["prices"]:
    print(f"  {p['variant']['id']} → {p['price']['currencyCode']} {p['price']['amount']}")

# Output:
# gid://shopify/ProductVariant/1001 → USD 43.00   ← Acme's negotiated rate
# gid://shopify/ProductVariant/1002 → USD 18.50
# gid://shopify/ProductVariant/1003 → USD 108.00
# gid://shopify/ProductVariant/1004 → USD 88.00
