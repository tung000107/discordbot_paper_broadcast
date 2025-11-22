"""Top papers command for monthly highlights."""
import discord
from discord import app_commands
from datetime import datetime
from src.config.logging import get_logger, LogContext

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

                # TODO: Implement actual top papers retrieval
                # For now, send a placeholder response

                embed = discord.Embed(
                    title=f"📊 {month} 熱門論文",
                    description="此功能正在開發中...\n\n"
                               "即將支援：\n"
                               "• arXiv 熱門論文\n"
                               "• ICLR/NeurIPS/ACL/CVPR 會議論文\n"
                               "• 主題分類（LLM、RAG、OCR 等）\n"
                               "• 引用數排序",
                    color=discord.Color.blue()
                )

                if topic:
                    embed.add_field(
                        name="篩選主題",
                        value=topic,
                        inline=False
                    )

                embed.set_footer(text="Monthly Push Scheduler")
                embed.timestamp = discord.utils.utcnow()

                await interaction.followup.send(embed=embed)

                logger.info("command_top_papers_complete")

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
