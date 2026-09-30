import Link from '@tiptap/extension-link'
import TextAlign from '@tiptap/extension-text-align'
import Underline from '@tiptap/extension-underline'
import StarterKit from '@tiptap/starter-kit'
import { EditorContent, useEditor } from '@tiptap/react'
import { useEffect, useRef, useState } from 'react'

import { saveDocument } from '@/entities/document'
import type { SelectionContext, SelectionContextBlock } from '@/entities/document'
import { ApiError } from '@/shared/api/client'
import {
  ManualFigure,
  ManualCaption,
  ManualCover,
  ManualCoverBody,
  ManualCoverHero,
  ManualCoverOrange,
  ManualFooter,
  ManualFooterPage,
  ManualFooterVersion,
  ManualHeader,
  ManualHeaderMark,
  ManualHeaderSites,
  ManualHeaderTitle,
  ManualBulletList,
  ManualHeading,
  ManualImage,
  ManualFigureFrame,
  ManualGallery,
  ManualListItem,
  ManualParagraph,
  ManualOrderedList,
  ManualNote,
  ManualNoteBody,
  ManualSection,
  ManualForm,
  ManualFormColumns,
  ManualWarning,
  ManualWarningBody,
  ManualTable,
  ManualTableCell,
  ManualTableHeader,
  ManualTableRow,
  ManualLegend,
  ManualLegendItem,
  ManualLegendLabel,
  ManualToc,
  ManualTocPage,
  ManualTocRow,
  ManualTocTitle,
  ManualPage,
  ManualPageBreak,
  StableBlockIds,
  AiBlockDecorations,
  aiBlockDecorationsKey,
} from '../model/extensions'
import styles from './document-editor.module.css'

interface DocumentEditorProps {
  documentId: string
  revision: number
  html: string
  assetUrls: Record<string, string>
  editable?: boolean
  onRevisionChange?: (revision: number) => void
  onSaveStateChange?: (state: 'saved' | 'changed' | 'saving' | 'error') => void
  onSaveError?: (message: string | null) => void
  selectionBlockIds?: string[]
  highlightBlockIds?: string[]
  onSelectionChange?: (context: SelectionContext) => void
}

function resolveAssetUrls(html: string, assetUrls: Record<string, string>) {
  return html.replace(/asset:\/\/([0-9a-f-]{36})/gi, (reference, assetId: string) => assetUrls[assetId] ?? reference)
}

function documentShell(html: string) {
  const match = html.match(/^\s*(<article\b[^>]*>)([\s\S]*)(<\/article>)\s*$/i)
  return match
    ? { opening: match[1], content: match[2], closing: match[3] }
    : { opening: '<article class="manual">', content: html, closing: '</article>' }
}

interface EditorDocument {
  content: string
  header: string
  footer: string
}

function toEditorPages(html: string): EditorDocument {
  const container = window.document.createElement('div')
  container.innerHTML = html
  const headerElement = container.querySelector(':scope > .manual-header')
  const footerElement = container.querySelector(':scope > .manual-footer')
  const header = headerElement?.outerHTML ?? ''
  const footer = footerElement?.outerHTML ?? ''
  headerElement?.remove()
  footerElement?.remove()

  const pages: string[][] = [[]]
  for (const child of Array.from(container.children)) {
    if (child.classList.contains('manual-page-break')) {
      pages.push([])
    } else {
      pages.at(-1)?.push(child.outerHTML)
    }
  }

  return {
    header,
    footer,
    content: pages
      .filter((page, index) => page.length > 0 || index === 0)
      .map((page, index) => {
        const repeatedHeader = index === 0 && page.some((item) => item.includes('manual-cover'))
          ? ''
          : header
        const numberedFooter = repeatedHeader === '' && index === 0
          ? ''
          : footer.replace(
          /(<span\b[^>]*class="[^"]*manual-footer__page[^"]*"[^>]*>)[\s\S]*?(<\/span>)/i,
          `$1${index + 1}$2`,
          )
        return `<section class="manual-page" data-page-number="${index + 1}">${repeatedHeader}${page.join('')}${numberedFooter}</section>`
      })
      .join(''),
  }
}

function fromEditorPages(html: string, chrome: Pick<EditorDocument, 'header' | 'footer'>) {
  const container = window.document.createElement('div')
  container.innerHTML = html
  const pages = Array.from(container.querySelectorAll(':scope > .manual-page'))
  const content = pages.map((page) => {
    page.querySelectorAll(':scope > .manual-header, :scope > .manual-footer').forEach((node) => node.remove())
    return page.innerHTML
  })
  return `${chrome.header}${chrome.footer}${content
    .map((page, index) => index === 0
      ? page
      : `<div class="manual-page-break" data-block-id="b_page_${String(index + 1).padStart(3, '0')}" data-block-type="page-break"></div>${page}`)
    .join('')}`
}

