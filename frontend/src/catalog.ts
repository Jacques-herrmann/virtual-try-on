// Catalogue Vinted (arbre des catégories, grilles de tailles) côté interface.

import type { CategoryNode, VintedCatalog } from './types'

export interface CascadeOption {
  label: string
  value?: string
  children?: CascadeOption[]
}

/**
 * Options de `CascadeSelect` : un groupe a `children`, une feuille a `value` et pas de
 * `children` (PrimeVue reconnaît un groupe à la présence de la clé).
 */
export function cascadeOptions(nodes: CategoryNode[]): CascadeOption[] {
  return nodes.map((node) =>
    node.children.length
      ? { label: node.label, children: cascadeOptions(node.children) }
      : { label: node.label, value: String(node.id) },
  )
}

export function depth(nodes: CategoryNode[]): number {
  return nodes.length ? 1 + Math.max(...nodes.map((n) => depth(n.children))) : 0
}

function find(
  nodes: CategoryNode[],
  id: string,
  parents: string[] = [],
): { node: CategoryNode; path: string[] } | null {
  for (const node of nodes) {
    const path = [...parents, node.label]
    if (String(node.id) === id) return { node, path }
    const found = find(node.children, id, path)
    if (found) return found
  }
  return null
}

export function categoryPath(
  catalog: VintedCatalog | null,
  id: string | null | undefined,
): string[] | null {
  if (!catalog || !id) return null
  return find(catalog.catalog, id)?.path ?? null
}

export function isLeaf(catalog: VintedCatalog | null, id: string | null | undefined): boolean {
  if (!catalog || !id) return false
  const found = find(catalog.catalog, id)
  return !!found && !found.node.children.length
}

export function sizesFor(catalog: VintedCatalog | null, id: string | null | undefined): string[] {
  if (!catalog || !id) return []
  const group = find(catalog.catalog, id)?.node.size_group
  return group ? (catalog.size_groups[group] ?? []) : []
}
