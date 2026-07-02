from langchain_core.tools import tool

_PRODUCT_INFO = {
    "capella": """
## Couchbase Capella (DBaaS)
Fully managed cloud database-as-a-service. No ops burden — Couchbase handles provisioning, patching, backups, and scaling.

**Key offerings:**
- **Capella Operational**: Multi-model NoSQL (document, key-value, full-text search, eventing, analytics) on AWS, GCP, Azure
- **Capella Columnar**: Real-time analytical store with SQL++ — zero-ETL from operational clusters via streaming
- **Capella App Services**: Managed Sync Gateway + mobile backend; handles sync, auth, delta sync for Couchbase Lite clients
- **Capella AI Services**: Vector Search + embedding pipelines for AI/RAG use cases

**Pricing model**: Based on compute credits and data throughput. Free tier available.
**SLA**: 99.99% uptime SLA on Enterprise plan.
**Security**: SOC 2 Type II, ISO 27001, HIPAA-eligible, PCI-DSS ready; private endpoints, VPC peering, CMEK.
""",
    "server": """
## Couchbase Server (Self-Managed)
Enterprise-grade NoSQL database deployable on-prem, VMs, containers (Kubernetes via Couchbase Autonomous Operator).

**Editions:**
- **Enterprise**: Full feature set, production support, XDCR, encryption at rest, auditing, LDAP
- **Community**: Free, open-source, limited features (no XDCR encryption, no backup tools, no advanced security)

**Services per node** (services are independently scalable):
- Data service (KV store)
- Query service (N1QL/SQL++)
- Index service (GSI)
- Search service (FTS + Vector)
- Analytics service (columnar OLAP)
- Eventing service
- Backup service

**Deployment**: Bare metal, VMs, Docker, Kubernetes (CAO), Helm charts available.
""",
    "mobile": """
## Couchbase Mobile
Edge-to-cloud sync stack for offline-first mobile and edge applications.

**Components:**
- **Couchbase Lite**: Embedded NoSQL database for iOS, Android, React Native, Flutter, .NET, Java
  - Full CRUD + query (SQL++ subset), binary attachments (blobs)
  - Works fully offline; syncs when connectivity restored
- **Sync Gateway**: Middleware server that bridges Couchbase Lite ↔ Capella/Server
  - Handles authentication, authorization, conflict resolution, delta sync
  - WebSocket-based continuous replication
  - REST API for server-side document access

**Use cases**: Field service apps, point-of-sale, healthcare at the bedside, IoT edge, logistics.
""",
    "analytics": """
## Couchbase Analytics (Columnar)
Zero-ETL OLAP engine that runs analytical SQL++ queries against live operational data.

**Two modes:**
1. **Integrated Analytics** (on Couchbase Server): Shadow dataset mirrors operational data; analytics queries don't impact KV/query service
2. **Capella Columnar**: Dedicated analytical cluster fed by continuous streaming from operational Capella clusters or external sources (Kafka, S3)

**Key capabilities:**
- SQL++ (superset of SQL) with JSON path expressions
- Window functions, UNNEST for array flattening, lateral joins
- External datasets: query S3, Kafka topics directly
- Approximate query processing for very large datasets
- Connect to BI tools via JDBC/ODBC
""",
}

