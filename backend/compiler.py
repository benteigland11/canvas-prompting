import sys
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from .database import get_session
from .models import Workspace, Node, Edge

# Ensure cg modules can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from cg.cg_universal_graph_python.src.graph import Graph, Node as GraphNode, Edge as GraphEdge
from cg.universal_llm_context_bundle_python.src.llm_context_bundle import LLMContextBundleBuilder

router = APIRouter()

class RunRequest(BaseModel):
    target_node_id: str

@router.post("/workspaces/{workspace_id}/run")
def compile_and_run(workspace_id: str, request: RunRequest, session: Session = Depends(get_session)):
    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    # 1. Load the database nodes and edges into the universal topological graph
    g = Graph[Node]()
    node_map = {}
    for node in workspace.nodes:
        g.add_node(GraphNode(id=node.id, payload=node))
        node_map[node.id] = node
        
    for edge in workspace.edges:
        g.add_edge(GraphEdge(source=edge.source_node_id, target=edge.target_node_id))
        
    # 2. Walk the ancestors of the target node
    if request.target_node_id not in node_map:
        raise HTTPException(status_code=404, detail="Target node not found")
        
    ancestors = g.ancestors(request.target_node_id)
    ancestors.add(request.target_node_id) # Include the target node itself
    
    # 3. Build a subgraph to topologically sort only the relevant lineage
    subgraph = Graph[Node]()
    for n_id in ancestors:
        subgraph.add_node(GraphNode(id=n_id, payload=node_map[n_id]))
        
    for edge in workspace.edges:
        if edge.source_node_id in ancestors and edge.target_node_id in ancestors:
            subgraph.add_edge(GraphEdge(source=edge.source_node_id, target=edge.target_node_id))
            
    try:
        sorted_node_ids = subgraph.topological_sort()
    except ValueError:
        raise HTTPException(status_code=400, detail="Cycle detected in workspace graph")
        
    # 4. Compile the lineage into an LLM Context Bundle
    builder = LLMContextBundleBuilder()
    builder.set_system_prompt("You are a helpful spatial assistant. You can use tools to modify the canvas.")
    
    for n_id in sorted_node_ids:
        db_node = node_map[n_id]
        
        # Map our visual Card Types to LLM roles
        role = "user"
        if db_node.type.lower() in ["assistant", "output"]:
            role = "assistant"
        elif db_node.type.lower() in ["system", "lens"]:
            role = "system"
            
        builder.add_message(role=role, content=db_node.content)
        
    # (Here we would also register function tools using builder.add_function_tool)
    bundle = builder.build()
    
    # 5. Return the exact compacted context payload that the Execution Engine will dispatch
    return {
        "status": "compiled",
        "linearized_lineage": sorted_node_ids,
        "payload": bundle.to_dict()
    }
