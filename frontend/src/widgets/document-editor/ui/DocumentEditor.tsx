import Link from '@tiptap/extension-link'
import TextAlign from '@tiptap/extension-text-align'
import Underline from '@tiptap/extension-underline'
import StarterKit from '@tiptap/starter-kit'
import { EditorContent, useEditor } from '@tiptap/react'
import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'

import { saveDocument, uploadDocumentAsset } from '@/entities/document'
import type { SelectionContext, SelectionContextBlock } from '@/entities/document'
import { ApiError } from '@/shared/api/client'
import { cn } from '@/shared/lib/cn'
import {
  documentShell,
  normalizeCanonicalHtml,
  resolveAssetUrls,
  restoreAssetReferences,
  toEditableDocument,
} from '../model/canonical-html'
import { clearLocalDraft, getLocalDraft, saveLocalDraft } from '../model/localDraftStore'
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
  ManualPageBreak,
  StableBlockIds,
  AiBlockDecorations,
  aiBlockDecorationsKey,
} from '../model/extensions'

const toolGroupClass = 'relative flex min-h-8 items-center gap-0.5 border-r border-[#dfe2e6] px-2 first:pl-0 last:border-r-0 last:pr-0'
const toolButtonClass = cn(
  'h-8 w-8 cursor-pointer rounded-[3px] border border-transparent bg-transparent p-0 text-[15px] text-[#30363d]',
  'hover:bg-[#eef1f4] aria-pressed:border-[#c7d9f3] aria-pressed:bg-[#e5eefb] aria-pressed:text-[#174f9e]',
  'disabled:cursor-default disabled:opacity-45',
)

