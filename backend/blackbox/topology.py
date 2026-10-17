"""The acme service topology, hand-authored.

Hand-authored rather than random because the demo depends on specific graph
shapes being true:
  * affected_services of checkout-api must reach exactly 11 dependents, 3 of them
    customer-facing;
  * the cheapest DEPENDS_ON path checkout-api -> ledger-service must run
    through payments-api (criticality-weighted, not merely hop count);
  * there must be chains 5+ hops deep, or affected services is not interesting.
"""

# name: (tier, revenue_critical, customer_facing, language, description)
SERVICES = {
    "edge-gateway":       (1, True,  False, "go",     "North-south edge router and TLS termination"),
    "web-bff":            (1, True,  True,  "ts",     "Backend-for-frontend for the web storefront"),
    "mobile-bff":         (1, True,  True,  "ts",     "Backend-for-frontend for iOS and Android"),
    "partner-api":        (1, True,  True,  "go",     "Public partner REST API and webhooks"),
    "admin-console":      (1, False, False, "ts",     "Internal operator console"),
    "status-page":        (1, False, False, "ts",     "Public status and uptime page"),
    "health-aggregator":  (2, False, False, "go",     "Rolls up service health probes"),
    "order-orchestrator": (2, True,  False, "java",   "Saga orchestration for order placement"),
    "checkout-api":       (2, True,  False, "ts",     "Checkout session and payment intent handling"),
    "cart-service":       (2, False, False, "ts",     "Cart persistence and pricing preview"),
    "catalog-api":        (2, False, False, "java",   "Product catalog reads"),
    "search-api":         (2, False, False, "go",     "Product search and faceting"),
    "recommendation-api": (3, False, False, "python", "Related-products model serving"),
    "loyalty-service":    (3, False, False, "java",   "Points accrual and redemption"),
    "receipts-service":   (3, False, False, "ts",     "Receipt generation and archival"),
    "fraud-screen":       (2, True,  False, "python", "Realtime fraud scoring on checkout"),
    "email-dispatch":     (3, False, False, "ts",     "Transactional email delivery"),
    "webhook-relay":      (3, False, False, "go",     "Outbound webhook fan-out with retries"),
    "analytics-ingest":   (3, False, False, "go",     "Clickstream and order event ingestion"),
    "notifications-api":  (2, False, False, "ts",     "Notification preferences and fan-out"),
    "push-gateway":       (3, False, False, "go",     "APNs and FCM push delivery"),
    "template-renderer":  (3, False, False, "ts",     "Handlebars template rendering service"),
    "user-profile":       (2, False, False, "java",   "User profile and preferences"),
    "auth-service":       (1, True,  False, "go",     "OIDC token issuance and introspection"),
    "session-store":      (3, False, False, "go",     "Session state with TTL eviction"),
    "permissions-api":    (2, False, False, "java",   "RBAC policy evaluation"),
    "billing-api":        (2, True,  False, "java",   "Subscription and invoice orchestration"),
    "payments-api":       (2, True,  False, "java",   "Payment authorization and capture"),
    "ledger-service":     (2, True,  False, "ts",     "Double-entry ledger, source of financial truth"),
    "invoice-service":    (3, False, False, "java",   "Invoice PDF generation"),
    "tax-engine":         (3, False, False, "python", "Jurisdictional tax calculation"),
    "currency-oracle":    (3, False, False, "go",     "FX rate cache and conversion"),
    "settlement-worker":  (3, False, False, "java",   "Nightly settlement batch"),
    "reconciliation-job": (3, False, False, "python", "Ledger-to-bank reconciliation"),
    "inventory-service":  (2, False, False, "java",   "Stock levels and reservations"),
    "shipping-api":       (3, False, False, "go",     "Carrier rates and label purchase"),
    "pricing-engine":     (2, False, False, "python", "Dynamic price and promotion resolution"),
    "feature-flags":      (3, False, False, "go",     "Flag evaluation at the edge"),
    "postgres-primary":   (3, True,  False, "sql",    "Primary OLTP Postgres cluster"),
    "redis-cache":        (3, False, False, "c",      "Shared Redis cache and rate limiter"),
    "kafka-bus":          (3, False, False, "scala",  "Event backbone"),
    "object-store":       (3, False, False, "c",      "S3-compatible blob storage"),
}

