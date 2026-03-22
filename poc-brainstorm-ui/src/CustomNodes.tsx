import { Handle, Position, type NodeProps } from '@xyflow/react'

export type NodeData = {
  label: string
  expandable?: boolean
  /** Native tooltip (e.g. parse error detail on file nodes) */
  title?: string
  /** Secondary line (path, qname, user description, …) */
  subtitle?: string
  /** Technical label before overlay merge (RAW + overlay mode) */
  rawLabel?: string
  /** Technical subtitle before overlay merge */
  rawSubtitle?: string
  onTest?: (e: React.MouseEvent) => void
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
      title="Mock: leaf = unit test; parent = smoke + child tests"
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

export function CapabilityNode({ data, selected }: NodeProps) {
  const d = data as NodeData
  return (
    <div className={`rf-node cap ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label">{d.label}</span>
        <TestBtn onTest={d.onTest} />
      </div>
      <Subtitle text={d.subtitle} />
      {hint(d.expandable)}
      <Handle type="source" position={Position.Bottom} className="h" />
    </div>
  )
}

export function SurfaceNode({ data, selected }: NodeProps) {
  const d = data as NodeData
  return (
    <div className={`rf-node surface ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label">{d.label}</span>
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
        <TestBtn onTest={d.onTest} />
      </div>
      <Subtitle text={d.subtitle} />
      {hint(d.expandable)}
      <Handle type="source" position={Position.Bottom} className="h" />
    </div>
  )
}

export function CodeNode({ data, selected }: NodeProps) {
  const d = data as NodeData
  return (
    <div
      className={`rf-node code ${selected ? 'selected' : ''}`}
      title={d.title ?? undefined}
    >
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label mono">{d.label}</span>
        <TestBtn onTest={d.onTest} />
      </div>
      <Subtitle text={d.subtitle} />
      <Handle type="source" position={Position.Bottom} className="h" />
    </div>
  )
}

export function FloatingNode({ data, selected }: NodeProps) {
  const d = data as NodeData
  return (
    <div className={`rf-node floating ${selected ? 'selected' : ''}`}>
      <div className="node-row">
        <span className="node-label mono small">{d.label}</span>
        <TestBtn onTest={d.onTest} />
      </div>
      <span className="float-badge">unlinked</span>
    </div>
  )
}
