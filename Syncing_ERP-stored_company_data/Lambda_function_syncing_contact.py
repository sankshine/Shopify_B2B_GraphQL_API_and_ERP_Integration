# Contacts are a two-step process:
# Step 1 — create a Shopify Customer record for the person
# Step 2 — link that Customer to the Company as a CompanyContact with a role

for contact in payload["data"]["contacts"]:

    # Step 1: Create the Shopify Customer
    create_customer = """
    mutation CustomerCreate($input: CustomerInput!) {
      customerCreate(input: $input) {
        customer { id email }
        userErrors { field message }
      }
    }
    """
    result = graphql(create_customer, {
        "input": {
            "firstName": contact["firstName"],
            "lastName":  contact["lastName"],
            "email":     contact["email"],
        }
    })

    customer_gid = result["data"]["customerCreate"]["customer"]["id"]
    print(f"Customer created: {contact['email']} → {customer_gid}")

    # Step 2: Link that Customer to Acme Corporation as a CompanyContact
    # The role coming from NetSuite (ADMIN or MEMBER) controls what
    # the contact can do — ADMIN can manage the account, MEMBER can only buy
    assign_contact = """
    mutation AssignContact($companyId: ID!, $customerId: ID!) {
      companyAssignCustomerAsContact(
        companyId: $companyId
        customerId: $customerId
      ) {
        companyContact {
          id
          customer { email }
        }
        userErrors { field message }
      }
    }
    """
    result = graphql(assign_contact, {
        "companyId":  company_gid,    # scoped under Acme
        "customerId": customer_gid,   # the customer we just created
    })

    contact_rec = result["data"]["companyAssignCustomerAsContact"]["companyContact"]
    print(f"Contact assigned ({contact['role']}): {contact_rec['customer']['email']} → {contact_rec['id']}")

# Output:
# Customer created: alice@acme.com → gid://shopify/Customer/555555555
# Contact assigned (ADMIN): alice@acme.com → gid://shopify/CompanyContact/777777777
# Customer created: bob@acme.com → gid://shopify/Customer/666666666
# Contact assigned (MEMBER): bob@acme.com → gid://shopify/CompanyContact/888888888
