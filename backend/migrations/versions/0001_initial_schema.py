from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db_pg.models import Base
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from app.db_pg.models import Base
    Base.metadata.drop_all(bind=op.get_bind())
