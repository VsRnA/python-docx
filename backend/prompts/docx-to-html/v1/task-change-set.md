Apply the user's request to the supplied current HTML revision.

Return a `change_set` envelope containing only operations over stable `data-block-id` values.
Do not rewrite unaffected blocks. Preserve the theme, classes and asset references. Every replace
operation must include the expected source hash supplied with the request.

If target_block_ids is not empty, treat it as a hard edit scope: only return operations whose
block_id is in target_block_ids. Use neighboring blocks only for context; do not rewrite, delete or
insert after blocks outside target_block_ids.
