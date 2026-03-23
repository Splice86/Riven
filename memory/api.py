"""Memory API server - FastAPI endpoints for memory storage and search."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from database import MemoryDB, init_db

app = FastAPI(title="Riven Memory API")

# Global database instance
db: MemoryDB | None = None


class AddMemoryRequest(BaseModel):
    """Request to add a memory with tags/properties."""
    content: str
    keywords: list[str] | None = None
    properties: dict[str, str] | None = None
    created_at: str | None = None  # Optional timestamp (ISO format)


class AddSummaryRequest(BaseModel):
    """Request to add a summary memory with links to target memories."""
    content: str
    keywords: list[str] | None = None
    properties: dict[str, str] | None = None
    created_at: str  # Required timestamp (ISO format) - set by agent
    target_ids: list[int]  # List of memory IDs to link to
    link_type: str = "summary_of"


class SearchRequest(BaseModel):
    """Request to search memories."""
    query: str
    limit: int = 50


@app.on_event("startup")
async def startup():
    """Initialize the database on startup."""
    global db
    init_db()
    db = MemoryDB()


@app.post("/memories")
async def add_memory(request: AddMemoryRequest) -> dict:
    """Add a new memory with optional keywords and properties.
    
    Args:
        request: Memory content, optional keywords, properties, and created_at timestamp
        
    Returns:
        The ID of the created memory
    """
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    memory_id = db.add_memory(
        content=request.content,
        keywords=request.keywords,
        properties=request.properties,
        created_at=request.created_at
    )
    
    return {"id": memory_id, "content": request.content[:100]}


@app.post("/memories/summary")
async def add_summary(request: AddSummaryRequest) -> dict:
    """Add a summary memory and link it to target memories.
    
    The created_at timestamp is required and should be set by the agent
    making the API call to time-bound the summary.
    
    Args:
        request: Summary content, keywords, properties, created_at, target_ids, link_type
        
    Returns:
        The ID of the created summary memory
    """
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Add the summary memory
    summary_id = db.add_memory(
        content=request.content,
        keywords=request.keywords,
        properties=request.properties,
        created_at=request.created_at
    )
    
    # Link to each target memory
    for target_id in request.target_ids:
        db.add_link(
            source_id=summary_id,
            target_id=target_id,
            link_type=request.link_type
        )
    
    return {"id": summary_id, "content": request.content[:100], "linked_to": request.target_ids}


@app.post("/memories/search")
async def search_memories(request: SearchRequest) -> dict:
    """Search memories using the query DSL.
    
    Args:
        request: Query string and limit
        
    Returns:
        List of matching memories
    """
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    results = db.search(request.query, limit=request.limit)
    
    return {"memories": results, "count": len(results)}


@app.get("/memories/{memory_id}")
async def get_memory(memory_id: int) -> dict:
    """Get a memory by ID.
    
    Args:
        memory_id: The ID of the memory
        
    Returns:
        The memory data
    """
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Search returns a list, we need to find the specific one
    results = db.search(f"id:{memory_id}", limit=1)
    if not results:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return results[0]


@app.get("/stats")
async def get_stats() -> dict:
    """Get memory statistics.
    
    Returns:
        Count of memories
    """
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    # Count memories
    results = db.search("", limit=10000)
    
    return {"count": len(results)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8030)
