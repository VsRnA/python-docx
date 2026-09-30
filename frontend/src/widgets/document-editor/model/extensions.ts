import Heading from '@tiptap/extension-heading'
import Image from '@tiptap/extension-image'
import Paragraph from '@tiptap/extension-paragraph'
import BulletList from '@tiptap/extension-bullet-list'
import OrderedList from '@tiptap/extension-ordered-list'
import Table from '@tiptap/extension-table'
import TableCell from '@tiptap/extension-table-cell'
import TableHeader from '@tiptap/extension-table-header'
import TableRow from '@tiptap/extension-table-row'
import ListItem from '@tiptap/extension-list-item'
import { Extension, mergeAttributes, Node } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Decoration, DecorationSet } from '@tiptap/pm/view'

const classAttribute = (defaultClass: string) => ({
  default: defaultClass,
  parseHTML: (element: HTMLElement) => element.getAttribute('class') ?? defaultClass,
  renderHTML: (attributes: Record<string, unknown>) =>
    attributes.class ? { class: String(attributes.class) } : {},
})

const blockAttributes = {
  htmlId: {
    default: null,
    parseHTML: (element: HTMLElement) => element.getAttribute('id'),
    renderHTML: (attributes: Record<string, unknown>) =>
      attributes.htmlId ? { id: attributes.htmlId } : {},
  },
  blockId: {
    default: null,
    parseHTML: (element: HTMLElement) => element.getAttribute('data-block-id'),
    renderHTML: (attributes: Record<string, unknown>) =>
      attributes.blockId ? { 'data-block-id': attributes.blockId } : {},
  },
  blockType: {
    default: null,
    parseHTML: (element: HTMLElement) => element.getAttribute('data-block-type'),
    renderHTML: (attributes: Record<string, unknown>) =>
      attributes.blockType ? { 'data-block-type': attributes.blockType } : {},
  },
}

export const StableBlockIds = Extension.create({
  name: 'stableBlockIds',
  addProseMirrorPlugins() {
    return [
      new Plugin({
        appendTransaction(transactions, _oldState, newState) {
          if (!transactions.some((transaction) => transaction.docChanged)) return null
          const transaction = newState.tr
          let changed = false
          newState.doc.descendants((node, position) => {
            if (!node.isBlock || !node.type.spec.attrs?.blockId || node.attrs.blockId) return
            transaction.setNodeMarkup(position, undefined, {
              ...node.attrs,
              blockId: `b_${crypto.randomUUID()}`,
              blockType: node.attrs.blockType ?? node.type.name,
            })
            changed = true
          })
          return changed ? transaction : null
        },
      }),
    ]
  },
})

export const aiBlockDecorationsKey = new PluginKey<DecorationSet>('aiBlockDecorations')

export const AiBlockDecorations = Extension.create({
  name: 'aiBlockDecorations',
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: aiBlockDecorationsKey,
        state: {
          init: () => DecorationSet.empty,
          apply(transaction, previous, _oldState, newState) {
            const meta = transaction.getMeta(aiBlockDecorationsKey) as
              | { contextBlockIds?: string[]; highlightBlockIds?: string[] }
              | undefined
            if (!meta) return previous.map(transaction.mapping, transaction.doc)

            const contextIds = new Set(meta.contextBlockIds ?? [])
            const highlightIds = new Set(meta.highlightBlockIds ?? [])
            const decorations: Decoration[] = []
            newState.doc.descendants((node, position) => {
              const blockId = node.attrs.blockId
              if (!node.isBlock || typeof blockId !== 'string') return
              const classes = [
                contextIds.has(blockId) ? 'ai-context-block' : '',
                highlightIds.has(blockId) ? 'ai-highlight-block' : '',
              ].filter(Boolean)
              if (classes.length) decorations.push(Decoration.node(position, position + node.nodeSize, { class: classes.join(' ') }))
            })
            return DecorationSet.create(newState.doc, decorations)
          },
        },
        props: {
          decorations(state) {
            return aiBlockDecorationsKey.getState(state)
          },
        },
      }),
    ]
  },
})

