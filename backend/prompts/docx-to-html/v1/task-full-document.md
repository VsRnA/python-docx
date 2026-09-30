Convert the source document package into a complete editable manual.

The package contains clearly labelled inputs with different roles:

- SOURCE_DOCUMENT.docx is authoritative for text, facts and editable structure.
- SOURCE_RENDER.pdf is authoritative for source page boundaries, image placement, anchored labels,
  arrows, numbering and the original visual composition.
- STYLE_REFERENCE.pdf and STYLE_OVERVIEW images are visual references only.

Never copy product names, text, facts, images or page numbers from the style references.

Requirements:

1. Preserve document order, all text, tables, figures, captions and safety notices.
2. Apply the requested Villartec theme using approved classes only.
3. Use every source image supplied after the DOCX by referencing its existing `asset://<asset_id>`.
   Return base64 in `assets` only for a newly generated flattened replacement image.
4. Use semantic tags and the closest approved component.
5. Preserve the source language. Translation is performed by another service.
6. Report every ambiguous or unsupported source element in `warnings`.
7. Return a single `full_document` JSON envelope without Markdown fences.
8. Match the reference page system consistently, while using only approved components and classes.
