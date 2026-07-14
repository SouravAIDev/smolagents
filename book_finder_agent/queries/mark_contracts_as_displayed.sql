-- Mark books as displayed in session context after showing to user.
-- Supports arbitrary display counts and batch updates via {values_clause}.
-- Parameters: session_id, question_text
-- {values_clause} format: (doc_id_1, display_count_1), (doc_id_2, display_count_2), ...

UPDATE {context_table} AS context
SET 
    is_displayed = TRUE,
    display_count = COALESCE(context.display_count, 0) + COALESCE(doc_counts.doc_count, 1)
FROM (
    VALUES
        {values_clause}
) AS doc_counts(doc_id, doc_count)
WHERE context.doc_id = doc_counts.doc_id
  AND context.session_id = %s
  AND context.question = %s;