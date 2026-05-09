import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { ViewportCameraStore } from '../cg/frontend-viewport-camera-store-typescript/src/viewport_camera_store.ts'
import { gridPatternCss } from '../cg/frontend-canvas-grid-pattern-typescript/src/canvas_grid_pattern.ts'
import { hitTestTopmost } from '../cg/frontend-canvas-hit-tester-typescript/src/canvas_hit_tester.ts'
import { buildEdgePath } from '../cg/frontend-edge-path-builder-typescript/src/edge_path_builder.ts'
import { ToolbarActionRegistry } from '../cg/frontend-toolbar-action-registry-typescript/src/toolbar_action_registry.ts'
import { resolveToolbarState, runGuard, reflowGuard, alwaysEnabled } from '../cg/frontend-toolbar-state-resolver-typescript/src/toolbar_state_resolver.ts'
import type { ToolbarContext } from '../cg/frontend-toolbar-state-resolver-typescript/src/toolbar_state_resolver.ts'
import type { HitNode } from '../cg/frontend-canvas-hit-tester-typescript/src/canvas_hit_tester.ts'

// ── Types ────────────────────────────────────────────
type CardType = 'source' | 'lens' | 'action' | 'output'

interface ContextMenuState {
  /** Screen-space X position of the menu anchor. */
  x: number
  /** Screen-space Y position of the menu anchor. */
  y: number
  /** The card ID under the cursor, or null for empty canvas. */
  targetCardId: string | null
  /** World-space position (for "create here"). */
  worldX: number
  worldY: number
}

interface CardNode {
  id: string
  type: CardType
  title: string
  content: string
  x: number
  y: number
  width: number
  height: number
  zIndex: number
}

interface WireEdge {
  id: string
  sourceId: string
  targetId: string
}

// ── Demo Data ────────────────────────────────────────
const DEMO_CARDS: CardNode[] = [
  {
    id: 'src-1', type: 'source', title: 'Project Requirements',
    content: 'Build a spatial canvas UI that treats the LLM context window as a visual, manipulable graph rather than a linear chat.',
    x: 80, y: 120, width: 260, height: 140, zIndex: 0,
  },
  {
    id: 'lens-1', type: 'lens', title: 'System Prompt',
    content: 'You are a senior frontend architect. Output structured, modular TypeScript with clean separation of concerns.',
    x: 420, y: 80, width: 260, height: 130, zIndex: 1,
  },
  {
    id: 'act-1', type: 'action', title: 'Generate Component',
    content: 'Using the project requirements and system prompt, generate the CanvasSurface React component with pan/zoom support.',
    x: 280, y: 320, width: 260, height: 140, zIndex: 2,
  },
  {
    id: 'out-1', type: 'output', title: 'LLM Response',
    content: 'Awaiting execution…\n\nSelect this card and click ▶ Run to compile context and fire the request.',
    x: 620, y: 300, width: 260, height: 140, zIndex: 3,
  },
]

const DEMO_EDGES: WireEdge[] = [
  { id: 'e1', sourceId: 'src-1', targetId: 'act-1' },
  { id: 'e2', sourceId: 'lens-1', targetId: 'act-1' },
  { id: 'e3', sourceId: 'act-1', targetId: 'out-1' },
]

// ── Card type theme ──────────────────────────────────
const CARD_COLORS: Record<CardType, string> = {
  source: '#5B8DEF',
  lens: '#F5A623',
  action: '#FF9800',
  output: '#2EC4B6',
}

const CARD_LABELS: Record<CardType, string> = {
  source: 'SRC',
  lens: 'LENS',
  action: 'ACT',
  output: 'OUT',
}

