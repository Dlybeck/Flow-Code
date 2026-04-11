import type React from 'react'
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
  /** Flow map: uncertain calls hidden; number of omitted dashed edges from this node */
  hiddenUncertainCount?: number
  /** Number of pending comments anchored to this node */
  commentCount?: number
  /** True when this node's file was modified by the last apply */
  isChanged?: boolean
  /** True when overlay re-annotation is in flight for this node */
  isAnnotating?: boolean
  /** True while AI is re-labeling all nodes — drives cascade scan animation */
  isRelabeling?: boolean
  /** Animation delay in seconds for the cascading scan effect (0 = top of graph) */
  scanDelay?: number
}

function hint(expandable?: boolean) {
  if (!expandable) return null
  return <span className="node-hint">double-click to drill</span>
}

function Subtitle({ text }: { text?: string }) {
  if (!text) return null
  return <div className="node-subtitle">{text}</div>
}

function CommentBadge({ count }: { count?: number }) {
  if (!count || count < 1) return null
  const label = count === 1 ? '1 pending comment' : `${count} pending comments`
  return (
    <span
      className="comment-node-badge"
      title={label}
      role="img"
      aria-label={label}
    >
      <span className="comment-node-badge-dot" aria-hidden />
    </span>
  )
}

function ChangedBadge({ active }: { active?: boolean }) {
  if (!active) return null
  return (
    <span
      className="changed-node-badge"
      title="Modified by last apply"
      role="img"
      aria-label="Changed"
    >
      <span className="changed-node-badge-dot" aria-hidden />
    </span>
  )
}

function AnnotatingBadge({ active }: { active?: boolean }) {
  if (!active) return null
  return (
    <span
      className="annotating-node-badge"
      title="Re-annotating…"
      role="img"
      aria-label="Annotating"
    >
      <span className="annotating-node-badge-pulse" aria-hidden />
    </span>
  )
}

function FlowHiddenUncertainBadge({ count }: { count?: number }) {
  if (!count || count < 1) return null
  const title =
    count === 1
      ? '1 call site in this function goes to something we do not show as its own box (often a library or decorator). Turn on "Show uncertain detail" in the header to see it.'
      : `${count} separate call sites in this function go to targets we do not show as their own boxes (e.g. one library constructor plus several decorators)—not "${count} functions," just ${count} lines of code. Turn on "Show uncertain detail" to see each.`
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

function scanStyle(d: NodeData): React.CSSProperties | undefined {
  if (!d.isRelabeling || d.scanDelay === undefined) return undefined
  return { '--node-scan-delay': `${d.scanDelay}s` } as React.CSSProperties
}

export function SurfaceNode({ data, selected }: NodeProps) {
  const d = data as NodeData
  return (
    <div
      className={`rf-node surface ${selected ? 'selected' : ''} ${d.isChanged ? 'node-changed' : ''} ${d.isRelabeling ? 'node-relabeling' : ''}`}
      style={scanStyle(d)}
    >
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label">{d.label}</span>
        <FlowHiddenUncertainBadge count={d.hiddenUncertainCount} />
        <CommentBadge count={d.commentCount} />
        <ChangedBadge active={d.isChanged && !d.isAnnotating} />
        <AnnotatingBadge active={d.isAnnotating} />
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
    <div
      className={`rf-node feature ${selected ? 'selected' : ''} ${d.isChanged ? 'node-changed' : ''} ${d.isRelabeling ? 'node-relabeling' : ''}`}
      style={scanStyle(d)}
    >
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label">{d.label}</span>
        <FlowHiddenUncertainBadge count={d.hiddenUncertainCount} />
        <CommentBadge count={d.commentCount} />
        <ChangedBadge active={d.isChanged && !d.isAnnotating} />
        <AnnotatingBadge active={d.isAnnotating} />
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
    <div
      className={`rf-node boundary ${selected ? 'selected' : ''} ${d.isChanged ? 'node-changed' : ''} ${d.isRelabeling ? 'node-relabeling' : ''}`}
      style={scanStyle(d)}
    >
      <Handle type="target" position={Position.Top} className="h" />
      <div className="node-row">
        <span className="node-label">{d.label}</span>
        <CommentBadge count={d.commentCount} />
        <ChangedBadge active={d.isChanged} />
      </div>
      <Subtitle text={d.subtitle} />
      <span className="boundary-badge">uncertain</span>
      <Handle type="source" position={Position.Bottom} className="h" />
    </div>
  )
}
