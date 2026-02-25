# ERP holds Acme's negotiated prices under TIER_A
# These get grouped into one catalog linked to one price list
# so all of Acme's locations see the same negotiated rates

erp_tier = {
    "tier_name":    "TIER_A",
    "company_name": "Acme Corporation",
    "currency":     "USD",
    "discount_pct": 20.0,
    "location_gids": [
        "gid://shopify/CompanyLocation/111111111",   # Acme HQ
        "gid://shopify/CompanyLocation/222222222",   # Acme Dallas
    ]
}

# Step 1: Create the price list
create_pl = """
mutation PriceListCreate($input: PriceListCreateInput!) {
  priceListCreate(input: $input) {
    priceList { id name }
    userErrors  { field message }
  }
}
"""
result = graphql(create_pl, {
    "input": {
        "name":     f"ERP {erp_tier['tier_name']} — {erp_tier['company_name']}",
        "currency": erp_tier["currency"],
        "parent": {
            "adjustment": {
                "type":  "PERCENTAGE_DECREASE",
                "value": str(erp_tier["discount_pct"]),
            },
            "settings": {"compareAtMode": "NULLIFY"}
        }
    }
})
pl_gid = result["data"]["priceListCreate"]["priceList"]["id"]
print(f"Price list created: {pl_gid}")

# Step 2: Create catalog and link the price list to Acme's locations
create_catalog = """
mutation CatalogCreate($input: CatalogCreateInput!) {
  catalogCreate(input: $input) {
    catalog { id title }
    userErrors { field message }
  }
}
"""
result = graphql(create_catalog, {
    "input": {
        "title":       f"{erp_tier['company_name']} Catalog",
        "status":      "ACTIVE",
        "priceListId": pl_gid,
        "context": {
            "companyLocationIds": erp_tier["location_gids"]
        }
    }
})
catalog_gid = result["data"]["catalogCreate"]["catalog"]["id"]
print(f"Catalog created and linked: {catalog_gid}")

