from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import UserContext, get_current_user, get_db
from agent_publisher.services.prompt_template_service import PromptTemplateService

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default="rewrite", max_length=50)
    description: str = ""
    content: str = ""
    variables: list[str] = []


class PromptTemplateUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    content: str | None = None
    variables: list[str] | None = None


class PromptTemplateOut(BaseModel):
    id: int
    name: str
    category: str
    description: str
    content: str
    variables: list[str] | None
    usage_count: int
    owner_email: str | None
    is_builtin: bool
    created_at: str | None
    updated_at: str | None


@router.get("", response_model=list[PromptTemplateOut])
async def list_prompts(
    category: str | None = None,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = PromptTemplateService(db)
    templates = await svc.list_templates(None if user.is_admin else user.email, category=category, keyword=keyword)
    return [
        PromptTemplateOut(
            id=item.id,
            name=item.name,
            category=item.category,
            description=item.description,
            content=item.content,
            variables=item.variables,
            usage_count=item.usage_count,
            owner_email=item.owner_email,
            is_builtin=item.is_builtin,
            created_at=item.created_at.isoformat() if item.created_at else None,
            updated_at=item.updated_at.isoformat() if item.updated_at else None,
        )
        for item in templates
    ]


@router.get("/categories")
async def list_prompt_categories(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = PromptTemplateService(db)
    templates = await svc.list_templates(None if user.is_admin else user.email)
    categories = sorted({item.category for item in templates})
    return {"items": categories}


@router.post("", response_model=PromptTemplateOut)
async def create_prompt(
    data: PromptTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = PromptTemplateService(db)
    item = await svc.create_template(
        owner_email=None if user.is_admin else user.email,
        name=data.name,
        category=data.category,
        description=data.description,
        content=data.content,
        variables=data.variables,
    )
    return PromptTemplateOut(
        id=item.id,
        name=item.name,
        category=item.category,
        description=item.description,
        content=item.content,
        variables=item.variables,
        usage_count=item.usage_count,
        owner_email=item.owner_email,
        is_builtin=item.is_builtin,
        created_at=item.created_at.isoformat() if item.created_at else None,
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
    )


@router.put("/{template_id}", response_model=PromptTemplateOut)
async def update_prompt(
    template_id: int,
    data: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = PromptTemplateService(db)
    item = await svc.get_template(template_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    if item.is_builtin and not user.is_admin:
        raise HTTPException(status_code=403, detail="Built-in prompt template can only be edited by admin")
    if item.owner_email and item.owner_email != user.email and not user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    updates = data.model_dump(exclude_none=True)
    updated = await svc.update_template(item, updates)
    return PromptTemplateOut(
        id=updated.id,
        name=updated.name,
        category=updated.category,
        description=updated.description,
        content=updated.content,
        variables=updated.variables,
        usage_count=updated.usage_count,
        owner_email=updated.owner_email,
        is_builtin=updated.is_builtin,
        created_at=updated.created_at.isoformat() if updated.created_at else None,
        updated_at=updated.updated_at.isoformat() if updated.updated_at else None,
    )


@router.delete("/{template_id}")
async def delete_prompt(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = PromptTemplateService(db)
    item = await svc.get_template(template_id)
    if not item:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    if item.is_builtin:
        raise HTTPException(status_code=403, detail="Built-in prompt template cannot be deleted")
    if item.owner_email and item.owner_email != user.email and not user.is_admin:
        raise HTTPException(status_code=403, detail="Access denied")
    await svc.delete_template(item)
    return {"ok": True}
