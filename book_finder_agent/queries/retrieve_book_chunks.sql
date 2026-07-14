-- Retrieve supporting manuscript chunks ranked by semantic similarity
-- Parameters: query_vector (VECTOR(1536)), isbn_list (list of ISBNs), limit (int)

SELECT
    chunk_id,
    isbn,
    chunk_order_number,
    chunk_text,
    1 - (chunk_embeddings <=> %s::vector) AS similarity_score,
    chunk_embeddings <=> %s::vector AS distance
FROM book_content_chunked_backup_2
WHERE isbn IN ({isbn_placeholders})
ORDER BY chunk_embeddings <=> %s::vector ASC
LIMIT %s;