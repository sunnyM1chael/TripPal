# Existing HMDP System Findings

These findings define integration risks and a future Java backlog. They were confirmed before this Python platform phase. No Java changes are included in the current scope, and this document does not attempt a wider Java audit.

## Integration risks

- The configured Spring Boot service was not running during verification, so live response examples and the actual database's travel-data coverage remain unverified.
- Java APIs may return HTTP 200 while the body contains `success=false`. Python must inspect the body envelope rather than treating every 2xx response as success.
- The current authorization header value is opaque. Python must forward it unchanged and must not assume or add a `Bearer` prefix.
- The Java response envelope contains `success`, `errorMsg`, `data`, and `total`. These fields are transport details and must terminate in the Python integration layer.
- Existing Blog, Like, and Follow capabilities do not establish complete review, favorite, or travel-profile capabilities. Python must not infer those semantics.
- Real data coverage for travel use cases has not been verified. Platform tests must not depend on a running Java service or assumed city data.

## Existing system issues

- The nearby-shop flow currently accepts coordinates but clears them before executing the query, so it falls back to ordinary category pagination.
- The user-detail endpoint uses an ID with ambiguous semantics: registration creates separate user and user-info IDs, while the endpoint queries user info by its primary key.
- The authentication exclusion covers `/shop/**`, which includes shop write operations as well as public reads. The effective write-security boundary needs review before an agent receives write capability.

## Future Java backlog

- Restore and verify GEO behavior, including data initialization, coordinate conventions, distance units, pagination, and empty results.
- Correct and document user versus user-info identifier semantics.
- Separate public shop reads from protected shop writes and define service-to-service identity.
- Publish stable API contracts with pagination, error, and authentication semantics.
- Verify actual data coverage before designing any product-specific travel integration.
- Add product-specific APIs only after concrete product requirements are agreed.

These items are intentionally deferred. The current Python skeleton provides only the integration infrastructure required to accommodate their future resolution.

