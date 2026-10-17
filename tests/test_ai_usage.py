import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from pydantic import BaseModel
from fastapi.testclient import TestClient
from openai import OpenAIError

from app import ai_usage as usage
from app.config import Settings, get_settings
from app.main import app


@pytest.fixture(autouse=True)
def fresh_meter(monkeypatch):
    monkeypatch.setattr(usage, "meter", usage.UsageMeter())


def body(model="gpt-4.1-mini", input_tokens=1000, cached=500, output=100):
    return {"id":"resp_test", "object":"response", "created_at":1,
            "model":model, "output":[], "service_tier":"default", "usage":{
                "input_tokens":input_tokens, "output_tokens":output,
                "input_tokens_details":{"cached_tokens":cached}, "total_tokens":input_tokens+output}}


def client(handler, **kwargs):
    return usage.create_observed_client(api_key="test-secret-not-logged", transport=httpx.MockTransport(handler), **kwargs)


async def request(c, feature="legislative.explain", model="gpt-4.1-mini"):
    return await usage.observed_call(feature, model, c.responses.create,
                                     model=model, input="PRIVATE NEWS CONTENT", store=False)


def test_cached_tokens_are_not_double_charged():
    tokens=usage.token_usage(body())
    assert usage.estimated_cost("gpt-4.1-mini",tokens)==pytest.approx(0.00041)
    assert tokens["total_tokens"]==1100


def test_embedding_usage_and_cost():
    tokens=usage.token_usage({"usage":{"prompt_tokens":1000,"total_tokens":1000}})
    assert tokens["output_tokens"]==0
    assert usage.estimated_cost("text-embedding-3-small",tokens)==pytest.approx(0.00002)


@pytest.mark.parametrize("payload", [{}, {"usage":None}, {"usage":{"input_tokens":True}}, {"usage":{"input_tokens":-1}}])
def test_missing_or_invalid_usage_is_unknown(payload):
    assert usage.estimated_cost("gpt-4.1-mini",usage.token_usage(payload)) is None


@pytest.mark.parametrize("model,tier", [("unknown-model",None),("gpt-4.1-mini","priority"),("gpt-4.1-mini","flex")])
def test_unknown_price_or_tier_does_not_claim_zero(model,tier):
    assert usage.estimated_cost(model,usage.token_usage(body()),tier) is None


def test_invalid_cached_count_is_unknown():
    assert usage.estimated_cost("gpt-4.1-mini",usage.token_usage(body(cached=1001))) is None


def test_pinned_model_has_price():
    assert usage.estimated_cost("gpt-4.1-mini-2025-04-14",usage.token_usage(body()))==pytest.approx(0.00041)


def test_actual_sdk_request_tokens_no_secrets_or_prompt(caplog):
    async def run():
        async with client(lambda r: httpx.Response(200,json=body(),headers={"x-request-id":"req_test"})) as c:
            return await request(c)
    with caplog.at_level("INFO",logger="uvicorn.error"):
        response=asyncio.run(run())
    assert response.id=="resp_test"
    group=usage.meter.snapshot()["groups"][0]
    assert group["input_tokens"]==1000 and group["cached_input_tokens"]==500
    assert group["attempts"]==1 and group["usage_unknown"]==0
    assert "req_test" in caplog.text
    assert "PRIVATE NEWS CONTENT" not in caplog.text
    assert "test-secret-not-logged" not in caplog.text


def test_sdk_retry_is_counted_once_per_http_attempt(caplog):
    calls=[]
    def handler(r):
        calls.append(r)
        if len(calls)==1:
            return httpx.Response(429,json={"error":{"message":"test rate limit"}},headers={"retry-after":"0.001"})
        return httpx.Response(200,json=body())
    async def run():
        async with client(handler,max_retries=1) as c:
            await request(c)
    with caplog.at_level("INFO",logger="uvicorn.error"):
        asyncio.run(run())
    group=usage.meter.snapshot()["groups"][0]
    assert len(calls)==2 and group["attempts"]==2 and group["retries"]==1
    assert group["http_errors"]==1 and group["cost_unknown"]==1
    assert group["input_tokens"]==1000
    assert caplog.text.count("AI_USAGE ")==2


def test_timeout_retries_are_unknown_not_free():
    def handler(r):
        raise httpx.ReadTimeout("DO NOT LOG THIS SECRET",request=r)
    async def run():
        async with client(handler,max_retries=1) as c:
            with pytest.raises(OpenAIError):
                await request(c)
    asyncio.run(run())
    group=usage.meter.snapshot()["groups"][0]
    assert group["attempts"]==2 and group["transport_unknown"]==2
    assert group["cost_unknown"]==2
    assert usage.current_call.get() is None