interface DocumentEditorProps {
  documentId: string
  revision: number
  html: string
  assetUrls: Record<string, string>
  styleSettings?: Record<string, unknown>
  editable?: boolean
  onRevisionChange?: (revision: number) => void
  onSaveStateChange?: (state: 'saved' | 'changed' | 'saving' | 'error') => void
  onSaveError?: (message: string | null) => void
  selectionBlockIds?: string[]
  highlightBlockIds?: string[]
  onSelectionChange?: (context: SelectionContext) => void
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
  styleSettings = {},
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
  const [zoom, setZoom] = useState(70)
  const [assetUrlMap, setAssetUrlMap] = useState(assetUrls)
  const [assetUploadError, setAssetUploadError] = useState<string | null>(null)
  const pageSetting = typeof styleSettings.page === 'string' ? styleSettings.page : 'A4, portrait'
  const pageMatch = pageSetting.match(/^\s*(A4|A5|Letter)\s*(?:,\s*(portrait|landscape))?\s*$/i)
  const pageWidths: Record<string, string> = { A4: '210mm', A5: '148mm', Letter: '216mm' }
  const pageHeights: Record<string, string> = { A4: '297mm', A5: '210mm', Letter: '279mm' }
  const selectedPage = pageMatch?.[1]?.toLowerCase() === 'letter' ? 'Letter' : pageMatch?.[1]?.toUpperCase() ?? 'A4'
  const landscape = pageMatch?.[2]?.toLowerCase() === 'landscape'
  const marginValues = typeof styleSettings.margins === 'string' ? styleSettings.margins.match(/\d+(?:\.\d+)?/g) : null
  const verticalMargin = marginValues?.length === 3 && marginValues.every((value) => Number(value) >= 8 && Number(value) <= 40) ? `${marginValues[0]}mm` : '24mm'
  const horizontalMargin = marginValues?.length === 3 && marginValues.every((value) => Number(value) >= 8 && Number(value) <= 40) ? `${marginValues[1]}mm` : '13mm'
  const bottomMargin = marginValues?.length === 3 && marginValues.every((value) => Number(value) >= 8 && Number(value) <= 40) ? `${marginValues[2]}mm` : '18mm'
  const accentColor = typeof styleSettings.accent === 'string' && /^#[\da-f]{6}$/i.test(styleSettings.accent) ? styleSettings.accent : '#f67828'
  const fontFamily = ['Lato', 'Arial', 'Helvetica', 'Inter'].includes(String(styleSettings.font)) ? String(styleSettings.font) : 'Lato'
  const editorThemeStyle = {
    '--manual-orange': accentColor,
    '--manual-page-width': landscape ? pageHeights[selectedPage] : pageWidths[selectedPage],
    '--manual-page-min-height': landscape ? pageWidths[selectedPage] : pageHeights[selectedPage],
    '--manual-page-padding-top': verticalMargin,
    '--manual-page-padding-x': horizontalMargin,
    '--manual-page-padding-bottom': bottomMargin,
    '--manual-editor-font': fontFamily,
  } as CSSProperties
  useEffect(() => {
    const viewport = canvasViewportRef.current
    if (!viewport) return
    const fitToViewport = () => {
      const pageWidthMm = Number.parseFloat(landscape ? pageHeights[selectedPage] : pageWidths[selectedPage])
      const pageWidthPx = pageWidthMm * (96 / 25.4)
      const availableWidth = Math.max(1, viewport.clientWidth - 48)
      setZoom(Math.max(50, Math.min(100, Math.floor((availableWidth / pageWidthPx) * 100))))
    }
    const observer = new ResizeObserver(fitToViewport)
    observer.observe(viewport)
    fitToViewport()
    return () => observer.disconnect()
  }, [landscape, selectedPage])
  const imageInputRef = useRef<HTMLInputElement>(null)
  const canvasViewportRef = useRef<HTMLDivElement>(null)
  const revisionRef = useRef(revision)
  const shellRef = useRef(documentShell(html))
  const editorDocumentRef = useRef(
    toEditableDocument(resolveAssetUrls(shellRef.current.content, assetUrls)),
  )
  const changeSequenceRef = useRef(0)
  const savedSequenceRef = useRef(0)
  const savingRef = useRef(false)
  const acceptUpdatesRef = useRef(false)
  const draftRestoreRef = useRef(false)
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
    onUpdate: ({ editor: updatedEditor }) => {
      if (!acceptUpdatesRef.current) return
      changeSequenceRef.current += 1
      const editorHtml = normalizeCanonicalHtml(restoreAssetReferences(updatedEditor.getHTML(), assetUrlMap))
      const canonicalHtml = `${shellRef.current.opening}${editorHtml}${shellRef.current.closing}`
      void saveLocalDraft({ documentId, baseRevision: revisionRef.current, html: canonicalHtml, updatedAt: Date.now() })
        .catch(() => onSaveError?.('Не удалось сохранить локальную копию изменений'))
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
    setAssetUrlMap((current) => ({ ...assetUrls, ...current }))
  }, [assetUrls])

  useEffect(() => {
    if (!editor) return
    acceptUpdatesRef.current = false
    const frame = window.requestAnimationFrame(() => {
      acceptUpdatesRef.current = true
    })
    return () => window.cancelAnimationFrame(frame)
  }, [editor])

  useEffect(() => {
    if (!editor || draftRestoreRef.current) return
    draftRestoreRef.current = true
    void getLocalDraft(documentId).then((draft) => {
      if (!draft) return
      if (draft.baseRevision !== revisionRef.current) {
        onSaveError?.('На этом устройстве есть черновик от другой редакции. Сравните версии перед продолжением.')
        setSaveState('error')
        return
      }
      shellRef.current = documentShell(draft.html)
      editorDocumentRef.current = toEditableDocument(resolveAssetUrls(shellRef.current.content, assetUrlMap))
      acceptUpdatesRef.current = false
      editor.commands.setContent(editorDocumentRef.current.content, false)
      changeSequenceRef.current += 1
      setSaveState('changed')
      window.requestAnimationFrame(() => { acceptUpdatesRef.current = true })
    }).catch(() => onSaveError?.('Не удалось прочитать локальный черновик'))
  }, [assetUrlMap, documentId, editor, onSaveError])

  useEffect(() => {
    const retryPendingDraft = () => {
      void getLocalDraft(documentId).then((draft) => {
        if (draft && draft.baseRevision === revisionRef.current) setSaveState('changed')
      }).catch(() => undefined)
    }
    window.addEventListener('online', retryPendingDraft)
    return () => window.removeEventListener('online', retryPendingDraft)
  }, [documentId])

  useEffect(() => {
    if (!editor || revisionRef.current === revision) return
    revisionRef.current = revision
    shellRef.current = documentShell(html)
    editorDocumentRef.current = toEditableDocument(resolveAssetUrls(shellRef.current.content, assetUrlMap))
    acceptUpdatesRef.current = false
    editor.commands.setContent(editorDocumentRef.current.content, false)
    window.requestAnimationFrame(() => {
      acceptUpdatesRef.current = true
    })
    setSaveState('saved')
  }, [assetUrlMap, editor, html, revision])

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
          const editorHtml = normalizeCanonicalHtml(restoreAssetReferences(editor.getHTML(), assetUrlMap))
          const canonicalHtml = `${shellRef.current.opening}${editorHtml}${shellRef.current.closing}`
          const result = await saveDocument(documentId, revisionRef.current, canonicalHtml)
          revisionRef.current = result.revision
          savedSequenceRef.current = savingSequence
          onSaveError?.(null)
          onRevisionChange?.(result.revision)
        } while (changeSequenceRef.current > savedSequenceRef.current)
        await clearLocalDraft(documentId)
        setSaveState('saved')
      } catch (error) {
        setSaveState('error')
        onSaveError?.(saveErrorMessage(error))
      } finally {
        savingRef.current = false
      }
    }, 1200)
    return () => window.clearTimeout(timeout)
  }, [assetUrlMap, documentId, editor, onRevisionChange, onSaveError, saveState])

  if (!editor) return null

  return (
    <div className="workbench-editor min-h-[calc(100vh-108px)]">
      <div
        className="workbench-toolbar sticky top-[108px] z-[25] flex min-h-11 items-center overflow-visible border-b border-app-border bg-white px-4 py-1 max-[1160px]:overflow-x-auto"
        role="toolbar"
        aria-label="Форматирование"
      >
        <div className={toolGroupClass}>
          <select
            className="min-h-8 rounded-control border border-[#d5d9de] bg-white py-0 pl-[9px] pr-7 text-[#30363d]"
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
        <div className={toolGroupClass}>
          <button className={cn(toolButtonClass, 'font-extrabold')} type="button" title="Жирный (⌘B)" aria-label="Жирный" disabled={!editable} aria-pressed={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}>B</button>
          <button className={cn(toolButtonClass, 'font-serif italic')} type="button" title="Курсив (⌘I)" aria-label="Курсив" disabled={!editable} aria-pressed={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}>I</button>
          <button className={cn(toolButtonClass, 'underline underline-offset-2')} type="button" title="Подчёркивание (⌘U)" aria-label="Подчёркивание" disabled={!editable} aria-pressed={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}>U</button>
          <button className={toolButtonClass} type="button" title="Добавить или изменить ссылку" aria-label="Ссылка" disabled={!editable} aria-pressed={editor.isActive('link')} onClick={() => {
            const currentHref = editor.getAttributes('link').href as string | undefined
            const href = window.prompt('Введите адрес ссылки', currentHref ?? 'https://')
            if (href === null) return
            if (!href.trim()) editor.chain().focus().unsetLink().run()
            else editor.chain().focus().setLink({ href: href.trim() }).run()
          }}>↗</button>
        </div>
        <div className={toolGroupClass}>
          <button className={toolButtonClass} type="button" title="Маркированный список" aria-label="Маркированный список" disabled={!editable} aria-pressed={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}>•≡</button>
          <button className={toolButtonClass} type="button" title="Нумерованный список" aria-label="Нумерованный список" disabled={!editable} aria-pressed={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}>1≡</button>
        </div>
        <div className={toolGroupClass}>
          <button className={cn(toolButtonClass, 'text-left')} type="button" title="По левому краю" aria-label="По левому краю" disabled={!editable} aria-pressed={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()}>≡</button>
          <button className={cn(toolButtonClass, 'text-center')} type="button" title="По центру" aria-label="По центру" disabled={!editable} aria-pressed={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()}>≡</button>
          <button className={cn(toolButtonClass, 'text-right')} type="button" title="По правому краю" aria-label="По правому краю" disabled={!editable} aria-pressed={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()}>≡</button>
          <button className={toolButtonClass} type="button" title="По ширине" aria-label="По ширине" disabled={!editable} aria-pressed={editor.isActive({ textAlign: 'justify' })} onClick={() => editor.chain().focus().setTextAlign('justify').run()}>☰</button>
        </div>
        <div className={toolGroupClass}>
          <button
            className={toolButtonClass}
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
            <div className="absolute left-[5px] top-[calc(100%+7px)] z-40 w-[184px] rounded-[7px] border border-[#d3d7dc] bg-white p-3 shadow-[0_10px_30px_rgb(28_36_46_/_18%)]">
              <strong className="mb-[9px] block text-center text-xs font-semibold text-[#555e68]">{tableSize.cols} × {tableSize.rows}</strong>
              <div className="grid grid-cols-[repeat(5,24px)] justify-center gap-1">
                {Array.from({ length: 25 }, (_, index) => {
                  const row = Math.floor(index / 5) + 1
                  const col = (index % 5) + 1
                  const active = row <= tableSize.rows && col <= tableSize.cols
                  return (
                    <button
                      className="h-6 w-6 rounded-sm border border-[#bfc5cc] bg-white data-[active=true]:border-[#3d76c5] data-[active=true]:bg-[#dce9fb]"
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
          <button className={toolButtonClass} type="button" title="Вставить изображение" aria-label="Вставить изображение" disabled={!editable} onClick={() => imageInputRef.current?.click()}>▧</button>
          <input ref={imageInputRef} className="hidden" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" onChange={async (event) => {
            const file = event.target.files?.[0]
            if (!file) return
            setAssetUploadError(null)
            try {
              const asset = await uploadDocumentAsset(documentId, file)
              setAssetUrlMap((current) => ({ ...current, [asset.id]: asset.url }))
              editor.chain().focus().setImage({ src: asset.url, alt: asset.alt, title: asset.filename }).run()
            } catch {
              setAssetUploadError('Не удалось загрузить изображение. Проверьте формат и размер файла.')
            } finally {
              event.currentTarget.value = ''
            }
          }} />
          <button className={toolButtonClass} type="button" title="Разрыв страницы" aria-label="Разрыв страницы" disabled={!editable} onClick={() => editor.chain().focus().insertContent({ type: 'pageBreak' }).run()}>↵</button>
          {editor.isActive('table') && <details className="relative"><summary className="grid h-8 cursor-pointer list-none place-items-center rounded-control px-2 text-xs font-semibold hover:bg-[#f1f3f5]">Таблица ⋯</summary><div className="absolute left-0 top-[calc(100%+7px)] z-40 grid w-[190px] rounded-[7px] border border-[#d3d7dc] bg-white p-1.5 shadow-popover"><button className="rounded px-2 py-1.5 text-left text-xs hover:bg-[#f1f3f5]" type="button" onClick={() => editor.chain().focus().addRowBefore().run()}>Добавить строку выше</button><button className="rounded px-2 py-1.5 text-left text-xs hover:bg-[#f1f3f5]" type="button" onClick={() => editor.chain().focus().addRowAfter().run()}>Добавить строку ниже</button><button className="rounded px-2 py-1.5 text-left text-xs hover:bg-[#f1f3f5]" type="button" onClick={() => editor.chain().focus().deleteRow().run()}>Удалить строку</button><button className="rounded px-2 py-1.5 text-left text-xs hover:bg-[#f1f3f5]" type="button" onClick={() => editor.chain().focus().addColumnBefore().run()}>Добавить столбец слева</button><button className="rounded px-2 py-1.5 text-left text-xs hover:bg-[#f1f3f5]" type="button" onClick={() => editor.chain().focus().addColumnAfter().run()}>Добавить столбец справа</button><button className="rounded px-2 py-1.5 text-left text-xs hover:bg-[#f1f3f5]" type="button" onClick={() => editor.chain().focus().deleteColumn().run()}>Удалить столбец</button><button className="rounded px-2 py-1.5 text-left text-xs text-app-danger hover:bg-[#fff1f1]" type="button" onClick={() => editor.chain().focus().deleteTable().run()}>Удалить таблицу</button></div></details>}
        </div>
        <div className={cn(toolGroupClass, 'ml-auto')}>
          <button className={toolButtonClass} type="button" title="Отменить (⌘Z)" aria-label="Отменить" disabled={!editable || !editor.can().chain().focus().undo().run()} onClick={() => editor.chain().focus().undo().run()}>↶</button>
          <button className={toolButtonClass} type="button" title="Повторить (⇧⌘Z)" aria-label="Повторить" disabled={!editable || !editor.can().chain().focus().redo().run()} onClick={() => editor.chain().focus().redo().run()}>↷</button>
        </div>
      </div>
      {assetUploadError && <p className="mx-4 my-0 text-sm text-app-danger" role="alert">{assetUploadError}</p>}
      <div ref={canvasViewportRef} className="workbench-canvas flex min-w-0 justify-center overflow-x-auto px-6 pb-24 pt-7 max-[760px]:justify-start max-[760px]:px-3">
        <div className="origin-top" style={{ ...editorThemeStyle, zoom: zoom / 100 }}>
          <EditorContent className="document-theme" editor={editor} />
        </div>
      </div>
      <footer className="workbench-footer fixed bottom-0 z-20 flex min-h-9 items-center justify-between gap-4 border-t border-app-border bg-white px-4 text-xs text-app-muted max-[1279px]:pr-[380px] max-[760px]:pr-4" aria-label="Состояние редактора">
        <span>Страница документа · {selectedPage}{landscape ? ' альбомная' : ' книжная'}</span>
        <span>{editable ? 'Изменения сохраняются автоматически' : 'Только просмотр'}</span>
        <span className="flex items-center gap-1"><button className="grid h-6 w-6 place-items-center rounded border-0 bg-transparent text-app-text hover:bg-[#f1f3f5]" type="button" onClick={() => setZoom((value) => Math.max(50, value - 10))} aria-label="Уменьшить масштаб">−</button><span className="min-w-10 text-center">{zoom}%</span><button className="grid h-6 w-6 place-items-center rounded border-0 bg-transparent text-app-text hover:bg-[#f1f3f5]" type="button" onClick={() => setZoom((value) => Math.min(150, value + 10))} aria-label="Увеличить масштаб">+</button></span>
      </footer>
    </div>
  )
}
