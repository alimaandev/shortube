from __future__ import annotations

import logging

import click

from shortube.config import get_settings
from shortube.db import Database
from shortube.discover import discover
from shortube.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def _run_pipeline(
    topic: str,
    privacy: str = "private",
    channel: str | None = None,
    dry_run: bool = False,
    video_id: int | None = None,
) -> dict[str, str]:
    click.echo(f"Pipeline starting for: {topic[:60]}...")
    result = run_pipeline(
        topic, privacy=privacy, channel_id=channel,
        dry_run=dry_run, video_id=video_id,
    )
    if "url" in result:
        click.echo(f"Done — {result['url']}")
    else:
        click.echo("Pipeline complete.")
    return result


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is not None:
        return
    ctx.invoke(show_trends)


@cli.command()
@click.option("--niche", default=None)
@click.option("--count", default=10, type=int)
def show_trends(niche, count):
    """Show trending topics for your niche."""
    niche_val = niche or get_settings().niche
    db = Database()
    ideas = discover(niche_val, max_results=count)
    for idea in ideas:
        db.add_topic(idea.title, niche=niche_val, source=idea.source, score=idea.score)

    if not ideas:
        click.echo("No trending topics found.")
        return

    click.echo(f"\nTrending topics for niche: {niche_val}")
    click.echo("-" * 60)
    click.echo(f"{'#':<4} {'Score':<7} {'Source':<15} {'Title'}")
    click.echo("-" * 60)
    for i, idea in enumerate(ideas, 1):
        click.echo(
            f"{i:<4} {idea['score']:<7.1f} {idea['source']:<15} "
            f"{idea['title'][:80]}"
        )
    click.echo(f"\n{len(ideas)} topics found")
    click.echo("Generate:  python -m shortube.main generate -t \"Title\"")
    click.echo("Auto:      python -m shortube.main auto")
    click.echo("Desktop:   python -m shortube.main desktop")


@cli.command()
@click.option("-t", "--topic", required=True)
@click.option("--dry-run", is_flag=True)
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
def generate(topic, dry_run, public, channel):
    """Generate a Short for a specific topic."""
    privacy = "public" if public else "private"
    db = Database()
    tid = db.add_topic(topic, niche=get_settings().niche)
    vid = db.create_video(tid, privacy=privacy)
    _run_pipeline(topic, privacy, channel, dry_run, video_id=vid)


@cli.command()
@click.option("--niche", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
def auto(niche, dry_run, public, channel):
    """Auto-mode: pick the best undiscovered topic, generate, upload."""
    niche_val = niche or get_settings().niche
    db = Database()
    ideas = discover(niche_val, max_results=5)

    for idea in ideas:
        if not db.is_topic_used(idea.title):
            topic = idea.title
            click.echo(f"Auto-selected: {topic}")
            tid = db.add_topic(topic, niche=niche_val, source=idea.source, score=idea.score)
            privacy = "public" if public else "private"
            vid = db.create_video(tid, privacy=privacy)
            try:
                _run_pipeline(topic, privacy, channel, dry_run, video_id=vid)
                db.mark_topic_used(topic)
            except Exception as e:
                click.echo(f"Pipeline failed: {e}", err=True)
            return

    click.echo("No undiscovered topics found.")


@cli.command()
@click.argument("channel_id", required=False)
def set_channel(channel_id):
    """Set the default YouTube channel ID (persists in .env)."""
    env_path = get_settings().base_dir / ".env"
    if not channel_id:
        click.echo(f"Current channel: {get_settings().upload_channel_id or '(none)'}")
        return

    lines = []
    found = False
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("UPLOAD_CHANNEL_ID="):
                lines.append(f"UPLOAD_CHANNEL_ID={channel_id}")
                found = True
            else:
                lines.append(line)

    if not found:
        lines.append(f"UPLOAD_CHANNEL_ID={channel_id}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(f"Channel set to: {channel_id}")


@cli.command()
def desktop():
    """Start the desktop UI."""
    from shortube.desktop import run
    run()


if __name__ == "__main__":
    cli()
