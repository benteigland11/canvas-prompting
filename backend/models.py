from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
import uuid

class Workspace(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = "New Workspace"
    
    nodes: List["Node"] = Relationship(back_populates="workspace")
    edges: List["Edge"] = Relationship(back_populates="workspace")

class Node(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id")
    type: str  # e.g., "Source", "Lens", "Action", "Output"
    content: str = ""
    x: float = 0.0
    y: float = 0.0
    
    workspace: Workspace = Relationship(back_populates="nodes")

class Edge(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id")
    source_node_id: str = Field(foreign_key="node.id")
    target_node_id: str = Field(foreign_key="node.id")
    
    workspace: Workspace = Relationship(back_populates="edges")