function restoreAssetReferences(html: string, assetUrls: Record<string, string>) {
  const container = window.document.createElement('div')
  container.innerHTML = html
  const urlToAsset = new Map<string, string>()
  Object.entries(assetUrls).forEach(([assetId, url]) => {
    urlToAsset.set(url, assetId)
    urlToAsset.set(url.replaceAll('&', '&amp;'), assetId)
    try {
      urlToAsset.set(new URL(url).href, assetId)
    } catch {
      // Keep the literal URL variants above when the browser cannot parse it.
    }
  })
  container.querySelectorAll('img[src]').forEach((image) => {
    const src = image.getAttribute('src') ?? ''
    const assetId = urlToAsset.get(src)
    if (assetId) image.setAttribute('src', `asset://${assetId}`)
  })
  return container.innerHTML
}

function normalizeCanonicalHtml(html: string) {
  const container = window.document.createElement('div')
  container.innerHTML = html
  container.querySelectorAll('[data-ai-context], [data-ai-highlight]')
    .forEach((element) => {
      element.removeAttribute('data-ai-context')
      element.removeAttribute('data-ai-highlight')
    })
  // Tiptap adds editor-only table sizing markup. Canonical column widths live in colwidth.
  container.querySelectorAll('colgroup').forEach((element) => element.remove())
  container.querySelectorAll('table[style], tbody[style], tr[style], th[style], td[style]')
    .forEach((element) => element.removeAttribute('style'))
  const selector = [
    'p', 'h1', 'h2', 'h3', 'h4', 'section', 'div.manual-page-break',
    'ul', 'ol', 'li', 'table', 'tr', 'th', 'td', 'figure', 'figcaption',
  ].join(',')
  container.querySelectorAll(selector).forEach((element) => {
    if (element.closest('header.manual-header, footer.manual-footer')) return
    if (!element.hasAttribute('data-block-id')) {
      element.setAttribute('data-block-id', `b_${crypto.randomUUID()}`)
    }
    if (!element.hasAttribute('data-block-type')) {
      element.setAttribute('data-block-type', element.tagName.toLowerCase())
    }
  })
  return container.innerHTML
}

function saveErrorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return 'Неизвестная ошибка сервера'
  if (typeof error.details === 'object' && error.details && 'detail' in error.details) {
    const detail = (error.details as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return `Сервер вернул ошибку ${error.status}`
}

function compactText(text: string, maxLength = 220) {
  const compacted = text.replace(/\s+/g, ' ').trim()
  return compacted.length > maxLength ? `${compacted.slice(0, maxLength - 1)}…` : compacted
}

function selectedContext(editor: NonNullable<ReturnType<typeof useEditor>>): SelectionContext {
  const { doc, selection } = editor.state
  const blocks = new Map<string, SelectionContextBlock>()
  doc.nodesBetween(selection.from, selection.to, (node) => {
    const blockId = node.attrs.blockId
    if (node.isBlock && typeof blockId === 'string' && blockId) {
      blocks.set(blockId, {
        blockId,
        blockType: node.type.name,
        textPreview: compactText(node.textContent),
      })
    }
  })
  if (!blocks.size) {
    for (let depth = selection.$from.depth; depth >= 0; depth -= 1) {
      const node = selection.$from.node(depth)
      const blockId = node.attrs.blockId
      if (node.isBlock && typeof blockId === 'string' && blockId) {
        blocks.set(blockId, {
          blockId,
          blockType: node.type.name,
          textPreview: compactText(node.textContent),
        })
        break
      }
    }
  }
  const selectedText = selection.empty ? '' : compactText(doc.textBetween(selection.from, selection.to, ' '))
  const blockList = Array.from(blocks.values())
  const fallbackPreview = blockList.map((block) => block.textPreview).filter(Boolean).join(' ')
  const textPreview = compactText(selectedText || fallbackPreview)
  return {
    scope: selection.empty && blockList.length ? 'current-block' : blockList.length ? 'selection' : 'document',
    blockIds: blockList.map((block) => block.blockId),
    blocks: blockList,
    selectedText,
    textPreview,
    characterCount: (selectedText || fallbackPreview).length,
  }
}

export function DocumentEditor({
  documentId,
  revision,
  html,
  assetUrls,
  editable = true,
  onRevisionChange,
  onSaveStateChange,
  onSaveError,
  selectionBlockIds = [],
  highlightBlockIds = [],
  onSelectionChange,
}: DocumentEditorProps) {
  const [saveState, setSaveState] = useState<'saved' | 'changed' | 'saving' | 'error'>('saved')
  const [tablePickerOpen, setTablePickerOpen] = useState(false)
  const [tableSize, setTableSize] = useState({ rows: 3, cols: 3 })
  const revisionRef = useRef(revision)
  const shellRef = useRef(documentShell(html))
  const editorDocumentRef = useRef(
    toEditorPages(resolveAssetUrls(shellRef.current.content, assetUrls)),
  )
  const changeSequenceRef = useRef(0)
  const savedSequenceRef = useRef(0)
  const savingRef = useRef(false)
  const acceptUpdatesRef = useRef(false)
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: false,
        paragraph: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
      }),
      StableBlockIds,
      AiBlockDecorations,
      ManualParagraph,
      ManualHeading,
      ManualHeader,
      ManualHeaderMark,
      ManualHeaderTitle,
      ManualHeaderSites,
      ManualFooter,
      ManualFooterPage,
      ManualFooterVersion,
      ManualCover,
      ManualCoverOrange,
      ManualCoverHero,
      ManualCoverBody,
      ManualToc,
      ManualTocRow,
      ManualTocTitle,
      ManualTocPage,
      ManualLegend,
      ManualLegendItem,
      ManualLegendLabel,
      ManualPage,
      ManualPageBreak,
      ManualBulletList,
      ManualOrderedList,
      ManualListItem,
      ManualSection,
      ManualGallery,
      ManualFigureFrame,
      ManualNote,
      ManualNoteBody,
      ManualForm,
      ManualFormColumns,
      ManualWarning,
      ManualWarningBody,
      ManualFigure,
      ManualCaption,
      ManualImage.configure({ allowBase64: false }),
      Link.configure({ openOnClick: false }),
      Underline,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      ManualTable.configure({ resizable: true }),
      ManualTableRow,
      ManualTableHeader,
      ManualTableCell,
    ],
    content: editorDocumentRef.current.content,
    immediatelyRender: false,
    editable,
    onUpdate: () => {
      if (!acceptUpdatesRef.current) return
      changeSequenceRef.current += 1
      setSaveState('changed')
    },
    onSelectionUpdate: ({ editor: selectedEditor }) => {
      onSelectionChange?.(selectedContext(selectedEditor))
    },
  })

  useEffect(() => {
    editor?.setEditable(editable)
  }, [editable, editor])

  useEffect(() => {
    if (!editor) return
    acceptUpdatesRef.current = false
    const frame = window.requestAnimationFrame(() => {
      acceptUpdatesRef.current = true
    })
    return () => window.cancelAnimationFrame(frame)
  }, [editor])

  useEffect(() => {
    if (!editor || revisionRef.current === revision) return
    revisionRef.current = revision
    shellRef.current = documentShell(html)
    editorDocumentRef.current = toEditorPages(resolveAssetUrls(shellRef.current.content, assetUrls))
    acceptUpdatesRef.current = false
    editor.commands.setContent(editorDocumentRef.current.content, false)
    window.requestAnimationFrame(() => {
      acceptUpdatesRef.current = true
    })
    setSaveState('saved')
  }, [assetUrls, editor, html, revision])

  useEffect(() => {
    onSaveStateChange?.(saveState)
  }, [onSaveStateChange, saveState])

  useEffect(() => {
    if (!editor) return
    onSelectionChange?.(selectedContext(editor))
  }, [editor, onSelectionChange, revision])

  useEffect(() => {
    if (!editor) return
    editor.view.dispatch(
      editor.state.tr.setMeta(aiBlockDecorationsKey, {
        contextBlockIds: selectionBlockIds,
        highlightBlockIds,
      }),
    )
  }, [editor, highlightBlockIds, selectionBlockIds])

  useEffect(() => {
    if (!editor || saveState !== 'changed') return
    const timeout = window.setTimeout(async () => {
      if (savingRef.current) return
      savingRef.current = true
      try {
        do {
          const savingSequence = changeSequenceRef.current
          setSaveState('saving')
          const unpagedHtml = fromEditorPages(editor.getHTML(), editorDocumentRef.current)
          const editorHtml = normalizeCanonicalHtml(restoreAssetReferences(unpagedHtml, assetUrls))
          const canonicalHtml = `${shellRef.current.opening}${editorHtml}${shellRef.current.closing}`
          const result = await saveDocument(documentId, revisionRef.current, canonicalHtml)
          revisionRef.current = result.revision
          savedSequenceRef.current = savingSequence
          onSaveError?.(null)
          onRevisionChange?.(result.revision)
        } while (changeSequenceRef.current > savedSequenceRef.current)
        setSaveState('saved')
      } catch (error) {
        setSaveState('error')
        onSaveError?.(saveErrorMessage(error))
      } finally {
        savingRef.current = false
      }
    }, 1200)
    return () => window.clearTimeout(timeout)
  }, [assetUrls, documentId, editor, onRevisionChange, onSaveError, saveState])

  if (!editor) return null

  return (
    <div className={styles.workspace}>
      <div className={styles.toolbar} role="toolbar" aria-label="Форматирование">
        <div className={styles.toolGroup}>
          <select
            aria-label="Стиль абзаца"
            disabled={!editable}
            value={
              editor.isActive('heading', { level: 1 }) ? 'h1'
                : editor.isActive('heading', { level: 2 }) ? 'h2'
                  : editor.isActive('heading', { level: 3 }) ? 'h3'
                    : 'p'
            }
            onChange={(event) => {
              const value = event.target.value
              if (value === 'p') editor.chain().focus().setParagraph().run()
              else editor.chain().focus().setHeading({ level: Number(value.slice(1)) as 1 | 2 | 3 }).run()
            }}
          >
            <option value="p">Обычный текст</option>
            <option value="h1">Заголовок 1</option>
            <option value="h2">Заголовок 2</option>
            <option value="h3">Заголовок 3</option>
          </select>
        </div>
        <div className={styles.toolGroup}>
          <button className={styles.bold} type="button" title="Жирный (⌘B)" aria-label="Жирный" disabled={!editable} aria-pressed={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}>B</button>
          <button className={styles.italic} type="button" title="Курсив (⌘I)" aria-label="Курсив" disabled={!editable} aria-pressed={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}>I</button>
          <button className={styles.underline} type="button" title="Подчёркивание (⌘U)" aria-label="Подчёркивание" disabled={!editable} aria-pressed={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}>U</button>
        </div>
        <div className={styles.toolGroup}>
          <button type="button" title="Маркированный список" aria-label="Маркированный список" disabled={!editable} aria-pressed={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}>•≡</button>
          <button type="button" title="Нумерованный список" aria-label="Нумерованный список" disabled={!editable} aria-pressed={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}>1≡</button>
        </div>
        <div className={styles.toolGroup}>
          <button className={styles.alignLeft} type="button" title="По левому краю" aria-label="По левому краю" disabled={!editable} aria-pressed={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()}>≡</button>
          <button className={styles.alignCenter} type="button" title="По центру" aria-label="По центру" disabled={!editable} aria-pressed={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()}>≡</button>
          <button className={styles.alignRight} type="button" title="По правому краю" aria-label="По правому краю" disabled={!editable} aria-pressed={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()}>≡</button>
          <button type="button" title="По ширине" aria-label="По ширине" disabled={!editable} aria-pressed={editor.isActive({ textAlign: 'justify' })} onClick={() => editor.chain().focus().setTextAlign('justify').run()}>☰</button>
        </div>
        <div className={`${styles.toolGroup} ${styles.tableControl}`}>
          <button
            type="button"
            title="Вставить таблицу"
            aria-label="Вставить таблицу"
            aria-expanded={tablePickerOpen}
            disabled={!editable}
            onClick={() => setTablePickerOpen((open) => !open)}
          >
            ▦
          </button>
          {tablePickerOpen && (
            <div className={styles.tablePicker}>
              <strong>{tableSize.cols} × {tableSize.rows}</strong>
              <div className={styles.tableGrid}>
                {Array.from({ length: 25 }, (_, index) => {
                  const row = Math.floor(index / 5) + 1
                  const col = (index % 5) + 1
                  const active = row <= tableSize.rows && col <= tableSize.cols
                  return (
                    <button
                      key={`${row}-${col}`}
                      type="button"
                      aria-label={`Таблица ${col} на ${row}`}
                      data-active={active}
                      onMouseEnter={() => setTableSize({ rows: row, cols: col })}
                      onFocus={() => setTableSize({ rows: row, cols: col })}
                      onClick={() => {
                        editor.chain().focus().insertTable({ rows: row, cols: col, withHeaderRow: true }).run()
                        setTablePickerOpen(false)
                      }}
                    />
                  )
                })}
              </div>
            </div>
          )}
        </div>
        <div className={`${styles.toolGroup} ${styles.historyTools}`}>
          <button type="button" title="Отменить (⌘Z)" aria-label="Отменить" disabled={!editable || !editor.can().chain().focus().undo().run()} onClick={() => editor.chain().focus().undo().run()}>↶</button>
          <button type="button" title="Повторить (⇧⌘Z)" aria-label="Повторить" disabled={!editable || !editor.can().chain().focus().redo().run()} onClick={() => editor.chain().focus().redo().run()}>↷</button>
        </div>
      </div>
      <div className={styles.canvas}>
        <EditorContent className={styles.document} editor={editor} />
      </div>
    </div>
  )
}
