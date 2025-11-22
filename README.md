# Discord Research Assistant (DRA)

A Discord bot that generates Traditional Chinese summaries of arXiv papers with PDF reports and provides monthly curated lists of influential research papers.

## Features

- **📄 Paper Summarization**: Extract arXiv papers and generate structured Traditional Chinese summaries
- **🤖 Multi-Stage LLM Pipeline**: Pre-sanitizer → Main Summarizer → Validator for quality assurance
- **📊 PDF Reports**: Automatically generate professional PDF reports
- **💾 Smart Caching**: Redis-based caching for metadata, summaries, and PDFs (7-30 day TTLs)
- **⏱️ Rate Limiting**: Multi-tier rate limiting (default, trusted, admin)
- **📈 Cost Tracking**: Token usage and cost estimation per request and daily aggregates
- **🔄 Streaming Updates**: Real-time progress updates in Discord

## Architecture

```
Discord ↔ Bot Service ─┬─ LLM Service (OpenAI/vLLM)
                        ├─ Retriever (arXiv/Semantic Scholar)
                        ├─ PDF Exporter
                        ├─ Redis Cache
                        └─ Scheduler (Monthly Push)
```

### Multi-Stage LLM Pipeline

1. **Stage A (Pre-Sanitizer)**: Small model cleans and validates metadata
2. **Stage B (Main Summarizer)**: Primary model generates 繁體中文 structured summary
3. **Stage C (Validator)**: Low-temperature validation of JSON schema and language compliance

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- OpenAI API Key (or self-hosted vLLM)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd discord-arxiv
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Required environment variables**
   ```bash
   DISCORD_TOKEN=your_discord_bot_token
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_BASE_URL=https://api.openai.com/v1  # or vLLM endpoint
   ```

4. **Start services with Docker Compose**
   ```bash
   docker-compose up -d
   ```

5. **Check logs**
   ```bash
   docker-compose logs -f bot
   ```

### Local Development (without Docker)

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Redis**
   ```bash
   docker run -d -p 6379:6379 redis:7-alpine
   ```

3. **Run the bot**
   ```bash
   python -m src.bot.main
   ```

## Discord Commands

### `/summarize <arxiv_id_or_url>`

Generate a Traditional Chinese summary of an arXiv paper.

**Examples:**
```
/summarize 2401.01234
/summarize https://arxiv.org/abs/2401.01234
/summarize https://arxiv.org/pdf/2401.01234.pdf
```

**Output:**
- Structured embed with 4 sections (簡介/背景/方法/結論)
- Bullet points highlighting key contributions
- PDF report attachment

**Processing time:** Typically 10-30 seconds

### `/top-papers [month] [topic]`

Get top cited papers from arXiv and conferences (coming soon).

**Examples:**
```
/top-papers
/top-papers 2024-11
/top-papers 2024-11 LLM
```

## Configuration

### Environment Variables

