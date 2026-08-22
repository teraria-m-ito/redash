import click
from flask.cli import AppGroup
from sqlalchemy import inspect

manager = AppGroup(help="Insights management commands.")


@manager.command(name="create_table")
def create_table():
    """Create the insights table if it does not exist."""
    from redash.models import Insight, db

    engine = db.get_engine()
    table_name = Insight.__tablename__

    if table_name in inspect(engine).get_table_names():
        click.echo("Table '{}' already exists.".format(table_name))
        return

    Insight.__table__.create(bind=engine)
    click.echo("Created table '{}'.".format(table_name))
