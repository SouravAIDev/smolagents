-- Retrieve books via semantic (embedding-based) search with pgvector cosine similarity
-- Returns ranked results based on vector similarity to the query embedding
-- Used for Flow A standard retrieval and hybrid semantic + filter searches

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
    STRING_AGG(DISTINCT au.author_name, ', ' ORDER BY au.author_name) AS all_authors,
    STRING_AGG(DISTINCT g.genre_name, ', ' ORDER BY g.genre_name) AS all_genres,
    STRING_AGG(DISTINCT c.contributor_name, ', ' ORDER BY c.contributor_name) AS all_contributors,
    STRING_AGG(DISTINCT pr.prize_name, ', ' ORDER BY pr.prize_name) AS all_prizes,
    STRING_AGG(DISTINCT l.location_name, ', ' ORDER BY l.location_name) AS all_locations,
    -- Similarity score calculation
    (1 - (bs.summary_embedding <=> %s::vector)) AS embedding_similarity,
    ROW_NUMBER() OVER (ORDER BY (1 - (bs.summary_embedding <=> %s::vector)) DESC) AS rank
FROM books b
LEFT JOIN book_summaries bs ON b.book_id = bs.book_id
LEFT JOIN authors au ON b.book_id = au.book_id
LEFT JOIN genres g ON b.book_id = g.book_id
LEFT JOIN contributors c ON b.book_id = c.book_id
LEFT JOIN prizes pr ON b.book_id = pr.book_id
LEFT JOIN locations l ON b.book_id = l.book_id
LEFT JOIN publishers p ON b.publisher_id = p.publisher_id
LEFT JOIN audience_details a ON b.book_id = a.book_id
WHERE
    -- Similarity threshold filter
    (1 - (bs.summary_embedding <=> %s::vector)) >= %s
    -- Optional exact-match filters applied via WHERE clause
    %s
GROUP BY
    b.book_id, b.title, b.isbn, b.isbn_13, b.publication_date, b.publication_year,
    b.author_id, bs.summary_text, bs.summary_length, p.publisher_name, a.audience_type,
    bs.summary_embedding
ORDER BY embedding_similarity DESC
LIMIT %s;