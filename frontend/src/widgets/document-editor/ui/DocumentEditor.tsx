import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'

import type { SelectionContext, SelectionContextBlock, SelectionTarget } from '@/entities/document'
import { resolveAssetUrls } from '../model/canonical-html'

interface DocumentEditorProps {
  html: string
  assetUrls: Record<string, string>
  onSelectionChange?: (context: SelectionContext) => void
}

export interface DocumentEditorHandle {
  scrollToHeading: (blockId: string | null, headingIndex: number, label?: string) => void
  clearSelection: () => void
}

function compactText(value: string, max = 220) {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

function blockId(element: Element): string | null {
  return element.getAttribute('data-block-id') || element.getAttribute('data-b')
}

function closestBlock(element: Element | null): Element | null {
  return element?.closest('.block, [data-block-id], [data-b]') || null
}

function ensureBlockIds(doc: Document) {
  let counter = 0
  doc.querySelectorAll<HTMLElement>('.block, section.page').forEach((element) => {
    if (blockId(element)) return
    counter += 1
    element.setAttribute('data-block-id', `block-${String(counter).padStart(4, '0')}`)
    element.setAttribute('data-block-type', element.matches('section.page') ? 'page' : 'block')
  })
}

function assetIdForImage(image: Element, assetUrls: Record<string, string>) {
  const source = image.getAttribute('src')
  if (!source) return undefined
  const normalizedSource = new URL(source, window.location.href).href
  return Object.entries(assetUrls).find(([, url]) => new URL(url, window.location.href).href === normalizedSource)?.[0]
}

function assetFormatForImage(image: Element): string | undefined {
  const source = image.getAttribute('src') || ''
  if (source.startsWith('data:image/svg+xml')) return 'SVG'
  const pathname = source.split(/[?#]/, 1)[0].toLowerCase()
  if (pathname.endsWith('.svg')) return 'SVG'
  if (pathname.endsWith('.png')) return 'PNG'
  if (pathname.endsWith('.jpg') || pathname.endsWith('.jpeg')) return 'JPEG'
  if (pathname.endsWith('.webp')) return 'WebP'
  return undefined
}

function inlineSvgIndex(svg: Element, block: Element | null): number | undefined {
  if (svg.tagName.toLowerCase() !== 'svg' || !block) return undefined
  const index = Array.from(block.querySelectorAll<Element>('svg')).indexOf(svg)
  return index >= 0 ? index : undefined
}

function selectionContext(frame: HTMLIFrameElement, assetUrls: Record<string, string>, forced?: Element | null): SelectionContext {
  const doc = frame.contentDocument
  if (!doc) return { scope: 'document', blockIds: [], blocks: [], selectedText: '', textPreview: '', characterCount: 0, target: { kind: 'document' } }
  const selection = doc.getSelection()
  const selected = selection && !selection.isCollapsed ? selection.toString() : ''
  const range = selection && !selection.isCollapsed ? selection.getRangeAt(0) : null
  const elements = Array.from(doc.body.querySelectorAll('p,div,li,td,th,figcaption,h1,h2,h3,h4,section,article,img,svg'))
  const forcedBlock = closestBlock(forced || null)
  const targets = forced ? [forcedBlock || forced] : elements.filter((element) => {
    if (!range) return false
    try { return range.intersectsNode(element) } catch { return false }
  })
  const unique = new Map<string, SelectionContextBlock>()
  targets.forEach((element) => {
    const id = blockId(element) || blockId(element.closest('[data-block-id], [data-b]') || element)
    if (!id || unique.has(id)) return
    unique.set(id, { blockId: id, blockType: element.tagName.toLowerCase(), textPreview: compactText(element.textContent || element.getAttribute('alt') || '') })
  })
  const blocks = Array.from(unique.values())
  const normalizedSelected = selected.replace(/\s+/g, ' ').trim()
  const preview = compactText(normalizedSelected || blocks.map((item) => item.textPreview).join(' '))
  const forcedImage = forced?.tagName.toLowerCase() === 'img' ? forced : null
  const forcedSvg = forced?.tagName.toLowerCase() === 'svg' ? forced : null
  const selectedBlockId = blocks[0]?.blockId
  const selectedBlock = forcedBlock || null
  let target: SelectionTarget = { kind: 'document' }
  if (forcedImage) {
    target = {
      kind: 'image',
      blockId: selectedBlockId,
      assetId: assetIdForImage(forcedImage, assetUrls),
      assetFormat: assetFormatForImage(forcedImage),
    }
  } else if (forcedSvg) {
    target = {
      kind: 'image',
      blockId: selectedBlockId,
      assetFormat: 'SVG',
      svgIndex: inlineSvgIndex(forcedSvg, selectedBlock),
    }
  } else if (selected) {
    target = { kind: 'text', blockId: selectedBlockId, selectedText: normalizedSelected.slice(0, 8000) }
  } else if (selectedBlockId) {
    target = { kind: 'block', blockId: selectedBlockId }
  }
  return {
    scope: selected ? 'selection' : blocks.length ? 'current-block' : 'document',
    blockIds: blocks.map((item) => item.blockId),
    blocks,
    selectedText: normalizedSelected.slice(0, 8000),
    textPreview: preview,
    characterCount: preview.length,
    target,
  }
}

export const DocumentEditor = forwardRef<DocumentEditorHandle, DocumentEditorProps>(function DocumentEditor({
  html,
  assetUrls,
  onSelectionChange,
}, ref) {
  const frameRef = useRef<HTMLIFrameElement>(null)
  const pointerSelectionRef = useRef<Element | null>(null)
  const [loaded, setLoaded] = useState(false)

  useImperativeHandle(ref, () => ({
    scrollToHeading(blockIdValue, headingIndex, label) {
      const doc = frameRef.current?.contentDocument
      if (!doc) return
      const target = blockIdValue
        ? doc.querySelector(`[data-block-id="${CSS.escape(blockIdValue)}"], [data-b="${CSS.escape(blockIdValue)}"], #${CSS.escape(blockIdValue)}`)
        : null
      const headings = Array.from(doc.querySelectorAll('h1, h2, h3, h4, .block.h, .block.sub'))
      const normalizedLabel = label?.replace(/[.·…\s]+/g, ' ').trim().toLocaleLowerCase()
      const byLabel = normalizedLabel
        ? headings.find((heading) => (heading.textContent || '').replace(/[.·…\s]+/g, ' ').trim().toLocaleLowerCase() === normalizedLabel)
        : null
      const fallback = byLabel || headings[headingIndex]
      ;(target || fallback)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      const highlighted = target || fallback
      if (!highlighted) return
      highlighted.setAttribute('data-outline-target', 'true')
      window.setTimeout(() => highlighted.removeAttribute('data-outline-target'), 1400)
    },
    clearSelection() {
      const doc = frameRef.current?.contentDocument
      doc?.querySelectorAll('[data-ai-selected]').forEach((node) => node.removeAttribute('data-ai-selected'))
    },
  }), [])

  const prepareNavigation = (doc: Document) => {
    const headings = Array.from(doc.querySelectorAll('h1, h2, h3, h4, .block.h, .block.sub'))
    headings.forEach((heading, index) => {
      const id = heading.getAttribute('data-block-id') || heading.id || `document-heading-${index + 1}`
      if (!heading.id) heading.id = id
    })
    doc.querySelectorAll<HTMLAnchorElement>('a[href^="#"]').forEach((link) => {
      const targetId = decodeURIComponent(link.getAttribute('href')?.slice(1) || '')
      if (!targetId) return
      let target: Element | null = doc.getElementById(targetId) || doc.querySelector(`[data-block-id="${CSS.escape(targetId)}"], [data-b="${CSS.escape(targetId)}"]`)
      if (!target) {
        const linkLabel = (link.textContent || '').replace(/[.·…\s]+/g, ' ').trim().toLocaleLowerCase()
        target = headings.find((heading) => (heading.textContent || '').replace(/[.·…\s]+/g, ' ').trim().toLocaleLowerCase() === linkLabel) || null
        if (target) link.setAttribute('href', `#${target.id}`)
      }
      if (target && !target.id) target.id = targetId
    })
  }

  useEffect(() => {
    const frame = frameRef.current
    if (!frame || !loaded) return
    const doc = frame.contentDocument
    if (!doc) return
    ensureBlockIds(doc)
    prepareNavigation(doc)
    const clear = () => doc.querySelectorAll('[data-ai-selected]').forEach((node) => node.removeAttribute('data-ai-selected'))
    const selectElement = (element: Element) => { clear(); element.setAttribute('data-ai-selected', 'true'); onSelectionChange?.(selectionContext(frame, assetUrls, element)) }
    const onClick = (event: Event) => {
      const target = event.target as Element | null
      const element = target?.closest('img, p, li, td, th, figcaption, h1, h2, h3, h4, svg, .block, [data-block-id], [data-b]')
      if (element) selectElement(element)
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Element | null
      const element = target?.closest('img, svg, .block, [data-block-id], [data-b]')
      pointerSelectionRef.current = element || null
      if (element) selectElement(element)
    }
    const onMouseUp = () => window.setTimeout(() => {
      const pointerSelection = pointerSelectionRef.current
      pointerSelectionRef.current = null
      if (pointerSelection?.matches('img, svg')) return
      const context = selectionContext(frame, assetUrls)
      if (context.blockIds.length || context.selectedText) { clear(); onSelectionChange?.(context) }
    }, 0)
    const onLinkClick = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest<HTMLAnchorElement>('a[href^="#"]')
      if (!link) return
      const targetId = decodeURIComponent(link.getAttribute('href')?.slice(1) || '')
      const target = doc.getElementById(targetId) || doc.querySelector(`[data-block-id="${CSS.escape(targetId)}"], [data-b="${CSS.escape(targetId)}"]`)
      if (!target) return
      event.preventDefault()
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    doc.addEventListener('click', onClick)
    doc.addEventListener('pointerdown', onPointerDown)
    doc.addEventListener('mouseup', onMouseUp)
    doc.addEventListener('click', onLinkClick, true)
    onSelectionChange?.(selectionContext(frame, assetUrls))
    return () => { doc.removeEventListener('click', onClick); doc.removeEventListener('pointerdown', onPointerDown); doc.removeEventListener('mouseup', onMouseUp); doc.removeEventListener('click', onLinkClick, true) }
  }, [assetUrls, loaded, onSelectionChange])

  useEffect(() => {
    const doc = frameRef.current?.contentDocument
    if (!doc) return
    const styleHost = doc.head || doc.documentElement || doc.body
    if (!styleHost) return
    const style = doc.createElement('style')
    style.textContent = [
      'html,body{margin:0 !important;min-height:100%;background:#e9e4df !important}',
      'body{padding:24px !important}',
      'body > article, body > .document-theme, body > .manual-document, body > .sheet{margin-left:auto !important;margin-right:auto !important;background:#fff !important;box-shadow:0 2px 14px rgb(23 23 23 / 14%),0 0 0 1px rgb(229 225 220 / 90%) !important}',
      '[data-ai-selected]{outline:2px solid #f36f21 !important;outline-offset:2px;cursor:crosshair}',
      '[data-outline-target]{outline:2px solid #d95d16 !important;outline-offset:4px}',
      'img{cursor:crosshair}',
    ].join('')
    styleHost.appendChild(style)
  }, [loaded])

  return (
    <div className="workbench-editor min-h-[calc(100vh-64px)] bg-app-shell">
      <div className="flex justify-center overflow-auto p-6">
        <iframe ref={frameRef} className="min-h-[calc(100vh-64px)] w-full border-0 bg-white shadow-[0_1px_8px_rgb(0_0_0_/_14%)]" sandbox="allow-same-origin" srcDoc={resolveAssetUrls(html, assetUrls)} onLoad={() => setLoaded(true)} title="HTML-документ" />
      </div>
    </div>
  )
})
