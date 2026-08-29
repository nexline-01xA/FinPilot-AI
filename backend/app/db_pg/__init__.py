"""
SQLAlchemy/PostgreSQL port of finpilot/core/schema.sql -- the Phase 3
target model. NOT wired into the running application (app.main still uses
the tested sqlite3 core via app.services). Written as a faithful 1:1
translation, UNVERIFIED: SQLAlchemy is not installed in the environment
this was built in, so these models have never been imported, instantiated,
or run against a real Postgres instance. See docs/VERIFICATION_MATRIX.md
before trusting this layer.
"""
