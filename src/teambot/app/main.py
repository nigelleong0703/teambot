from __future__ import annotations

from fastapi import FastAPI, Request

from ..channels.runtimes.discord import DiscordInteractionRuntime
from ..channels.runtimes.feishu import FeishuLarkRuntime
from ..channels.runtimes.slack import SlackBoltRuntime
from ..channels.runtimes.telegram import TelegramPtbRuntime
from ..channels.runtimes.whatsapp import WhatsAppPywaRuntime
from ..gateway.manager import GatewayManager
from ..skills.manager import SkillService
from .bootstrap import build_agent_service

app = FastAPI(title="TeamBot Agent Core MVP")
service = build_agent_service()
gateway_manager = GatewayManager(service_getter=lambda: service)
discord_runtime = DiscordInteractionRuntime()
feishu_runtime = FeishuLarkRuntime()
slack_runtime = SlackBoltRuntime()
telegram_runtime = TelegramPtbRuntime()
whatsapp_runtime = WhatsAppPywaRuntime()


def _gateway_payload(result: object) -> dict:
    if isinstance(result, dict):
        return result
    return result.model_dump()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events/slack")
async def handle_slack_event(request: Request) -> dict:
    return _gateway_payload(
        await slack_runtime.handle_request(
            request=request,
            gateway_manager=gateway_manager,
            fallback=lambda: gateway_manager.handle_http_request(channel="slack", request=request),
        )
    )


@app.post("/events/{channel}")
async def handle_channel_event_legacy(channel: str, request: Request) -> dict:
    if channel == "discord":
        return _gateway_payload(
            await discord_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="discord", request=request),
            )
        )
    if channel == "feishu":
        return _gateway_payload(
            await feishu_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="feishu", request=request),
            )
        )
    if channel == "telegram":
        return _gateway_payload(
            await telegram_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="telegram", request=request),
            )
        )
    if channel == "whatsapp":
        return _gateway_payload(
            await whatsapp_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="whatsapp", request=request),
            )
        )
    return _gateway_payload(await gateway_manager.handle_http_request(channel=channel, request=request))


@app.post("/gateway/{channel}/events")
async def handle_channel_event(channel: str, request: Request) -> dict:
    if channel == "discord":
        return _gateway_payload(
            await discord_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="discord", request=request),
            )
        )
    if channel == "feishu":
        return _gateway_payload(
            await feishu_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="feishu", request=request),
            )
        )
    if channel == "slack":
        return _gateway_payload(
            await slack_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="slack", request=request),
            )
        )
    if channel == "telegram":
        return _gateway_payload(
            await telegram_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="telegram", request=request),
            )
        )
    if channel == "whatsapp":
        return _gateway_payload(
            await whatsapp_runtime.handle_request(
                request=request,
                gateway_manager=gateway_manager,
                fallback=lambda: gateway_manager.handle_http_request(channel="whatsapp", request=request),
            )
        )
    return _gateway_payload(await gateway_manager.handle_http_request(channel=channel, request=request))


@app.get("/events/whatsapp")
async def handle_whatsapp_challenge_legacy(request: Request):
    return await whatsapp_runtime.handle_challenge(request)


@app.get("/gateway/whatsapp/events")
async def handle_whatsapp_challenge(request: Request):
    return await whatsapp_runtime.handle_challenge(request)


@app.get("/skills")
async def list_skills() -> dict:
    manifests = [m.__dict__ for m in service.registry.list_manifests()]
    loaded_docs = SkillService.list_available_skill_docs()
    loaded_names = sorted({doc.name for doc in loaded_docs})
    return {
        "runtime_skills": manifests,
        "loaded_skill_names": loaded_names,
        "active_skill_names": loaded_names,
        "all_skills": [
            {
                "name": s.name,
                "description": s.description,
                "source": s.source,
                "path": s.path,
                "enabled": True,
            }
            for s in loaded_docs
        ],
    }


@app.get("/conversations")
async def list_conversations() -> dict:
    records = await service.store.list_conversations()
    return {
        "items": [r.model_dump() for r in records],
    }


@app.post("/skills/sync")
async def sync_skills(force: bool = False) -> dict:
    synced, skipped = SkillService.sync_all(force=force)
    service.reload_runtime()
    return {"ok": True, "synced": synced, "skipped": skipped}


@app.post("/skills/{skill_name}/enable")
async def enable_skill(skill_name: str, force: bool = False) -> dict:
    ok = SkillService.enable_skill(skill_name, force=force)
    service.reload_runtime()
    return {"ok": ok, "skill_name": skill_name}


@app.post("/skills/{skill_name}/disable")
async def disable_skill(skill_name: str) -> dict:
    ok = SkillService.disable_skill(skill_name)
    service.reload_runtime()
    return {"ok": ok, "skill_name": skill_name}


def run() -> None:
    import uvicorn

    uvicorn.run("teambot.app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
