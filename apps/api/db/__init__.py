"""Persistence layer for apps/api.

`base` holds the declarative base and session plumbing; `models` holds the
SQLAlchemy mapping of every entity in docs/database/database-design.md.

Why the ORM lives here and not in packages/schemas: that package is the
typed *contract* layer every module builds against, and its own docstring
says ORM mapping, migrations, and persistence logic are out of scope for it.
It is also a shared path needing cross-owner sign-off, whereas apps/api is
owned outright by Developer 3/Kamogelo. The two stay connected by importing
the enums from packages/schemas rather than redeclaring them (see models.py).
"""