_FEATURE_DETAILS = {
    "kv": """
## Key-Value (KV) Operations
The lowest-latency access path — sub-millisecond P99 at scale.

**Operations**: get, insert, upsert, replace, remove, getAndTouch (renew TTL), getAndLock (pessimistic locking)
**Sub-document API**: Read or mutate nested JSON fields without fetching the full document — reduces network I/O by up to 90%
**Expiry (TTL)**: Per-document TTL for cache-style workloads
**Durability**: Configurable majority/majority-and-persist-active/persist-to-majority

**Python SDK example:**
```python
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions, GetOptions, UpsertOptions
from datetime import timedelta

cluster = Cluster("couchbases://cb.example.cloud.couchbase.com",
                  ClusterOptions(PasswordAuthenticator("user", "password")))
cluster.wait_until_ready(timedelta(seconds=5))

bucket = cluster.bucket("travel-sample")
collection = bucket.scope("inventory").collection("airline")

# Basic upsert
collection.upsert("airline_10", {"type": "airline", "name": "Delta", "country": "US"})

# Get with TTL touch
result = collection.get_and_touch("airline_10", timedelta(seconds=3600))
doc = result.content_as[dict]

# Sub-document mutation (update only one field)
from couchbase.subdocument import upsert as sd_upsert
collection.mutate_in("airline_10", [sd_upsert("name", "Delta Air Lines")])
```
""",
    "n1ql": """
## N1QL / SQL++ Query Language
A superset of SQL that works natively on JSON documents. No schema required — query any JSON shape.

**Key features:**
- Standard SQL: SELECT, JOIN, GROUP BY, HAVING, ORDER BY, LIMIT/OFFSET
- JSON extensions: UNNEST arrays into rows, USE KEYS for KV-backed joins, nested path expressions (`address.city`)
- DML: INSERT, UPDATE, UPSERT, DELETE, MERGE
- Subqueries, correlated subqueries, CTEs (WITH clause)
- ARRAY and OBJECT comprehensions
- EXPLAIN plan, covering indexes, adaptive indexes

**Index types:**
- Global Secondary Index (GSI) — most common, asynchronous
- Primary index (full scan, dev only)
- Partial index (WHERE clause filter)
- Array index (index elements inside arrays)

**Python SDK example:**
```python
from couchbase.options import QueryOptions

result = cluster.query(
    "SELECT a.name, a.country FROM `travel-sample`.inventory.airline a WHERE a.country = $country",
    QueryOptions(named_parameters={"country": "US"})
)
for row in result:
    print(row)
```
""",
    "fts": """
## Full-Text Search (FTS) + Vector Search
Integrated search engine — no Elasticsearch needed.

**Text search capabilities:**
- Fuzzy matching, stemming, stop words, language-aware analyzers (50+ languages)
- Phrase search, wildcard, regexp, date range, numeric range
- Facets, highlighting, sorting by score or field value
- Geo-spatial queries (point-in-radius, bounding box)

**Vector Search (Couchbase 7.6+ / Capella):**
- Store float32 or int8 vector embeddings directly in documents
- HNSW index for ANN search
- Hybrid search: combine vector similarity with keyword filters in one query
- Use case: RAG pipelines, semantic search, recommendation engines

**Python SDK example (FTS):**
```python
from couchbase.search import SearchQuery, MatchQuery, SearchOptions

result = cluster.search_query(
    "travel-search-index",
    SearchQuery.match("luxury hotel", field="description"),
    SearchOptions(limit=10, highlight=True)
)
for hit in result.rows():
    print(hit.id, hit.score)
```

**Python SDK example (Vector Search):**
```python
from couchbase.vector_search import VectorQuery, VectorSearch

vector = [0.12, 0.34, ...]  # embedding from your model

result = cluster.search(
    "my-vector-index",
    VectorSearch.from_vector_query(VectorQuery("embedding_field", vector, num_candidates=3)),
)
```
""",
    "eventing": """
## Eventing Service
Serverless functions that trigger on document mutations — like database triggers but far more powerful.

**Trigger types:**
- OnUpdate: fires on insert or update
- OnDelete: fires on delete
- Timer: scheduled execution

**Capabilities:**
- Access any Couchbase bucket/collection (read, write, delete) from function code
- Call external HTTP endpoints (curl) for webhooks, enrichment, notifications
- JavaScript runtime with Couchbase-specific built-ins
- Lifecycle management: deploy/undeploy without restart, resume from checkpoint

**Use cases**: Denormalization, data enrichment, notifications, audit trails, cascading deletes, ETL to other systems.

**Example handler:**
```javascript
function OnUpdate(doc, meta) {
    if (doc.type === "order" && doc.status === "placed") {
        var notification = {"orderId": meta.id, "customer": doc.customerId};
        curl("POST", "https://notifications.internal/order", {body: notification});
    }
}
```
""",
    "xdcr": """
## Cross Datacenter Replication (XDCR)
Active-active or active-passive replication across Couchbase clusters in different regions or cloud providers.

**Modes:**
- **Unidirectional**: source → target (DR, reporting replica)
- **Bidirectional / Active-Active**: both clusters accept writes; conflict resolution via timestamp or custom policy

**Use cases:**
- Geo-distributed applications (route users to nearest cluster)
- Disaster recovery with near-zero RPO
- Blue/green cluster upgrades
- Multi-cloud or hybrid-cloud data distribution

**Conflict resolution strategies:**
- Last-write-wins (sequence number or timestamp)
- Custom conflict resolution via Eventing

**Advanced XDCR:**
- Filter replicated documents by expression
- Pause/resume replication
- Monitor lag and throughput in UI or REST API
""",
    "transactions": """
## ACID Transactions
Multi-document, multi-collection, multi-bucket ACID transactions (Couchbase 7.0+).

**Properties:**
- Atomicity: all operations commit or all roll back
- Consistency: respects document constraints
- Isolation: Read Committed isolation by default; optional Serializable
- Durability: configurable majority/persist durability

**Python SDK example:**
```python
from couchbase.transactions import TransactionOptions
from couchbase.durability import DurabilityLevel

def transfer(ctx):
    src = ctx.get(collection, "account:alice")
    dst = ctx.get(collection, "account:bob")
    amount = 100

    ctx.replace(src, {**src.content_as[dict], "balance": src.content_as[dict]["balance"] - amount})
    ctx.replace(dst, {**dst.content_as[dict], "balance": dst.content_as[dict]["balance"] + amount})

cluster.transactions.run(transfer)
```
""",
    "security": """
## Security & Compliance
Enterprise-grade security controls built in.

**Authentication:**
- Local users, LDAP/Active Directory integration, SAML SSO (Capella)
- Certificate-based (mTLS) for node-to-node and client-to-cluster

**Authorization:**
- Role-Based Access Control (RBAC): 50+ built-in roles, custom roles
- Scope/collection-level granularity in Couchbase 7.x+

**Encryption:**
- TLS 1.2/1.3 in transit (enforced by default in Capella)
- Encryption at rest: AES-256 (Enterprise; Capella always on)
- Customer-Managed Encryption Keys (CMEK) on Capella

**Compliance certifications (Capella):**
- SOC 2 Type II, ISO 27001, HIPAA-eligible, PCI-DSS, FedRAMP (in progress)

**Auditing:** Log all data access and admin operations to immutable audit log.
""",
    "sdk": """
## Couchbase SDKs
Official SDKs for all major languages, all built on the same libcouchbase C core.

**Supported languages:**
- Python (`pip install couchbase`) — async support via asyncio
- Java / Kotlin (Spring Data Couchbase integration available)
- Node.js / TypeScript
- .NET / C#
- Go
- PHP
- Scala
- C / C++ (libcouchbase directly)
- Ruby

**Python SDK quick-start:**
```python
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions
from datetime import timedelta

cluster = Cluster(
    "couchbases://your-capella-endpoint.cloud.couchbase.com",
    ClusterOptions(PasswordAuthenticator("username", "password"))
)
cluster.wait_until_ready(timedelta(seconds=10))

bucket = cluster.bucket("your-bucket")
collection = bucket.default_collection()

# KV
collection.upsert("key1", {"hello": "world"})
doc = collection.get("key1").content_as[dict]

# SQL++
for row in cluster.query("SELECT * FROM `your-bucket` LIMIT 10"):
    print(row)
```

**Connection string formats:**
- Capella: `couchbases://cb.<id>.cloud.couchbase.com`  (TLS required)
- Server: `couchbase://localhost` or `couchbases://host` for TLS
""",
    "data_model": """
## Couchbase Data Model
Hierarchical namespace: Cluster → Bucket → Scope → Collection → Document

**Hierarchy:**
- **Cluster**: one logical Couchbase deployment (or Capella database)
- **Bucket**: top-level namespace; up to 30 per cluster; unit of replication & persistence settings
- **Scope**: logical grouping within a bucket (like a schema); up to 1000 per bucket
- **Collection**: like a table, but schema-free JSON; up to 1000 per scope
- **Document**: JSON object, max 20 MB; identified by a string key

**Key design guidelines:**
- Use type field (e.g. `"type": "user"`) to distinguish document kinds within a collection
- Collections are the preferred isolation boundary (replace old type-per-bucket anti-pattern)
- Embed related data when accessed together; reference (by key) when data diverges
- Use sub-document API to avoid over-fetching large documents

**Example document (user profile):**
```json
{
  "type": "user",
  "id": "user::abc123",
  "email": "alice@example.com",
  "profile": {
    "name": "Alice",
    "preferences": {"theme": "dark", "notifications": true}
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```
""",
    "performance": """
## Performance & Scalability
Couchbase is designed for high throughput and low latency at scale.

**Benchmark baselines (reference):**
- KV read/write: sub-millisecond P99 at millions of ops/sec
- SQL++ queries: depend on index coverage; covered index queries <5ms typical
- FTS queries: <10ms P99 for typical full-text queries

**Scaling model:**
- Horizontal scale-out by adding nodes (not sharding by hand)
- Each service scales independently — add query nodes without adding KV nodes
- Auto-sharding via vBuckets (1024 vBuckets per bucket)
- Rebalance is online; no downtime during node addition/removal

**Caching:**
- All data served from RAM (Couchbase is memory-first)
- Ejection policies: valueOnly (default) or fullEviction
- Size buckets to fit working set in RAM for best latency

**Connection pooling:**
- The SDK maintains persistent connections; one `Cluster` instance per process
- Built-in retry logic with configurable retry strategies
""",
}

