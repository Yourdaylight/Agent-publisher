from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.models.agent import Agent, AGENT_ROLES, AGENT_SOURCE_MODES
from agent_publisher.schemas.agent import AgentCreate, AgentOut, AgentUpdate
from agent_publisher.services.task_service import TaskService

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _validate_agent_config(data: AgentCreate | AgentUpdate, is_create: bool = True) -> None:
    """Validate agent configuration based on source_mode."""
    source_mode = getattr(data, 'source_mode', None)
    if source_mode is None and not is_create:
        return
    if source_mode == "rss" and is_create:
        rss_sources = getattr(data, 'rss_sources', None)
        if not rss_sources:
            raise HTTPException(422, "RSS mode requires at least one RSS source")
    if source_mode == "skills_feed" and is_create:
        allowed = getattr(data, 'allowed_skill_sources', None)
        if not allowed:
            raise HTTPException(422, "Skills feed mode requires 'allowed_skill_sources'")


@router.post("", response_model=AgentOut)
async def create_agent(data: AgentCreate, db: AsyncSession = Depends(get_db)):
    _validate_agent_config(data, is_create=True)
    agent = Agent(**data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("", response_model=list[AgentOut])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).order_by(Agent.id))
    return result.scalars().all()


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: int, data: AgentUpdate, db: AsyncSession = Depends(get_db)
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    _validate_agent_config(data, is_create=False)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/generate")
async def generate_for_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    task_svc = TaskService(db)
    task = await task_svc.run_generate(agent_id)
    return {"task_id": task.id, "status": task.status}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db)):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    await db.delete(agent)
    await db.commit()
    return {"message": "Agent deleted"}
