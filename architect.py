"""Project architecture map.

This file describes how the parts of this project relate so an agent
can plan glue code and widget choices at the app level.
"""

from cartograph.architect.schema import Architecture, Component, Edge

architecture = Architecture(
    schema_version="0.1",
    goal="A Spatial Canvas Architecture for LLMs, moving from linear chat to a topological graph context.",
    components=[
        Component(
            id="user",
            kind="external",
            description="The person interacting with the spatial canvas.",
        ),
        Component(
            id="canvas_ui",
            kind="frontend",
            domains=["frontend"],
            description="Spatial UI rendering cards, wires, thread trays, and stale state indicators.",
            parent="frontend_app",
        ),
        Component(
            id="reactive_store",
            kind="datastore",
            domains=["data"],
            description="Local reactive graph state (DAG of cards and wires). Tracks stale dependencies.",
            parent="frontend_app",
        ),
        Component(
            id="session_state",
            kind="service",
            domains=["frontend"],
            description="Manages idle/loading/ready/error transitions for the active workspace.",
            parent="frontend_app",
        ),
        Component(
            id="fetch_client",
            kind="service",
            domains=["frontend"],
            description="Resilient HTTP client with exponential backoff for syncing to the backend.",
            parent="frontend_app",
        ),
        Component(
            id="frontend_app",
            kind="application",
            description="The frontend web application (React/Vite).",
        ),
        Component(
            id="workspace_api",
            kind="service",
            domains=["backend"],
            description="FastAPI endpoints for CRUD operations on workspaces and sessions.",
            parent="backend_app",
        ),
        Component(
            id="compiler",
            kind="service",
            domains=["backend"],
            description="Topological compiler that walks backward up wires to gather context into a zero-noise payload.",
            parent="backend_app",
        ),
        Component(
            id="execution_engine",
            kind="service",
            domains=["backend"],
            description="Fires one-shot and parallel LLM requests with the compiled context.",
            parent="backend_app",
        ),
        Component(
            id="agent_runtime",
            kind="service",
            domains=["backend"],
            description="Handles LLM tool calls (SpawnCard, UpdateCard, LinkCards) for bi-directional mutability.",
            parent="backend_app",
        ),
        Component(
            id="relational_db",
            kind="datastore",
            domains=["data"],
            description="Database (e.g. Postgres or SQLite) storing workspace JSON graphs, auth, and sessions.",
            parent="backend_app",
        ),
        Component(
            id="backend_app",
            kind="deployment",
            description="The FastAPI backend server handling API requests and LLM orchestration.",
        ),
        Component(
            id="llm_service",
            kind="external",
            description="The underlying LLM API (e.g., Gemini, Claude).",
        ),
    ],
    edges=[
        Edge(source="user", target="canvas_ui", kind="interacts_with"),
        Edge(source="canvas_ui", target="reactive_store", kind="reads_writes", what="Graph mutations"),
        Edge(source="canvas_ui", target="session_state", kind="triggers", what="Load/Save events"),
        Edge(source="session_state", target="fetch_client", kind="calls", what="Wraps API requests"),
        Edge(source="fetch_client", target="workspace_api", kind="calls", what="HTTP Requests"),
        Edge(source="session_state", target="reactive_store", kind="mutates", what="Hydrates graph"),
        Edge(source="workspace_api", target="relational_db", kind="reads_writes", what="Session Data"),
        Edge(source="canvas_ui", target="compiler", kind="triggers_run", what="Target node ID"),
        Edge(source="compiler", target="relational_db", kind="reads", what="Ancestry paths/Graph topology"),
        Edge(source="compiler", target="execution_engine", kind="passes_context", what="Linearized context array"),
        Edge(source="execution_engine", target="llm_service", kind="calls", what="Prompt + Tools"),
        Edge(source="llm_service", target="agent_runtime", kind="returns_tools", what="Canvas Operations"),
        Edge(source="agent_runtime", target="relational_db", kind="mutates", what="Updates graph state"),
    ],
    notes="The architecture prioritizes a reactive state DAG. The LLM acts as a multi-player co-editor via Canvas Operations.",
)
