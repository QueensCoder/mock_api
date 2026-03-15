# Architecture Decision Record

Decisions made for the backend infrastructure. Each section documents the options considered, their trade-offs, and the chosen approach with rationale.

---

## Table of Contents

1. [CDC & Sync Mechanism (Postgres → Redis Search)](#1-cdc--sync-mechanism-postgres--redis-search)
2. [Redis Search Engine](#2-redis-search-engine)
3. [Audit Logging (Postgres → Snowflake)](#3-audit-logging-postgres--snowflake)
4. [ETL vs CDC for Snowflake](#4-etl-vs-cdc-for-snowflake)
5. [Chosen Architecture](#5-chosen-architecture)
6. [Cost Comparison (AWS)](#6-cost-comparison-aws)
7. [Local Development](#7-local-development)

---

## 1. CDC & Sync Mechanism (Postgres → Redis Search)

How changes in Postgres get propagated to the Redis search index.

---

### Redpanda Connect ✅ Chosen

A single Go binary / Docker container with a declarative YAML pipeline. Reads Postgres WAL via a logical replication slot. Supports fan-out to multiple outputs (Redis + S3) from one pipeline.

**Pros**
- Single container, ~60MB image, fast startup
- Zero Postgres query load — reads WAL which is written anyway
- Fan-out to multiple destinations (Redis, S3, HTTP, etc.) in one YAML file
- At-least-once delivery — replication slot retains WAL if the consumer goes down
- No JVM, no Kafka required
- Open source, free — pay only for compute (~$5–10/month on AWS Fargate)
- One replication slot serves both Redis search and Snowflake audit pipelines
- YAML config — no application code changes needed to add new indexed tables
- Actively developed by Redpanda (production-grade, large community)

**Cons**
- Postgres requires `wal_level = logical` (config change + RDS reboot)
- Replication slot accumulates WAL if consumer lags — needs a CloudWatch alarm on `OldestReplicationSlotLag`
- Less community content than Debezium
- Postgres CDC input is newer than Debezium's connector
- No managed cloud offering — self-hosted only

---

### Debezium Server

Standalone JVM-based CDC tool. Industry standard. Reads WAL via logical replication.

**Pros**
- Most battle-tested CDC tool available
- Extensive documentation and community
- Supports every major database
- Strong connector ecosystem
- At-least-once delivery via replication slot

**Cons**
- Java/JVM dependency — 512MB minimum RAM, realistically 1GB+
- Heavy Docker footprint (~$30–40/month on Fargate vs ~$5–10 for Redpanda Connect)
- Complex connector configuration
- Designed around Kafka — Debezium Server avoids Kafka but feels like a workaround
- No native fan-out without Kafka
- Same `wal_level = logical` requirement and replication slot risk

---

### Full Debezium + Apache Kafka (MSK)

Debezium connector running inside Kafka Connect, with events flowing through Kafka topics.

**Pros**
- Exactly-once semantics with Kafka transactions
- True fan-out — multiple independent consumers from the same WAL stream
- Kafka retains events for replay indefinitely
- Industry standard at large scale
- Mature Snowflake Kafka connector available

**Cons**
- Kafka + Zookeeper + Kafka Connect + Debezium + your app = 6+ containers locally
- MSK costs $450–850/month minimum for a production HA cluster
- Significant operational overhead
- Complete overkill unless you already run Kafka or need multiple independent consumers at scale

---

### Python WAL Consumer (`psycopg3` logical replication)

A lightweight Python service that opens a logical replication connection directly to Postgres and processes `pgoutput` messages.

**Pros**
- No extra Docker containers — runs as part of the existing Python project
- Fits the existing stack perfectly (Python, same dependencies)
- Full control over consumer logic
- Same WAL-based guarantees as Debezium
- Cheapest possible compute — sidecar to the existing app

**Cons**
- You own all the code — LSN tracking, snapshot logic, reconnection, error handling, backfill
- Not a small amount of work to do reliably
- No community support — bespoke code
- No fan-out without building it yourself

---

### Application → Redis Streams → Celery

Service layer writes an event to a Redis Stream after the Postgres commit. Celery consumer group reads from the stream.

**Pros**
- Zero Postgres load — no WAL reading, no replication slot
- No Postgres config changes required
- Redis Streams are persistent — messages survive worker downtime
- Consumer groups give at-least-once delivery
- Reuses existing Celery and Redis infrastructure
- Simplest implementation

**Cons**
- Tiny but real drop window — if the process crashes between Postgres commit and the Redis `XADD` call, the event is permanently lost
- Misses out-of-band changes — direct DB edits, migrations, bulk imports never reach the index
- Application must always go through the service layer — bypassing it silently breaks the index
- No before/after values — you know a row changed, not what it looked like before

---

### SQLAlchemy Event Listeners → Celery (plain)

SQLAlchemy `after_flush` event fires in-process and dispatches a Celery task.

**Pros**
- Simple to implement
- Zero Postgres load
- No infrastructure changes

**Cons**
- Task dispatch can fail silently if Redis is down at dispatch time
- Process crash between commit and dispatch permanently drops the event
- No catch-up mechanism — drift between Postgres and Redis is silent and undetectable
- No before/after values
- Worst redundancy of all options considered

---

### Transactional Outbox

Write an outbox row to Postgres in the same transaction as the business record. Poll the outbox from a separate process and dispatch indexing tasks.

**Pros**
- Atomic — outbox row and business record commit together or not at all
- Survives process crashes and Redis downtime
- Built-in audit trail of pending/failed sync operations
- No dropped records

**Cons**
- Adds a write to every business operation — extra Postgres load
- Polling adds read load to Postgres
- More complex schema and logic
- Ruled out by the constraint of keeping Postgres load minimal

---

### Postgres LISTEN/NOTIFY

Application or trigger sends `NOTIFY`, a persistent listener receives it.

**Pros**
- Low implementation complexity
- Low Postgres overhead

**Cons**
- Messages are **permanently lost** if the consumer is not connected at the moment of `NOTIFY`
- No persistence, no replay
- Unacceptable redundancy for a search index
- Triggers add Postgres load (ruled out)

---

### Summary Table

| Option | DB Load | Redundancy | Docker Footprint | Complexity | Cost (AWS) |
|---|---|---|---|---|---|
| **Redpanda Connect** ✅ | Near zero | Excellent | ~60MB single container | Low (YAML) | ~$5–10/mo |
| Debezium Server | Near zero | Excellent | Heavy (JVM, 1GB+) | Medium | ~$30–40/mo |
| Debezium + Kafka (MSK) | Near zero | Best possible | Very heavy | High | ~$600–850/mo |
| Python WAL Consumer | Near zero | Excellent | None (part of app) | High (own code) | ~$0 extra |
| App → Redis Streams | Zero | Good | None | Low | ~$0 extra |
| SQLAlchemy Events | Zero | Poor | None | Very low | ~$0 extra |
| Transactional Outbox | Medium | Good | None | Medium | ~$0 extra |
| LISTEN/NOTIFY | Low | Poor | None | Low | ~$0 extra |

---

## 2. Redis Search Engine

### Redis Stack ✅ Chosen

Drop-in replacement for plain Redis. Superset that adds RediSearch, RedisJSON, and RedisTimeSeries. Fully Redis-compatible on port 6379.

**Pros**
- Full-text search with BM25 ranking
- Secondary indexing on any field — numeric ranges, tag filters, geo
- Aggregations and faceted search
- Sub-millisecond query latency
- Same port and client as plain Redis — no application changes to existing Redis usage
- RedisInsight UI bundled on port 8001 (local dev)
- No separate Elasticsearch/OpenSearch cluster needed
- Open source

**Cons**
- Larger Docker image than plain Redis
- Data is in-memory — index is rebuilt from Postgres if Redis is restarted (mitigated by the CDC pipeline)
- Not suited for analytics queries — use Snowflake for that
- Memory-bound — index size limited by available RAM
- Not a replacement for Elasticsearch at very large scale (tens of millions of documents)

### Plain Redis

**Pros** — Already running, zero extra cost.

**Cons** — No query capability beyond key lookup. Cannot do full-text search, range filters, or faceting without application-level workarounds.

### Elasticsearch / OpenSearch

**Pros** — Industry standard for full-text search. Massive scale. Rich query DSL.

**Cons** — Separate cluster to operate. High memory requirements. AWS OpenSearch starts at ~$50–100/month for the smallest HA cluster. Separate sync pipeline needed. Overkill for this use case.

---

## 3. Audit Logging (Postgres → Snowflake)

How every row-level change (insert, update, delete) is captured with before/after values and stored in Snowflake.

### Redpanda Connect → S3 → Snowpipe ✅ Chosen

The same Redpanda Connect pipeline used for Redis search adds S3 as a second output. Redpanda Connect batches events and writes JSON/Parquet files to S3. Snowpipe auto-ingests on file arrival.

**Pros**
- Reuses the existing Redpanda Connect pipeline and replication slot — no extra infrastructure
- Captures every operation including deletes with full before/after values
- Zero additional Postgres load
- S3 is extremely cheap for log storage
- Snowpipe latency is 1–3 minutes — appropriate for audit logs
- Snowpipe cost is ~$0.06 per 1000 files — essentially free at moderate volume
- Append-only Snowflake table — complete immutable history
- Locally: MinIO replaces S3, DuckDB queries the JSON files with Snowflake-compatible SQL

**Cons**
- Requires Snowflake account (no free local equivalent)
- Snowpipe latency (1–3 min) not suitable if you need real-time audit queries
- S3 bucket management and IAM required
- JSON file compaction needed over time (small files problem at high volume — mitigated with Snowpipe's auto-ingest and batching config)

---

## 4. ETL vs CDC for Snowflake

### Why ETL is wrong for audit logs

| Requirement | ETL (Fivetran, Airbyte) | CDC (Redpanda Connect) |
|---|---|---|
| Captures deletes | No — deleted rows are gone | Yes — delete operations recorded |
| Before/after values | No | Yes — full row state at each point |
| Multiple changes between polls | Collapsed to final state | Every intermediate state captured |
| Postgres load | Yes — polling queries | No — WAL reads only |
| Latency | 15 min – 1 hour | 1–3 minutes (Snowpipe) |

ETL is the right tool for syncing current state to a data warehouse. It is the wrong tool for audit logs where you need the complete history of every change.

---

### Fivetran

**Pros** — Fully managed, zero infrastructure, easy setup, hundreds of connectors.

**Cons** — $500–2000+/month depending on rows synced. Does not capture deletes. Collapses intermediate updates. Adds polling load to Postgres.

---

### Airbyte (self-hosted)

**Pros** — Open source. Free software cost. Large connector library. Postgres → Snowflake connector available.

**Cons** — Does not capture deletes. Collapses intermediate updates. Polling adds Postgres read load. Requires its own Docker infrastructure (~$30–50/month compute). CDC mode available but immature and still requires a replication slot — at that point just use Redpanda Connect.

---

### AWS Glue

**Pros** — Managed, serverless, integrates with AWS ecosystem.

**Cons** — Batch ETL only. Does not capture deletes. Adds Postgres load. Complex PySpark jobs. Expensive at $0.44/DPU-hour for continuous jobs.

---

### Snowpipe Streaming (direct API)

**Pros** — Sub-second latency directly into Snowflake. No S3 staging.

**Cons** — Higher cost than standard Snowpipe. Requires Snowflake SDK integration in the pipeline. Unnecessary for audit logs where minutes of latency is acceptable.

---

### ETL Summary Table

| Option | Captures Deletes | Before/After Values | DB Load | Monthly Cost | Right for Audit? |
|---|---|---|---|---|---|
| **Redpanda Connect → S3 → Snowpipe** ✅ | Yes | Yes | None | ~$5–15 | Yes |
| Fivetran | Partial | No | Yes (polling) | $500–2000+ | No |
| Airbyte self-hosted | No | No | Yes (polling) | ~$30–50 | No |
| AWS Glue | No | No | Yes (polling) | Variable | No |
| Snowpipe Streaming | Yes | Yes | None | Higher | Overkill |

---

## 5. Chosen Architecture

```
Postgres Primary (source of truth)
        │ WAL / logical replication slot (wal_level = logical)
        │ Reads WAL that is already written — near-zero CPU overhead
        ├──► Redpanda Connect  ◄── single Go container, YAML pipeline
        │         │
        │         ├──► Redis Streams
        │         │         │
        │         │         ▼
        │         │    Celery Worker ──► Redis Stack (search index)
        │         │
        │         └──► S3 / MinIO (batched JSON)
        │                   │
        │                   ▼ Snowpipe auto-ingest
        │              Snowflake audit_log table (append-only)
        │
        └──► Read Replica (dedicated infra — analytics, app reads)
                  No replication slot here. This replica is untouched.
```

**Why the slot lives on the primary, not the read replica**

The existing read replica is dedicated infrastructure with its own query workload and SLAs. Adding a logical replication slot to it would create contention and violate that contract.

The primary is the right source for CDC:
- WAL is already generated there — Redpanda Connect reads bytes that exist regardless
- CPU impact is near-zero: WAL streaming bypasses the query engine entirely
- This is the standard approach — it is what Debezium and Redpanda Connect docs default to

**The one real risk: WAL accumulation if the consumer lags.** Fully mitigated (see Section 7).

**Why this works**
- One replication slot on the primary, one consumer, two destinations
- Redis search and Snowflake audit are fully decoupled from the application
- Read replica is completely untouched — no slot, no extra load
- Adding a new table to the pipeline is a YAML config change — no application code
- Locally: MinIO replaces S3, DuckDB replaces Snowflake for query validation
- Fails independently — Redis being down does not affect Snowflake ingestion and vice versa

**When to add a dedicated CDC replica instead**

Only if the primary is consistently above 70% CPU utilization, or WAL rate exceeds 50 MB/s. At that point a `db.r6g.large` replica (~$175/month) isolates all CDC risk from production traffic.

---

## 6. Cost Comparison (AWS)

| Component | Our Stack | Debezium + MSK | Fivetran + Debezium |
|---|---|---|---|
| CDC / stream processor | ~$5–10/mo (Redpanda Connect) | ~$600–850/mo (MSK) | ~$30–40/mo (Debezium Server) |
| Audit log ingestion | ~$0–5/mo (Snowpipe) | ~$0–5/mo (Snowpipe) | $500–2000+/mo (Fivetran) |
| Redis Stack | ~$15–30/mo (ElastiCache or self-hosted) | Same | Same |
| **Total (streaming infra)** | **~$20–45/mo** | **~$620–890/mo** | **~$530–2040/mo** |
| *(Optional) dedicated CDC replica* | *+~$175/mo if primary > 70% CPU* | Same | Same |

Postgres RDS with `wal_level = logical`: set on the **primary's** parameter group. Requires a reboot. The read replica's parameter group is not changed.

---

## 7. Local Development

| Component | Local Docker | Production |
|---|---|---|
| Postgres | `postgres:16-alpine` | RDS PostgreSQL primary (replication slot here) |
| Read Replica | Not used for CDC | RDS Read Replica — dedicated infra, untouched by CDC |
| Redis Stack | `redis/redis-stack:latest` | ElastiCache + Redis Stack or self-hosted |
| Redpanda Connect | `ghcr.io/redpandadata/connect` | ECS Fargate |
| S3 staging | MinIO (already running) | AWS S3 |
| Snowpipe | Write JSON to local files | Snowpipe auto-ingest from S3 |
| Snowflake | DuckDB (queries same JSON, same SQL dialect) | Snowflake |

**Required Postgres config for CDC**

Apply to the **primary's parameter group**. The read replica's parameter group is not changed.

```sql
-- Primary RDS parameter group
wal_level = logical
```

Requires a primary reboot (schedule during a maintenance window). No changes to the read replica.

**Replication slot health**

Monitor `OldestReplicationSlotLag` in CloudWatch. Alert if it exceeds a threshold (e.g. 1GB). If Redpanda Connect is down for an extended period, Postgres will accumulate WAL to preserve it for the slot.