_SDK_EXAMPLES = {
    "python_connect": """
## Python SDK: Connect to Couchbase Capella
```python
import os
from couchbase.cluster import Cluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions
from datetime import timedelta

# Use environment variables for credentials
endpoint = os.environ["CB_ENDPOINT"]   # e.g. cb.xxxxx.cloud.couchbase.com
username = os.environ["CB_USERNAME"]
password = os.environ["CB_PASSWORD"]
bucket_name = os.environ["CB_BUCKET"]

cluster = Cluster(
    f"couchbases://{endpoint}",
    ClusterOptions(PasswordAuthenticator(username, password))
)
cluster.wait_until_ready(timedelta(seconds=10))
bucket = cluster.bucket(bucket_name)
collection = bucket.default_collection()
print("Connected to Couchbase Capella!")
```
""",
    "python_crud": """
## Python SDK: Full CRUD Example
```python
from couchbase.exceptions import DocumentNotFoundException

# CREATE / UPSERT
collection.upsert("product::001", {
    "type": "product",
    "name": "Widget Pro",
    "price": 29.99,
    "inventory": 500
})

# READ
try:
    result = collection.get("product::001")
    product = result.content_as[dict]
    print(f"Found: {product['name']}")
except DocumentNotFoundException:
    print("Document not found")

# UPDATE via sub-document (efficient partial update)
from couchbase.subdocument import upsert as sd_upsert, increment
collection.mutate_in("product::001", [
    sd_upsert("price", 24.99),
    increment("inventory", -1)
])

# DELETE
collection.remove("product::001")
```
""",
    "python_query": """
## Python SDK: SQL++ Queries
```python
from couchbase.options import QueryOptions

# Parameterized query (always use params, never string interpolation)
result = cluster.query(
    '''SELECT p.name, p.price, p.inventory
       FROM `my-bucket`.`shop`.`products` p
       WHERE p.price < $max_price AND p.inventory > 0
       ORDER BY p.price ASC
       LIMIT $limit''',
    QueryOptions(named_parameters={"max_price": 50.0, "limit": 20})
)

rows = list(result)
print(f"Found {len(rows)} products")
for row in rows:
    print(f"  {row['name']}: ${row['price']}")
```
""",
    "python_fts": """
## Python SDK: Full-Text Search
```python
from couchbase.search import SearchQuery, MatchPhraseQuery, TermRangeQuery, BooleanQuery, SearchOptions
from couchbase.options import SearchOptions

# Simple match
result = cluster.search_query(
    "products-search-index",
    SearchQuery.match("organic coffee beans"),
    SearchOptions(limit=10, fields=["name", "description"])
)

for hit in result.rows():
    print(f"Score {hit.score:.3f}: {hit.id}")
    print(f"  Fields: {hit.fields}")

# Boolean compound query
bool_query = BooleanQuery(
    must=[SearchQuery.match_phrase("machine learning", field="content")],
    must_not=[SearchQuery.term("deprecated", field="tags")],
    should=[SearchQuery.term("python", field="tags")]
)
result = cluster.search_query("docs-index", bool_query, SearchOptions(limit=5))
```
""",
    "python_transactions": """
## Python SDK: ACID Transactions
```python
from couchbase.transactions import TransactionOptions

def transfer_funds(ctx):
    sender_key = "account::alice"
    receiver_key = "account::bob"
    amount = 500.00

    sender_doc = ctx.get(collection, sender_key)
    receiver_doc = ctx.get(collection, receiver_key)

    sender = sender_doc.content_as[dict]
    receiver = receiver_doc.content_as[dict]

    if sender["balance"] < amount:
        ctx.rollback()
        return

    sender["balance"] -= amount
    receiver["balance"] += amount

    ctx.replace(sender_doc, sender)
    ctx.replace(receiver_doc, receiver)
    # commit is automatic when function returns without error

try:
    cluster.transactions.run(transfer_funds)
    print("Transfer complete")
except Exception as e:
    print(f"Transaction failed: {e}")
```
""",
    "python_async": """
## Python SDK: Async / asyncio
```python
import asyncio
from acouchbase.cluster import AsyncCluster
from couchbase.auth import PasswordAuthenticator
from couchbase.options import ClusterOptions
from datetime import timedelta

async def main():
    cluster = AsyncCluster(
        "couchbases://cb.example.cloud.couchbase.com",
        ClusterOptions(PasswordAuthenticator("user", "password"))
    )
    await cluster.wait_until_ready(timedelta(seconds=10))
    collection = cluster.bucket("my-bucket").default_collection()

    # Concurrent upserts
    await asyncio.gather(*[
        collection.upsert(f"doc::{i}", {"value": i})
        for i in range(100)
    ])

    result = await cluster.query("SELECT COUNT(*) as total FROM `my-bucket`")
    async for row in result:
        print(f"Total docs: {row['total']}")

asyncio.run(main())
```
""",
}

