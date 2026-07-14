-- Fallback show-more query when original session question is unavailable.
-- Fetches latest question for session and returns undisplayed + displayed documents.
-- Parameters: session_id (appears 4 times), limit_undisplayed, limit_final
-- Placeholders: context_table


WITH latest_question AS (
    SELECT question
    FROM {context_table}
    WHERE session_id = %s
      AND is_expired = FALSE
    ORDER BY id DESC
    LIMIT 1
),

undisplayed AS (
    SELECT ctx.*
    FROM {context_table} ctx
    JOIN latest_question lq ON ctx.question = lq.question
    WHERE ctx.session_id = %s
      AND ctx.is_displayed = FALSE
      AND ctx.is_expired = FALSE
    ORDER BY ctx.context_score DESC
    LIMIT %s
),

displayed AS (
    SELECT ctx.*, TRUE AS already_displayed
    FROM {context_table} ctx
    JOIN latest_question lq ON ctx.question = lq.question
    WHERE ctx.session_id = %s
      AND ctx.is_displayed = TRUE
      AND ctx.is_expired = FALSE
),

total AS (
    SELECT COUNT(*) AS total_count
    FROM {context_table} ctx
    JOIN latest_question lq ON ctx.question = lq.question
    WHERE ctx.session_id = %s
      AND ctx.is_expired = FALSE
)

SELECT combined.*, total.total_count
FROM (
        SELECT *
        FROM displayed
        UNION ALL
        SELECT u.*, FALSE AS already_displayed
        FROM undisplayed u
    ) combined
    CROSS JOIN total
ORDER BY context_score DESC
LIMIT % s;