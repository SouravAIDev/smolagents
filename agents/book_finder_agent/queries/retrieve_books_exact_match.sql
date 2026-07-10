-- Retrieve books via exact-match filtering on structured metadata
-- Filters by ISBN, publication date, publisher, audience, genre, or author
-- Used by Step A4 for hard-filter metadata constraints and combined with semantic search

SELECT DISTINCT
    b.book_id,
    b.title,
    b.isbn,
    b.isbn_13,
    b.publication_date,
    b.publication_year,
    b.author_id,
    bs.summary_text,
    bs.summary_length,
    p.publisher_name,
    a.audience_type,
    -- Aggregated fields from many-to-many tables
    STRING_AGG (
        DISTINCT au.author_name,
        ', '
        ORDER BY au.author_name
    ) AS all_authors,
    STRING_AGG (
        DISTINCT g.genre_name,
        ', '
        ORDER BY g.genre_name
    ) AS all_genres,
    STRING_AGG (
        DISTINCT c.contributor_name,
        ', '
        ORDER BY c.contributor_name
    ) AS all_contributors,
    STRING_AGG (
        DISTINCT pr.prize_name,
        ', '
        ORDER BY pr.prize_name
    ) AS all_prizes,
    STRING_AGG (
        DISTINCT l.location_name,
        ', '
        ORDER BY l.location_name
    ) AS all_locations,
    -- Filter match count for relevance scoring
    CASE
        WHEN b.isbn = % s
        OR b.isbn_13 = % s THEN 1
        ELSE 0
    END + CASE
        WHEN au.author_name ILIKE % s THEN 1
        ELSE 0
    END + CASE
        WHEN g.genre_name ILIKE % s THEN 1
        ELSE 0
    END + CASE
        WHEN p.publisher_name ILIKE % s THEN 1
        ELSE 0
    END + CASE
        WHEN a.audience_type ILIKE % s THEN 1
        ELSE 0
    END AS filter_match_count,
    ROW_NUMBER() OVER (
        ORDER BY filter_match_count DESC, b.publication_date DESC
    ) AS rank
FROM
    books b
    LEFT JOIN book_summaries bs ON b.book_id = bs.book_id
    LEFT JOIN authors au ON b.book_id = au.book_id
    LEFT JOIN genres g ON b.book_id = g.book_id
    LEFT JOIN contributors c ON b.book_id = c.book_id
    LEFT JOIN prizes pr ON b.book_id = pr.book_id
    LEFT JOIN locations l ON b.book_id = l.book_id
    LEFT JOIN publishers p ON b.publisher_id = p.publisher_id
    LEFT JOIN audience_details a ON b.book_id = a.book_id
WHERE
    -- At least one filter must match (avoid returning all books)
    (
        b.isbn = % s
        OR b.isbn_13 = % s
        OR au.author_name ILIKE % s
        OR g.genre_name ILIKE % s
        OR p.publisher_name ILIKE % s
        OR a.audience_type ILIKE % s
        OR EXTRACT(
            YEAR
            FROM b.publication_date
        ) BETWEEN % s AND %  s
    )
GROUP BY
    b.book_id,
    b.title,
    b.isbn,
    b.isbn_13,
    b.publication_date,
    b.publication_year,
    b.author_id,
    bs.summary_text,
    bs.summary_length,
    p.publisher_name,
    a.audience_type
ORDER BY filter_match_count DESC, b.publication_date DESC
LIMIT % s;