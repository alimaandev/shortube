import React, { useState, useEffect } from "react";
import { api, getApiToken, setApiToken } from "../api/client";

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [templates, setTemplates] = useState<{ id: string; name: string }[]>([]);
  const [apiToken, setApiTokenState] = useState(getApiToken());

  useEffect(() => {
    Promise.all([
      api.settings(),
      api.schedule().catch((): { schedule: Record<string, unknown> } => ({ schedule: {} })),
      api.templates().catch(() => ({ templates: [] })),
    ])
      .then(([res, sched, tmpl]) => {
        const merged = {
          ...res.settings,
          schedule_enabled: (sched.schedule?.enabled as boolean) ?? false,
          schedule_interval_hours: (sched.schedule?.interval_hours as number) ?? 6,
          schedule_max_daily: (sched.schedule?.max_daily as number) ?? 4,
        };
        setSettings(merged);
        setTemplates(tmpl.templates);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const updateField = (key: string, value: unknown) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMsg("");

    const mainSettings = { ...settings };
    const scheduleSettings: Record<string, unknown> = {};

    const scheduleKeys = ["schedule_enabled", "schedule_interval_hours", "schedule_max_daily", "schedule_niche", "schedule_privacy"];
    for (const key of scheduleKeys) {
      if (key in mainSettings) {
        scheduleSettings[key.replace("schedule_", "")] = mainSettings[key];
        delete mainSettings[key];
      }
    }

    if (apiToken) {
      setApiToken(apiToken);
      mainSettings.web_token = apiToken;
    }

    try {
      await api.updateSettings(mainSettings);
      if (Object.keys(scheduleSettings).length > 0) {
        await api.updateSchedule(scheduleSettings);
      }
      setMsg("Settings saved successfully");
    } catch (e: unknown) {
      setMsg(`Error: ${e instanceof Error ? e.message : "Unknown"}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="card">Loading...</div>;
  }

  return (
    <div style={{ maxWidth: 700, margin: "0 auto" }}>
      <div className="card">
        <h2>LLM Settings</h2>
        <div className="form-group">
          <label>Provider</label>
          <select
            value={String(settings.llm_provider || "groq")}
            onChange={(e) => updateField("llm_provider", e.target.value)}
          >
            <option value="groq">Groq</option>
            <option value="openrouter">OpenRouter</option>
            <option value="ollama">Ollama</option>
          </select>
        </div>
        <div className="form-group">
          <label>Model</label>
          <input
            value={String(settings.llm_model || "")}
            onChange={(e) => updateField("llm_model", e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Temperature</label>
          <input
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={Number(settings.llm_temperature || 0.8)}
            onChange={(e) =>
              updateField("llm_temperature", parseFloat(e.target.value))
            }
          />
        </div>
      </div>

      <div className="card">
        <h2>Voiceover Settings</h2>
        <div className="form-group">
          <label>Voice Name</label>
          <input
            value={String(settings.voice_name || "")}
            onChange={(e) => updateField("voice_name", e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Speed</label>
          <input
            type="number"
            step="0.05"
            min="0.5"
            max="2"
            value={Number(settings.voice_speed || 1.15)}
            onChange={(e) =>
              updateField("voice_speed", parseFloat(e.target.value))
            }
          />
        </div>
        <div className="form-group">
          <label>Volume</label>
          <input
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={Number(settings.voice_volume || 1.0)}
            onChange={(e) =>
              updateField("voice_volume", parseFloat(e.target.value))
            }
          />
        </div>
      </div>

      <div className="card">
        <h2>Visual Template</h2>
        <div className="form-group">
          <label>Template (colors, transitions, caption style)</label>
          <select
            value={String(settings.template || "premium")}
            onChange={(e) => updateField("template", e.target.value)}
          >
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.id})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="card">
        <h2>Video Settings</h2>
        <div className="form-group">
          <label>Width</label>
          <input
            type="number"
            value={Number(settings.video_width || 1080)}
            onChange={(e) =>
              updateField("video_width", parseInt(e.target.value))
            }
          />
        </div>
        <div className="form-group">
          <label>Height</label>
          <input
            type="number"
            value={Number(settings.video_height || 1920)}
            onChange={(e) =>
              updateField("video_height", parseInt(e.target.value))
            }
          />
        </div>
        <div className="form-group">
          <label>FPS</label>
          <input
            type="number"
            value={Number(settings.video_fps || 30)}
            onChange={(e) =>
              updateField("video_fps", parseInt(e.target.value))
            }
          />
        </div>
        <div className="form-group">
          <label>Bumper Duration (seconds)</label>
          <input
            type="number"
            step="0.1"
            value={Number(settings.bumper_duration || 1.5)}
            onChange={(e) =>
              updateField("bumper_duration", parseFloat(e.target.value))
            }
          />
        </div>
      </div>

      <div className="card">
        <h2>Media Settings</h2>
        <div className="form-group">
          <label>Image Provider</label>
          <select
            value={String(settings.image_provider || "auto")}
            onChange={(e) => updateField("image_provider", e.target.value)}
          >
            <option value="auto">Auto (Pexels → Pixabay → AI)</option>
            <option value="pexels">Pexels only</option>
            <option value="pixabay">Pixabay only</option>
            <option value="pollinations">Pollinations AI</option>
          </select>
        </div>
        <div className="form-group">
          <label>Prefer Videos Over Images</label>
          <select
            value={settings.media_prefer_videos !== false ? "true" : "false"}
            onChange={(e) => updateField("media_prefer_videos", e.target.value === "true")}
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>
        <div className="form-group">
          <label>Fallback to Next Provider</label>
          <select
            value={settings.image_provider_fallback !== false ? "true" : "false"}
            onChange={(e) => updateField("image_provider_fallback", e.target.value === "true")}
          >
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </div>
      </div>

      <div className="card">
        <h2>Content Settings</h2>
        <div className="form-group">
          <label>Default Niche</label>
          <input
            value={String(settings.niche || "")}
            onChange={(e) => updateField("niche", e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Background Music Path</label>
          <input
            value={String(settings.background_music_path || "")}
            onChange={(e) =>
              updateField("background_music_path", e.target.value)
            }
          />
        </div>
        <div className="form-group">
          <label>Music Volume</label>
          <input
            type="number"
            value={Number(settings.music_volume || 15)}
            onChange={(e) =>
              updateField("music_volume", parseFloat(e.target.value))
            }
          />
        </div>
        <div className="form-group">
          <label>Duck Threshold</label>
          <input
            type="number"
            value={Number(settings.duck_threshold || 6)}
            onChange={(e) =>
              updateField("duck_threshold", parseFloat(e.target.value))
            }
          />
        </div>
      </div>

      <div className="card">
        <h2>Scheduling</h2>
        <div className="form-group">
          <label>Enable Auto-Schedule</label>
          <select
            value={settings.schedule_enabled === true ? "true" : "false"}
            onChange={(e) => updateField("schedule_enabled", e.target.value === "true")}
          >
            <option value="false">Disabled</option>
            <option value="true">Enabled</option>
          </select>
        </div>
        <div className="form-group">
          <label>Interval (hours)</label>
          <input
            type="number"
            min="1"
            max="168"
            value={Number(settings.schedule_interval_hours || 6)}
            onChange={(e) =>
              updateField("schedule_interval_hours", parseInt(e.target.value))
            }
          />
        </div>
        <div className="form-group">
          <label>Max Videos Per Day</label>
          <input
            type="number"
            min="1"
            max="24"
            value={Number(settings.schedule_max_daily || 4)}
            onChange={(e) =>
              updateField("schedule_max_daily", parseInt(e.target.value))
            }
          />
        </div>
      </div>

      <div className="card">
        <h2>Upload Settings</h2>
        <div className="form-group">
          <label>Privacy</label>
          <select
            value={String(settings.upload_privacy || "public")}
            onChange={(e) => updateField("upload_privacy", e.target.value)}
          >
            <option value="public">Public</option>
            <option value="unlisted">Unlisted</option>
            <option value="private">Private</option>
          </select>
        </div>
        <div className="form-group">
          <label>Category ID</label>
          <input
            value={String(settings.upload_category || "22")}
            onChange={(e) => updateField("upload_category", e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Language</label>
          <input
            value={String(settings.upload_language || "en")}
            onChange={(e) => updateField("upload_language", e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Channel ID</label>
          <input
            value={String(settings.upload_channel_id || "")}
            onChange={(e) => updateField("upload_channel_id", e.target.value)}
          />
        </div>
        <div className="form-group">
          <label>Tags (comma separated)</label>
          <input
            value={
              Array.isArray(settings.tags_default)
                ? settings.tags_default.join(", ")
                : ""
            }
            onChange={(e) =>
              updateField(
                "tags_default",
                e.target.value.split(",").map((t) => t.trim())
              )
            }
          />
        </div>
      </div>

      <div className="card">
        <h2>Job Queue</h2>
        <div className="form-group">
          <label>Use Redis Queue (RQ)</label>
          <select
            value={settings.use_rq === true ? "true" : "false"}
            onChange={(e) => updateField("use_rq", e.target.value === "true")}
          >
            <option value="false">Threads (in-process)</option>
            <option value="true">Redis Queue (RQ)</option>
          </select>
        </div>
        <div className="form-group">
          <label>Redis URL</label>
          <input
            value={String(settings.redis_url || "redis://localhost:6379/0")}
            onChange={(e) => updateField("redis_url", e.target.value)}
          />
        </div>
      </div>

      <div className="card">
        <h2>Security</h2>
        <div className="form-group">
          <label>API Token</label>
          <input
            type="password"
            value={apiToken}
            onChange={(e) => setApiTokenState(e.target.value)}
            placeholder={
              settings.web_token_set === true
                ? "Token is set — enter a new one to rotate"
                : "Set a token to protect the API (empty = no auth)"
            }
            autoComplete="off"
          />
          <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
            {settings.web_token_set === true ? (
              <span style={{ color: "#4caf50" }}>Auth enabled</span>
            ) : (
              <span style={{ color: "#ef5350" }}>
                Auth disabled — anyone on your network can trigger uploads
              </span>
            )}
          </div>
        </div>
      </div>

      <button
        className="btn btn-primary"
        onClick={handleSave}
        disabled={saving}
        style={{ width: "100%", padding: 12, justifyContent: "center" }}
      >
        {saving ? "Saving..." : "Save Settings"}
      </button>

      {msg && (
        <div
          style={{
            marginTop: 12,
            textAlign: "center",
            color: msg.startsWith("Error") ? "#ef5350" : "#4caf50",
            fontSize: 14,
          }}
        >
          {msg}
        </div>
      )}
    </div>
  );
};

export default Settings;
