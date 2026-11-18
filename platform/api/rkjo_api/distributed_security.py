"""S1 admission lock adapted to L1 canonical principals, without omnichannel scope."""
import anyio
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from rkjo_kernel.security.authority import AuthorityDenied, AuthorityUnavailable, user_claim, api_claim


async def authorized_request(request, call_next, *, tenant, subject, role):
    authority = request.app.state.security_authority
    if authority is None:
        return await call_next(request)
    if not tenant or not subject:
        return JSONResponse(status_code=403, content={"detail": "Canonical identity required."})
    session = authority.session()
    try:
        conn = await run_in_threadpool(session.__enter__)
    except AuthorityUnavailable:
        return JSONResponse(status_code=503, content={"detail": "Security authority unavailable."})
    try:
        await run_in_threadpool(authority.check, user_claim(tenant, subject), connection=conn)
        await run_in_threadpool(authority.check, api_claim(tenant, subject, role), connection=conn)
        return await call_next(request)
    except AuthorityDenied:
        return JSONResponse(status_code=403, content={"detail": "Canonical authorization denied."})
    except AuthorityUnavailable:
        return JSONResponse(status_code=503, content={"detail": "Security authority unavailable."})
    finally:
        with anyio.CancelScope(shield=True):
            await run_in_threadpool(session.__exit__, None, None, None)
