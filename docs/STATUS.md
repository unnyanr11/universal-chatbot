# Feature ledger and completion checklist

| Capability | Status | Evidence / remaining work |
|---|---|---|
| Initial schema/migration | Implemented for SQLite; PostgreSQL unverified | Repeatable migration exercised in tests |
| Login, expiry, hashed sessions, logout | Implemented | Database integration tests |
| Login budget | Implemented, limited | Atomic database counter; global 20 attempts/minute, not production abuse prevention |
| Tenant isolation | Implemented for existing project/assistant routes | Cross-organisation access and membership removal tests |
| Projects/environments | Partial | Seeded development projects; no project management or environment promotion |
| Roles | Partial | Read/write policies enforced; invitations/custom roles/member UI pending |
| Assistant creation | Partial | Validated draft creation only; no publish/rollback/editing |
| Local inference adapter | Partial | Transport contract tested; real Ollama unavailable |
| Hardware diagnostic | Implemented | RAM/disk/tool availability; GPU not measured |
| Synthetic businesses | Implemented | Explicit development-only seed; no automatic credentials |
| Compose/PostgreSQL | Unverified | Docker absent in build environment |
| React admin/widget/SDK/mobile | Planned | Phase 1 and 4 |
| Knowledge/embeddings/RAG/deletion | Planned | Phase 1; no invented citation or answer metrics |
| Ingestion worker | Planned | Phase 1; no empty worker scaffolding |
| Booking/action execution/reminders | Planned | Phase 2; no simulated success |
| Connectors/tickets | Planned | Phase 3; external providers require configuration |
| Human inbox/memory/privacy exports | Planned | No claim of implemented user deletion/export |
| Workflows/audit/analytics | Planned | Phase 5 |
| Voice/cloud inference/Flutter | Optional, unimplemented | Phase 6 |
| Evaluation/benchmarks | Planned | No accuracy/throughput claims |

Phase 0 remains incomplete until PostgreSQL and real inference paths are tested and foundation guardrails/admin operations are finished. No later phase is complete.
