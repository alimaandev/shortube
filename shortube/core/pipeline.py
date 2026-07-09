from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from shortube.agents import (
    AgentPipeline,
    HookGenerator,
    OutlineAgent,
    QualityReviewer,
    ScriptEditor,
    ScriptWriter,
    SEOOptimizer,
    TopicAnalyzer,
)
from shortube.agents.base import BaseAgent
from shortube.agents.research import ResearchAgent
from shortube.config import NICHE
from shortube.config.settings import Settings, get_settings
from shortube.core.exceptions import PipelineError
from shortube.core.interfaces import (
    ResearchEngine as ResearchEngineInterface,
    ScriptWriter as ScriptWriterInterface,
    StoryboardGenerator,
    VideoAssembler,
    VideoUploader,
    VoiceGenerator,
)
from shortube.core.types import Script, Storyboard
from shortube.research import ResearchEngine
from shortube.shared.cache import DiskCache
from shortube.shared.draft import slugify
from shortube.shared.llm import LLMProvider, create_llm
from shortube.shared.logging import get_logger
from shortube.shared.prompts import SCRIPT_SYSTEM_PROMPT
from shortube.storyboard import StoryboardEngine


class Pipeline:
    def __init__(self, config: Settings | None = None):
        self.config = config or get_settings()
        self.logger: logging.Logger = get_logger("pipeline")
        self._llm: LLMProvider | None = None
        self.cache = DiskCache(
            cache_dir=self.config.cache_dir,
            default_ttl=self.config.cache_default_ttl,
        )

        # Injected stages
        self._script_writer: ScriptWriterInterface | None = None
        self._voice_generator: VoiceGenerator | None = None
        self._video_assembler: VideoAssembler | None = None
        self._video_uploader: VideoUploader | None = None

        # Agent pipeline
        self._agents: list[BaseAgent] | None = None

        # Lazy-init research + storyboard engines (need llm)
        self._research_engine: ResearchEngineInterface | None = None
        self._storyboard_engine: StoryboardGenerator | None = None

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = create_llm(
                provider=self.config.llm_provider,
                api_key=self.config.groq_api_key,
                model=self.config.llm_model,
            )
        return self._llm

    def _ensure_research(self) -> ResearchEngineInterface:
        if self._research_engine is None:
            self._research_engine = ResearchEngine(llm=self.llm)
        return self._research_engine

    def _ensure_storyboard(self) -> StoryboardGenerator:
        if self._storyboard_engine is None:
            self._storyboard_engine = StoryboardEngine(llm=self.llm, cache=self.cache)
        return self._storyboard_engine

    # ── Dependency injection ─────────────────────────────────────────

    def configure(self, **stages: Any) -> Pipeline:
        for key, impl in stages.items():
            if key == "agents":
                self._agents = list(impl)
            else:
                setattr(self, f"_{key}", impl)
        return self

    def use_agents(self, enabled: bool = True) -> Pipeline:
        if enabled and self._agents is None:
            research = self._ensure_research()
            self._agents = [
                TopicAnalyzer(self.llm),
                ResearchAgent(self.llm, research),
                OutlineAgent(self.llm),
                HookGenerator(self.llm),
                ScriptWriter(self.llm),
                ScriptEditor(self.llm),
                SEOOptimizer(self.llm),
                QualityReviewer(self.llm),
            ]
        elif not enabled:
            self._agents = None
        return self

    def with_storyboard(self, engine: StoryboardGenerator | None = None) -> Pipeline:
        if engine is not None:
            self._storyboard_engine = engine
        return self

    def with_research(self, engine: ResearchEngineInterface | None = None) -> Pipeline:
        if engine is not None:
            self._research_engine = engine
        return self

    # ── Stage runners ────────────────────────────────────────────────

    def write_script(self, topic: str) -> Script:
        if self._agents:
            self.logger.info("Using agent pipeline for script generation")
            agent_pipeline = AgentPipeline(self._agents)
            context = agent_pipeline.run(topic)

            # Quality gate retry loop
            max_retries = self.config.quality_max_retries
            retry = 0
            while not context.get("quality_passed", False) and retry < max_retries:
                retry += 1
                self.logger.info(
                    "Quality score %d — retry %d/%d",
                    context.get("quality_score", 0), retry, max_retries,
                )
                context["revision_notes"] = context.get("quality_notes", "")
                editor = next(a for a in agent_pipeline.agents if a.name == "script_editor")
                reviewer = next(a for a in agent_pipeline.agents if a.name == "quality_reviewer")
                context = editor.execute(context)
                context = reviewer.execute(context)

            script = context.get("script")
            if script is None:
                raise PipelineError("Agent pipeline did not produce a Script")
            if not context.get("quality_passed", False):
                self.logger.warning("Script failed quality after %d retries — proceeding anyway", retry)
            self._last_context = context
            return script

        if self._script_writer:
            return self._script_writer.write_script(topic)

        self.logger.info("Using direct LLM for script generation")
        user_prompt = (
            f"Topic: {topic}\n"
            f"Niche: {NICHE}\n"
            "Write a Shorts script for this topic. Return JSON only."
        )
        raw = self.llm.generate_json(
            SCRIPT_SYSTEM_PROMPT.template, user_prompt,
            temperature=0.8, max_tokens=800,
        )
        raw["full_text"] = " ".join([
            raw.get("hook", ""),
            *raw.get("points", []),
            raw.get("cta", ""),
        ])
        return Script.from_legacy_dict(raw)

    def generate_voiceover(self, text: str, output_path: str) -> str:
        if self._voice_generator:
            return self._voice_generator.generate(text, output_path)
        from shortube.modules.voice import generate_voiceover as _legacy_voice
        return _legacy_voice(text, output_path)

    def generate_storyboard(self, script: Script, voiceover_path: str) -> Storyboard:
        engine = self._ensure_storyboard()
        return engine.generate(script, voiceover_path)

    def assemble_video(
        self, storyboard: Storyboard, voiceover_path: str, output_path: str
    ) -> str:
        if self._video_assembler:
            return self._video_assembler.assemble(storyboard, voiceover_path, output_path)

        if storyboard.scenes:
            from shortube.modules.assemble import assemble_from_storyboard
            return assemble_from_storyboard(storyboard, voiceover_path, output_path)

        from shortube.config import PEXELS_API_KEY
        from shortube.storyboard.providers import PexelsProvider

        provider = PexelsProvider(PEXELS_API_KEY)
        all_clips: list[str] = []
        for kw in storyboard.script.keywords:
            assets = provider.search(kw, media_type="video", orientation="portrait", max_results=5)
            for asset in assets:
                dest = Path(output_path).parent / f"clip_{asset.provider}_{hashlib.sha256(asset.url.encode()).hexdigest()[:16]}.mp4"
                if not dest.exists():
                    provider.download(asset.url, dest)
                all_clips.append(str(dest))
                if len(all_clips) >= 6:
                    break
            if len(all_clips) >= 6:
                break

        if not all_clips:
            raise PipelineError("No video clips could be retrieved for assembly")

        from shortube.modules.assemble import assemble as _legacy_assemble
        return _legacy_assemble(
            video_paths=all_clips,
            voiceover_path=voiceover_path,
            script_data=storyboard.script.to_legacy_dict(),
            output_path=output_path,
        )

    def upload_video(
        self,
        video_path: str,
        script: Script,
        privacy: str = "private",
        channel_id: str | None = None,
        seo_context: dict | None = None,
    ) -> str:
        if self._video_uploader:
            return self._video_uploader.upload(video_path, script, privacy, channel_id)
        from shortube.modules.upload import upload_video as _legacy_upload

        # Build description from SEO data
        desc_hook = ""
        if seo_context:
            desc_hook = seo_context.get("description_hook", "")
        if not desc_hook:
            desc_hook = script.hook

        hashtags = " ".join(f"#{t.replace(' ', '')}" for t in script.tags[:8])
        points_bullets = "\n".join(f"• {p}" for p in script.points)
        description = f"{desc_hook}\n\n{points_bullets}\n\n{script.cta}\n\n{hashtags}"

        # Truncate tags to YouTube's 500-char limit
        tags = list(script.tags)
        while tags and len(",".join(tags)) > 500:
            tags.pop()

        return _legacy_upload(
            video_path=video_path,
            title=script.title,
            description=description,
            tags=tags,
            privacy=privacy,
            channel_id=channel_id,
            publish_at=self.config.upload_publish_at or None,
            playlist_id=self.config.upload_playlist_id or None,
        )

    # ── Full pipeline ────────────────────────────────────────────────

    def run(
        self,
        topic: str,
        output_dir: str | None = None,
        privacy: str = "private",
        channel_id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, str]:
        cfg = get_settings()
        slug = slugify(topic)
        draft_dir = Path(output_dir or cfg.assets_dir) / slug
        draft_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.logger.info("Pipeline step 1/5 — Script")
            script = self.write_script(topic)
            draft_path = draft_dir / f"{slug}_draft.json"
            with open(draft_path, "w", encoding="utf-8") as f:
                json.dump(script.to_legacy_dict(), f, indent=2, ensure_ascii=False)

            self.logger.info("Pipeline step 2/5 — Voiceover (SSML + timestamps)")
            voice_path = str(draft_dir / "voiceover.mp3")
            from shortube.modules.voice import generate_voiceover_with_timestamps
            timestamps = generate_voiceover_with_timestamps(
                script.hook, script.points, script.cta, voice_path
            )

            self.logger.info("Pipeline step 3/5 — Storyboard")
            storyboard = self.generate_storyboard(script, voice_path)

            self.logger.info("Pipeline step 4/5 — Assembly")
            video_path = str(draft_dir / "final.mp4")
            self.assemble_video(storyboard, voice_path, video_path)

            result: dict[str, str] = {
                "script": str(draft_path),
                "voiceover": voice_path,
                "video": video_path,
            }

            if dry_run:
                self.logger.info("Dry-run mode — skipping upload")
                return result

            self.logger.info("Pipeline step 5/5 — Thumbnail + Upload")
            thumbnail_path = str(draft_dir / "thumbnail.jpg")
            try:
                from shortube.modules.thumbnail import generate_thumbnail
                generate_thumbnail(script.title, thumbnail_path, subtitle=script.hook)
                result["thumbnail"] = thumbnail_path
            except Exception as e:
                self.logger.warning("Thumbnail generation failed: %s", e)

            seo_context = getattr(self, "_last_context", {}).get("seo", {})
            url = self.upload_video(video_path, script, privacy, channel_id, seo_context=seo_context)
            result["url"] = url
            self.logger.info("Done — %s", url)
            return result

        except Exception:
            self.logger.warning("Pipeline failed — cleaning up partial artifacts in %s", draft_dir)
            shutil.rmtree(draft_dir, ignore_errors=True)
            raise
