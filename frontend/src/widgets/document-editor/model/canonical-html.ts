export interface DocumentShell {
  opening: string
  content: string
  closing: string
}

export interface EditableDocument {
  content: string
}

function createContainer(html: string) {
  const container = window.document.createElement('div')
  container.innerHTML = html
  return container
}

export function resolveAssetUrls(html: string, assetUrls: Record<string, string>) {
  return html.replace(/asset:\/\/([0-9a-f-]{36})/gi, (reference, assetId: string) => assetUrls[assetId] ?? reference)
}

export function documentShell(html: string): DocumentShell {
  const match = html.match(/^\s*(<article\b[^>]*>)([\s\S]*)(<\/article>)\s*$/i)
  return match
    ? { opening: match[1], content: match[2], closing: match[3] }
    : { opening: '<article class="manual">', content: html, closing: '</article>' }
}

function stripEditorChrome(container: HTMLElement) {
  container.querySelectorAll('[data-ai-context], [data-ai-highlight]')
    .forEach((element) => {
      element.removeAttribute('data-ai-context')
      element.removeAttribute('data-ai-highlight')
    })
  container.querySelectorAll('colgroup').forEach((element) => element.remove())
  container.querySelectorAll('table[style], tbody[style], tr[style], th[style], td[style]')
    .forEach((element) => element.removeAttribute('style'))
}

function unwrapEditorPages(container: HTMLElement) {
  const directPages = Array.from(container.querySelectorAll(':scope > .manual-page'))
  if (!directPages.length) return

  const hasCanonicalHeader = Boolean(container.querySelector(':scope > .manual-header'))
  const hasCanonicalFooter = Boolean(container.querySelector(':scope > .manual-footer'))
  const fallbackHeader = hasCanonicalHeader ? null : directPages[0]?.querySelector(':scope > .manual-header')?.cloneNode(true)
  const fallbackFooter = hasCanonicalFooter ? null : directPages[0]?.querySelector(':scope > .manual-footer')?.cloneNode(true)

  for (const page of directPages) {
    page.querySelectorAll(':scope > .manual-header, :scope > .manual-footer').forEach((node) => node.remove())
    const fragment = window.document.createDocumentFragment()
    while (page.firstChild) fragment.appendChild(page.firstChild)
    page.replaceWith(fragment)
  }

  if (fallbackHeader) container.prepend(fallbackHeader)
  if (fallbackFooter) container.insertBefore(fallbackFooter, container.children[1] ?? null)
}

export function toEditableDocument(html: string): EditableDocument {
  const container = createContainer(html)
  unwrapEditorPages(container)
  stripEditorChrome(container)
  return {
    content: container.innerHTML,
  }
}

export function restoreAssetReferences(html: string, assetUrls: Record<string, string>) {
  const container = createContainer(html)
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

export function normalizeCanonicalHtml(html: string) {
  const container = createContainer(html)
  unwrapEditorPages(container)
  stripEditorChrome(container)
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
