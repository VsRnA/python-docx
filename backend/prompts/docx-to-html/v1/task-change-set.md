Apply the user's request to the supplied current HTML revision.

Return a `change_set` envelope containing only operations over stable `data-block-id` values.
Do not rewrite unaffected blocks. Preserve the theme, classes and asset references. Every replace
operation must include the expected source hash supplied with the request.