# consumer -> [(provider, criticality 1-5, protocol)]
# criticality 5 == a hard synchronous dependency on the revenue path.
DEPENDS_ON = {
    "edge-gateway":       [("web-bff", 5, "http"), ("mobile-bff", 5, "http"),
                           ("partner-api", 4, "http"), ("admin-console", 2, "http"),
                           ("status-page", 1, "http")],
    "web-bff":            [("order-orchestrator", 5, "grpc"), ("cart-service", 4, "http"),
                           ("catalog-api", 3, "http"), ("search-api", 2, "http"),
                           ("recommendation-api", 1, "http"), ("auth-service", 5, "grpc")],
    "mobile-bff":         [("order-orchestrator", 5, "grpc"), ("cart-service", 4, "http"),
                           ("catalog-api", 3, "http"), ("auth-service", 5, "grpc"),
                           ("notifications-api", 2, "http")],
    "partner-api":        [("order-orchestrator", 4, "grpc"), ("loyalty-service", 2, "http"),
                           ("auth-service", 5, "grpc")],
    "admin-console":      [("order-orchestrator", 2, "grpc"), ("permissions-api", 4, "grpc"),
                           ("auth-service", 4, "grpc")],
    "status-page":        [("health-aggregator", 3, "http")],
    "health-aggregator":  [("notifications-api", 2, "http")],
    "order-orchestrator": [("checkout-api", 5, "grpc"), ("inventory-service", 4, "grpc"),
                           ("shipping-api", 2, "http")],
    "checkout-api":       [("payments-api", 5, "grpc"), ("inventory-service", 4, "grpc"),
                           ("pricing-engine", 3, "http"), ("fraud-screen", 3, "grpc"),
                           ("user-profile", 2, "http"), ("auth-service", 4, "grpc"),
                           ("feature-flags", 1, "http")],
    "cart-service":       [("checkout-api", 3, "http"), ("catalog-api", 3, "http"),
                           ("redis-cache", 4, "resp")],
    "catalog-api":        [("postgres-primary", 5, "pg"), ("redis-cache", 3, "resp")],
    "search-api":         [("catalog-api", 3, "http"), ("redis-cache", 2, "resp")],
    "recommendation-api": [("search-api", 2, "http"), ("catalog-api", 2, "http")],
    "loyalty-service":    [("checkout-api", 2, "http"), ("postgres-primary", 4, "pg")],
    "receipts-service":   [("checkout-api", 2, "http"), ("object-store", 3, "s3"),
                           ("template-renderer", 3, "http")],
    "fraud-screen":       [("ledger-service", 2, "grpc"), ("redis-cache", 4, "resp")],
    "email-dispatch":     [("receipts-service", 2, "http"), ("template-renderer", 3, "http")],
    "webhook-relay":      [("notifications-api", 3, "http"), ("kafka-bus", 4, "kafka")],
    "analytics-ingest":   [("checkout-api", 1, "kafka"), ("kafka-bus", 4, "kafka")],
    "notifications-api":  [("push-gateway", 3, "grpc"), ("template-renderer", 3, "http"),
                           ("redis-cache", 4, "resp"), ("postgres-primary", 4, "pg")],
    "push-gateway":       [("template-renderer", 2, "http"), ("object-store", 2, "s3")],
    "template-renderer":  [("object-store", 2, "s3")],
    "user-profile":       [("postgres-primary", 4, "pg"), ("redis-cache", 3, "resp"),
                           ("session-store", 3, "resp")],
    "auth-service":       [("session-store", 5, "resp"), ("permissions-api", 3, "grpc"),
                           ("postgres-primary", 4, "pg")],
    "session-store":      [("redis-cache", 5, "resp")],
    "permissions-api":    [("postgres-primary", 4, "pg")],
    "billing-api":        [("invoice-service", 3, "grpc"), ("tax-engine", 3, "http"),
                           ("ledger-service", 5, "grpc")],
    "payments-api":       [("ledger-service", 5, "grpc"), ("billing-api", 4, "grpc"),
                           ("currency-oracle", 2, "http"), ("fraud-screen", 3, "grpc")],
    "ledger-service":     [("postgres-primary", 5, "pg"), ("redis-cache", 3, "resp"),
                           ("kafka-bus", 3, "kafka")],
    "invoice-service":    [("template-renderer", 3, "http"), ("object-store", 3, "s3")],
    "tax-engine":         [("currency-oracle", 3, "http")],
    "currency-oracle":    [("redis-cache", 3, "resp")],
    "settlement-worker":  [("ledger-service", 5, "grpc"), ("kafka-bus", 3, "kafka")],
    "reconciliation-job": [("settlement-worker", 3, "grpc"), ("postgres-primary", 4, "pg")],
    "inventory-service":  [("postgres-primary", 5, "pg"), ("kafka-bus", 3, "kafka")],
    "shipping-api":       [("inventory-service", 3, "grpc"), ("postgres-primary", 3, "pg")],
    "pricing-engine":     [("catalog-api", 3, "http"), ("currency-oracle", 3, "http"),
                           ("feature-flags", 2, "http")],
    "feature-flags":      [("redis-cache", 4, "resp")],
}

