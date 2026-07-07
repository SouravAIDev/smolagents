#!/usr/bin/env python
"""
Database seeding script for Book Finder Agent test data.

This script initializes the PostgreSQL database with sample book data
including metadata, authors, genres, and excerpts for testing the agent.

Usage:
    python scripts/seed_database.py

Environment Variables:
    DB_HOST: PostgreSQL host (default: localhost)
    DB_PORT: PostgreSQL port (default: 5432)
    DB_NAME: Database name (default: book_finder_db)
    DB_USER: Database user (default: postgres)
    DB_PASSWORD: Database password (default: postgres)
"""

import os
import logging
import sys
from datetime import datetime, timedelta
import uuid

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Error: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection parameters
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'book_finder_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
}

# Sample book data
SAMPLE_BOOKS = [
    {
        'isbn': '978-0-06-112008-4',
        'title': 'To Kill a Mockingbird',
        'author': 'Harper Lee',
        'publisher': 'HarperCollins',
        'publication_date': '1960-07-11',
        'genre': 'Fiction',
        'summary': 'A gripping tale of racial injustice and childhood innocence in the American South.',
        'audience': 'Young Adults',
        'summary_snippet': 'When Southern lawyer Atticus Finch takes on a controversial case defending an innocent Black man',
    },
    {
        'isbn': '978-0-7432-7356-5',
        'title': '1984',
        'author': 'George Orwell',
        'publisher': 'Penguin Books',
        'publication_date': '1949-06-08',
        'genre': 'Dystopian',
        'summary': 'A dystopian social science fiction novel and cautionary tale about totalitarianism.',
        'audience': 'Adults',
        'summary_snippet': 'In a totalitarian state controlled by an all-knowing Party, citizens are under constant surveillance',
    },
    {
        'isbn': '978-0-14-143951-8',
        'title': 'Pride and Prejudice',
        'author': 'Jane Austen',
        'publisher': 'Penguin Classics',
        'publication_date': '1813-01-28',
        'genre': 'Romance',
        'summary': 'A romantic novel of manners and marriage in Georgian England.',
        'audience': 'Young Adults',
        'summary_snippet': 'Elizabeth Bennet navigates the complex social world of marriage prospects and family expectations',
    },
    {
        'isbn': '978-0-7432-7356-9',
        'title': 'The Great Gatsby',
        'author': 'F. Scott Fitzgerald',
        'publisher': 'Scribner',
        'publication_date': '1925-04-10',
        'genre': 'Fiction',
        'summary': 'A novel about wealth, love, and the American Dream in the Jazz Age.',
        'audience': 'Young Adults',
        'summary_snippet': 'Jay Gatsby pursues his lost love Daisy Buchanan across the bay in 1920s New York',
    },
    {
        'isbn': '978-0-545-01022-1',
        'title': 'Harry Potter and the Sorcerer\'s Stone',
        'author': 'J.K. Rowling',
        'publisher': 'Scholastic',
        'publication_date': '1998-09-01',
        'genre': 'Fantasy',
        'summary': 'A young wizard discovers his magical heritage and attends Hogwarts School of Witchcraft and Wizardry.',
        'audience': 'Children',
        'summary_snippet': 'Young Harry Potter learns he is a wizard and begins his magical education at Hogwarts',
    },
]

SAMPLE_EXCERPTS = [
    {
        'title': 'To Kill a Mockingbird',
        'excerpt': 'It was a pleasure to burn.',
        'location': 'Chapter 1',
    },
    {
        'title': '1984',
        'excerpt': 'War is peace. Freedom is slavery. Ignorance is strength.',
        'location': 'Book One, Chapter 1',
    },
    {
        'title': 'Pride and Prejudice',
        'excerpt': 'It is a truth universally acknowledged that a single man in possession of a good fortune must be in want of a wife.',
        'location': 'Chapter 1',
    },
    {
        'title': 'The Great Gatsby',
        'excerpt': 'So we beat on, boats against the current, borne back ceaselessly into the past.',
        'location': 'Chapter 9',
    },
]

SAMPLE_AWARDS = [
    {'title': 'To Kill a Mockingbird', 'award': 'Pulitzer Prize', 'year': 1961},
    {'title': '1984', 'award': 'Hugo Award', 'year': 1953},
    {'title': 'The Great Gatsby', 'award': 'National Book Award', 'year': 1926},
]


