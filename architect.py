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

        # ── Frontend Application ──────────────────────────────────────
        Component(
            id="frontend_app",
            kind="application",
            description="The frontend web application (React/Vite).",
        ),

        # ── Canvas UI Subsystem ───────────────────────────────────────
        Component(
            id="canvas_ui",
            kind="application",
            domains=["frontend"],
            description="The spatial canvas UI subsystem. Contains the visual layers for rendering cards, wires, thread trays, and the toolbar on an infinite pan/zoom surface.",
            parent="frontend_app",
        ),
        Component(
            id="canvas_surface",
            kind="frontend",
            domains=["frontend"],
            description="Infinite pan/zoom viewport with grid-dot background pattern. Manages camera state (pan, zoom, viewport bounds) and delegates hit-testing to child layers.",
            parent="canvas_ui",
            widgets=[
                "frontend-viewport-camera-store-typescript",
                "frontend-canvas-grid-pattern-typescript",
                "frontend-canvas-hit-tester-typescript",
            ],
        ),
        Component(
            id="card_renderer",
            kind="frontend",
            domains=["frontend"],
            description="Renders card nodes by type (Source, Lens, Action, Output). Each card is an elevated white surface with an accent-colored left stripe, title bar, content area, and status indicators.",
            parent="canvas_ui",
            widgets=["frontend-canvas-card-surface-typescript"],
        ),
        Component(
            id="wire_renderer",
            kind="frontend",
            domains=["frontend"],
            description="Renders directed edges (wires) between cards. Handles default, active, and stale-glow states. Draws animated dash patterns for in-progress execution and yellow pulse for stale dependencies.",
            parent="canvas_ui",
            widgets=[
                "frontend-edge-path-builder-typescript",
                "frontend-wire-state-resolver-typescript",
                "cg-frontend-light-streak-path-typescript",
            ],
        ),
        Component(
            id="thread_tray",
            kind="frontend",
            domains=["frontend"],
            description="Ephemeral micro-thread panel that slides out from a card. Provides a bounded chat context for iterating on a single card's content without polluting the main canvas. Exposes a 'Commit to Card' action.",
            parent="canvas_ui",
            widgets=[
                "universal-thread-store-typescript",
                "frontend-thread-tray-controller-typescript",
            ],
        ),
        Component(
            id="toolbar",
            kind="frontend",
            domains=["frontend"],
            description="Control bar with Run, Re-flow, card creation buttons, and workspace controls. Docked to the canvas edge.",
            parent="canvas_ui",
            widgets=[
                "frontend-toolbar-action-registry-typescript",
                "frontend-toolbar-state-resolver-typescript",
            ],
        ),
        Component(
            id="theme_layer",
            kind="service",
            domains=["frontend"],
            description="Design token system and theme mode provider. Applies the Tiger12 warm-light palette (Inter + Cardo, orange accent) to :root via CSS custom properties. Manages light/dark/system mode.",
            parent="canvas_ui",
            widgets=[
                "cg-frontend-design-tokens-javascript",
                "frontend-canvas-theme-provider-typescript",
            ],
        ),

        # ── UX Orchestration System ─────────────────────────────────
        Component(
            id="ux_system",
            kind="application",
            domains=["universal"],
            description="The behavioral interaction system mapping to UX domains: Populating, Framing, Probing, Neurosurgery, and Delegation. Acts as the cognitive nervous system between UI and Backend.",
        ),
        Component(
            id="population_controller",
            kind="service",
            domains=["universal"],
            description="Handles Shatter-Drop parsing, Forced Collision detection, and Atmosphere Pinning.",
            parent="ux_system",
        ),
        Component(
            id="framing_controller",
            kind="service",
            domains=["universal"],
            description="Enforces Camera-as-Prompt context boundaries, manages Aura Scrubbing (Shift+Scroll), and explicit Wormhole Tethering.",
            parent="ux_system",
        ),
        Component(
            id="neurosurgery_controller",
            kind="service",
            domains=["universal"],
            description="Manages Premise Hijacking, Synapse Severing (Delete wires), The Shove (context exile), and the Re-Flow Ripple.",
            parent="ux_system",
        ),
        Component(
            id="delegation_engine",
            kind="service",
            domains=["universal"],
            description="Command router that bundles cards for Explode, Squash, and Auto-Tectonics dispatch to the backend execution layer.",
            parent="ux_system",
        ),

        # Population Sub-Engines
        Component(id="shatter_engine", kind="module", domains=["universal"], description="Parses dropped PDFs/folders and spawns card clusters.", parent="population_controller"),
        Component(id="collision_physics", kind="module", domains=["universal"], description="Monitors drag coordinates and triggers Synthesize prompts on card smashes.", parent="population_controller"),
        Component(id="atmosphere_registry", kind="module", domains=["universal"], description="Tracks cards pinned to viewport edges and injects them as global system prompts.", parent="population_controller"),

        # Framing Sub-Engines
        Component(id="viewport_culler", kind="module", domains=["universal"], description="Hooks camera bounds to filter off-screen context.", parent="framing_controller"),
        Component(id="aura_scrubber", kind="module", domains=["universal"], description="Manages the translucent Gravity Well, scaling radius via Shift+Scroll to select nodes.", parent="framing_controller"),
        Component(id="wormhole_router", kind="module", domains=["universal"], description="Listens for Alt+Click to draw and track glowing spatial-bypass Edges.", parent="framing_controller"),

        # Neurosurgery Sub-Engines
        Component(id="premise_hijacker", kind="module", domains=["universal"], description="Converts rendered cards to raw <textarea> for direct edits.", parent="neurosurgery_controller"),
        Component(id="synapse_sever", kind="module", domains=["universal"], description="Hit-tests SVG wires for Hover+Delete to sever Edges.", parent="neurosurgery_controller"),
        Component(id="shove_physics", kind="module", domains=["universal"], description="Calculates cluster distance to lerp opacity and drop context gravity.", parent="neurosurgery_controller"),
        Component(id="ripple_propagator", kind="module", domains=["universal"], description="Walks downstream edges from edited nodes to mark children Stale.", parent="neurosurgery_controller"),

        # Delegation Sub-Engines
        Component(id="lasso_selector", kind="module", domains=["universal"], description="Handles bounding box grouping of multiple cards.", parent="delegation_engine"),
        Component(id="macro_dispatcher", kind="module", domains=["universal"], description="Bundles lassoed cards for Explode/Squash macros sent to backend.", parent="delegation_engine"),
        Component(id="auto_tectonics", kind="module", domains=["universal"], description="Spring-physics (d3-force) to repel disjoint clusters and organize wires.", parent="delegation_engine"),

        # ── Frontend Data / Services ─────────────────────────────────
        Component(
            id='reactive_store',
            kind='datastore',
            domains=['data'],
            description='Local reactive graph state (DAG of cards and wires). Tracks stale dependencies.',
            parent='frontend_app',
            widgets=['frontend-reactive-stale-store-typescript'],
        ),
        Component(
            id='session_state',
            kind='service',
            domains=['frontend'],
            description='Manages idle/loading/ready/error transitions for the active workspace.',
            parent='frontend_app',
            widgets=['frontend-session-state-store-typescript'],
        ),
        Component(
            id='fetch_client',
            kind='service',
            domains=['frontend'],
            description='Resilient HTTP client with exponential backoff for syncing to the backend.',
            parent='frontend_app',
            widgets=['frontend-retry-fetch-client-typescript'],
        ),

        # ── Backend ──────────────────────────────────────────────────
        Component(
            id="backend_app",
            kind="deployment",
            description="The FastAPI backend server handling API requests and LLM orchestration.",
        ),
        Component(
            id="workspace_api",
            kind="service",
            domains=["backend"],
            description="FastAPI endpoints for CRUD operations on workspaces and sessions.",
            parent="backend_app",
        ),
        Component(
            id='compiler',
            kind='service',
            domains=['backend'],
            description='Topological compiler that walks backward up wires to gather context into a zero-noise payload.',
            parent='backend_app',
            widgets=[
                'cg_universal_graph_python',
                'universal_llm_context_bundle_python',
            ],
        ),
        Component(
            id='execution_engine',
            kind='service',
            domains=['backend'],
            description='Fires one-shot and parallel LLM requests with the compiled context.',
            parent='backend_app',
            widgets=['cg_backend_llm_provider_interface_python'],
        ),
        Component(
            id='agent_runtime',
            kind='service',
            domains=['backend'],
            description='Handles LLM tool calls (SpawnCard, UpdateCard, LinkCards) for bi-directional mutability.',
            parent='backend_app',
            widgets=[
                'cg_universal_tool_invocation_python',
                'cg_universal_agent_tool_loop_python',
            ],
        ),
        Component(
            id="relational_db",
            kind="datastore",
            domains=["data"],
            description="Database (e.g. Postgres or SQLite) storing workspace JSON graphs, auth, and sessions.",
            parent="backend_app",
        ),
        Component(
            id="llm_service",
            kind="external",
            description="The underlying LLM API (e.g., Gemini, Claude).",
        ),
    ],
    edges=[
        # User ↔ Canvas
        Edge(source="user", target="canvas_surface", kind="interacts_with", what="Pan, zoom, click, drag"),
        Edge(source="user", target="toolbar", kind="interacts_with", what="Run, Re-flow, create card"),
        Edge(source="user", target="thread_tray", kind="interacts_with", what="Ephemeral chat, Commit to Card"),

        # Canvas internal layers ↔ Reactive Store
        Edge(source="canvas_surface", target="reactive_store", kind="reads", what="Node positions for layout"),
        Edge(source="card_renderer", target="reactive_store", kind="reads_writes", what="Card content, type, stale status"),
        Edge(source="wire_renderer", target="reactive_store", kind="reads", what="Edge topology, stale flags"),
        Edge(source="thread_tray", target="reactive_store", kind="reads_writes", what="Ephemeral thread state, commit mutations"),

        # Theme provides to all canvas layers
        Edge(source="theme_layer", target="canvas_surface", kind="provides", what="CSS custom properties"),
        Edge(source="theme_layer", target="card_renderer", kind="provides", what="Card accent colors, typography"),
        Edge(source="theme_layer", target="wire_renderer", kind="provides", what="Wire stroke styles, stale-glow tokens"),

        # Toolbar triggers
        Edge(source="toolbar", target="compiler", kind="triggers_run", what="Target node ID"),
        Edge(source="toolbar", target="reactive_store", kind="mutates", what="Create card, re-flow stale"),

        # UX Behaviors
        Edge(source="user", target="population_controller", kind="interacts_with", what="Shatter-drop files, pin rules"),
        Edge(source="user", target="framing_controller", kind="interacts_with", what="Shift+scroll aura, Alt+click tether"),
        Edge(source="user", target="neurosurgery_controller", kind="interacts_with", what="Double-click to hijack, delete to sever"),
        Edge(source="user", target="delegation_engine", kind="interacts_with", what="Lasso and click Squash/Explode"),
        
        Edge(source="population_controller", target="reactive_store", kind="mutates", what="Bulk spawn cards, update gravity"),
        Edge(source="framing_controller", target="canvas_surface", kind="reads_writes", what="Viewport bounds, Aura UI overlay"),
        Edge(source="neurosurgery_controller", target="reactive_store", kind="mutates", what="Edit nodes, delete edges, trigger Re-Flow"),
        Edge(source="delegation_engine", target="compiler", kind="triggers_run", what="Specialized sub-graph prompts"),

        # Session / Network
        Edge(source="canvas_surface", target="session_state", kind="triggers", what="Load/Save events"),
        Edge(source="session_state", target="fetch_client", kind="calls", what="Wraps API requests"),
        Edge(source="fetch_client", target="workspace_api", kind="calls", what="HTTP Requests"),
        Edge(source="session_state", target="reactive_store", kind="mutates", what="Hydrates graph"),

        # Backend
        Edge(source="workspace_api", target="relational_db", kind="reads_writes", what="Session Data"),
        Edge(source="compiler", target="relational_db", kind="reads", what="Ancestry paths/Graph topology"),
        Edge(source="compiler", target="execution_engine", kind="passes_context", what="Linearized context array"),
        Edge(source="execution_engine", target="llm_service", kind="calls", what="Prompt + Tools"),
        Edge(source="llm_service", target="agent_runtime", kind="returns_tools", what="Canvas Operations"),
        Edge(source="agent_runtime", target="relational_db", kind="mutates", what="Updates graph state"),
    ],
    notes="The architecture prioritizes a reactive state DAG. The canvas_ui subsystem is decomposed into visual layers (surface, cards, wires, threads, toolbar) fed by a shared theme_layer. The LLM acts as a multi-player co-editor via Canvas Operations.",
)
