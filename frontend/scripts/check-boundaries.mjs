import { readdir, readFile } from 'node:fs/promises'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const sourceRoot = fileURLToPath(new URL('../src/', import.meta.url))
const frontendRoot = fileURLToPath(new URL('../', import.meta.url))
const layers = ['shared', 'entities', 'features', 'widgets', 'pages', 'app']
const forbidden = {
  shared: new Set(['entities', 'features', 'widgets', 'pages', 'app']),
  entities: new Set(['features', 'widgets', 'pages', 'app']),
  features: new Set(['widgets', 'pages', 'app']),
  widgets: new Set(['pages', 'app']),
  pages: new Set(['app']),
  app: new Set(),
}
const violations = []

async function walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) await walk(path)
    else if (/\.(?:ts|tsx)$/.test(entry.name)) await inspect(path)
  }
}

async function inspect(path) {
  const source = await readFile(path, 'utf8')
  const currentLayer = relative(sourceRoot, path).split('/')[0]
  if (!layers.includes(currentLayer)) return
  for (const match of source.matchAll(/from\s+['"]@\/([^/'"]+)/g)) {
    const importedLayer = match[1]
    if (forbidden[currentLayer]?.has(importedLayer)) {
      violations.push(`${relative(frontendRoot, path)} -> ${importedLayer}`)
    }
  }
}

await walk(sourceRoot)
if (violations.length) {
  console.error(`FSD import boundary violations:\n${violations.join('\n')}`)
  process.exitCode = 1
} else {
  console.log('FSD import boundaries: ok')
}
