"""Durable per-tenant/mission token reservations, including uncertain calls.

A crashed or failed call keeps its full reservation charged. Automatic retry or
refund is deliberately absent: the provider may already have consumed tokens.
No prompts, responses, API credentials or policy payloads are stored here.
"""
import json
from uuid import uuid4


class PostgresLLMLedger:
    def __init__(self, connection_factory):
        self.connect = connection_factory
        with self.connect() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS rkjo_llm_budgets (
                tenant_id TEXT NOT NULL, mission_id TEXT NOT NULL,
                charged BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (tenant_id, mission_id))''')
            con.execute('''CREATE TABLE IF NOT EXISTS rkjo_llm_calls (
                call_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, mission_id TEXT NOT NULL,
                trace_id TEXT NOT NULL, reserved BIGINT NOT NULL, state TEXT NOT NULL,
                receipt JSONB NOT NULL DEFAULT '{}')''')

    def reserve(self, context, amount, limit, receipt):
        from .gateway import LLMBudgetExceededError
        if not context.tenant_id:
            raise ValueError('Tenant is required for durable LLM budgets.')
        identifier = str(uuid4())
        with self.connect() as con:
            con.execute('INSERT INTO rkjo_llm_budgets (tenant_id, mission_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                        (context.tenant_id, context.mission_id))
            charged = con.execute('SELECT charged FROM rkjo_llm_budgets WHERE tenant_id=%s AND mission_id=%s FOR UPDATE',
                                  (context.tenant_id, context.mission_id)).fetchone()[0]
            if charged + amount > limit:
                raise LLMBudgetExceededError('LLM cumulative total token budget exhausted before call.')
            con.execute('UPDATE rkjo_llm_budgets SET charged=charged+%s WHERE tenant_id=%s AND mission_id=%s',
                        (amount, context.tenant_id, context.mission_id))
            con.execute('INSERT INTO rkjo_llm_calls VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)',
                        (identifier, context.tenant_id, context.mission_id, context.trace_id,
                         amount, 'reserved', json.dumps(receipt)))
        return identifier

    def finish(self, identifier, response=None, *, succeeded=True):
        with self.connect() as con:
            row = con.execute('SELECT tenant_id,mission_id,reserved,state FROM rkjo_llm_calls WHERE call_id=%s FOR UPDATE',
                              (identifier,)).fetchone()
            if row is None or row[3] != 'reserved':
                raise ValueError('LLM reservation already settled or unavailable.')
            tenant, mission, reserved, _ = row
            charged = response.usage.total_tokens if response is not None else reserved
            receipt = {} if response is None else {
                'provider': response.provider, 'model': response.model, 'latency_ms': response.latency_ms,
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens,
            }
            con.execute('UPDATE rkjo_llm_budgets SET charged=charged+%s WHERE tenant_id=%s AND mission_id=%s',
                        (charged-reserved, tenant, mission))
            con.execute('UPDATE rkjo_llm_calls SET state=%s, receipt=receipt || %s::jsonb WHERE call_id=%s',
                        (('succeeded' if succeeded else 'rejected') if response is not None else 'uncertain', json.dumps(receipt), identifier))
