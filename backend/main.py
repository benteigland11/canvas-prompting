from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from contextlib import asynccontextmanager

from .database import engine, create_db_and_tables, get_session
from .models import Workspace, Node, Edge
from .compiler import router as compiler_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(compiler_router)

@app.post("/workspaces/", response_model=Workspace)
def create_workspace(workspace: Workspace, session: Session = Depends(get_session)):
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace

@app.get("/workspaces/{workspace_id}", response_model=Workspace)
def get_workspace(workspace_id: str, session: Session = Depends(get_session)):
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace

# TODO: Add Node and Edge CRUD
# TODO: Add Compiler / Execution Engine endpoints

@app.post("/workspaces/{workspace_id}/nodes/", response_model=Node)
def create_node(workspace_id: str, node: Node, session: Session = Depends(get_session)):
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    node.workspace_id = workspace_id
    session.add(node)
    session.commit()
    session.refresh(node)
    return node

@app.get("/workspaces/{workspace_id}/nodes/", response_model=List[Node])
def list_nodes(workspace_id: str, session: Session = Depends(get_session)):
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace.nodes

@app.put("/nodes/{node_id}", response_model=Node)
def update_node(node_id: str, node_update: Node, session: Session = Depends(get_session)):
    db_node = session.get(Node, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")
    db_node.content = node_update.content
    db_node.x = node_update.x
    db_node.y = node_update.y
    session.add(db_node)
    session.commit()
    session.refresh(db_node)
    return db_node

@app.delete("/nodes/{node_id}")
def delete_node(node_id: str, session: Session = Depends(get_session)):
    db_node = session.get(Node, node_id)
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")
    session.delete(db_node)
    session.commit()
    return {"ok": True}

@app.post("/workspaces/{workspace_id}/edges/", response_model=Edge)
def create_edge(workspace_id: str, edge: Edge, session: Session = Depends(get_session)):
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    edge.workspace_id = workspace_id
    session.add(edge)
    session.commit()
    session.refresh(edge)
    return edge

@app.get("/workspaces/{workspace_id}/edges/", response_model=List[Edge])
def list_edges(workspace_id: str, session: Session = Depends(get_session)):
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace.edges

@app.delete("/edges/{edge_id}")
def delete_edge(edge_id: str, session: Session = Depends(get_session)):
    db_edge = session.get(Edge, edge_id)
    if not db_edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    session.delete(db_edge)
    session.commit()
    return {"ok": True}

# TODO: Add Compiler / Execution Engine endpoints
