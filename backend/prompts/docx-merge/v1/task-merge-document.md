# Task: merge several DOCX manuals into one final document

You receive several DOCX source documents and a PDF rendering for each source. The user does not choose a merge strategy. You must decide the clean final structure yourself and return one polished, print-ready HTML document that can be rendered to a final PDF using the approved theme.

Authoritative content:

- SOURCE DOCX files and SOURCE_RENDER PDFs are the only sources of facts, text, tables, warnings, captions, product names, model numbers, images, diagrams and sequence.
- STYLE_REFERENCE and STYLE_OVERVIEW files are visual guidance only. Never copy their text, facts, product names, images, page numbers or content.

Merge behavior:

- Produce a single coherent manual, not a mechanical concatenation.
- Use the user-provided source order as an orientation signal, but decide the final structure that creates the cleanest combined manual.
- Preserve every meaningful fact, warning, technical characteristic, table, image, caption and procedural instruction.
- Merge obvious duplicate boilerplate only when no meaning is lost. If uncertain, keep both pieces of source content.
- Normalize headings, table presentation, warnings, captions, page breaks, intro sections, footers and visual rhythm to the approved theme.
- If the sources describe multiple models, make that clear in headings, tables and section labels.
- Do not invent facts or fill missing data from style references.
- The output should be ready for automatic PDF rendering without additional manual formatting.

HTML contract:

- Return only JSON matching the supplied schema.
- `document.document_id` must exactly match the requested document id.
- `document.theme_id` and `document.theme_version` must exactly match the requested theme.
- `document.html` must use only approved tags, attributes, components and CSS classes.
- Every editable block must have a stable unique `data-block-id`.
- Use `asset://...` references for source images listed in the manifest.
- Put only newly generated or flattened replacement images in `document.assets`.
- Prefer adding `data-source-file-id` to major blocks when you can identify the source file.
