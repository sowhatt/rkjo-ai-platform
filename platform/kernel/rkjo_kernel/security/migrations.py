"""Explicit additive migration; never runs during request handling."""
from hashlib import sha256
from pathlib import Path


def apply_authority_migrations(connection):
    name = '001_principal_authority.sql'
    content = (Path(__file__).parent / 'migrations' / name).read_bytes()
    checksum = sha256(content).hexdigest()
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(current_database() || ':' || current_schema() || ':security-migration',0))")
        connection.execute('''CREATE TABLE IF NOT EXISTS security_schema_migrations (
            name TEXT PRIMARY KEY, sha256 TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        history = dict(connection.execute('SELECT name,sha256 FROM security_schema_migrations').fetchall())
        if history and history != {name: checksum}:
            raise ValueError('Unknown or changed security migration.')
        if history:
            return ()
        connection.execute(content.decode())
        connection.execute('INSERT INTO security_schema_migrations(name,sha256) VALUES (%s,%s)', (name, checksum))
    return (name,)