const containerNode = (
  name: string,
  tag: string,
  selector: string,
  defaultClass: string,
  content = 'block+',
) => Node.create({
  name,
  group: 'block',
  content,
  defining: true,
  addAttributes() {
    return { ...blockAttributes, class: classAttribute(defaultClass) }
  },
  parseHTML() {
    return [{ tag: `${tag}.${selector}` }]
  },
  renderHTML({ HTMLAttributes }) {
    return [tag, mergeAttributes(HTMLAttributes), 0]
  },
})

const inlineNode = (name: string, tag: string, selector: string, defaultClass: string) => Node.create({
  name,
  group: 'inline',
  content: 'text*',
  inline: true,
  addAttributes() {
    return { ...blockAttributes, class: classAttribute(defaultClass) }
  },
  parseHTML() {
    return [{ tag: `${tag}.${selector}` }]
  },
  renderHTML({ HTMLAttributes }) {
    return [tag, mergeAttributes(HTMLAttributes), 0]
  },
})

export const ManualHeader = containerNode('manualHeader', 'header', 'manual-header', 'manual-header', 'inline*')
export const ManualFooter = containerNode('manualFooter', 'footer', 'manual-footer', 'manual-footer', 'inline*')
export const ManualCover = containerNode('manualCover', 'section', 'manual-cover', 'manual-cover')
export const ManualCoverOrange = containerNode('manualCoverOrange', 'div', 'manual-cover__orange', 'manual-cover__orange')
export const ManualCoverHero = containerNode('manualCoverHero', 'div', 'manual-cover__hero', 'manual-cover__hero')
export const ManualCoverBody = containerNode('manualCoverBody', 'div', 'manual-cover__body', 'manual-cover__body')
export const ManualToc = containerNode('manualToc', 'section', 'manual-toc', 'manual-toc')
export const ManualTocRow = containerNode('manualTocRow', 'div', 'manual-toc__row', 'manual-toc__row', 'inline*')
export const ManualLegend = containerNode('manualLegend', 'section', 'manual-legend', 'manual-legend manual-columns manual-columns--2')
export const ManualLegendItem = containerNode('manualLegendItem', 'div', 'manual-legend__item', 'manual-legend__item')
export const ManualHeaderMark = inlineNode('manualHeaderMark', 'span', 'manual-header__mark', 'manual-header__mark')
export const ManualHeaderTitle = inlineNode('manualHeaderTitle', 'span', 'manual-header__title', 'manual-header__title')
export const ManualHeaderSites = inlineNode('manualHeaderSites', 'span', 'manual-header__sites', 'manual-header__sites')
export const ManualFooterPage = inlineNode('manualFooterPage', 'span', 'manual-footer__page', 'manual-footer__page')
export const ManualFooterVersion = inlineNode('manualFooterVersion', 'span', 'manual-footer__version', 'manual-footer__version')
export const ManualTocTitle = Node.create({
  name: 'manualTocTitle',
  group: 'inline',
  content: 'text*',
  inline: true,
  addAttributes() {
    return {
      ...blockAttributes,
      class: classAttribute('manual-toc__title'),
      href: {
        default: null,
        parseHTML: (element: HTMLElement) => element.getAttribute('href'),
        renderHTML: (attributes: Record<string, unknown>) =>
          attributes.href ? { href: String(attributes.href) } : {},
      },
    }
  },
  parseHTML() {
    return [{ tag: 'a.manual-toc__title' }, { tag: 'span.manual-toc__title' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['a', mergeAttributes(HTMLAttributes), 0]
  },
})
export const ManualTocPage = inlineNode('manualTocPage', 'span', 'manual-toc__page', 'manual-toc__page')
export const ManualLegendLabel = inlineNode('manualLegendLabel', 'span', 'manual-legend__label', 'manual-legend__label')
export const ManualPage = Node.create({
  name: 'manualPage',
  group: 'block',
  content: 'block*',
  defining: true,
  isolating: true,
  addAttributes() {
    return {
      class: classAttribute('manual-page'),
      pageNumber: {
        default: null,
        parseHTML: (element: HTMLElement) => element.getAttribute('data-page-number'),
        renderHTML: (attributes: Record<string, unknown>) =>
          attributes.pageNumber ? { 'data-page-number': String(attributes.pageNumber) } : {},
      },
    }
  },
  parseHTML() {
    return [{ tag: 'section.manual-page' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['section', mergeAttributes(HTMLAttributes), 0]
  },
})
export const ManualPageBreak = Node.create({
  name: 'manualPageBreak',
  group: 'block',
  atom: true,
  selectable: true,
  addAttributes() {
    return { ...blockAttributes, class: classAttribute('manual-page-break') }
  },
  parseHTML() {
    return [{ tag: 'div.manual-page-break' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes)]
  },
})

export const ManualParagraph = Paragraph.extend({
  addAttributes() {
    return { ...this.parent?.(), ...blockAttributes, class: classAttribute('manual-paragraph') }
  },
})

export const ManualHeading = Heading.extend({
  addAttributes() {
    return { ...this.parent?.(), ...blockAttributes, class: classAttribute('manual-heading') }
  },
})

export const ManualImage = Image.extend({
  addAttributes() {
    return { ...this.parent?.(), ...blockAttributes, class: classAttribute('') }
  },
})

export const ManualSection = containerNode('manualSection', 'section', 'manual-section', 'manual-section')
export const ManualGallery = containerNode('manualGallery', 'div', 'manual-gallery', 'manual-gallery')
export const ManualFigureFrame = containerNode('manualFigureFrame', 'div', 'manual-figure__frame', 'manual-figure__frame')
export const ManualNote = containerNode('manualNote', 'section', 'manual-note', 'manual-note')
export const ManualNoteBody = containerNode('manualNoteBody', 'div', 'manual-note__body', 'manual-note__body')
export const ManualForm = containerNode('manualForm', 'section', 'manual-form', 'manual-form')
export const ManualFormColumns = containerNode('manualFormColumns', 'div', 'manual-form__columns', 'manual-form__columns')

export const ManualWarning = Node.create({
  name: 'manualWarning',
  group: 'block',
  content: 'block+',
  defining: true,
  addAttributes() {
    return { ...blockAttributes, class: classAttribute('manual-warning') }
  },
  parseHTML() {
    return [{ tag: 'section.manual-warning' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['section', mergeAttributes(HTMLAttributes), 0]
  },
})

export const ManualFigure = Node.create({
  name: 'manualFigure',
  group: 'block',
  content: 'block+',
  defining: true,
  addAttributes() {
    return { ...blockAttributes, class: classAttribute('manual-figure') }
  },
  parseHTML() {
    return [{ tag: 'figure.manual-figure' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['figure', mergeAttributes(HTMLAttributes), 0]
  },
})

export const ManualCaption = Node.create({
  name: 'manualCaption',
  group: 'block',
  content: 'inline*',
  addAttributes() {
    return { ...blockAttributes, class: classAttribute('manual-caption') }
  },
  parseHTML() {
    return [{ tag: 'figcaption.manual-caption' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['figcaption', mergeAttributes(HTMLAttributes), 0]
  },
})

export const ManualWarningBody = Node.create({
  name: 'manualWarningBody',
  group: 'block',
  content: 'block+',
  addAttributes() {
    return { ...blockAttributes, class: classAttribute('manual-warning__body') }
  },
  parseHTML() {
    return [{ tag: 'div.manual-warning__body' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes), 0]
  },
})

export const ManualTable = Table.extend({
  addAttributes() {
    return { ...this.parent?.(), ...blockAttributes, class: classAttribute('manual-table') }
  },
})

export const ManualBulletList = BulletList.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      ...blockAttributes,
      class: classAttribute('manual-list manual-list--unordered'),
    }
  },
})

export const ManualOrderedList = OrderedList.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      ...blockAttributes,
      class: classAttribute('manual-list manual-list--ordered'),
    }
  },
})

export const ManualListItem = ListItem.extend({
  addAttributes() {
    return { ...this.parent?.(), ...blockAttributes, class: classAttribute('') }
  },
})

export const ManualTableRow = TableRow.extend({
  addAttributes() {
    return { ...this.parent?.(), ...blockAttributes, class: classAttribute('') }
  },
})

export const ManualTableHeader = TableHeader.extend({
  addAttributes() {
    return { ...this.parent?.(), ...blockAttributes, class: classAttribute('') }
  },
})

export const ManualTableCell = TableCell.extend({
  addAttributes() {
    return { ...this.parent?.(), ...blockAttributes, class: classAttribute('') }
  },
})
