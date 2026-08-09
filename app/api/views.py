from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.session import get_db
from app.db.models import Article
from app.api.routes import search_articles, analyze_article
from app.core.schemas import SearchArticlesQuery, ListArticlesQuery
from app.services import articles as article_service
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Frontend Views"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Render the main SPA shell."""
    return templates.TemplateResponse(request=request, name="index.html", context={})


@router.get("/ui/discover", response_class=HTMLResponse)
async def discover_articles(request: Request, q: str = "", db: AsyncSession = Depends(get_db)):
    """Fetch from GNews via the existing search_articles route, and return HTML."""
    if not q:
        return templates.TemplateResponse(request=request, name="components/article_card.html", context={"articles": []})
        
    try:
        query_params = SearchArticlesQuery(q=q, max_results=9)
        # Call the backend endpoint logic directly
        saved_articles = await search_articles(query_params=query_params, db=db)
    except HTTPException as e:
        logger.error(f"HTTPError searching news: {e.detail}")
        saved_articles = []
    except Exception as e:
        logger.error(f"Error searching news: {e}")
        saved_articles = []
        
    return templates.TemplateResponse(request=request, name="components/article_card.html", context={"articles": saved_articles})


@router.post("/ui/analyze/{article_id}", response_class=HTMLResponse)
async def trigger_analysis_view(
    request: Request, 
    article_id: str, 
    db: AsyncSession = Depends(get_db)
):
    """Trigger AI analysis via the existing analyze_article route, return a pending vault card."""
    try:
        art_uuid = uuid.UUID(article_id)
        
        # Call the backend endpoint logic directly
        try:
            await analyze_article(article_id=art_uuid, db=db)
        except HTTPException as e:
            if e.status_code != 409:
                raise
        
        # Re-fetch for the template and return vault card view
        article = await db.scalar(select(Article).where(Article.id == art_uuid).options(joinedload(Article.ai_summary)))
        return templates.TemplateResponse(request=request, name="components/vault_card.html", context={"articles": [article]})
        
    except HTTPException as e:
        return HTMLResponse(f"<div style='color:red;'>Error: {e.detail}</div>", status_code=e.status_code)
    except Exception as e:
        logger.error(f"Error triggering analysis: {e}")
        return HTMLResponse(f"<div style='color:red;'>Error: {str(e)}</div>", status_code=500)


@router.get("/ui/vault", response_class=HTMLResponse)
async def vault_articles(request: Request, query_params: ListArticlesQuery = Depends(), db: AsyncSession = Depends(get_db)):
    """Fetch all articles for the vault tab."""
    sort_val = query_params.sort_by.value if hasattr(query_params.sort_by, "value") else str(query_params.sort_by)
    articles = await article_service.query(
        db,
        q=query_params.q,
        status=query_params.status,
        sentiment=query_params.sentiment,
        min_score=query_params.min_score,
        max_score=query_params.max_score,
        sort_by=sort_val,
        start_date=query_params.start_date,
        end_date=query_params.end_date,
        limit=query_params.limit,
        offset=query_params.offset,
    )
    return templates.TemplateResponse(request=request, name="components/vault_card.html", context={"articles": articles})


@router.get("/ui/vault/card/{article_id}", response_class=HTMLResponse)
async def vault_single_card(request: Request, article_id: str, db: AsyncSession = Depends(get_db)):
    """Poll endpoint for a single vault card."""
    try:
        art_uuid = uuid.UUID(article_id)
        article = await article_service.get_by_id(db, art_uuid)
        
        if not article:
            # Return 200 OK with empty string so HTMX replaces the card with nothing (destroys it)
            # returning 404 would cause HTMX to ignore the response and keep polling forever.
            return HTMLResponse("", status_code=200)
            
        return templates.TemplateResponse(request=request, name="components/vault_card.html", context={"articles": [article]})
    except Exception as e:
        logger.error(f"Error polling card: {e}")
        return HTMLResponse(f"<div style='color:red;'>Error: {str(e)}</div>", status_code=500)
