import Link from '@tiptap/extension-link'
import TextAlign from '@tiptap/extension-text-align'
import Underline from '@tiptap/extension-underline'
import StarterKit from '@tiptap/starter-kit'
import { EditorContent, useEditor } from '@tiptap/react'
import { useEffect, useRef, useState } from 'react'

import { saveDocument } from '@/entities/document'
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
  return Object.entries(assetUrls).reduce(
    (result, [assetId, url]) => {
      const reference = `asset://${assetId}`
      return result
        .split(url)
        .join(reference)
        .split(url.replaceAll('&', '&amp;'))
        .join(reference)
    },
    html,
  )
}

export function DocumentEditor({
  documentId,
  revision,
  html,
  assetUrls,
  editable = true,
  onRevisionChange,
  onSaveStateChange,
}: DocumentEditorProps) {
  const [saveState, setSaveState] = useState<'saved' | 'changed' | 'saving' | 'error'>('saved')
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
    if (!editor || saveState !== 'changed') return
    const timeout = window.setTimeout(async () => {
      if (savingRef.current) return
      savingRef.current = true
      try {
        do {
          const savingSequence = changeSequenceRef.current
          setSaveState('saving')
          const unpagedHtml = fromEditorPages(editor.getHTML(), editorDocumentRef.current)
          const editorHtml = restoreAssetReferences(unpagedHtml, assetUrls)
          const canonicalHtml = `${shellRef.current.opening}${editorHtml}${shellRef.current.closing}`
          const result = await saveDocument(documentId, revisionRef.current, canonicalHtml)
          revisionRef.current = result.revision
          savedSequenceRef.current = savingSequence
          onRevisionChange?.(result.revision)
        } while (changeSequenceRef.current > savedSequenceRef.current)
        setSaveState('saved')
      } catch {
        setSaveState('error')
      } finally {
        savingRef.current = false
      }
    }, 1200)
    return () => window.clearTimeout(timeout)
  }, [assetUrls, documentId, editor, onRevisionChange, saveState])

  if (!editor) return null

  return (
    <div className={styles.workspace}>
      <div className={styles.toolbar} role="toolbar" aria-label="Форматирование">
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
        <button type="button" disabled={!editable} aria-pressed={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}>Жирный</button>
        <button type="button" disabled={!editable} aria-pressed={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}>Курсив</button>
        <button type="button" disabled={!editable} aria-pressed={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}>Подчеркнуть</button>
        <button type="button" disabled={!editable} aria-pressed={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}>Список</button>
        <button type="button" disabled={!editable} aria-pressed={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}>Нумерация</button>
        <button type="button" disabled={!editable} onClick={() => editor.chain().focus().setTextAlign('left').run()}>Слева</button>
        <button type="button" disabled={!editable} onClick={() => editor.chain().focus().setTextAlign('center').run()}>По центру</button>
        <button type="button" disabled={!editable} onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>Таблица</button>
        <button type="button" disabled={!editable || !editor.can().chain().focus().undo().run()} onClick={() => editor.chain().focus().undo().run()}>Отменить</button>
        <button type="button" disabled={!editable || !editor.can().chain().focus().redo().run()} onClick={() => editor.chain().focus().redo().run()}>Повторить</button>
        <span className={styles.saveState}>{saveState}</span>
      </div>
      <div className={styles.canvas}>
        <EditorContent className={styles.document} editor={editor} />
      </div>
    </div>
  )
}
