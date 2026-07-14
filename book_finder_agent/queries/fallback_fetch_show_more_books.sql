-- Fallback pagination query used when the primary fetch_show_more_books returns no results.
-- Retrieves books for the LATEST question under this session (instead of a specific question),
-- allowing pagination to continue even if the question text has changed slightly.


WITH latest_question AS (
    SELECT question
    FROM {context_table}
    WHERE session_id = %s
      AND is_expired = FALSE
    ORDER BY id DESC
    LIMIT 1
),

undisplayed AS (
    SELECT crdd.*
    FROM {context_table} crdd
    JOIN latest_question lq ON crdd.question = lq.question
    WHERE crdd.session_id = %s
      AND crdd.is_displayed = FALSE
      AND crdd.is_expired = FALSE
    ORDER BY crdd.context_score DESC
    LIMIT %s
),

displayed AS (
    SELECT crdd.*, TRUE AS is_displayed
    FROM {context_table} crdd
    JOIN latest_question lq ON crdd.question = lq.question
    WHERE crdd.session_id = %s
      AND crdd.is_displayed = TRUE
      AND crdd.is_expired = FALSE
),

total AS (
    SELECT COUNT(*) AS total_count
    FROM {context_table} crdd
    JOIN latest_question lq ON crdd.question = lq.question
    WHERE crdd.session_id = %s
      AND crdd.is_expired = FALSE
)

SELECT combined.*, total.total_count
FROM (
        SELECT *
        FROM displayed
        UNION ALL
        SELECT u.*, FALSE AS is_displayed
        FROM undisplayed u
    ) combined
    CROSS JOIN total
ORDER BY context_score DESC
LIMIT % s;