_DISCOVERY_CATEGORIES = {
    "data_model": [
        "How is your data currently structured? Is it relational (tables/rows) or hierarchical (documents/objects)?",
        "Do you have variable schemas or entities with optional fields that differ per record?",
        "What are the typical document sizes and how do you handle large objects or binary attachments?",
        "Do you need to model many-to-many relationships, and if so, how do you currently handle them?",
        "How often does your schema evolve, and what is the cost of schema migrations today?",
    ],
    "scale": [
        "What are your current data volumes (GB/TB) and expected growth over the next 2-3 years?",
        "What are your peak read and write throughput requirements (operations per second)?",
        "Do different parts of your workload have different scaling needs (e.g., read-heavy vs write-heavy)?",
        "How do you handle traffic spikes today, and what is the lead time to scale your current database?",
        "Do you need to scale storage and compute independently?",
    ],
    "latency": [
        "What are your P99 latency requirements for read and write operations?",
        "Are there specific API endpoints or user flows where latency is business-critical?",
        "Do you use caching (Redis, Memcached) today, and what are you caching? Why not serve from the primary DB?",
        "What percentage of your reads are for single known keys vs. complex queries?",
        "Do you have SLAs with end customers that include database response time?",
    ],
    "consistency": [
        "Does your application require strong consistency (read-your-own-writes) or can it tolerate eventual consistency?",
        "Are there critical financial or inventory operations that require ACID transactions across multiple records?",
        "How do you currently handle concurrent updates to the same record?",
        "What is the business impact of serving a slightly stale read in your most sensitive workflows?",
        "Do you need linearizable reads, or is causal consistency sufficient?",
    ],
    "availability": [
        "What is your target uptime (99.9%? 99.99%?) and what are the business consequences of downtime?",
        "Do you need active-active multi-region deployments for disaster recovery or geo-distribution?",
        "What is your current RTO (recovery time objective) and RPO (recovery point objective) for DR scenarios?",
        "Have you experienced unplanned database outages in the past year? What caused them?",
        "Do you need zero-downtime deployments and rolling upgrades?",
    ],
    "geo_distribution": [
        "Do you have users or data processing needs in multiple geographic regions?",
        "Do you need data residency or sovereignty compliance (data must stay in a specific country)?",
        "Do you route users to a nearest region for latency, and does the database follow that pattern?",
        "How do you currently synchronize data between regions?",
        "Can users in one region update data that users in another region also write to?",
    ],
    "search": [
        "Do you need full-text search capabilities? If so, do you run a separate Elasticsearch/Solr cluster?",
        "What search features do you need: fuzzy matching, facets, highlighting, geo-search, language analyzers?",
        "Are you building any AI/ML features that require vector similarity search or semantic search?",
        "How much operational overhead does managing a separate search cluster create for your team?",
        "Do your search queries need to join with transactional data in real time?",
    ],
    "mobile_edge": [
        "Do you have a mobile app or edge/IoT component that needs to work offline?",
        "How do you currently sync data between mobile/edge clients and your backend?",
        "What is the volume of mobile clients (devices) that need to sync simultaneously?",
        "How do you handle conflict resolution when the same record is modified offline by multiple clients?",
        "What is the network reliability profile of your mobile/edge deployments?",
    ],
    "analytics": [
        "Do you run analytical queries (aggregations, trends, reporting) against your operational database?",
        "Do those analytical queries impact production read performance today?",
        "What BI tools or dashboards do your business users rely on?",
        "How much latency is acceptable for analytical queries (real-time <1s, near-real-time <60s, batch)?",
        "Do you have a separate data warehouse (Snowflake, Redshift)? What is the ETL lag?",
    ],
    "operations": [
        "What is the size of your DBA/ops team, and how much time do they spend on database administration?",
        "Do you prefer managed cloud (DBaaS) or self-managed deployments? What drives that preference?",
        "What monitoring and alerting tools do you use today, and what metrics do you track for database health?",
        "How do you handle database upgrades today — is downtime required?",
        "What is your backup and restore strategy, and when did you last test a restore?",
    ],
    "security_compliance": [
        "What compliance frameworks must you adhere to (SOC 2, HIPAA, PCI-DSS, GDPR, FedRAMP)?",
        "Do you need encryption at rest and in transit, and who manages encryption keys?",
        "How do you manage database access control — individual credentials, LDAP/AD, SSO?",
        "Do you need audit logging of all data access and administrative operations?",
        "Are there data masking or field-level security requirements for PII?",
    ],
    "migration": [
        "What database are you migrating from, and what is the primary motivation for moving?",
        "What are the most painful aspects of your current database (cost, ops burden, performance, missing features)?",
        "Do you have a target cutover date or hard deadline?",
        "What is your tolerance for application code changes during migration?",
        "Do you need a parallel-run / shadow-write phase to validate correctness before full cutover?",
    ],
}


