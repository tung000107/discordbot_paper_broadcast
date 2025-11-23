"""Top papers command for monthly highlights."""
import discord
from discord import app_commands
from datetime import datetime
from src.config.logging import get_logger, LogContext
from src.agents import TopPapersCoordinator, TopicCategory
from src.agents.retriever import RetrieverAgent
from src.agents.summarizer import SummarizerAgent
from src.agents.categorizer import TopicCategorizer
from src.llm.client import LLMClient
from src.llm.pipeline import SummarizationPipeline
from src.retriever.semantic_scholar import SemanticScholarRetriever
from src.config.cache import RedisCache
from src.config.settings import settings

logger = get_logger(__name__)


class TopPapersCommand(app_commands.Command):
    """Slash command: /top-papers [month] [topic]"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            name="top-papers",
            description="Get top cited papers from arXiv and conferences",
            callback=self.callback,
        )

        # Initialize dependencies
        self.cache = RedisCache(redis_url=settings.redis_url)
        self.llm_client = LLMClient(cache=self.cache)
        self.s2_retriever = SemanticScholarRetriever(
            cache=self.cache,
            api_key=settings.s2_api_key or None
        )

        # Initialize agents
        self.retriever_agent = RetrieverAgent(
            s2_retriever=self.s2_retriever,
            cache=self.cache,
        )
        self.pipeline = SummarizationPipeline(
            llm_client=self.llm_client,
            cache=self.cache,
        )
        self.summarizer_agent = SummarizerAgent(
            pipeline=self.pipeline,
            max_concurrent=3,
        )
        self.categorizer = TopicCategorizer(llm_client=self.llm_client)

        # Initialize coordinator
        self.coordinator = TopPapersCoordinator(
            retriever=self.retriever_agent,
            summarizer=self.summarizer_agent,
            categorizer=self.categorizer,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
        month: str = None,
        topic: str = None
    ):
        """Handle /top-papers command.

        Args:
            interaction: Discord interaction
            month: Optional month (YYYY-MM format)
            topic: Optional topic filter
        """
        with LogContext(
            user_id=str(interaction.user.id),
            channel_id=str(interaction.channel_id),
            command="top-papers",
        ):
            logger.info("command_top_papers", month=month, topic=topic)

            await interaction.response.defer()

            try:
                # Default to current month if not specified
                if not month:
                    month = datetime.utcnow().strftime("%Y-%m")

                # Parse topic filter if provided
                topic_filter = None
                if topic:
                    topic_map = {
                        "LLM架構": TopicCategory.LLM_ARCHITECTURE,
                        "LLM應用": TopicCategory.LLM_APPLICATION,
                        "RAG改良": TopicCategory.RAG_IMPROVEMENT,
                        "RAG應用": TopicCategory.RAG_APPLICATION,
                        "OCR": TopicCategory.OCR,
                        "LLM Router": TopicCategory.LLM_ROUTER,
                    }
                    topic_filter = topic_map.get(topic)

                # Send initial processing message
                processing_embed = discord.Embed(
                    title=f"🔍 正在搜尋 {month} 熱門論文...",
                    description="正在檢索論文並生成摘要，請稍候...",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=processing_embed)

                # Retrieve and process papers using coordinator
                # min_citations=None enables adaptive threshold based on month age
                grouped_papers = await self.coordinator.get_top_papers(
                    month=month,
                    topic_filter=topic_filter,
                    top_n=20,
                    min_citations=None,  # Adaptive: 0 for current month, increases with age
                )

                if not grouped_papers:
                    no_results_embed = discord.Embed(
                        title="📊 查無結果",
                        description=f"在 {month} 找不到符合條件的論文。",
                        color=discord.Color.orange()
                    )
                    await interaction.edit_original_response(embed=no_results_embed)
                    return

                # Create embeds for each topic (max 5 papers per topic)
                embeds = []
                for topic_category, papers in grouped_papers.items():
                    # Limit to 5 papers per topic as per TDS
                    top_papers = papers[:5]

                    embed = discord.Embed(
                        title=f"📊 {month} 熱門論文 - {topic_category.value}",
                        color=discord.Color.blue()
                    )

                    for idx, ranked_paper in enumerate(top_papers, 1):
                        paper = ranked_paper.candidate
                        summary = ranked_paper.summary

                        # Build paper description
                        description_parts = [
                            f"**作者**: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}",
                            f"**引用數**: {paper.citation_count}",
                            f"**發布日期**: {paper.published.strftime('%Y-%m-%d')}",
                        ]

                        # Add summary intro if available
                        if summary and "intro" in summary:
                            intro = summary["intro"][:150]
                            description_parts.append(f"\n{intro}...")

                        description_parts.append(f"\n[arXiv]({paper.entry_url}) | [PDF]({paper.pdf_url})")

                        embed.add_field(
                            name=f"{idx}. {paper.title[:100]}{'...' if len(paper.title) > 100 else ''}",
                            value="\n".join(description_parts),
                            inline=False
                        )

                    embed.set_footer(text=f"共 {len(papers)} 篇論文 | 顯示前 {len(top_papers)} 篇")
                    embed.timestamp = discord.utils.utcnow()

                    embeds.append(embed)

                # Send embeds (Discord has a limit of 10 embeds per message)
                if embeds:
                    await interaction.edit_original_response(embed=embeds[0])
                    for embed in embeds[1:10]:  # Send remaining embeds
                        await interaction.followup.send(embed=embed)

                logger.info("command_top_papers_complete", topics=len(grouped_papers))

            except Exception as e:
                logger.error("command_top_papers_error", error=str(e))
                error_embed = discord.Embed(
                    title="❌ 錯誤",
                    description=f"無法取得熱門論文：{str(e)[:200]}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed)


@app_commands.describe(
    month="Month in YYYY-MM format (default: current month)",
    topic="Topic filter (e.g., LLM, RAG, OCR)"
)
async def top_papers_decorator(month: str = None, topic: str = None):
    """Decorator for type hints."""
    pass
