# Canvas Prompting

A new paradigm for interacting with Large Language Models. 

Instead of a traditional, linear, single-threaded chat interface, **Canvas Prompting** provides a **topological, spatial DAG (Directed Acyclic Graph) interface**. 

You place nodes (cards) on a canvas and draw wires between them. The backend's **Topological Context Compiler** traverses your graph's ancestry to construct the exact context window payload you want. This allows for:
- Non-linear conversations
- Branching thoughts and parallel prompting
- Easy context compaction and visual payload building

## Architecture
The system is built on a split Frontend/Backend architecture powered by Cartograph widgets:

- **Frontend (React/Vite)**: A reactive, topological canvas utilizing a stale-store to seamlessly handle visual graph mutations and session state.
- **Backend (FastAPI/Python)**: A robust execution engine that walks the graph topologies, dynamically limits token payloads using Cartograph blueprints, and compiles the finalized system+user context bundles for LLM dispatch.

## Development
This project utilizes [Cartograph](https://cartograph.tools) for widget and dependency management. 

*More documentation to come as the backend and compiler execution engines are built out!*
