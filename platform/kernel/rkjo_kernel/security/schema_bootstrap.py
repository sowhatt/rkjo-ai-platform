"""Explicit migration command; never invoked implicitly by an API request."""
import psycopg
from .configuration import authority_from_env
from .migrations import apply_authority_migrations


def main():
    authority = authority_from_env()
    if authority is None:
        raise RuntimeError("Select distributed security profile before migration.")
    with psycopg.connect(authority.database_url) as connection:
        apply_authority_migrations(connection)


if __name__ == "__main__":
    main()
