from __future__ import annotations

from fastapi import FastAPI

from ..skills.manager import SkillService, list_available_skills
from .bootstrap import build_agent_service
from ..domain.models import InboundEvent

app = FastAPI(title="TeamBot Agent Core MVP")
service = build_agent_service()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events/slack")
async def handle_slack_event(event: InboundEvent) -> dict:
    """MVP ingress endpoint.

    In production this handler should:
    1) ack immediately,
    2) push event to durable queue,
    3) let worker call AgentService.process_event.
    """
    reply = await service.process_event(event)
    return {
        "ack": True,
        "reply": reply.model_dump(),
    }


@app.get("/skills")
async def list_skills() -> dict:
    manifests = [m.__dict__ for m in service.registry.list_manifests()]
    active = set(list_available_skills())
    all_skills = SkillService.list_all_skills()
    return {
        "runtime_skills": manifests,
        "active_skill_names": sorted(active),
        "all_skills": [
            {
                "name": s.name,
                "description": s.description,
                "source": s.source,
                "path": s.path,
                "enabled": s.name in active,
            }
            for s in all_skills
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


