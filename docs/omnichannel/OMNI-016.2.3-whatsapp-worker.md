# OMNI-016.2.3 — WhatsApp outbound worker runbook

Status: **implementation ready for local validation**, **not proof of an actual Meta send**. Deploy only after a test tenant and a verified phone number have been configured in Meta.

## Boundaries and safety

- A process environment (preferably injected by a managed secret store) supplies one Meta token per tenant/account; never check tokens into Git or write them to logs.
- `RKJO_OMNI_WHATSAPP_ACCOUNTS_JSON` is *metadata only* and holds `token_env`, never `access_token`. Deployment operations must keep this configuration restricted even though it contains no tokens.
- Templates listed in metadata are expected to have been approved in Meta **for that WhatsApp Business account**. This first implementation does not query Meta for template status. Approval/revocation synchronisation remains an operational requirement. Remove revoked templates promptly.
- The worker is fail-closed when an account/template is not registered.
- Only text and template payload kinds are supported. Media, buttons, list serialization remain unsupported.
- The WhatsApp 24h window derives only from verified inbound events in PostgreSQL; human takeover is fenced by conversation ownership.
- At-least-once transport cannot guarantee exactly-once provider sends. On uncertain Meta acknowledgement, subsequent retries are fenced and manual reconciliation is required. Never forcibly mark uncertain rows pending.
- Operator receipt status is updated by the existing verified WhatsApp webhook path, not by the outbound worker.

## Required database bootstrap

Prior to running the process, initialize the schemas through the normal deployment migration/bootstrap, including:
- `PostgreSQLConversationRouter.initialize_schema()`
- `PostgreSQLNotificationStore.initialize_schema()`
- `PostgreSQLDeliveryLedger.initialize_schema()`
- Inbox/outbox schemas required by the existing webhook routing flow.

Do **not** initialize tables on every worker restart.

## Environment (example only; no credentials)

```bash
# Inject RKJO_DATABASE_URL via your secrets manager.
export RKJO_OMNI_WHATSAPP_ACCOUNTS_JSON='[
  {
    "tenant_id": "tenant-a",
    "channel_account_id": "phone-a",
    "phone_number_id": "12345678901",
    "token_env": "RKJO_META_TOKEN_TENANT_A",
    "approved_templates": [
      {"id":"welcome","name":"welcome_fr","language_code":"fr"}
    ]
  }
]'
# Inject RKJO_META_TOKEN_TENANT_A via your secrets manager.
export RKJO_META_GRAPH_VERSION=v23.0
export RKJO_OMNI_NOTIFICATION_MAX_ATTEMPTS=4
export RKJO_OMNI_DELIVERY_POLL_SECONDS=1
export RKJO_OMNI_DELIVERY_BATCH_SIZE=50
```

The deployment environment must explicitly grant account-specific Meta permissions. Use separate staging and production tokens, with rotation and revocation procedures. Restrict the PostgreSQL connection and worker logs. Do not enable `AllowAllChannelPolicy` with live Meta traffic.

## Start (after setting PYTHONPATH)

```bash
python3 -m rkjo_worker.omnichannel_whatsapp_delivery
```

Stop using SIGTERM or SIGINT to let the current cycle end. Deploy a single replica initially, then exercise row-lease concurrency before scaling up.

## Validation plan

1. Offline: `python3 -m pytest tests/worker/test_omnichannel_whatsapp_delivery.py -v`.
2. Offline with PostgreSQL: `python3 -m pytest tests/kernel/omnichannel/test_whatsapp_runtime.py -v`.
3. Regression: `python3 -m pytest tests/kernel/omnichannel tests/kernel/multimodal tests/worker/test_omnichannel_rabbitmq_dispatcher.py -q`.
4. Broker: use the existing opt-in live RabbitMQ test with separate test credentials.
5. Meta pilot: use a designated WhatsApp test phone number/recipient. Verify accepted provider `wamid`, outbound ledger, signed webhook `sent`/`delivered` receipts, template outside the 24h window, human takeover, revoked template fail-closed, and no duplicate sends after ambiguous HTTP outcomes.
6. Monitor: number of pending/failed/uncertain notifications, retry rates, age of queued items, DLQ, missing receipts, time since last processed message, and credential expiry.

No real Meta send is executed by automated tests at this stage.
