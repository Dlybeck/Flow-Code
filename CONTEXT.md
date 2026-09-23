# Flow-Code Visualization Language

Flow-Code presents source-grounded program behavior through recursively
expandable flows. This glossary defines the stable product concepts independently
of any particular renderer.

## Language

**Behavior**:
One understandable execution story connecting a root node to one or more leaf
nodes.

**Root node**:
The visible boundary where execution enters a behavior or an expanded child
flow. At the top level it represents a trigger; inside a seed node it represents
entry from the parent flow.
_Avoid_: Entrypoint, source

**Node**:
One visible action in a behavior. A node may be backed by one or more
source-grounded program elements.
_Avoid_: Function, file

**Seed node**:
A node containing a child behavior that the viewer can expand. Expansion reveals
more detail about the same action rather than a separate unrelated execution.
_Avoid_: Branch

**Focused view**:
The child behavior shown after entering a seed node. The selected seed becomes
the focused view's root node while retaining a navigable path back to its parent.
_Avoid_: Inline expansion

**Leaf node**:
The visible boundary where execution leaves a behavior or expanded child flow.
At the top level it represents an observable outcome; inside a seed node it
returns control or data to the parent flow.
_Avoid_: Call-graph leaf, dead end

**Branch**:
An alternate execution path selected by program behavior. A branch is distinct
from a seed node's expandable detail.
_Avoid_: Expansion

**Evidence graph**:
The complete source-grounded model from which visible behaviors and nodes are
projected. It preserves canonical source identity when one program element
appears in several behaviors.
_Avoid_: View, diagram
