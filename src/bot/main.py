"""Discord bot main entry point."""
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from src.config.settings import settings
from src.config.logging import configure_logging, get_logger
from src.config.cache import RedisCache
from src.retriever.arxiv import ArxivRetriever
from src.retriever.semantic_scholar import SemanticScholarRetriever
from src.llm.client import LLMClient
from src.llm.pipeline import SummarizationPipeline
from src.exporter.pdf import PDFExporter
from src.bot.commands.summarize import SummarizeCommand
from src.bot.commands.top_papers import TopPapersCommand

configure_logging()
logger = get_logger(__name__)


class DiscordResearchBot(commands.Bot):
    """Discord Research Assistant bot."""

    def __init__(self):
        """Initialize bot."""
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",  # Fallback prefix (we use slash commands)
            intents=intents,
        )

        # Initialize components
        self.cache: RedisCache = None
        self.arxiv: ArxivRetriever = None
        self.semantic_scholar: SemanticScholarRetriever = None
        self.llm: LLMClient = None
        self.pipeline: SummarizationPipeline = None
        self.pdf_exporter: PDFExporter = None

    async def setup_hook(self) -> None:
        """Setup hook called when bot starts."""
        logger.info("bot_setup_start")

        # Initialize cache
        self.cache = RedisCache(settings.redis_url)
        await self.cache.connect()

        # Initialize retrievers
        self.arxiv = ArxivRetriever(self.cache)
        self.semantic_scholar = SemanticScholarRetriever(
            self.cache,
            api_key=settings.s2_api_key if settings.s2_api_key else None
        )

        # Initialize LLM components
        self.llm = LLMClient(self.cache)
        self.pipeline = SummarizationPipeline(self.llm, self.cache)

        # Initialize PDF exporter
        self.pdf_exporter = PDFExporter()

        # Register commands
        self.tree.add_command(SummarizeCommand(self))
        self.tree.add_command(TopPapersCommand(self))

        # Sync commands if configured
        if settings.sync_commands:
            if settings.command_scope == "guild" and settings.guild_ids:
                for guild_id in settings.guild_ids:
                    guild = discord.Object(id=guild_id)
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                    logger.info("commands_synced_guild", guild_id=guild_id)
            else:
                await self.tree.sync()
                logger.info("commands_synced_global")

        logger.info("bot_setup_complete")

    async def on_ready(self) -> None:
        """Called when bot is ready."""
        logger.info("bot_ready", user=str(self.user), guilds=len(self.guilds))

    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Handle errors."""
        logger.error("bot_error", event=event)

    async def close(self) -> None:
        """Cleanup on bot shutdown."""
        logger.info("bot_shutdown")
        if self.cache:
            await self.cache.disconnect()
        await super().close()


async def main():
    """Main entry point."""
    bot = DiscordResearchBot()

    try:
        async with bot:
            await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        logger.info("bot_interrupted")
    except Exception as e:
        logger.error("bot_fatal_error", error=str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
