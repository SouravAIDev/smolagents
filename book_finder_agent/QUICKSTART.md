# Book Finder Agent — Quick Start Guide

Get the Book Finder Agent running in **5 minutes** for local development.

## Prerequisites

- **Docker & Docker Compose** installed and running
- **Python 3.10+** (for local testing)
- **curl** or similar HTTP client
- **5 GB disk space** for database and dependencies

## 1. Clone and Setup (1 minute)

```bash
git clone <repository-url>
cd book_finder_agent

# Create .env from example
cp .env.example .env
```

## 2. Start Services with Docker Compose (2 minutes)

```bash
# Start PostgreSQL, Redis (optional), and the agent
docker-compose up -d

# Wait for services to start
sleep 10

# Verify agent is running
curl http://localhost:5000/utility/book-content-rag-agent/
```

Expected output:
```
Book Finder Agent is running!
```

## 3. Test the Agent (1 minute)

### Health Check

```bash
curl http://localhost:5000/utility/book-content-rag-agent/health
```

Expected response:
```json
{"status": "healthy"}
```

### Make Your First Request

```bash
curl -X POST http://localhost:5000/utility/book-content-rag-agent/prediction \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test",
    "session_id": "dev-session-1",
    "concierge_id": "test-concierge",
    "question": "Find books about artificial intelligence",
    "agent_arguments": {
      "user_query": "Find books about artificial intelligence",
      "book_summary_details": null,
      "search_sentence": null,
      "genre_details": null,
      "quotes": null,
      "audience_details": null,
      "location_details": null,
      "contributor_details": null,
      "character_details": null,
      "contributor_biography_details": null,
      "prize_details": null,
      "section_details": null,
      "publisher_details": null,
      "imprint_details": null,
      "show_more_details": null
    }
  }'
```

## 4. View Logs

```bash
# See agent logs
docker-compose logs -f book-finder-agent

# See database logs
docker-compose logs -f postgres
```

## 5. Stop Services

```bash
docker-compose down
```

---

## Common Customizations

### Change Similarity Threshold

Edit `.env`:

```bash
SIMILARITY_THRESHOLD=0.5  # Default is 0.3, increase for stricter matching
```

Then restart:

```bash
docker-compose restart book-finder-agent
```

### Use a Different LLM Model

Edit `.env`:

```bash
LLM_MODEL_NAME=gemini-1.5-pro  # or another available model
LLM_TEMPERATURE=0.5  # Lower = more deterministic, Higher = more creative
```

Restart agent:

```bash
docker-compose restart book-finder-agent
```

### Increase Max Books Returned

Edit `.env`:

```bash
MAX_BOOK_IDS=500  # Default is 300
BOOKS_PER_RESULT=10  # Default is 5
```

Restart:

```bash
docker-compose restart book-finder-agent
```

### Enable Debugging

Edit `.env`:

```bash
FLASK_ENV=development
LOG_LEVEL=DEBUG
```

Restart:

```bash
docker-compose restart book-finder-agent
```

Then view detailed logs:

```bash
docker-compose logs -f book-finder-agent | grep "DEBUG"
```

---

## Example: Pagination (Show More)

After getting initial results, request more:

```bash
curl -X POST http://localhost:5000/utility/book-content-rag-agent/prediction \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test",
    "session_id": "dev-session-1",
    "concierge_id": "test-concierge",
    "question": "Find books about artificial intelligence",
    "agent_arguments": {
      "user_query": "Find books about artificial intelligence",
      "show_more_details": {
        "length": 5,
        "question": "Find books about artificial intelligence"
      }
    }
  }'
```

---

## Next Steps

1. **Read full guides**:
   - `DEVELOPER_GUIDE.md` for complete local setup
   - `DEPLOYMENT_GUIDE.md` to deploy to production
   - `CONFIG_REFERENCE.md` for all configuration options

2. **Run tests**:
   ```bash
   docker-compose exec book-finder-agent python -m pytest tests/ -v
   ```

3. **Check metrics**:
   ```bash
   curl http://localhost:5000/metrics  # If Prometheus is enabled
   ```

4. **Inspect database**:
   ```bash
   docker-compose exec postgres psql -U postgres -d book_finder_db
   ```

---

## Troubleshooting

### Port 5000 already in use?

```bash
# Edit docker-compose.yml and change
ports:
  - "5001:5000"  # Map to 5001 instead
```

### Docker Compose file not found?

Create a minimal `docker-compose.yml`:

```yaml
version: '3.8'
services:
  postgres:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_DB: book_finder_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  book-finder-agent:
    build: .
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: book_finder_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      GCLOUD_PROJECT_ID: test-project
      FLASK_ENV: development
    ports:
      - "5000:5000"
    depends_on:
      - postgres

volumes:
  postgres_data:
```

### Agent won't start?

```bash
# Check logs
docker-compose logs book-finder-agent

# Rebuild image
docker-compose build --no-cache book-finder-agent
docker-compose up
```

### Can't connect to database?

```bash
# Verify database is running
docker-compose ps

# Test connection
docker-compose exec postgres psql -U postgres -d book_finder_db -c "SELECT 1;"
```

---

## What's Next?

Once you have the agent running:

1. **Explore the API**: Try different filter combinations
2. **Adjust Configuration**: Tweak scoring weights, thresholds, model parameters
3. **Read Full Guides**: Dive into DEVELOPER_GUIDE.md for advanced setups
4. **Deploy**: Follow DEPLOYMENT_GUIDE.md to move to production

**For detailed information, see DEVELOPER_GUIDE.md**