// ── App ──────────────────────────────────────────────
export default function App() {
  const [cards, setCards] = useState<CardNode[]>(DEMO_CARDS)
  const [edges] = useState<WireEdge[]>(DEMO_EDGES)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [staleIds] = useState<Set<string>>(new Set())
  const [cameraState, setCameraState] = useState({ panX: 0, panY: 0, zoom: 1, viewportWidth: 0, viewportHeight: 0 })
  const [createMenuOpen, setCreateMenuOpen] = useState(false)
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null)
  const [dragging, setDragging] = useState<{ id: string; offsetX: number; offsetY: number } | null>(null)
  const [panning, setPanning] = useState(false)
  const mouseRef = useRef({ x: 0, y: 0 })

  const viewportRef = useRef<HTMLDivElement>(null)
  const cameraRef = useRef<ViewportCameraStore>(new ViewportCameraStore())
  const createBtnRef = useRef<HTMLDivElement>(null)

  const camera = cameraRef.current

  // ── Toolbar Action Registry ─────────────────────
  const registry = useMemo(() => {
    const r = new ToolbarActionRegistry()
    r.registerAll([
      { id: 'run', label: 'Run', icon: '▶', shortcut: 'Ctrl+Enter', group: 'execution', handler: () => {}, guard: runGuard },
      { id: 'reflow', label: 'Re-flow', icon: '↻', shortcut: 'Ctrl+Shift+R', group: 'execution', handler: () => {}, guard: reflowGuard },
      { id: 'create', label: 'Create', icon: '+', group: 'creation', handler: () => setCreateMenuOpen(o => !o), guard: alwaysEnabled },
    ])
    return r
  }, [])

  // ── Resolved toolbar state ──────────────────────
  const toolbarContext: ToolbarContext = useMemo(() => {
    const selArray = [...selectedIds]
    return {
      selectedNodeIds: selArray,
      selectedNodeTypes: selArray.map(id => cards.find(c => c.id === id)?.type ?? ''),
      staleNodeIds: [...staleIds],
      executingNodeIds: [],
    }
  }, [selectedIds, cards, staleIds])

  const resolvedActions = useMemo(
    () => resolveToolbarState(registry.getAll(), toolbarContext),
    [registry, toolbarContext]
  )

  // ── Camera sync ─────────────────────────────────
  useEffect(() => {
    const unsub = camera.subscribe(setCameraState)
    const resize = () => {
      if (viewportRef.current) {
        const { width, height } = viewportRef.current.getBoundingClientRect()
        camera.setViewport(width, height)
      }
    }
    resize()
    window.addEventListener('resize', resize)
    return () => { unsub(); window.removeEventListener('resize', resize) }
  }, [camera])

  // ── Grid background ─────────────────────────────
  const gridCss = useMemo(() => gridPatternCss(cameraState, {
    dotColor: '#e0ddd8',
    dotRadius: 1.2,
    baseSpacing: 24,
  }), [cameraState])

  // ── Hit-test nodes ──────────────────────────────
  const hitNodes: HitNode[] = useMemo(
    () => cards.map(c => ({ id: c.id, x: c.x, y: c.y, width: c.width, height: c.height, zIndex: c.zIndex })),
    [cards]
  )

  // ── Wire paths ──────────────────────────────────
  const wirePaths = useMemo(() => {
    return edges.map(edge => {
      const src = cards.find(c => c.id === edge.sourceId)
      const tgt = cards.find(c => c.id === edge.targetId)
      if (!src || !tgt) return null

      const sourceRect = { x: src.x, y: src.y, width: src.width, height: src.height }
      const targetRect = { x: tgt.x, y: tgt.y, width: tgt.width, height: tgt.height }

      const result = buildEdgePath(sourceRect, targetRect, { curvature: 0.4 })
      const isStale = staleIds.has(edge.sourceId) || staleIds.has(edge.targetId)
      return { id: edge.id, d: result.path, isStale }
    }).filter(Boolean)
  }, [edges, cards, staleIds])

  // ── Context menu open logic ─────────────────────
  const openContextMenu = useCallback((screenX: number, screenY: number) => {
    const rect = viewportRef.current?.getBoundingClientRect()
    if (!rect) return
    const localX = screenX - rect.left
    const localY = screenY - rect.top
    const world = camera.screenToWorld(localX, localY)
    const hit = hitTestTopmost(world, hitNodes)

    if (hit) {
      setSelectedIds(new Set([hit.nodeId]))
    }

    setContextMenu({
      x: screenX,
      y: screenY,
      targetCardId: hit?.nodeId ?? null,
      worldX: world.x,
      worldY: world.y,
    })
    setCreateMenuOpen(false)
  }, [camera, hitNodes])

  const closeContextMenu = useCallback(() => setContextMenu(null), [])

  // ── Context menu action handlers ────────────────
  const handleCtxDuplicate = useCallback(() => {
    if (!contextMenu?.targetCardId) return
    const src = cards.find(c => c.id === contextMenu.targetCardId)
    if (!src) return
    const id = `${src.type}-${Date.now()}`
    const dup: CardNode = {
      ...src,
      id,
      x: src.x + 30,
      y: src.y + 30,
      zIndex: cards.length,
    }
    setCards(prev => [...prev, dup])
    setSelectedIds(new Set([id]))
    closeContextMenu()
  }, [contextMenu, cards, closeContextMenu])

  const handleCtxDelete = useCallback(() => {
    if (!contextMenu?.targetCardId) return
    setCards(prev => prev.filter(c => c.id !== contextMenu.targetCardId))
    setSelectedIds(new Set())
    closeContextMenu()
  }, [contextMenu, closeContextMenu])

  const handleCtxCreateHere = useCallback((type: CardType) => {
    if (!contextMenu) return
    const id = `${type}-${Date.now()}`
    const newCard: CardNode = {
      id,
      type,
      title: `New ${type.charAt(0).toUpperCase() + type.slice(1)}`,
      content: '',
      x: contextMenu.worldX - 130,
      y: contextMenu.worldY - 60,
      width: 260,
      height: 120,
      zIndex: cards.length,
    }
    setCards(prev => [...prev, newCard])
    setSelectedIds(new Set([id]))
    closeContextMenu()
  }, [contextMenu, cards.length, closeContextMenu])

  const handleCtxFitView = useCallback(() => {
    if (cards.length === 0) { closeContextMenu(); return }
    const minX = Math.min(...cards.map(c => c.x))
    const minY = Math.min(...cards.map(c => c.y))
    const maxX = Math.max(...cards.map(c => c.x + c.width))
    const maxY = Math.max(...cards.map(c => c.y + c.height))
    camera.fitBounds({ x: minX, y: minY, width: maxX - minX, height: maxY - minY }, 60)
    closeContextMenu()
  }, [cards, camera, closeContextMenu])

  // ── Pointer handlers ────────────────────────────
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.92 : 1.08
    camera.zoomAt(e.clientX, e.clientY - (viewportRef.current?.getBoundingClientRect().top ?? 0), delta)
  }, [camera])

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    openContextMenu(e.clientX, e.clientY)
  }, [openContextMenu])

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    // Right-click is handled by onContextMenu — don't process here
    if (e.button === 2) return
    if (contextMenu) { closeContextMenu(); return }
    if (createMenuOpen) { setCreateMenuOpen(false); return }

    const rect = viewportRef.current?.getBoundingClientRect()
    if (!rect) return

    const screenX = e.clientX - rect.left
    const screenY = e.clientY - rect.top
    const world = camera.screenToWorld(screenX, screenY)

    const hit = hitTestTopmost(world, hitNodes)
    if (hit) {
      // Select the card
      if (e.shiftKey) {
        setSelectedIds(prev => {
          const next = new Set(prev)
          if (next.has(hit.nodeId)) next.delete(hit.nodeId)
          else next.add(hit.nodeId)
          return next
        })
      } else {
        setSelectedIds(new Set([hit.nodeId]))
      }
      // Start dragging
      const card = cards.find(c => c.id === hit.nodeId)!
      setDragging({ id: hit.nodeId, offsetX: world.x - card.x, offsetY: world.y - card.y })
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    } else {
      // Deselect and start panning
      setSelectedIds(new Set())
      setPanning(true)
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    }
  }, [camera, hitNodes, cards, createMenuOpen])

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (dragging) {
      const rect = viewportRef.current?.getBoundingClientRect()
      if (!rect) return
      const world = camera.screenToWorld(e.clientX - rect.left, e.clientY - rect.top)
      setCards(prev => prev.map(c =>
        c.id === dragging.id
          ? { ...c, x: world.x - dragging.offsetX, y: world.y - dragging.offsetY }
          : c
      ))
    } else if (panning) {
      camera.pan(e.movementX, e.movementY)
    }
  }, [dragging, panning, camera])

  const handlePointerUp = useCallback(() => {
    setDragging(null)
    setPanning(false)
  }, [])

  // ── Create card ─────────────────────────────────
  const createCard = useCallback((type: CardType) => {
    const center = camera.screenToWorld(cameraState.viewportWidth / 2, cameraState.viewportHeight / 2)
    const id = `${type}-${Date.now()}`
    const newCard: CardNode = {
      id,
      type,
      title: `New ${type.charAt(0).toUpperCase() + type.slice(1)}`,
      content: '',
      x: center.x - 130 + (Math.random() - 0.5) * 60,
      y: center.y - 60 + (Math.random() - 0.5) * 60,
      width: 260,
      height: 120,
      zIndex: cards.length,
    }
    setCards(prev => [...prev, newCard])
    setSelectedIds(new Set([id]))
    setCreateMenuOpen(false)
  }, [camera, cameraState, cards.length])

  // ── Track mouse position for G-key summon ──────
  useEffect(() => {
    const track = (e: MouseEvent) => { mouseRef.current = { x: e.clientX, y: e.clientY } }
    window.addEventListener('mousemove', track)
    return () => window.removeEventListener('mousemove', track)
  }, [])

  // ── Keyboard shortcuts ──────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // G key opens context menu at mouse position
      if (e.key === 'g' || e.key === 'G') {
        if (!contextMenu) {
          e.preventDefault()
          openContextMenu(mouseRef.current.x, mouseRef.current.y)
          return
        }
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        const run = resolvedActions.find(a => a.action.id === 'run')
        if (run?.enabled) console.log('▶ Run triggered for:', [...selectedIds])
      }
      if (e.key === 'Backspace' || e.key === 'Delete') {
        if (selectedIds.size > 0) {
          setCards(prev => prev.filter(c => !selectedIds.has(c.id)))
          setSelectedIds(new Set())
        }
      }
      if (e.key === 'Escape') {
        setSelectedIds(new Set())
        setCreateMenuOpen(false)
        closeContextMenu()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selectedIds, resolvedActions, contextMenu, openContextMenu, closeContextMenu])

  return (
    <div className="canvas-app">
      {/* ── Toolbar ── */}
      <div className="toolbar" id="toolbar">
        <span className="toolbar-title">Spatial Canvas</span>

        <div className="toolbar-group">
          {resolvedActions.filter(a => a.action.group === 'execution').map(a => (
            <button
              key={a.action.id}
              className={`toolbar-btn ${a.action.id === 'run' ? 'toolbar-btn--primary' : ''}`}
              disabled={!a.enabled}
              title={a.reason ?? (a.action as { shortcut?: string }).shortcut ?? ''}
              onClick={() => {
                if (a.enabled) console.log(`Action: ${a.action.id}`, [...selectedIds])
              }}
            >
              {(a.action as { icon?: string }).icon} {a.action.label}
            </button>
          ))}
        </div>

        <div className="toolbar-divider" />

        <div className="toolbar-group" style={{ position: 'relative' }} ref={createBtnRef}>
          <button
            className="toolbar-btn"
            onClick={() => setCreateMenuOpen(o => !o)}
          >
            + Create
          </button>
          {createMenuOpen && (
            <div className="create-menu" onClick={e => e.stopPropagation()}>
              {(['source', 'lens', 'action', 'output'] as CardType[]).map(type => (
                <button key={type} className="create-menu-item" onClick={() => createCard(type)}>
                  <span className="create-menu-dot" style={{ background: CARD_COLORS[type] }} />
                  {type.charAt(0).toUpperCase() + type.slice(1)} Card
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="toolbar-divider" />

        <span className="toolbar-zoom">{Math.round(cameraState.zoom * 100)}%</span>

        {selectedIds.size > 0 && (
          <span className="toolbar-selection">
            {selectedIds.size} selected
          </span>
        )}
      </div>

      {/* ── Canvas Viewport ── */}
      <div
        id="canvas-viewport"
        ref={viewportRef}
        className={`canvas-viewport ${panning ? 'panning' : ''}`}
        style={{
          backgroundImage: gridCss.backgroundImage,
          backgroundSize: gridCss.backgroundSize,
          backgroundPosition: gridCss.backgroundPosition,
        }}
        onWheel={handleWheel}
        onContextMenu={handleContextMenu}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <div
          className="canvas-world"
          style={{
            transform: `translate(${cameraState.panX}px, ${cameraState.panY}px) scale(${cameraState.zoom})`,
          }}
        >
          {/* ── Wires ── */}
          <svg className="wire-layer" style={{ overflow: 'visible' }}>
            {wirePaths.map(w => w && (
              <path
                key={w.id}
                className={`wire-path ${w.isStale ? 'stale' : ''}`}
                d={w.d}
              />
            ))}
          </svg>

          {/* ── Cards ── */}
          {cards.map(card => (
            <div
              key={card.id}
              className={`card-node ${selectedIds.has(card.id) ? 'selected' : ''} ${staleIds.has(card.id) ? 'stale' : ''}`}
              style={{ left: card.x, top: card.y, width: card.width, zIndex: card.zIndex }}
            >
              <div className={`card-accent card-accent--${card.type}`} />
              <div className="card-header">
                <span className="card-type-badge">{CARD_LABELS[card.type]}</span>
                <span className="card-title">{card.title}</span>
              </div>
              <div className="card-body">{card.content}</div>
            </div>
          ))}
        </div>

        {/* ── Empty state ── */}
        {cards.length === 0 && (
          <div className="empty-state">
            <h2>Your canvas is empty</h2>
            <p>Click <strong>+ Create</strong> or press <strong>G</strong> to get started</p>
          </div>
        )}
      </div>

      {/* ── Context Menu ── */}
      {contextMenu && (
        <>
          <div className="ctx-backdrop" onClick={closeContextMenu} />
          <div
            className="ctx-menu"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <div className="ctx-menu-header">
              {contextMenu.targetCardId
                ? cards.find(c => c.id === contextMenu.targetCardId)?.title ?? 'Card'
                : 'Canvas'}
            </div>

            {contextMenu.targetCardId ? (
              /* ── Card context items ── */
              <>
                <button className="ctx-menu-item" onClick={() => {
                  console.log('Edit:', contextMenu.targetCardId)
                  closeContextMenu()
                }}>
                  <span className="ctx-icon">✏️</span> Edit Title
                </button>
                <button className="ctx-menu-item" onClick={handleCtxDuplicate}>
                  <span className="ctx-icon">📋</span> Duplicate
                </button>
                <button className="ctx-menu-item" onClick={() => {
                  console.log('Thread:', contextMenu.targetCardId)
                  closeContextMenu()
                }}>
                  <span className="ctx-icon">💬</span> Open Thread
                </button>
                <div className="ctx-menu-sep" />
                <button className="ctx-menu-item ctx-menu-item--danger" onClick={handleCtxDelete}>
                  <span className="ctx-icon">🗑️</span> Delete
                </button>
              </>
            ) : (
              /* ── Canvas context items ── */
              <>
                {(['source', 'lens', 'action', 'output'] as CardType[]).map(type => (
                  <button key={type} className="ctx-menu-item" onClick={() => handleCtxCreateHere(type)}>
                    <span className="create-menu-dot" style={{ background: CARD_COLORS[type] }} />
                    {type.charAt(0).toUpperCase() + type.slice(1)} Card
                  </button>
                ))}
                <div className="ctx-menu-sep" />
                <button className="ctx-menu-item" onClick={handleCtxFitView}>
                  <span className="ctx-icon">🔍</span> Fit to View
                </button>
              </>
            )}

            <div className="ctx-menu-hint">
              {contextMenu.targetCardId ? 'Right-click or G' : 'Right-click or G'}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
