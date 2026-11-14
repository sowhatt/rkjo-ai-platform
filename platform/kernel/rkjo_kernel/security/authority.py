"""PostgreSQL authority for explicitly composed distributed runtimes.

Adapted from S1 ada39d0: only user/API grants belong to L2.
Local provisioning never overrides a canonical deny.
There is no positive cache. A shared admission lock spans the complete operation,
including business commits and local provider HTTP. An exclusive administrative
lock makes successful revocation wait for admitted operations to finish. Locks
are schema/database scoped; session-affine connections are required.

Administration is a trusted operator interface, never an HTTP/payload interface.
Unknown grants fail closed. CAS prevents lost updates and accidental reactivation.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
import json
from uuid import uuid4

import psycopg


class AuthorityDenied(PermissionError):
    pass


class AuthorityUnavailable(RuntimeError):
    pass


class AuthorityConflict(RuntimeError):
    pass


def fingerprint(value):
    def convert(item):
        if isinstance(item, (set, frozenset)):
            return sorted(item)
        raise TypeError('Unsupported authority value.')
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             default=convert, allow_nan=False).encode()).hexdigest()


def user_claim(tenant, user):
    return tenant, 'user', fingerprint(user), fingerprint('active-user')


def api_claim(tenant, user, role):
    return tenant, 'api', fingerprint(user), fingerprint(role)


_trace = ContextVar('security_authority_trace', default=None)
_active = ContextVar('security_authority_operation', default=None)
_LOCK = "hashtextextended(current_database() || ':' || current_schema() || ':security-authority',0)"


class PostgreSQLSecurityAuthority:
    def __init__(self, database_url):
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError('Explicit authority database URL required.')
        self.database_url = database_url

    @contextmanager
    def session(self, *, exclusive=False):
        try:
            with psycopg.connect(self.database_url, autocommit=True, connect_timeout=3) as conn:
                conn.execute("SET lock_timeout = '5s'")
                function = 'pg_advisory_lock' if exclusive else 'pg_advisory_lock_shared'
                conn.execute(f'SELECT {function}({_LOCK})')
                # Connection close releases the session lock on every exit path.
                yield conn
        except psycopg.Error:
            raise AuthorityUnavailable('Security authority unavailable.') from None

    @contextmanager
    def operation(self):
        active = _active.get()
        if active is not None:
            if active[0] is not self:
                raise AuthorityUnavailable('Conflicting security authorities.')
            yield active[1]
            return
        with self.session() as conn:
            token = _active.set((self, conn, uuid4()))
            try:
                yield conn
            finally:
                _active.reset(token)

    @staticmethod
    def _validate(claim):
        tenant, kind, subject, expected = claim
        if (not isinstance(tenant, str) or not 1 <= len(tenant) <= 200
                or tenant != tenant.strip() or kind not in {'user','api'}
                or any(not isinstance(v, str) or len(v) != 64 or any(c not in '0123456789abcdef' for c in v)
                       for v in (subject, expected))):
            raise ValueError('Invalid authority claim.')

    def check(self, claim, *, connection=None, operation_id=None):
        self._validate(claim)
        if connection is None:
            with self.operation() as conn:
                return self.check(claim, connection=conn, operation_id=_active.get()[2])
        tenant, kind, subject, expected = claim
        try:
            row = connection.execute('''SELECT fingerprint,version,enabled FROM security_grants
                WHERE tenant_id=%s AND kind=%s AND subject_hash=%s''', (tenant, kind, subject)).fetchone()
            allowed = row is not None and row[2] and row[0] == expected
            version = row[1] if row else 0
            self._audit(connection, operation_id or uuid4(), claim, version,
                        'allow' if allowed else 'deny', 'runtime')
        except psycopg.Error:
            raise AuthorityUnavailable('Security authority unavailable.') from None
        if not allowed:
            raise AuthorityDenied('Canonical authorization denied.')
        return version

    @staticmethod
    def _audit(conn, operation, claim, version, decision, actor):
        conn.execute('''INSERT INTO security_authority_audit
            (operation_id,tenant_id,kind,subject_hash,version,decision,actor_hash,trace_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
            (operation, *claim[:3], version, decision, fingerprint(actor), _trace.get()))

    def change(self, claim, *, enabled, expected_version, actor):
        """Trusted operator CAS. Version zero creates; revocation never deletes."""
        self._validate(claim)
        if (type(enabled) is not bool or type(expected_version) is not int or expected_version < 0
                or not isinstance(actor, str) or not actor.strip()):
            raise ValueError('Explicit operator, version and boolean required.')
        if _active.get() is not None:
            raise AuthorityConflict('Administration inside an admitted operation is forbidden.')
        with self.session(exclusive=True) as conn, conn.transaction():
            current = conn.execute('''SELECT version FROM security_grants
                WHERE tenant_id=%s AND kind=%s AND subject_hash=%s''', claim[:3]).fetchone()
            if (current[0] if current else 0) != expected_version:
                raise AuthorityConflict('Authority version conflict.')
            version = expected_version + 1
            conn.execute('''INSERT INTO security_grants
                (tenant_id,kind,subject_hash,fingerprint,version,enabled) VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id,kind,subject_hash) DO UPDATE
                SET fingerprint=EXCLUDED.fingerprint, version=EXCLUDED.version, enabled=EXCLUDED.enabled''',
                (*claim, version, enabled))
            self._audit(conn, uuid4(), claim, version, 'grant' if enabled else 'revoke', actor)
        return version
