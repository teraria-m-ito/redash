import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from sys import exit
from urllib.parse import urlparse

import click
from flask.cli import AppGroup
from sqlalchemy.orm.exc import NoResultFound

from redash import models, settings
from redash.query_runner import get_configuration_schema_for_query_runner_type
from redash.utils.configuration import ConfigurationContainer

manager = AppGroup(help="Sample database management commands.")


class SampleDb:
    ZIP_NAME = "dvdrental.zip"
    TAR_NAME = "dvdrental.tar"
    DB_NAME = "dvdrental"
    DATA_SOURCE_NAME = "DVD Rental"
    DATA_SOURCE_TYPE = "pg"
    DEFAULT_WORKDIR = "/tmp/redash-sample-db"
    # PostgreSQL Tutorial DVD Rental sample (同梱)
    PACKAGE_DIR = Path(__file__).resolve().parent / "sample_data"


def _bundled_zip_path():
    return SampleDb.PACKAGE_DIR / SampleDb.ZIP_NAME


def _pg_defaults_from_settings():
    parsed = urlparse(settings.SQLALCHEMY_DATABASE_URI)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
    }


def _env_with_pgpassword(password):
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    else:
        env.pop("PGPASSWORD", None)
    return env


def _require_binaries(*commands):
    missing = [name for name in commands if shutil.which(name) is None]
    if missing:
        click.echo(
            "Error: required command(s) not found: {}. "
            "Install postgresql-client (e.g. apt-get install -y postgresql-client).".format(", ".join(missing))
        )
        exit(1)


def _resolve_pg_connection(host, port, user, password):
    defaults = _pg_defaults_from_settings()
    return {
        "host": host or defaults["host"],
        "port": port or defaults["port"],
        "user": user or defaults["user"],
        "password": defaults["password"] if password is None else password,
    }


def _run_psql(sql, host, port, user, password, database="postgres"):
    cmd = [
        "psql",
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        database,
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]
    result = subprocess.run(cmd, env=_env_with_pgpassword(password), capture_output=True, text=True)
    if result.returncode != 0:
        click.echo(result.stderr or result.stdout)
        exit(1)
    return result.stdout


def _database_exists(host, port, user, password, db_name):
    out = _run_psql(
        "SELECT 1 FROM pg_database WHERE datname = '{}'".format(db_name.replace("'", "''")),
        host,
        port,
        user,
        password,
    )
    return "1" in out


def _table_count(host, port, user, password, db_name):
    out = _run_psql(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'",
        host,
        port,
        user,
        password,
        database=db_name,
    )
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return 0


def _drop_database(host, port, user, password, db_name):
    if not _database_exists(host, port, user, password, db_name):
        click.echo("Database '{}' does not exist; skip drop.".format(db_name))
        return

    click.echo("Dropping database '{}' ...".format(db_name))
    _run_psql(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{}' AND pid <> pg_backend_pid()".format(
            db_name.replace("'", "''")
        ),
        host,
        port,
        user,
        password,
    )
    _run_psql('DROP DATABASE "{}"'.format(db_name), host, port, user, password)


def _remove_workdir(workdir):
    path = Path(workdir)
    if path.exists():
        shutil.rmtree(path)
        click.echo("Removed temporary directory {}.".format(path))


def _extract_bundled_archive(workdir):
    zip_path = _bundled_zip_path()
    if not zip_path.exists():
        click.echo("Error: bundled sample archive not found: {}".format(zip_path))
        exit(1)

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    tar_path = workdir / SampleDb.TAR_NAME

    click.echo("Using bundled archive {}".format(zip_path))
    click.echo("Extracting to {} ...".format(workdir))
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(workdir)
    if not tar_path.exists():
        click.echo("Error: {} not found after unzip.".format(SampleDb.TAR_NAME))
        exit(1)
    return tar_path


def _restore_database(tar_path, host, port, user, password, db_name, force):
    exists = _database_exists(host, port, user, password, db_name)
    if exists and force:
        _drop_database(host, port, user, password, db_name)
        exists = False

    if not exists:
        click.echo("Creating database '{}' ...".format(db_name))
        _run_psql('CREATE DATABASE "{}"'.format(db_name), host, port, user, password)
    elif _table_count(host, port, user, password, db_name) > 0:
        click.echo("Database '{}' already has tables; skip restore (use --force to recreate).".format(db_name))
        return

    click.echo("Restoring {} into '{}' ...".format(tar_path, db_name))
    cmd = [
        "pg_restore",
        "-h",
        host,
        "-p",
        str(port),
        "-U",
        user,
        "-d",
        db_name,
        "--no-owner",
        "--no-privileges",
        str(tar_path),
    ]
    result = subprocess.run(cmd, env=_env_with_pgpassword(password), capture_output=True, text=True)
    # pg_restore は警告でも非0を返すことがあるため、テーブル有無で成否を判定する
    tables = _table_count(host, port, user, password, db_name)
    if tables == 0:
        click.echo(result.stderr or result.stdout or "pg_restore failed.")
        exit(1)
    if result.returncode != 0 and result.stderr:
        click.echo(result.stderr.strip())
    click.echo("Restored {} public tables.".format(tables))