def test_tokens_preserved_even_when_structured_output_is_invalid(caplog):
    class Output(BaseModel):
        answer: str
    payload=body()
    payload["output"]=[{"type":"message","id":"msg_test","role":"assistant","status":"completed",
                       "content":[{"type":"output_text","text":"not valid json","annotations":[]}]}]
    async def run():
        async with client(lambda r:httpx.Response(200,json=payload)) as c:
            with pytest.raises(ValueError):
                await usage.observed_call("news.explain_news","gpt-4.1-mini",c.responses.parse,
                                          model="gpt-4.1-mini",input="private",text_format=Output)
    with caplog.at_level("INFO",logger="uvicorn.error"):
        asyncio.run(run())
    assert usage.meter.snapshot()["groups"][0]["input_tokens"]==1000
    assert '"outcome":"failed"' in caplog.text


def test_embedding_sdk_call_instrumented():
    async def run():
        async with client(lambda r:httpx.Response(200,json={"model":"text-embedding-3-small","object":"list","data":[],"usage":{"prompt_tokens":20,"total_tokens":20}})) as c:
            await usage.observed_call("embeddings.document","text-embedding-3-small",c.embeddings.create,model="text-embedding-3-small",input=["PRIVATE"],encoding_format="float")
    asyncio.run(run())
    group=usage.meter.snapshot()["groups"][0]
    assert group["input_tokens"]==20 and group["output_tokens"]==0


def test_actual_returned_model_used_not_configured_alias():
    async def run():
        async with client(lambda r:httpx.Response(200,json=body(model="unknown-provider-model"))) as c:
            await request(c)
    asyncio.run(run())
    group=usage.meter.snapshot()["groups"][0]
    assert group["model"]=="unknown-provider-model" and group["cost_unknown"]==1


def test_concurrent_features_do_not_mix():
    async def run():
        async with client(lambda r:httpx.Response(200,json=body())) as c:
            await asyncio.gather(request(c,"news.how_it_affects_me"),request(c,"plans.ask"))
    asyncio.run(run())
    groups=usage.meter.snapshot()["groups"]
    assert {g["feature"] for g in groups}=={"news.how_it_affects_me","plans.ask"}
    assert all(g["attempts"]==1 and g["input_tokens"]==1000 for g in groups)


def test_telemetry_failure_does_not_break_generation(monkeypatch):
    def broken(*args):
        raise RuntimeError("metrics unavailable")
    monkeypatch.setattr(usage.meter,"record",broken)
    async def run():
        async with client(lambda r:httpx.Response(200,json=body())) as c:
            result=await request(c)
            assert result.id=="resp_test"
    asyncio.run(run())


def test_cancellation_propagates_and_resets_context():
    async def cancelled(**kwargs):
        raise asyncio.CancelledError()
    async def run():
        with pytest.raises(asyncio.CancelledError):
            await usage.observed_call("plans.ask","gpt-4.1-mini",cancelled)
        assert usage.current_call.get() is None
    asyncio.run(run())


def test_protected_endpoint_readonly_and_no_generation():
    settings=Settings(_env_file=None,supabase_url="https://test.supabase.co",supabase_service_role_key="test",openai_api_key="test",internal_api_secret="test-internal-secret")
    app.dependency_overrides[get_settings]=lambda:settings
    try:
        with TestClient(app) as c:
            assert c.get("/internal/ai-usage").status_code==401
            assert c.get("/internal/ai-usage",headers={"X-Internal-Secret":"invalid"}).status_code==401
            response=c.get("/internal/ai-usage",headers={"X-Internal-Secret":"test-internal-secret"})
            assert response.status_code==200
            data=response.json()
            assert data["scope"]=="current_process_only" and data["billing_authoritative"] is False
            assert data["groups"]==[]
            assert c.get("/health").status_code==200
    finally:
        app.dependency_overrides.clear()


def event(i=1):
    return {"event":"ai_usage","schema_version":1,"event_id":str(i),"at":"2026-10-17T12:00:00+00:00",
            "feature":"plans.ask","model":"gpt-4.1-mini","attempt":1,"http_status":200,
            "input_tokens":1000,"output_tokens":100,"cached_input_tokens":500,"estimated_usd":0.00041}


def test_meter_is_thread_safe():
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n:usage.meter.record(event(n)),range(1000)))
    assert usage.meter.snapshot()["groups"][0]["attempts"]==1000


def test_summary_memory_is_bounded():
    for n in range(200):
        usage.meter.record(dict(event(n),model=str(n)))
    assert len(usage.meter.snapshot()["groups"])<=129


def test_restart_starts_a_new_explicit_scope():
    usage.meter.record(event())
    restarted=usage.UsageMeter().snapshot()
    assert restarted["groups"]==[]
    assert restarted["process_instance"]!=usage.meter.snapshot()["process_instance"]


def test_offline_report_deduplicates_log_exports_and_keeps_unknowns():
    from tools.ai_usage_report import report
    known="2026 fly [info] AI_USAGE "+json.dumps(event())
    unknown="AI_USAGE "+json.dumps(dict(event(2),input_tokens=None,output_tokens=None,estimated_usd=None))
    result=report(["unrelated log",known,known,unknown,"AI_USAGE invalid"])
    assert result["unique_events"]==2 and result["cost_unknown_attempts"]==1
    assert result["known_estimated_usd"]==pytest.approx(0.00041)
    assert result["scope"]=="captured_log_events_only"
