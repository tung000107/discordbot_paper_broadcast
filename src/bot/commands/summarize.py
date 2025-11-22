"""Summarize command for arXiv papers."""
import discord
from discord import app_commands
from pathlib import Path
from src.config.settings import settings
from src.config.logging import get_logger, LogContext
from src.retriever.arxiv import ArxivRetriever

logger = get_logger(__name__)


class SummarizeCommand(app_commands.Command):
    """Slash command: /summarize <arxiv_id_or_url>"""

    def __init__(self, bot):
        self.bot = bot
        super().__init__(
            name="summarize",
            description="Generate a Traditional Chinese summary of an arXiv paper",
            callback=self.callback,
        )

    async def callback(self, interaction: discord.Interaction, arxiv_input: str):
        """Handle /summarize command.

        Args:
            interaction: Discord interaction
            arxiv_input: arXiv ID or URL
        """
        with LogContext(
            user_id=str(interaction.user.id),
            channel_id=str(interaction.channel_id),
            command="summarize",
        ):
            logger.info("command_summarize", input=arxiv_input[:100])

            # Defer response (processing may take time)
            await interaction.response.defer()

            try:
                # Extract arXiv ID
                arxiv_ids = ArxivRetriever.extract_arxiv_ids(arxiv_input)
                if not arxiv_ids:
                    await interaction.followup.send(
                        "❌ 無法識別 arXiv ID。\n\n"
                        "請提供格式如下：\n"
                        "• `2401.01234`\n"
                        "• `https://arxiv.org/abs/2401.01234`\n"
                        "• `https://arxiv.org/pdf/2401.01234.pdf`"
                    )
                    return

                arxiv_id = arxiv_ids[0]  # Take first ID
                logger.info("arxiv_id_extracted", arxiv_id=arxiv_id)

                # Check rate limit
                allowed, reason = await self.bot.cache.check_rate_limit(
                    str(interaction.user.id),
                    settings.rate_limit_default_per_min,
                    settings.rate_limit_default_per_day,
                )
                if not allowed:
                    await interaction.followup.send(f"⏱️ {reason}")
                    return

                # Send initial status
                embed = discord.Embed(
                    title="📄 正在處理論文...",
                    description=f"arXiv ID: `{arxiv_id}`",
                    color=discord.Color.blue()
                )
                status_msg = await interaction.followup.send(embed=embed)

                # Retrieve paper metadata
                embed.description = f"arXiv ID: `{arxiv_id}`\n\n⏳ 正在擷取論文資料..."
                await status_msg.edit(embed=embed)

                paper = await self.bot.arxiv.get_paper(arxiv_id)
                if not paper:
                    embed.color = discord.Color.red()
                    embed.title = "❌ 錯誤"
                    embed.description = f"找不到論文：{arxiv_id}"
                    await status_msg.edit(embed=embed)
                    return

                # Update status: Generating summary
                embed.description = (
                    f"**{paper['title'][:100]}**\n\n"
                    f"⏳ 正在生成摘要...\n"
                    f"（此過程可能需要 10-30 秒）"
                )
                await status_msg.edit(embed=embed)

                # Generate summary
                summary = await self.bot.pipeline.summarize(paper)

                # Update status: Generating PDF
                embed.description = (
                    f"**{paper['title'][:100]}**\n\n"
                    f"✅ 摘要完成\n"
                    f"⏳ 正在生成 PDF..."
                )
                await status_msg.edit(embed=embed)

                # Export PDF
                pdf_info = self.bot.pdf_exporter.export(paper, summary)

                # Create final embed with summary
                final_embed = discord.Embed(
                    title=paper["title"][:256],  # Discord limit
                    url=paper["entry_url"],
                    color=discord.Color.green()
                )

                final_embed.add_field(
                    name="📝 簡介",
                    value=summary["intro"][:1024],
                    inline=False
                )
                final_embed.add_field(
                    name="📚 背景",
                    value=summary["background"][:1024],
                    inline=False
                )
                final_embed.add_field(
                    name="🔬 方法",
                    value=summary["method"][:1024],
                    inline=False
                )
                final_embed.add_field(
                    name="🎯 結論",
                    value=summary["conclusion"][:1024],
                    inline=False
                )

                # Add bullet points
                if summary.get("bullet_points"):
                    bullets = "\n".join([f"• {bp}" for bp in summary["bullet_points"][:5]])
                    final_embed.add_field(
                        name="💡 重點摘要",
                        value=bullets[:1024],
                        inline=False
                    )

                final_embed.set_footer(text=f"arXiv: {paper['arxiv_id']} | 生成時間")
                final_embed.timestamp = discord.utils.utcnow()

                # Send PDF as attachment
                pdf_path = Path(pdf_info["pdf_path"])
                if pdf_path.exists():
                    file = discord.File(str(pdf_path), filename=pdf_path.name)
                    await interaction.followup.send(embed=final_embed, file=file)
                    # Delete status message
                    await status_msg.delete()
                else:
                    # Fallback: send embed without PDF
                    await interaction.followup.send(embed=final_embed)
                    await status_msg.delete()

                logger.info("command_summarize_complete", arxiv_id=arxiv_id)

            except Exception as e:
                logger.error("command_summarize_error", error=str(e))
                error_embed = discord.Embed(
                    title="❌ 處理錯誤",
                    description=f"處理論文時發生錯誤：{str(e)[:200]}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed)


@app_commands.describe(
    arxiv_input="arXiv ID or URL (e.g., 2401.01234 or https://arxiv.org/abs/2401.01234)"
)
async def summarize_decorator(arxiv_input: str):
    """Decorator for type hints."""
    pass
