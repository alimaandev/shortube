from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import click

from shortube.config import DRAFT_DIR, NICHE as DEFAULT_NICHE
from shortube.config.settings import get_settings
from shortube.core.pipeline import Pipeline
from shortube.discovery import DiscoveryEngine
from shortube.shared.llm import create_llm
from shortube.shared.draft import (
    clear_used_topics,
    is_topic_used,
    load_draft,
    mark_topic_used,
    save_draft,
    slugify,
)
from shortube.modules.assemble import assemble
from shortube.modules.upload import list_channels, upload_video
from shortube.modules.voice import generate_voiceover


# ── Helpers ────────────────────────────────────────────────────────────

def _run_pipeline(
    topic: str, public: bool, channel: str | None,
    dry_run: bool = False, use_agents: bool = False,
) -> dict[str, str]:
    click.echo(f"[1/5] Generating script for: {topic[:60]}...")
    privacy = "public" if public else "private"
    pipeline = Pipeline()
    if use_agents:
        pipeline.use_agents(enabled=True)
    result = pipeline.run(
        topic, privacy=privacy, channel_id=channel, dry_run=dry_run,
    )
    click.echo(f"  Script: {result.get('script', 'N/A')}")
    click.echo(f"  Voice:  {result.get('voiceover', 'N/A')}")
    click.echo(f"  Video:  {result.get('video', 'N/A')}")
    if not dry_run and "url" in result:
        click.echo(f"  Upload: {result['url']}")
    click.echo("Done!")
    return result


def _discover_topics(
    niche: str,
    count: int,
    refresh: bool,
) -> list[dict]:
    engine = DiscoveryEngine(niche=niche)
    engine.register_defaults()
    ideas = engine.discover(niche=niche, max_results=count, use_cache=not refresh)

    if refresh:
        assets_dir = get_settings().assets_dir
        fresh = [i for i in ideas if not is_topic_used(assets_dir, i.title)]
        if not fresh and ideas:
            click.echo("  All topics already used. Clearing tracker for fresh start.")
            clear_used_topics(assets_dir)
            fresh = [i for i in ideas if not is_topic_used(assets_dir, i.title)]
        ideas = fresh

    return [{"title": i.title, "source": i.source, "score": i.score, "reason": i.reason} for i in ideas]


# ── Single unified command ─────────────────────────────────────────────

# ── Unified entry point ────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Shorts Automator — discover, generate, and upload YouTube Shorts.

    Run without arguments to see trending topics.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Default: show trends
    ctx.invoke(show_trends)


@cli.command()
@click.option("--niche", default=None)
@click.option("--count", default=10, type=int)
@click.option("--refresh", is_flag=True)
@click.option("--json-output", is_flag=True)
def show_trends(niche, count, refresh, json_output):
    """Show trending topics for your niche."""
    niche_val = niche or DEFAULT_NICHE
    ideas = _discover_topics(niche_val, count, refresh)
    if not ideas:
        click.echo("No trending topics found. Try --refresh or change --niche.")
        return
    if json_output:
        click.echo(json.dumps(ideas, indent=2, ensure_ascii=False))
        return
    click.echo(f"\nTrending topics for niche: {niche_val}")
    click.echo("-" * 60)
    click.echo(f"{'#':<4} {'Score':<7} {'Source':<15} {'Title'}")
    click.echo("-" * 60)
    for i, idea in enumerate(ideas, 1):
        click.echo(f"{i:<4} {idea['score']:<7.1f} {idea['source']:<15} {idea['title'][:80]}")
    click.echo(f"\n{len(ideas)} topics found")
    click.echo("\nGenerate with:  python -m shortube generate --topic \"Title\"")
    click.echo("Auto mode:      python -m shortube auto")
    click.echo("Batch mode:     python -m shortube batch-gen --count 3")


@cli.command()
@click.option("-t", "--topic", required=True, help="Topic for the Short")
@click.option("--agents", is_flag=True, help="Use the multi-agent script writer")
@click.option("--dry-run", is_flag=True, help="Generate locally without uploading")
@click.option("--public", is_flag=True, help="Upload as public")
@click.option("--channel", default=None, help="YouTube channel ID")
def generate(topic, agents, dry_run, public, channel):
    """Generate a Short for a specific topic."""
    _run_pipeline(topic, public, channel, dry_run, agents)
    if not dry_run:
        mark_topic_used(get_settings().assets_dir, topic)


