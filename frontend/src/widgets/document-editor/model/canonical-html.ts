export function resolveAssetUrls(html: string, assetUrls: Record<string, string>) {
  return html.replace(/asset:\/\/([0-9a-f-]{36})/gi, (reference, assetId: string) => assetUrls[assetId] ?? reference)
}
