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
5. Use heading tags only for actual chapter and section titles in the source hierarchy. Determine
   this from the DOCX heading/outline structure, numbering, and surrounding section relationships;
   uppercase text, bold formatting, font size, or a short standalone line alone do not make a heading.
   Do not promote warning labels (WARNING, CAUTION, DANGER, NOTE), table headers, list lead-ins,
   contents entries, captions, or inline labels to section headings. Render safety labels with the
   approved warning component and keep them out of the document outline.
6. Preserve the source language. Translation is performed by another service.
7. Put ambiguities and suspected source contradictions only in warnings. Do not insert editorial
   notes, unsupported corrections or a generated source-notes chapter into the manual.
8. Return a single full_document JSON envelope without Markdown fences.