TEAMS = {
    "Payments Platform": ["payments-api", "ledger-service", "billing-api", "invoice-service",
                          "tax-engine", "currency-oracle", "settlement-worker",
                          "reconciliation-job"],
    "Storefront":        ["web-bff", "mobile-bff", "checkout-api", "cart-service", "catalog-api",
                          "search-api", "recommendation-api", "pricing-engine",
                          "order-orchestrator"],
    "Identity":          ["auth-service", "session-store", "permissions-api", "user-profile",
                          "fraud-screen"],
    "Infrastructure":    ["edge-gateway", "postgres-primary", "redis-cache", "kafka-bus",
                          "object-store", "feature-flags", "health-aggregator", "status-page",
                          "admin-console", "inventory-service", "shipping-api"],
    "Growth":            ["notifications-api", "push-gateway", "template-renderer",
                          "email-dispatch", "webhook-relay", "analytics-ingest",
                          "loyalty-service", "receipts-service", "partner-api"],
}

# name, handle, role, timezone, team, on_call
PEOPLE = [
    ("Priya Raghavan",  "priya",   "Staff Engineer",      "Asia/Kolkata",      "Payments Platform", False),
    ("Marcus Webb",     "mwebb",   "SRE",                 "America/Denver",    "Infrastructure",    True),
    ("Dana Okonkwo",    "dana",    "Engineering Manager", "Europe/London",     "Payments Platform", False),
    ("Tomas Lindqvist", "tomas",   "Senior Engineer",     "Europe/Stockholm",  "Payments Platform", False),
    ("Aisha Bello",     "aisha",   "Senior Engineer",     "Africa/Lagos",      "Storefront",        False),
    ("Ben Ortiz",       "bortiz",  "Engineer",            "America/Chicago",   "Storefront",        False),
    ("Chen Wei",        "chenwei", "Staff Engineer",      "Asia/Shanghai",     "Storefront",        False),
    ("Sofia Marchetti", "sofia",   "Engineer",            "Europe/Rome",       "Storefront",        False),
    ("Liam Doyle",      "liam",    "Senior SRE",          "Europe/Dublin",     "Infrastructure",    False),
    ("Noor Haddad",     "noor",    "Staff Engineer",      "Asia/Dubai",        "Infrastructure",    False),
    ("Yusuf Demir",     "yusuf",   "Engineer",            "Europe/Istanbul",   "Infrastructure",    False),
    ("Grace Mbeki",     "grace",   "Senior Engineer",     "Africa/Nairobi",    "Identity",          False),
    ("Hugo Silva",      "hugo",    "Engineer",            "America/Sao_Paulo", "Identity",          False),
    ("Ingrid Vos",      "ingrid",  "Staff Engineer",      "Europe/Amsterdam",  "Identity",          False),
    ("Jae-won Park",    "jaewon",  "Senior Engineer",     "Asia/Seoul",        "Growth",            False),
    ("Kofi Mensah",     "kofi",    "Engineer",            "Africa/Accra",      "Growth",            False),
    ("Lena Fischer",    "lena",    "Engineering Manager", "Europe/Berlin",     "Growth",            False),
    ("Mei Tanaka",      "mei",     "Senior Engineer",     "Asia/Tokyo",        "Growth",            False),
]

# Files the scenarios depend on. Everything else is generated per service.
KEY_FILES = {
    "ledger-service":    ["src/db/connection-pool.ts", "src/ledger/post-entry.ts",
                          "src/ledger/balance.ts"],
    "notifications-api": ["src/db/pool.ts", "src/fanout/dispatch.ts"],
    "checkout-api":      ["src/session/create.ts", "src/payment/intent.ts", "src/http/retry.ts"],
    "payments-api":      ["src/client/LedgerClient.java", "src/auth/capture.java"],
}

GENERIC_FILES = ["src/http/server", "src/config/env", "src/metrics/emit", "src/db/migrate",
                 "src/lib/retry", "src/handlers/health"]

EXT = {"ts": ".ts", "go": ".go", "java": ".java", "python": ".py", "scala": ".scala",
       "c": ".c", "sql": ".sql"}


