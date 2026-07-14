-- Retrieves documents from session context filtered by JSONB metadata criteria.
-- Implements Flow C: applies selected filter constraints to previously retrieved books.
-- The {filter_type} placeholder is dynamically inserted (snake_case key name)
-- and values are matched case-insensitively.

WITH latest_question AS (
    SELECT question
    FROM {context_table}
    WHERE session_id = %s
      AND is_expired = FALSE
    ORDER BY id DESC
    LIMIT 1
)

SELECT 
    crdd.*,
    COUNT(*) OVER (PARTITION BY session_id, question) AS total_count
FROM {context_table} crdd
JOIN latest_question lq ON crdd.question = lq.question
WHERE crdd.session_id = %s
  AND crdd.question = lq.question
  AND crdd.is_expired = FALSE
  AND LOWER(CAST(crdd.metadata->'{filter_type}' AS TEXT)) = ANY(CAST(%s AS TEXT[]))
ORDER BY crdd.context_score DESC;