def _register_data_source(org_slug, name, host, port, user, password, db_name):
    org = models.Organization.get_by_slug(org_slug)
    existing = models.DataSource.query.filter(models.DataSource.name == name, models.DataSource.org == org).first()
    if existing:
        click.echo("Data source '{}' already exists (id={}).".format(name, existing.id))
        return existing

    schema = get_configuration_schema_for_query_runner_type(SampleDb.DATA_SOURCE_TYPE)
    options = ConfigurationContainer(
        {
            "host": host,
            "port": int(port),
            "user": user,
            "password": password or "",
            "dbname": db_name,
            "sslmode": "prefer",
        },
        schema,
    )
    if not options.is_valid():
        click.echo("Error: invalid data source configuration.")
        exit(1)

    data_source = models.DataSource.create_with_group(
        name=name,
        type=SampleDb.DATA_SOURCE_TYPE,
        options=options,
        org=org,
    )
    models.db.session.commit()
    click.echo("Created data source '{}' (id={}).".format(name, data_source.id))
    return data_source


def _delete_data_source(org_slug, name):
    org = models.Organization.get_by_slug(org_slug)
    data_source = models.DataSource.query.filter(models.DataSource.name == name, models.DataSource.org == org).first()
    if not data_source:
        click.echo("Data source '{}' not found; skip delete.".format(name))
        return False

    click.echo("Deleting data source '{}' (id={}) ...".format(name, data_source.id))
    data_source.delete()
    click.echo("Deleted data source '{}'.".format(name))
    return True


@manager.command(name="install")
@click.option("--org", "organization", default="default", help="Organization slug.")
@click.option("--name", "ds_name", default=SampleDb.DATA_SOURCE_NAME, help="Redash data source name.")
@click.option("--db-name", default=SampleDb.DB_NAME, help="PostgreSQL database name.")
@click.option("--host", default=None, help="PostgreSQL host (default: from REDASH_DATABASE_URL).")
@click.option("--port", default=None, type=int, help="PostgreSQL port (default: from REDASH_DATABASE_URL).")
@click.option("--user", default=None, help="PostgreSQL user (default: from REDASH_DATABASE_URL).")
@click.option("--password", default=None, help="PostgreSQL password (default: from REDASH_DATABASE_URL).")
@click.option("--workdir", default=SampleDb.DEFAULT_WORKDIR, help="Temporary extract directory.")
@click.option("--force", is_flag=True, help="Drop and recreate the sample database.")
@click.option("--skip-datasource", is_flag=True, help="Only load PostgreSQL; do not create Redash data source.")
def install(
    organization,
    ds_name,
    db_name,
    host,
    port,
    user,
    password,
    workdir,
    force,
    skip_datasource,
):
    """Restore bundled DVD Rental sample DB and register a Redash data source."""
    _require_binaries("psql", "pg_restore")
    pg = _resolve_pg_connection(host, port, user, password)

    click.echo("PostgreSQL target: {}@{}/{} (db={})".format(pg["user"], pg["host"], pg["port"], db_name))
    tar_path = _extract_bundled_archive(workdir)
    _restore_database(tar_path, pg["host"], pg["port"], pg["user"], pg["password"], db_name, force)

    if skip_datasource:
        click.echo("Skipped Redash data source registration.")
        return

    try:
        models.Organization.get_by_slug(organization)
    except NoResultFound:
        click.echo("Error: organization '{}' not found.".format(organization))
        exit(1)

    _register_data_source(organization, ds_name, pg["host"], pg["port"], pg["user"], pg["password"], db_name)
    click.echo("Done.")


@manager.command(name="uninstall")
@click.option("--org", "organization", default="default", help="Organization slug.")
@click.option("--name", "ds_name", default=SampleDb.DATA_SOURCE_NAME, help="Redash data source name.")
@click.option("--db-name", default=SampleDb.DB_NAME, help="PostgreSQL database name.")
@click.option("--host", default=None, help="PostgreSQL host (default: from REDASH_DATABASE_URL).")
@click.option("--port", default=None, type=int, help="PostgreSQL port (default: from REDASH_DATABASE_URL).")
@click.option("--user", default=None, help="PostgreSQL user (default: from REDASH_DATABASE_URL).")
@click.option("--password", default=None, help="PostgreSQL password (default: from REDASH_DATABASE_URL).")
@click.option("--workdir", default=SampleDb.DEFAULT_WORKDIR, help="Temporary extract directory to remove.")
@click.option("--skip-datasource", is_flag=True, help="Only drop PostgreSQL database.")
@click.option("--skip-database", is_flag=True, help="Only delete Redash data source.")
@click.option("--keep-workdir", is_flag=True, help="Do not remove temporary extract directory.")
def uninstall(
    organization,
    ds_name,
    db_name,
    host,
    port,
    user,
    password,
    workdir,
    skip_datasource,
    skip_database,
    keep_workdir,
):
    """Remove bundled DVD Rental sample DB and its Redash data source."""
    if skip_datasource and skip_database:
        click.echo("Error: specify at least one of datasource or database removal.")
        exit(1)

    pg = _resolve_pg_connection(host, port, user, password)
    click.echo("PostgreSQL target: {}@{}/{} (db={})".format(pg["user"], pg["host"], pg["port"], db_name))

    if not skip_datasource:
        try:
            models.Organization.get_by_slug(organization)
        except NoResultFound:
            click.echo("Error: organization '{}' not found.".format(organization))
            exit(1)
        _delete_data_source(organization, ds_name)

    if not skip_database:
        _require_binaries("psql")
        _drop_database(pg["host"], pg["port"], pg["user"], pg["password"], db_name)

    if not keep_workdir:
        _remove_workdir(workdir)

    click.echo("Done.")
