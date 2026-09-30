Convert the source document package into a complete editable manual.

Input roles:

- SOURCE_DOCUMENT.docx is authoritative for text, facts and editable structure.
- SOURCE_RENDER.pdf is authoritative for relationships between text, figures, arrows and labels.
- STYLE_REFERENCE.pdf and STYLE_OVERVIEW images are visual references only.

Requirements:

1. Preserve document order, all source text, numbers, tables, figures, captions and safety notices.
2. Reflow the content into the requested Villartec A4 theme using approved classes only.
3. Reference every supplied source image exactly by its asset:// id. Return base64 only for a newly
   generated flattened replacement image.
4. Use semantic tags and the closest approved component. Add stable data-block-id values.
5. Preserve the source language. Translation is performed by another service.
6. Put ambiguities and suspected source contradictions only in warnings. Do not insert editorial
   notes, unsupported corrections or a generated source-notes chapter into the manual.
7. Return a single full_document JSON envelope without Markdown fences.