# ---------------------------------------------------------------- globex tenant
# A deliberately different company on the same FalkorDB instance, in a
# separate graph. Different domain, different names -- so that flipping the
# tenant switch in the UI is visibly, obviously a different world.
GLOBEX_SERVICES = {
    "freight-portal":   (1, True,  True,  "ts",     "Shipper-facing booking portal"),
    "driver-app-api":   (1, True,  True,  "go",     "Mobile API for contract drivers"),
    "tms-core":         (2, True,  False, "java",   "Transport management core"),
    "route-planner":    (2, True,  False, "python", "Multi-stop route optimization"),
    "dispatch-engine":  (2, True,  False, "java",   "Load-to-driver assignment"),
    "telematics-ingest": (2, False, False, "go",    "Vehicle telemetry ingestion"),
    "eta-predictor":    (3, False, False, "python", "Arrival time model serving"),
    "customs-broker":   (3, False, False, "java",   "Cross-border documentation"),
    "rate-engine":      (2, True,  False, "python", "Freight rate quoting"),
    "fuel-cards":       (3, False, False, "go",     "Fuel card authorization"),
    "yard-manager":     (3, False, False, "ts",     "Yard and dock scheduling"),
    "warehouse-wms":    (2, False, False, "java",   "Warehouse management"),
    "invoice-ledger":   (2, True,  False, "ts",     "Freight billing ledger"),
    "cockroach-primary": (3, True, False, "sql",    "Primary distributed SQL store"),
    "nats-bus":         (3, False, False, "go",     "Message bus"),
    "blob-vault":       (3, False, False, "c",      "Document storage"),
}

GLOBEX_DEPENDS_ON = {
    "freight-portal":    [("tms-core", 5, "grpc"), ("rate-engine", 4, "http"),
                          ("invoice-ledger", 3, "grpc")],
    "driver-app-api":    [("dispatch-engine", 5, "grpc"), ("fuel-cards", 2, "http"),
                          ("telematics-ingest", 3, "http")],
    "tms-core":          [("route-planner", 4, "grpc"), ("dispatch-engine", 5, "grpc"),
                          ("warehouse-wms", 3, "grpc"), ("cockroach-primary", 5, "sql")],
    "route-planner":     [("eta-predictor", 3, "http"), ("cockroach-primary", 4, "sql")],
    "dispatch-engine":   [("yard-manager", 2, "http"), ("nats-bus", 4, "nats"),
                          ("cockroach-primary", 5, "sql")],
    "telematics-ingest": [("nats-bus", 4, "nats")],
    "eta-predictor":     [("telematics-ingest", 3, "http")],
    "customs-broker":    [("blob-vault", 3, "s3"), ("cockroach-primary", 3, "sql")],
    "rate-engine":       [("invoice-ledger", 4, "grpc"), ("cockroach-primary", 4, "sql")],
    "fuel-cards":        [("invoice-ledger", 3, "grpc")],
    "yard-manager":      [("warehouse-wms", 3, "grpc")],
    "warehouse-wms":     [("cockroach-primary", 4, "sql"), ("nats-bus", 3, "nats")],
    "invoice-ledger":    [("cockroach-primary", 5, "sql"), ("blob-vault", 2, "s3")],
}

GLOBEX_TEAMS = {
    "Freight Platform": ["tms-core", "dispatch-engine", "route-planner", "eta-predictor"],
    "Driver Experience": ["driver-app-api", "fuel-cards", "telematics-ingest"],
    "Revenue": ["invoice-ledger", "rate-engine", "customs-broker"],
    "Warehouse": ["warehouse-wms", "yard-manager"],
    "Core Infra": ["cockroach-primary", "nats-bus", "blob-vault", "freight-portal"],
}

GLOBEX_PEOPLE = [
    ("Oksana Petrenko", "oksana", "Staff Engineer",      "Europe/Kyiv",      "Freight Platform", False),
    ("Raul Jimenez",    "raul",   "SRE",                 "America/Mexico_City", "Core Infra",    True),
    ("Fatima Nasser",   "fatima", "Senior Engineer",     "Asia/Riyadh",      "Revenue",          False),
    ("Daniel Kim",      "dkim",   "Engineer",            "America/Los_Angeles", "Driver Experience", False),
    ("Anja Novak",      "anja",   "Engineering Manager", "Europe/Ljubljana", "Warehouse",        False),
    ("Thabo Nkosi",     "thabo",  "Senior Engineer",     "Africa/Johannesburg", "Freight Platform", False),
    ("Elena Rossi",     "elena",  "Staff Engineer",      "Europe/Rome",      "Revenue",          False),
    ("Hiroshi Sato",    "hiroshi", "Engineer",           "Asia/Tokyo",       "Core Infra",       False),
]
