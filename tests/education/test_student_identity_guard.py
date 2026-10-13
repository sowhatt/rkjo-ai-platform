"""Student identity guard checks."""
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from rkjo_api.education import router


def test_student_start_requires_individual_bearer():
    app = FastAPI()
    @app.middleware('http')
    async def operator(request, call_next):
        request.state.api_role = 'operator'
        request.state.api_tenant_id = str(uuid4())
        request.state.api_subject = None
        return await call_next(request)
    app.include_router(router)
    client = TestClient(app)
    response = client.post('/education/attempts', headers={'X-API-Key': 'operator'}, json={'assessment_id': str(uuid4()), 'learner_id': str(uuid4())})
    assert response.status_code == 403


def test_student_proof_submit_requires_individual_bearer():
    app = FastAPI()
    @app.middleware('http')
    async def operator(request, call_next):
        request.state.api_role = 'operator'
        request.state.api_tenant_id = str(uuid4())
        request.state.api_subject = None
        return await call_next(request)
    app.include_router(router)
    response = TestClient(app).post('/education/proof-challenges/' + str(uuid4()) + '/submit', headers={'X-API-Key': 'operator'}, json={'answer': '4'})
    assert response.status_code == 403
