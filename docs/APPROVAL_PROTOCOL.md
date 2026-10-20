# ORIGIN Cryptographic Human Approval Protocol (`docs/APPROVAL_PROTOCOL.md`)

**Milestone:** `04/05 — Verified Autonomous Recovery, Agent Orchestration & Operational Safety`  
**Endpoint:** `POST /api/v1/recovery/plans/{plan_id}/approve`  
**Module:** [`backend/app/modules/recovery/service.py`](file:///E:/Projects/ORIGIN/backend/app/modules/recovery/service.py)

---

## 1. Zero Implicit Authorizations

ORIGIN strictly rejects automatic execution of simulated or candidate plans. Real laboratory execution **must** be explicitly authorized by an authenticated human operator presenting valid credentials and role designations.

Attempting to execute an unapproved plan returns `HTTP 403 Forbidden`. Attempting to approve a plan that has not completed real isolated sandbox verification returns `HTTP 422 Unprocessable Content`.

---

## 2. Cryptographic Plan Hash (`compute_recovery_plan_hash`)

The plan hash binds the complete canonical representation of the recovery action:

$$\text{plan\_hash} = \text{SHA-256}\Big(\text{canonical\_json}\big(\text{plan\_id}, \text{plan\_version}, \text{target\_env}, \text{candidate\_id}, \text{action\_type}, \text{service}, \text{parameters}\big)\Big)$$

If an operator or automated agent mutates any parameter (`PATCH /api/v1/recovery/plans/{plan_id}`), the server:
1. Increments `plan_version`.
2. Recomputes `plan_hash`.
3. Revokes all active approvals (`decision = "REVOKED"`).
4. Reverts status to `AWAITING_APPROVAL`.

Executing with a token bound to an earlier version or hash fails with:
`HTTP 403: Execution denied: recovery plan was mutated after approval (plan_hash or plan_version mismatch).`

---

## 3. Single-Use Token Nonce & Replay Prevention

When approval is granted:
1. The server generates a cryptographically random token: `origin-appr-<secrets.token_urlsafe(24)>`.
2. The server hashes the token using `SHA-256` and persists `approval_token_hash` in `recovery_approvals`.
3. The raw token is returned **once** in the HTTP response to the caller.
4. When `POST /api/v1/recovery/plans/{plan_id}/execute` is called, the supplied token is hashed and compared using `secrets.compare_digest`.
5. Upon consumption, `approval.token_used = True` is committed. Subsequent calls with the same token return `HTTP 403 Forbidden (replay rejected)`.

---

## 4. Time-to-Live (TTL) Expiration

Approvals include an explicit `expires_at` timestamp (default $900$ seconds / 15 minutes). If execution is attempted after expiration, the `SafetyGovernor` rejects the request with `HTTP 403: Execution denied: human approval has expired`.
