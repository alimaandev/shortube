from __future__ import annotations

import logging
import threading
from tkinter import ttk, messagebox
from typing import Any

import customtkinter as ctk

from shortube.config import get_settings
from shortube.db import Database
from shortube.discover import discover
from shortube.pipeline import run_pipeline

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = 3000


class DesktopApp:
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.root = ctk.CTk()
        self.root.title("Shorts Automator")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)

        self.db = Database()
        self._running = threading.Event()

        self._build_ui()
        self._refresh()
        self.root.mainloop()

    # ── UI Build ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        tabview = ctk.CTkTabview(self.root, anchor="nw")
        tabview.pack(fill="both", expand=True, padx=12, pady=12)

        self._tab_dashboard = tabview.add("Dashboard")
        self._tab_topics = tabview.add("Topics")
        self._tab_jobs = tabview.add("Jobs")
        self._tab_settings = tabview.add("Settings")

        self._build_dashboard()
        self._build_topics()
        self._build_jobs()
        self._build_settings()

    # ── Dashboard ───────────────────────────────────────────────────

    def _build_dashboard(self) -> None:
        frame = self._tab_dashboard

        # ── Generate section ──
        gen_frame = ctk.CTkFrame(frame, corner_radius=10)
        gen_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            gen_frame, text="Generate Video",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 6))

        row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(row, text="Topic:", width=60).pack(side="left")
        self._topic_entry = ctk.CTkEntry(row, placeholder_text="Enter a topic or leave empty for auto")
        self._topic_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkLabel(row, text="Niche:", width=50).pack(side="left")
        self._niche_entry = ctk.CTkEntry(row, width=180, placeholder_text=get_settings().niche)
        self._niche_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            row, text="Generate", command=self._on_generate,
            width=100, fg_color="#2e7d32", hover_color="#1b5e20",
        ).pack(side="left")

        # ── Discover section ──
        disc_frame = ctk.CTkFrame(frame, corner_radius=10)
        disc_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            disc_frame, text="Trend Discovery",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 6))

        disc_row = ctk.CTkFrame(disc_frame, fg_color="transparent")
        disc_row.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkButton(
            disc_row, text="Scan Trends", command=self._on_discover,
            fg_color="#1565c0", hover_color="#0d47a1",
        ).pack(side="left")

        # ── Active Jobs section ──
        jobs_frame = ctk.CTkFrame(frame, corner_radius=10)
        jobs_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            jobs_frame, text="Active Jobs",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self._active_jobs_tree = ttk.Treeview(
            jobs_frame,
            columns=("id", "topic", "status", "progress", "error"),
            show="headings", height=4,
        )
        self._active_jobs_tree.heading("id", text="ID")
        self._active_jobs_tree.heading("topic", text="Topic")
        self._active_jobs_tree.heading("status", text="Status")
        self._active_jobs_tree.heading("progress", text="Progress")
        self._active_jobs_tree.heading("error", text="Error")
        self._active_jobs_tree.column("id", width=40)
        self._active_jobs_tree.column("topic", width=300)
        self._active_jobs_tree.column("status", width=80)
        self._active_jobs_tree.column("progress", width=70)
        self._active_jobs_tree.column("error", width=200)
        self._active_jobs_tree.pack(fill="x", padx=14, pady=(0, 10))

        # ── Recent Videos section ──
        vid_frame = ctk.CTkFrame(frame, corner_radius=10)
        vid_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(
            vid_frame, text="Recent Videos",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        vid_inner = ctk.CTkFrame(vid_frame, fg_color="transparent")
        vid_inner.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self._videos_tree = ttk.Treeview(
            vid_inner,
            columns=("id", "topic", "status", "video", "youtube", "created"),
            show="headings",
        )
        self._videos_tree.heading("id", text="ID")
        self._videos_tree.heading("topic", text="Topic")
        self._videos_tree.heading("status", text="Status")
        self._videos_tree.heading("video", text="File")
        self._videos_tree.heading("youtube", text="YouTube")
        self._videos_tree.heading("created", text="Created")
        self._videos_tree.column("id", width=40)
        self._videos_tree.column("topic", width=300)
        self._videos_tree.column("status", width=80)
        self._videos_tree.column("video", width=60)
        self._videos_tree.column("youtube", width=100)
        self._videos_tree.column("created", width=100)

        vsb = ttk.Scrollbar(vid_inner, orient="vertical", command=self._videos_tree.yview)
        self._videos_tree.configure(yscrollcommand=vsb.set)
        self._videos_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # ── Topics ──────────────────────────────────────────────────────

    def _build_topics(self) -> None:
        frame = self._tab_topics

        self._topics_tree = ttk.Treeview(
            frame,
            columns=("id", "title", "niche", "source", "score", "status"),
            show="headings",
        )
        self._topics_tree.heading("id", text="ID")
        self._topics_tree.heading("title", text="Title")
        self._topics_tree.heading("niche", text="Niche")
        self._topics_tree.heading("source", text="Source")
        self._topics_tree.heading("score", text="Score")
        self._topics_tree.heading("status", text="Status")
        self._topics_tree.column("id", width=40)
        self._topics_tree.column("title", width=450)
        self._topics_tree.column("niche", width=120)
        self._topics_tree.column("source", width=100)
        self._topics_tree.column("score", width=60)
        self._topics_tree.column("status", width=80)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._topics_tree.yview)
        self._topics_tree.configure(yscrollcommand=vsb.set)
        self._topics_tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        vsb.pack(side="right", fill="y", pady=10)

    # ── Jobs ────────────────────────────────────────────────────────

    def _build_jobs(self) -> None:
        frame = self._tab_jobs

        self._jobs_tree = ttk.Treeview(
            frame,
            columns=("id", "topic", "type", "status", "progress", "error"),
            show="headings",
        )
        self._jobs_tree.heading("id", text="ID")
        self._jobs_tree.heading("topic", text="Topic")
        self._jobs_tree.heading("type", text="Type")
        self._jobs_tree.heading("status", text="Status")
        self._jobs_tree.heading("progress", text="Progress")
        self._jobs_tree.heading("error", text="Error")
        self._jobs_tree.column("id", width=40)
        self._jobs_tree.column("topic", width=380)
        self._jobs_tree.column("type", width=80)
        self._jobs_tree.column("status", width=80)
        self._jobs_tree.column("progress", width=70)
        self._jobs_tree.column("error", width=280)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._jobs_tree.yview)
        self._jobs_tree.configure(yscrollcommand=vsb.set)
        self._jobs_tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        vsb.pack(side="right", fill="y", pady=10)

    # ── Settings ────────────────────────────────────────────────────

    def _build_settings(self) -> None:
        frame = self._tab_settings
        cfg = get_settings()

        scroll = ctk.CTkScrollableFrame(frame, corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # ── LLM section ──
        llm_sec = ctk.CTkFrame(scroll, corner_radius=8)
        llm_sec.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            llm_sec, text="Language Model",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        r1 = ctk.CTkFrame(llm_sec, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r1, text="Provider:", width=100).pack(side="left")
        self._provider_var = ctk.StringVar(value=cfg.llm_provider)
        ctk.CTkOptionMenu(
            r1, variable=self._provider_var,
            values=["groq", "openrouter", "ollama"], width=140,
        ).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(r1, text="Model:", width=60).pack(side="left")
        self._model_entry = ctk.CTkEntry(r1, width=220, placeholder_text=cfg.llm_model)
        self._model_entry.pack(side="left")

        r2 = ctk.CTkFrame(llm_sec, fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r2, text="Temperature:", width=100).pack(side="left")
        self._temp_var = ctk.DoubleVar(value=cfg.llm_temperature)
        ctk.CTkSlider(r2, variable=self._temp_var, from_=0.0, to=2.0, width=200).pack(
            side="left", padx=(0, 10)
        )
        self._temp_label = ctk.CTkLabel(r2, text=f"{cfg.llm_temperature:.1f}", width=30)
        self._temp_label.pack(side="left")

        def on_temp(*_a):
            self._temp_label.configure(text=f"{self._temp_var.get():.1f}")
        self._temp_var.trace_add("write", on_temp)

        # ── Voice section ──
        voice_sec = ctk.CTkFrame(scroll, corner_radius=8)
        voice_sec.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            voice_sec, text="Voiceover",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        r3 = ctk.CTkFrame(voice_sec, fg_color="transparent")
        r3.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r3, text="Voice:", width=100).pack(side="left")
        self._voice_var = ctk.StringVar(value=cfg.voice_name)
        ctk.CTkEntry(
            r3, textvariable=self._voice_var, width=300,
        ).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(r3, text="Speed:", width=50).pack(side="left")
        self._speed_var = ctk.DoubleVar(value=cfg.voice_speed)
        ctk.CTkSlider(r3, variable=self._speed_var, from_=0.5, to=2.0, width=150).pack(
            side="left", padx=(0, 8)
        )
        self._speed_label = ctk.CTkLabel(r3, text=f"{cfg.voice_speed:.2f}", width=30)
        self._speed_label.pack(side="left")

        def on_speed(*_a):
            self._speed_label.configure(text=f"{self._speed_var.get():.2f}")
        self._speed_var.trace_add("write", on_speed)

        # ── Video section ──
        vid_sec = ctk.CTkFrame(scroll, corner_radius=8)
        vid_sec.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            vid_sec, text="Video Output",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        r4 = ctk.CTkFrame(vid_sec, fg_color="transparent")
        r4.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r4, text="Width:", width=80).pack(side="left")
        self._vw_entry = ctk.CTkEntry(r4, width=80, placeholder_text=str(cfg.video_width))
        self._vw_entry.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(r4, text="Height:", width=60).pack(side="left")
        self._vh_entry = ctk.CTkEntry(r4, width=80, placeholder_text=str(cfg.video_height))
        self._vh_entry.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(r4, text="FPS:", width=40).pack(side="left")
        self._fps_entry = ctk.CTkEntry(r4, width=60, placeholder_text=str(cfg.video_fps))
        self._fps_entry.pack(side="left")

        r5 = ctk.CTkFrame(vid_sec, fg_color="transparent")
        r5.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r5, text="Bumper (s):", width=100).pack(side="left")
        self._bumper_entry = ctk.CTkEntry(r5, width=70,
                                           placeholder_text=str(cfg.bumper_duration))
        self._bumper_entry.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(r5, text="Transition (s):", width=100).pack(side="left")
        self._trans_entry = ctk.CTkEntry(r5, width=70,
                                          placeholder_text=str(cfg.transition_duration))
        self._trans_entry.pack(side="left")

        # ── Upload section ──
        upl_sec = ctk.CTkFrame(scroll, corner_radius=8)
        upl_sec.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            upl_sec, text="Upload",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        r6 = ctk.CTkFrame(upl_sec, fg_color="transparent")
        r6.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r6, text="Privacy:", width=100).pack(side="left")
        self._privacy_var = ctk.StringVar(value=cfg.upload_privacy)
        ctk.CTkOptionMenu(
            r6, variable=self._privacy_var,
            values=["public", "unlisted", "private"], width=120,
        ).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(r6, text="Category ID:", width=90).pack(side="left")
        self._cat_entry = ctk.CTkEntry(r6, width=60, placeholder_text=cfg.upload_category)
        self._cat_entry.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(r6, text="Language:", width=70).pack(side="left")
        self._lang_entry = ctk.CTkEntry(r6, width=60, placeholder_text=cfg.upload_language)
        self._lang_entry.pack(side="left")

        # ── Niche section ──
        niche_sec = ctk.CTkFrame(scroll, corner_radius=8)
        niche_sec.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            niche_sec, text="Content",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        r7 = ctk.CTkFrame(niche_sec, fg_color="transparent")
        r7.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(r7, text="Default Niche:", width=110).pack(side="left")
        self._niche_setting = ctk.CTkEntry(r7, width=300, placeholder_text=cfg.niche)
        self._niche_setting.pack(side="left")

        # ── Save button ──
        save_btn = ctk.CTkButton(
            scroll, text="Save Settings",
            command=self._on_save_settings,
            fg_color="#2e7d32", hover_color="#1b5e20",
            height=40, font=ctk.CTkFont(size=14, weight="bold"),
        )
        save_btn.pack(pady=(4, 10))

    def _on_save_settings(self) -> None:
        env_path = get_settings().base_dir / ".env"
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()

        # Filter out old keys we're replacing
        keys = {
            "LLM_PROVIDER", "LLM_MODEL", "LLM_TEMPERATURE",
            "VOICE_NAME", "VOICE_SPEED",
            "VIDEO_WIDTH", "VIDEO_HEIGHT", "VIDEO_FPS",
            "BUMPER_DURATION", "TRANSITION_DURATION",
            "UPLOAD_PRIVACY", "UPLOAD_CATEGORY", "UPLOAD_LANGUAGE",
            "NICHE",
        }
        lines = [l for l in lines if not any(l.startswith(k + "=") for k in keys)]

        new_lines = [
            f"LLM_PROVIDER={self._provider_var.get()}",
            f"LLM_MODEL={self._model_entry.get() or get_settings().llm_model}",
            f"LLM_TEMPERATURE={self._temp_var.get():.1f}",
            f"VOICE_NAME={self._voice_var.get()}",
            f"VOICE_SPEED={self._speed_var.get():.2f}",
            f"VIDEO_WIDTH={self._vw_entry.get() or get_settings().video_width}",
            f"VIDEO_HEIGHT={self._vh_entry.get() or get_settings().video_height}",
            f"VIDEO_FPS={self._fps_entry.get() or get_settings().video_fps}",
            f"BUMPER_DURATION={self._bumper_entry.get() or get_settings().bumper_duration}",
            f"TRANSITION_DURATION={self._trans_entry.get() or get_settings().transition_duration}",
            f"UPLOAD_PRIVACY={self._privacy_var.get()}",
            f"UPLOAD_CATEGORY={self._cat_entry.get() or get_settings().upload_category}",
            f"UPLOAD_LANGUAGE={self._lang_entry.get() or get_settings().upload_language}",
            f"NICHE={self._niche_setting.get() or get_settings().niche}",
        ]
        lines.extend(new_lines)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        messagebox.showinfo("Settings", "Settings saved to .env")

    # ── Actions ─────────────────────────────────────────────────────

    def _on_generate(self) -> None:
        topic = self._topic_entry.get().strip()
        niche = self._niche_entry.get().strip() or get_settings().niche

        if not topic:
            threading.Thread(
                target=self._auto_generate, args=(niche,), daemon=True
            ).start()
            return

        tid = self.db.add_topic(topic, niche=niche)
        vid = self.db.create_video(tid)
        jid = self.db.create_job(vid, "generate")
        threading.Thread(
            target=self._run_job, args=(jid, vid, topic, niche), daemon=True
        ).start()

    def _auto_generate(self, niche: str) -> None:
        ideas = discover(niche, max_results=10)
        for idea in ideas:
            if not self.db.is_topic_used(idea.title):
                tid = self.db.add_topic(
                    idea.title, niche=niche, source=idea.source, score=idea.score
                )
                vid = self.db.create_video(tid)
                jid = self.db.create_job(vid, "auto")
                self._run_job(jid, vid, idea.title, niche)
                return

    def _on_discover(self) -> None:
        niche = self._niche_entry.get().strip() or get_settings().niche
        threading.Thread(
            target=self._discover_worker, args=(niche,), daemon=True
        ).start()

    def _discover_worker(self, niche: str) -> None:
        try:
            ideas = discover(niche, max_results=20)
            for idea in ideas[:10]:
                self.db.add_topic(
                    idea.title, niche=niche, source=idea.source, score=idea.score
                )
        except Exception as e:
            logger.error("Discover failed: %s", e)

    def _run_job(
        self, job_id: int, video_id: int, topic: str, niche: str
    ) -> None:
        try:
            self.db.update_job(job_id, status="running")
            result = run_pipeline(topic, video_id=video_id)
            if "url" in result:
                self.db.mark_topic_used(topic)
            self.db.update_job(job_id, status="done", progress=100)
        except Exception as e:
            logger.error("Job %d failed: %s", job_id, e)
            self.db.update_job(job_id, status="failed", error=str(e))

    # ── Refresh ─────────────────────────────────────────────────────

    def _refresh(self) -> None:
        try:
            self._refresh_active_jobs()
            self._refresh_videos()
            self._refresh_topics()
            self._refresh_jobs()
        except Exception as e:
            logger.warning("Refresh failed: %s", e)
        self.root.after(REFRESH_INTERVAL, self._refresh)

    def _refresh_active_jobs(self) -> None:
        for row in self._active_jobs_tree.get_children():
            self._active_jobs_tree.delete(row)
        jobs = self.db.get_all_jobs(limit=10)
        for j in jobs:
            if j["status"] in ("queued", "running"):
                self._active_jobs_tree.insert(
                    "", "end",
                    values=(
                        j["id"],
                        (j.get("topic_title") or "")[:60],
                        j["status"],
                        f"{j['progress']}%",
                        (j.get("error") or "")[:50],
                    ),
                )

    def _refresh_videos(self) -> None:
        for row in self._videos_tree.get_children():
            self._videos_tree.delete(row)
        videos = self.db.get_recent_videos(limit=50)
        for v in videos:
            has_video = "Yes" if v.get("video_path") else ""
            has_yt = "View" if v.get("youtube_url") else ""
            self._videos_tree.insert(
                "", "end",
                values=(
                    v["id"],
                    (v.get("topic_title") or "")[:80],
                    v["status"],
                    has_video,
                    has_yt,
                    (v.get("created_at") or "")[:10],
                ),
            )

    def _refresh_topics(self) -> None:
        for row in self._topics_tree.get_children():
            self._topics_tree.delete(row)
        topics = self.db.get_all_topics(limit=100)
        for t in topics:
            self._topics_tree.insert(
                "", "end",
                values=(
                    t["id"],
                    (t.get("title") or "")[:80],
                    t.get("niche", ""),
                    t.get("source", ""),
                    t.get("score", ""),
                    "used" if t.get("used") else "new",
                ),
            )

    def _refresh_jobs(self) -> None:
        for row in self._jobs_tree.get_children():
            self._jobs_tree.delete(row)
        jobs = self.db.get_all_jobs(limit=100)
        for j in jobs:
            self._jobs_tree.insert(
                "", "end",
                values=(
                    j["id"],
                    (j.get("topic_title") or "")[:80],
                    j.get("job_type", ""),
                    j["status"],
                    f"{j['progress']}%",
                    (j.get("error") or "")[:80],
                ),
            )


def run() -> None:
    DesktopApp()
