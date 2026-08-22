import click
from flask.cli import AppGroup
from sqlalchemy import inspect

manager = AppGroup(help="Insights management commands.")


@manager.command(name="create_table")
def create_table():
    """Create insight_definitions / insights tables if they do not exist."""
    from redash.models import Insight, InsightDefinition, db

    engine = db.get_engine()
    existing = set(inspect(engine).get_table_names())

    for model in (InsightDefinition, Insight):
        table_name = model.__tablename__
        if table_name in existing:
            click.echo("Table '{}' already exists.".format(table_name))
            continue
        model.__table__.create(bind=engine)
        click.echo("Created table '{}'.".format(table_name))
        existing.add(table_name)
