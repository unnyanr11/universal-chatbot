# Local connector contracts

`GET /v1/projects/{project_id}/tools` returns the allowlisted local registry with versions, input/output JSON Schema, read/write classification, scope, confirmation, timeout, retry and idempotency metadata. The project/user context is always derived from the authenticated request.

`POST /v1/projects/{project_id}/tool-calls` accepts a name and arguments:

```json
{"name":"get_available_slots","arguments":{"service_id":"<scoped-service-id>"}}
```

Write calls require a stable idempotency key and return a proposed operation, never an implicitly executed write:

```json
{"name":"create_appointment","arguments":{"slot_id":"<scoped-slot-id>"},"idempotency_key":"host-operation-unique-key"}
```

Inspect the returned exact preview and ask the authenticated user to confirm. Only then call `POST /v1/projects/{project_id}/operations/{id}/confirm`. After a timeout, GET the same operation or retry confirmation with the same ID; do not create a fresh write as a blind retry.

For write sandboxing, set `dry_run:true`. The response is explicitly `execution:dry-run` / `state:simulated`; it creates no operation, appointment or external update. Reads still come from the real service. Schema-invalid arguments, cross-tenant IDs, unknown handlers and unconfigured email fail explicitly.

To add a local connector, implement a server-owned handler and strict Pydantic input/output models, add its reviewed contract to `registry.py`, reuse the request's tenant/user policy boundary, and add real database/policy/contract tests. Do not allow request/model-supplied SQL, Python, shell, browser scripts, arbitrary URLs or credentials. Preserve approval, timeout, idempotency and unknown-outcome semantics for any write.

Generic HTTP/OpenAPI imports, OAuth refresh tokens, external webhooks and MCP servers are not enabled. They require a reviewed transport with SSRF/DNS/redirect protections, encrypted credentials, provider signature/replay controls and reconciliation tests before adding it to this registry. `send_email` deliberately reports unavailable rather than silently simulating delivery. Merely adding credentials will not implement an absent adapter.