@cli.command()
@click.option("--niche", default=None)
@click.option("--refresh", is_flag=True)
@click.option("--agents", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
def auto(niche, refresh, agents, dry_run, public, channel):
    """Auto-mode: pick the best undiscovered topic, generate, upload."""
    niche_val = niche or DEFAULT_NICHE
    ideas = _discover_topics(niche_val, 1, refresh)
    if not ideas:
        click.echo("No undiscovered topics found. Use --refresh to reset.")
        return
    topic = ideas[0]["title"]
    click.echo(f"Auto-selected: {topic}")
    _run_pipeline(topic, public, channel, dry_run, agents)
    if not dry_run:
        mark_topic_used(get_settings().assets_dir, topic)


@cli.command()
@click.option("--count", default=3, type=int, help="Number of topics to generate")
@click.option("--niche", default=None)
@click.option("--refresh", is_flag=True)
@click.option("--agents", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
@click.option("--parallel", default=1, type=int, help="Number of parallel workers")
def batch_gen(count, niche, refresh, agents, dry_run, public, channel, parallel):
    """Batch generate multiple undiscovered topics."""
    niche_val = niche or DEFAULT_NICHE
    ideas = _discover_topics(niche_val, count, refresh)
    if not ideas:
        click.echo("No undiscovered topics found. Use --refresh to reset.")
        return
    click.echo(f"Batch generating {len(ideas)} topics with {parallel} worker(s)...")
    if parallel > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def _work(t):
            try:
                _run_pipeline(t, public, channel, dry_run, agents)
                if not dry_run:
                    mark_topic_used(get_settings().assets_dir, t)
                return t, None
            except Exception as e:
                return t, str(e)
        with ThreadPoolExecutor(max_workers=parallel) as ex:
            topics = [i["title"] for i in ideas]
            futures = {ex.submit(_work, t): t for t in topics}
            for f in as_completed(futures):
                t, err = f.result()
                if err:
                    click.echo(f"  FAILED: {t[:60]} — {err}", err=True)
                else:
                    click.echo(f"  Done: {t[:60]}")
    else:
        for i, idea in enumerate(ideas, 1):
            t = idea["title"]
            click.echo(f"\n[{i}/{len(ideas)}] {t[:60]}")
            try:
                _run_pipeline(t, public, channel, dry_run, agents)
                if not dry_run:
                    mark_topic_used(get_settings().assets_dir, t)
            except Exception as e:
                click.echo(f"  FAILED: {e}", err=True)


@cli.command()
def reset():
    """Clear the used-topics tracker."""
    clear_used_topics(get_settings().assets_dir)
    click.echo("Used-topics tracker cleared.")


@cli.command()
def channels():
    """List your YouTube channels."""
    click.echo("Your channels:")
    for ch in list_channels():
        click.echo(f"  {ch['title']}  →  {ch['id']}")


# ── Legacy subcommands (hidden, backward compat) ───────────────────────


@cli.command(hidden=True, name="run")
@click.option("--topic", required=True)
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--use-agents", is_flag=True)
def run_legacy(topic, public, channel, dry_run, use_agents):
    _run_pipeline(topic, public, channel, dry_run, use_agents)


@cli.command(hidden=True, name="script")
@click.option("--topic", required=True)
@click.option("--use-agents", is_flag=True)
def script_legacy(topic, use_agents):
    pipeline = Pipeline()
    if use_agents:
        pipeline.use_agents(enabled=True)
    script_obj = pipeline.write_script(topic)
    data = script_obj.to_legacy_dict()
    path = save_draft(topic, data, DRAFT_DIR)
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    click.echo(f"\nDraft saved: {path}")


@cli.command(hidden=True, name="produce")
@click.option("--draft", required=True)
@click.option("--output", default=None)
def produce_legacy(draft, output):
    data = load_draft(draft)
    draft_dir = Path(draft).parent
    voice_path = str(draft_dir / "voiceover.mp3")
    click.echo("[1/3] Voiceover...")
    generate_voiceover(data["full_text"], voice_path)
    click.echo("[2/3] Visuals...")
    from shortube.config import PEXELS_API_KEY
    from shortube.storyboard.providers import PexelsProvider
    provider = PexelsProvider(PEXELS_API_KEY)
    clip_paths: list[str] = []
    for kw in data.get("keywords", []):
        assets = provider.search(kw, media_type="video", orientation="portrait", max_results=3)
        for asset in assets:
            dest = draft_dir / f"clip_{asset.provider}_{hashlib.sha256(asset.url.encode()).hexdigest()[:16]}.mp4"
            if not dest.exists():
                provider.download(asset.url, dest)
            clip_paths.append(str(dest))
            if len(clip_paths) >= 6:
                break
        if len(clip_paths) >= 6:
            break
    click.echo(f"  {len(clip_paths)} clips")
    click.echo("[3/3] Assembly...")
    video_path = output or str(draft_dir / "final.mp4")
    assemble(clip_paths, voice_path, data, video_path, intro_text=data.get("topic"))
    click.echo(f"Video: {video_path}")


@cli.command(hidden=True, name="upload")
@click.option("--draft", required=True)
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
def upload_legacy(draft, public, channel):
    data = load_draft(draft)
    video_path = str(Path(draft).parent / "final.mp4")
    if not Path(video_path).exists():
        click.echo(f"Video not found: {video_path}. Run produce first.", err=True)
        sys.exit(1)
    privacy = "public" if public else "private"
    url = upload_video(
        video_path=video_path,
        title=data["title"],
        description="\n".join([data["hook"]] + data["points"] + [data["cta"]]),
        tags=data.get("tags"),
        privacy=privacy,
        channel_id=channel,
    )
    click.echo(f"Uploaded: {url}")


@cli.command(hidden=True, name="discover")
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--use-agents", is_flag=True)
def discover_legacy(public, channel, dry_run, use_agents):
    click.echo("Discovering trending topic via AI...")
    topic = create_llm().generate_json(
        "You are a trend researcher. Return JSON: {\"topic\": \"string\"}",
        "Find me a trending topic for a YouTube Short.",
        temperature=0.9, max_tokens=200,
    ).get("topic", "Interesting facts")
    click.echo(f"  Topic: {topic}")
    _run_pipeline(topic, public, channel, dry_run, use_agents)


@cli.command(hidden=True, name="trends")
@click.option("--niche", default=None)
@click.option("--count", default=10, type=int)
@click.option("--json-output", is_flag=True)
@click.option("--run", "run_count", default=0, type=int)
@click.option("--use-agents", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
@click.option("--refresh", is_flag=True)
def trends_legacy(niche, count, json_output, run_count, use_agents, dry_run, public, channel, refresh):
    niche_val = niche or DEFAULT_NICHE
    ideas = _discover_topics(niche_val, count if run_count else count, refresh)
    if not ideas:
        click.echo("No trends found.")
        return
    if json_output:
        click.echo(json.dumps(ideas, indent=2, ensure_ascii=False))
        return
    click.echo(f"\nTrending topics for niche: {niche_val}")
    click.echo("-" * 60)
    click.echo(f"{'#':<4} {'Score':<7} {'Source':<15} {'Title'}")
    click.echo("-" * 60)
    for i, idea in enumerate(ideas, 1):
        click.echo(f"{i:<4} {idea['score']:<7.1f} {idea['source']:<15} {idea['title'][:80]}")
    if run_count:
        click.echo(f"\nGenerating {run_count} videos...")
        for idea in ideas[:run_count]:
            click.echo(f"\n  {idea['title'][:60]}")
            try:
                _run_pipeline(idea['title'], public, channel, dry_run, use_agents)
                if not dry_run:
                    mark_topic_used(get_settings().assets_dir, idea['title'])
            except Exception as e:
                click.echo(f"  FAILED: {e}", err=True)


@cli.command(hidden=True, name="batch")
@click.argument("topics", nargs=-1, required=False)
@click.option("--public", is_flag=True)
@click.option("--channel", default=None)
@click.option("--dry-run", is_flag=True)
@click.option("--discover", is_flag=True)
@click.option("--count", default=5, type=int)
@click.option("--niche", default=None)
@click.option("--refresh", is_flag=True)
@click.option("--use-agents", is_flag=True)
def batch_legacy(topics, public, channel, dry_run, discover, count, niche, refresh, use_agents):
    if discover:
        niche_val = niche or DEFAULT_NICHE
        ideas = _discover_topics(niche_val, count, refresh)
        topics = tuple(i["title"] for i in ideas)
        if not topics:
            click.echo("No topics discovered.")
            return
        for t in topics:
            click.echo(f"  Discovered: {t}")
    if not topics:
        click.echo("Provide topics or use --discover.", err=True)
        sys.exit(1)
    click.echo(f"Batch: {len(topics)} topics")
    for i, t in enumerate(topics, 1):
        click.echo(f"\n[{i}/{len(topics)}] {t[:60]}")
        try:
            _run_pipeline(t, public, channel, dry_run, use_agents)
            if not dry_run:
                mark_topic_used(get_settings().assets_dir, t)
        except Exception as e:
            click.echo(f"  FAILED: {e}", err=True)
    click.echo("\nBatch complete.")


if __name__ == "__main__":
    cli()