See `.env.example` for all available options. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_MODEL` | Main summarization model | `gpt-4o-mini` |
| `OPENAI_MODEL_PRE` | Pre-processing model | `gpt-4o-mini` |
| `OPENAI_MODEL_VAL` | Validation model | `gpt-4o-mini` |
| `LLM_TEMPERATURE` | Generation temperature | `0.2` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `S2_API_KEY` | Semantic Scholar API key | (optional) |

### Rate Limits

Configured per user tier:

- **Default**: 3 requests/min, 20/day
- **Trusted**: 6 requests/min, 100/day
- **Admin**: Unlimited (tracked)

Adjust in `.env`:
```bash
RATE_LIMIT_DEFAULT_PER_MIN=3
RATE_LIMIT_DEFAULT_PER_DAY=20
```

### Using Self-Hosted vLLM

Uncomment the `vllm` service in `docker-compose.yml` and set:

```bash
OPENAI_BASE_URL=http://vllm:8000/v1
OPENAI_API_KEY=dummy  # vLLM doesn't require real key
```

## Project Structure

```
src/
├── bot/              # Discord bot & commands
│   ├── commands/     # Slash commands (/summarize, /top-papers)
│   └── main.py       # Bot entry point
├── llm/              # LLM pipeline
│   ├── client.py     # OpenAI-compatible client
│   ├── pipeline.py   # Multi-stage pipeline (A/B/C)
│   ├── prompts/      # Prompt templates
│   └── validators/   # Output validators
├── retriever/        # Data retrievers
│   ├── arxiv.py      # arXiv API client
│   └── semantic_scholar.py  # Citation data
├── exporter/         # PDF generation
│   └── pdf.py        # ReportLab PDF exporter
├── config/           # Configuration
│   ├── settings.py   # Pydantic settings
│   ├── logging.py    # Structured logging
│   └── cache.py      # Redis cache layer
└── telemetry/        # Observability (future)
```

## Caching Strategy

Redis key namespace: `dra:*`

| Key Pattern | TTL | Description |
|-------------|-----|-------------|
| `dra:paper:{id}:meta` | 7d | arXiv metadata |
| `dra:paper:{id}:summary:{model}:v1` | 30d | Generated summaries |
| `dra:pdf:{id}:{model}:v1` | 30d | PDF info |
| `dra:citations:{month}` | 7d | Monthly citation data |
| `dra:cost:daily:{date}` | 90d | Daily cost tracking |
| `dra:rate:discord:{user_id}:*` | 60s-24h | Rate limiting |

## Cost Management

The bot tracks token usage and estimated costs:

- Per-request tracking: `tokens_in`, `tokens_out`, `cost_estimated`, `duration_ms`
- Daily aggregates stored in Redis
- Simplified pricing estimates (configurable in `llm/client.py`)

View daily costs (requires admin access):
```python
from src.config.cache import RedisCache
cache = RedisCache("redis://localhost:6379/0")
await cache.connect()
costs = await cache.get_daily_cost("2024-11-22")
print(costs)  # {'tokens_in': 12500, 'tokens_out': 3200, 'cost_estimated': 0.025}
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Structure

- See `CLAUDE.md` for architecture guidelines
- See `TDS.md` for complete technical design specification
- See `AGENDA.md` for development phases and milestones

## Troubleshooting

### Bot not responding to commands

1. Check bot is online: `docker-compose logs bot`
2. Verify `SYNC_COMMANDS=true` in `.env`
3. For guild commands, set `COMMAND_SCOPE=guild` and `COMMAND_GUILD_IDS`
4. Manually sync: Bot will sync on startup if configured

### Redis connection errors

```bash
# Check Redis is running
docker-compose ps redis
# Check logs
docker-compose logs redis
```

### PDF generation issues

Chinese characters require proper font support. The PDF exporter uses reportlab's default Unicode support. For custom fonts, add TTF files and register in `src/exporter/pdf.py`.

### LLM API errors

- Check `OPENAI_BASE_URL` and `OPENAI_API_KEY`
- Verify API quota and rate limits
- Check logs: `docker-compose logs bot | grep llm_error`

## Roadmap

See `AGENDA.md` for detailed phases:

- ✅ **Phase 1**: Foundations (Bot, Retriever, LLM Pipeline)
- ✅ **Phase 2**: Feature Completion (/summarize command, PDF export)
- 🚧 **Phase 3**: Hardening (Tests, error handling, load testing)
- 📋 **Phase 4**: Launch (Monthly scheduler, /top-papers, observability)

## Contributing

This project follows the Technical Design Spec in `TDS.md`. Key principles:

- Multi-stage LLM pipeline for quality
- Aggressive caching for cost control
- Structured logging for observability
- Traditional Chinese (繁體中文) output
- Docker-first deployment

## License

[Add your license here]

## Support

For issues and questions:
- Check `CLAUDE.md` for development guidelines
- Review `TDS.md` for technical specifications
- See structured logs: `docker-compose logs bot | jq`
