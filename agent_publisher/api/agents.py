from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent, AGENT_ROLES, AGENT_SOURCE_MODES
from agent_publisher.schemas.agent import AgentCreate, AgentOut, AgentUpdate
from agent_publisher.services.task_service import TaskService

router = APIRouter(prefix="/api/agents", tags=["agents"])

# Maximum number of agents a non-admin user may create
USER_AGENT_LIMIT = 5


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


async def _check_account_ownership(
    account_id: int, user: UserContext, db: AsyncSession
) -> Account:
    """Verify user has access to the specified account."""
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    if not user.is_admin and account.owner_email != user.email:
        raise HTTPException(403, "Access denied")
    return account


async def _get_agent_with_ownership(
    agent_id: int, user: UserContext, db: AsyncSession
) -> Agent:
    """Fetch an agent and verify ownership through its Account."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if not user.is_admin:
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != user.email:
            raise HTTPException(403, "Access denied")
    return agent


@router.post("", response_model=AgentOut)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    _validate_agent_config(data, is_create=True)
    # Verify user owns the target account
    await _check_account_ownership(data.account_id, user, db)
    # Enforce per-user agent limit for non-admins
    if not user.is_admin:
        existing_count = (
            await db.execute(
                select(func.count(Agent.id))
                .join(Account, Agent.account_id == Account.id)
                .where(Account.owner_email == user.email)
            )
        ).scalar() or 0
        if existing_count >= USER_AGENT_LIMIT:
            raise HTTPException(
                403,
                f"Agent limit reached: non-admin users may create at most {USER_AGENT_LIMIT} agents",
            )
    agent = Agent(**data.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("", response_model=list[AgentOut])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    stmt = select(Agent).order_by(Agent.id)
    if not user.is_admin:
        stmt = stmt.join(Account).where(Account.owner_email == user.email)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return await _get_agent_with_ownership(agent_id, user, db)


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: int,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    agent = await _get_agent_with_ownership(agent_id, user, db)
    _validate_agent_config(data, is_create=False)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/generate")
async def generate_for_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    agent = await _get_agent_with_ownership(agent_id, user, db)
    task_svc = TaskService(db)
    task = await task_svc.run_generate(agent_id)
    return {"task_id": task.id, "status": task.status}


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    agent = await _get_agent_with_ownership(agent_id, user, db)
    await db.delete(agent)
    await db.commit()
    return {"message": "Agent deleted"}
