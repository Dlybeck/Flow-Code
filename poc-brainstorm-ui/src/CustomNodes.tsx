import { Handle, Position, type NodeProps } from '@xyflow/react'

export type NodeData = {
  label: string
  expandable?: boolean
  /** Native tooltip (e.g. parse error detail on file nodes) */
  title?: string
  /** Secondary line (path, qname, user description, …) */
  subtitle?: string
  /** Technical label before overlay merge */
  rawLabel?: string
  /** Technical subtitle before overlay merge */
  rawSubtitle?: string
  onTest?: (e: React.MouseEvent) => void
  /** Flow map: uncertain calls hidden; number of omitted dashed edges from this node */
  hiddenUncertainCount?: number
}

function hint(expandable?: boolean) {
  if (!expandable) return null
  return <span className="node-hint">double-click to drill</span>
}

function TestBtn({ onTest }: { onTest?: (e: React.MouseEvent) => void }) {
  if (!onTest) return null
  return (
    <button
      type="button"
      className="node-test"
      title="Show node id and technical labels"
      onMouseDown={(e) => e.stopPropagation()}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={onTest}
    >
      Test
    </button>
  )
}

function Subtitle({ text }: { text?: string }) {
  if (!text) return null
  return <div className="node-subtitle">{text}</div>
}

function FlowHiddenUncertainBadge({ count }: { count?: number }) {
  if (!count || count < 1) return null
  const title =
    count === 1
      ? '1 call site in this function goes to something we do not show as its own box (often a library or decorator). Turn on “Show uncertain detail” in the header to see it.'
      : `${count} separate call sites in this function go to targets we do not show as their own boxes (e.g. one library constructor plus several decorators)—not “${count} functions,” just ${count} lines of code. Turn on “Show uncertain detail” to see each.`
  return (
    <span
      className="flow-hidden-badge"
      title={title}
      role="img"
      aria-label={title}
    >
      <span className="flow-hidden-badge-dot" aria-hidden />
    </span>
  )
}

export function SurfaceNode({ data, selected }: NodeProps) {
  const d = data as NodeData
  return (
    <div className={`rf-node surface ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label">{d.label}</span>
        <FlowHiddenUncertainBadge count={d.hiddenUncertainCount} />
        <TestBtn onTest={d.onTest} />
      </div>
      <Subtitle text={d.subtitle} />
      {hint(d.expandable)}
      <Handle type="source" position={Position.Bottom} className="h" />
    </div>
  )
}

export function FeatureNode({ data, selected }: NodeProps) {
  const d = data as NodeData
  return (
    <div className={`rf-node feature ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label">{d.label}</span>
        <FlowHiddenUncertainBadge count={d.hiddenUncertainCount} />
        <TestBtn onTest={d.onTest} />
      </div>
      <Subtitle text={d.subtitle} />
      {hint(d.expandable)}
      <Handle type="source" position={Position.Bottom} className="h" />
    </div>
  )
}

/** Execution IR boundary: static analysis stopped here (unresolved / not traced). */
export function BoundaryNode({ data, selected }: NodeProps) {
  const d = data as NodeData
  return (
    <div className={`rf-node boundary ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label">{d.label}</span>
        <TestBtn onTest={d.onTest} />
      </div>
      <Subtitle text={d.subtitle} />
      <span className="boundary-badge">uncertain</span>
      <Handle type="source" position={Position.Bottom} className="h" />
    </div>
  )
}
