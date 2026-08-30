1. Safety for Database Connections & Credentials
🔐 1.1 Fernet Encryption at Rest
Zero Plaintext Storage: Target database credentials and connection URLs are never stored in plaintext in the platform database.
Strong Encryption: Encrypted using Fernet symmetric encryption (
app.core.security
) with keys derived via SHA-256.
Strict Decryption Boundary: Connection strings are only decrypted on-demand within
ConnectionManager
 at the exact moment a query is executed. Decrypted credentials are never returned in API responses or logged in application logs.
🏢 1.2 Multi-Tenant Isolation
Tenant Scoping: Every connection and chat session is strictly scoped by project_id and verified against the authenticated user's ID (current_user.id).
No Cross-Tenant Access: User A cannot view, test, or execute queries against User B's database connections.
🏊 1.3 Isolated Connection Pooling & Lifecycle Management
Dedicated Engine Pools:
ConnectionManager
 maintains isolated SQLAlchemy connection pools per project.
Automatic Resource Cleanup: When a connection is updated or deleted, the associated connection pool is immediately disposed of to prevent connection leaks.
2. Safety for SQL Execution & Guardrails
🛡️ 2.1 Deep AST (Abstract Syntax Tree) Read-Only Validation
Before any query reaches your database, it must pass through
app.domain.agent.sql_validator
:

Comment Sanitization: Strips SQL comments (--, /* */) to prevent hidden injection vectors.
Deep AST Parsing with sqlglot: Deconstructs the SQL query into an Abstract Syntax Tree.
Strict Whitelist: Only SELECT, WITH ... SELECT (CTEs), and set operations (UNION, INTERSECT, EXCEPT) are permitted.
Hard-Blocked Statements: Any mutation or administrative statement is immediately rejected before execution:
DML: INSERT, UPDATE, DELETE, MERGE
DDL: CREATE, DROP, ALTER, TRUNCATE
Permissions & Admin: GRANT, REVOKE, PRAGMA, EXEC, CALL, SET
Transaction Control: COMMIT, ROLLBACK, BEGIN
🚫 2.2 Semicolon Chaining & Multi-Statement Prevention
Disallows semicolon-separated query chaining (e.g. SELECT * FROM users; DROP TABLE orders;).
Ensures that exactly one read-only statement is parsed and executed per turn.
⏱️ 2.3 Query Execution Timeouts
All database executions are wrapped in an asynchronous timeout (asyncio.wait_for(..., timeout=30)).
Protects your database from runaway queries, expensive cartesian products, or hanging locks.
📊 2.4 Row Limits & Safe Type Serialization
Prevents memory exhaustion by capping query result sets (default 500 rows).
Safely serializes special database data types (Decimal, datetime, UUID, binary data) to JSON-compliant formats before returning to the agent or frontend.
🔁 2.5 Bounded Self-Correction Loop
If the LLM generates a query that fails database syntax/schema validation, it enters a self-correction loop capped at 3 retries max.
If the error persists after 3 attempts, the pipeline routes to
error_terminal_node
 with an explanation, preventing infinite loops or resource drain.


for additional safety
-in useers db create a user with read only access