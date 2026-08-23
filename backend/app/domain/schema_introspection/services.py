"""
SchemaIntrospection domain — stubs for repository, service, and router.

Phase 1 responsibilities:
- Reflect tables/columns/PKs/FKs from target DB via SQLAlchemy `inspect()`.
- Cache result as JSON in `SchemaCache` (platform DB), keyed by connection_id + project_id.
- Invalidate cache on re-introspect request.
"""
# TODO: implement in Phase 1