def create_tables(conn):
    """Create necessary tables if they don't exist."""
    logger.info("Creating tables...")
    
    with conn.cursor() as cur:
        # Enable pgvector extension
        cur.execute('CREATE EXTENSION IF NOT EXISTS vector;')
        
        # Create book_metadata table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS book_metadata_v2 (
                book_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                isbn VARCHAR(20) UNIQUE,
                title VARCHAR(255) NOT NULL,
                author_name VARCHAR(255),
                publisher_name VARCHAR(255),
                publication_date DATE,
                genre VARCHAR(100),
                subgenre VARCHAR(100),
                summary TEXT,
                audience VARCHAR(100),
                book_summary_embeddings vector(1536),
                title_embeddings vector(1536),
                genre_embeddings vector(1536),
                publisher_name_embeddings vector(1536),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create book_author table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS book_author_v2 (
                author_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                book_id UUID REFERENCES book_metadata_v2(book_id),
                author_name VARCHAR(255) NOT NULL,
                author_biography TEXT,
                author_name_embeddings vector(1536),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create book_genre table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS book_genre_v2 (
                genre_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                book_id UUID REFERENCES book_metadata_v2(book_id),
                genre VARCHAR(100) NOT NULL,
                subgenre VARCHAR(100),
                genre_embeddings vector(1536),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create book_excerpts table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS book_excerpts_v2 (
                excerpt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                book_id UUID REFERENCES book_metadata_v2(book_id),
                excerpt_text TEXT NOT NULL,
                excerpt_location VARCHAR(255),
                excerpt_embeddings vector(1536),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create book_award table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS book_award_v2 (
                award_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                book_id UUID REFERENCES book_metadata_v2(book_id),
                award_name VARCHAR(255) NOT NULL,
                award_year INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create book_publisher table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS book_publisher (
                publisher_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                publisher_name VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create session context table for pagination
        cur.execute('''
            CREATE TABLE IF NOT EXISTS book_retrieved_document_details (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                book_id UUID NOT NULL,
                question TEXT,
                book_data JSONB,
                is_displayed BOOLEAN DEFAULT FALSE,
                similarity_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # Create indices for performance
        cur.execute('CREATE INDEX IF NOT EXISTS idx_book_metadata_isbn ON book_metadata_v2(isbn);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_book_author_book_id ON book_author_v2(book_id);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_book_genre_book_id ON book_genre_v2(book_id);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_book_excerpts_book_id ON book_excerpts_v2(book_id);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_book_award_book_id ON book_award_v2(book_id);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_session_context_session_id ON book_retrieved_document_details(session_id);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_session_context_displayed ON book_retrieved_document_details(session_id, is_displayed);')
        
        conn.commit()
    
    logger.info("✓ Tables created successfully")


def seed_sample_data(conn):
    """Insert sample book data into the database."""
    logger.info("Seeding sample data...")
    
    with conn.cursor() as cur:
        # Insert publishers
        for book in SAMPLE_BOOKS:
            publisher = book['publisher']
            cur.execute(
                'INSERT INTO book_publisher (publisher_name) VALUES (%s) ON CONFLICT (publisher_name) DO NOTHING;',
                (publisher,)
            )
        conn.commit()
        
        # Insert books
        for book in SAMPLE_BOOKS:
            cur.execute('''
                INSERT INTO book_metadata_v2 (isbn, title, author_name, publisher_name, publication_date, genre, summary, audience)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (isbn) DO NOTHING
                RETURNING book_id;
            ''', (
                book['isbn'],
                book['title'],
                book['author'],
                book['publisher'],
                book['publication_date'],
                book['genre'],
                book['summary'],
                book['audience'],
            ))
            
            result = cur.fetchone()
            if result:
                book_id = result[0]
                
                # Insert author
                cur.execute('''
                    INSERT INTO book_author_v2 (book_id, author_name)
                    VALUES (%s, %s);
                ''', (book_id, book['author']))
                
                # Insert genre
                cur.execute('''
                    INSERT INTO book_genre_v2 (book_id, genre)
                    VALUES (%s, %s);
                ''', (book_id, book['genre']))
        
        conn.commit()
        
        # Insert excerpts
        for excerpt_data in SAMPLE_EXCERPTS:
            cur.execute(
                'SELECT book_id FROM book_metadata_v2 WHERE title = %s LIMIT 1;',
                (excerpt_data['title'],)
            )
            result = cur.fetchone()
            
            if result:
                book_id = result[0]
                cur.execute('''
                    INSERT INTO book_excerpts_v2 (book_id, excerpt_text, excerpt_location)
                    VALUES (%s, %s, %s);
                ''', (
                    book_id,
                    excerpt_data['excerpt'],
                    excerpt_data['location'],
                ))
        
        conn.commit()
        
        # Insert awards
        for award_data in SAMPLE_AWARDS:
            cur.execute(
                'SELECT book_id FROM book_metadata_v2 WHERE title = %s LIMIT 1;',
                (award_data['title'],)
            )
            result = cur.fetchone()
            
            if result:
                book_id = result[0]
                cur.execute('''
                    INSERT INTO book_award_v2 (book_id, award_name, award_year)
                    VALUES (%s, %s, %s);
                ''', (
                    book_id,
                    award_data['award'],
                    award_data['year'],
                ))
        
        conn.commit()
    
    logger.info("✓ Sample data seeded successfully")


def main():
    """Main function to orchestrate database seeding."""
    try:
        # Connect to PostgreSQL
        logger.info(f"Connecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        conn = psycopg2.connect(**DB_CONFIG)
        
        # Create tables
        create_tables(conn)
        
        # Seed sample data
        seed_sample_data(conn)
        
        # Close connection
        conn.close()
        
        logger.info("✓ Database seeding complete!")
        return 0
        
    except psycopg2.OperationalError as e:
        logger.error(f"Could not connect to database: {e}")
        return 1
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

