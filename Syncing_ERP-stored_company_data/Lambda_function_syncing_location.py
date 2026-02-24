# The company was already created in Shopify in the previous step
# and its GID was stored in the mapping table
company_gid = "gid://shopify/Company/987654321"

# Loop through every address in the NetSuite payload
for address in payload["data"]["addressBook"]:

    # companyLocationCreate is scoped directly under the Company GID
    # so Shopify knows this location belongs to Acme Corporation
    mutation = """
    mutation LocationCreate($companyId: ID!, $input: CompanyLocationInput!) {
      companyLocationCreate(companyId: $companyId, input: $input) {
        companyLocation {
          id
          name
        }
        userErrors { field message }
      }
    }
    """
    result = graphql(mutation, {
        "companyId": company_gid,   # scoped under Acme's GID
        "input": {
            "name": address["label"],
            "shippingAddress": {
                "address1":     address["addr1"],
                "city":         address["city"],
                "provinceCode": address["state"],
                "zip":          address["zip"],
                "countryCode":  address["country"],
            }
        }
    })

    loc = result["data"]["companyLocationCreate"]["companyLocation"]
    print(f"Location created: {loc['name']} → {loc['id']}")

# Output:
# Location created: Acme HQ → gid://shopify/CompanyLocation/111111111
# Location created: Acme Dallas Warehouse → gid://shopify/CompanyLocation/222222222