@tool
def get_couchbase_product_info(product: str) -> str:
    """Get detailed information about a Couchbase product or service.

    Args:
        product: One of: capella, server, mobile, analytics
    """
    key = product.lower().strip()
    return _PRODUCT_INFO.get(key, f"Unknown product '{product}'. Available: {', '.join(_PRODUCT_INFO.keys())}")


@tool
def get_couchbase_feature_details(feature: str) -> str:
    """Get technical details and Python SDK examples for a specific Couchbase feature.

    Args:
        feature: One of: kv, n1ql, fts, eventing, xdcr, transactions, security, sdk, data_model, performance
    """
    key = feature.lower().strip().replace(" ", "_").replace("-", "_")
    return _FEATURE_DETAILS.get(key, f"Unknown feature '{feature}'. Available: {', '.join(_FEATURE_DETAILS.keys())}")


@tool
def get_sdk_example(example_type: str) -> str:
    """Get a ready-to-use Python SDK code example for a common Couchbase operation.

    Args:
        example_type: One of: python_connect, python_crud, python_query, python_fts,
                      python_transactions, python_async
    """
    key = example_type.lower().strip().replace(" ", "_").replace("-", "_")
    return _SDK_EXAMPLES.get(key, f"Unknown example '{example_type}'. Available: {', '.join(_SDK_EXAMPLES.keys())}")


@tool
def get_discovery_questions(category: str) -> str:
    """Get a set of technical discovery questions for a given topic area to ask a prospect.

    Args:
        category: One of: data_model, scale, latency, consistency, availability,
                  geo_distribution, search, mobile_edge, analytics, operations,
                  security_compliance, migration
    """
    key = category.lower().strip().replace(" ", "_").replace("-", "_")
    questions = _DISCOVERY_CATEGORIES.get(key)
    if not questions:
        return f"Unknown category '{category}'. Available: {', '.join(_DISCOVERY_CATEGORIES.keys())}"
    return f"## Discovery Questions — {category.replace('_', ' ').title()}\n\n" + "\n".join(
        f"{i + 1}. {q}" for i, q in enumerate(questions)
    )


couchbase_tools = [
    get_couchbase_product_info,
    get_couchbase_feature_details,
    get_sdk_example,
    get_discovery_questions,
]
