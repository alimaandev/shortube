import React, { useState, useEffect, useCallback, useRef } from "react";
import { api, Trend, Job, Video, connectJobWebSocket } from "../api/client";

const Dashboard: React.FC = () => {
  const [topic, setTopic] = useState("");
  const [niche, setNiche] = useState("");
  const [trends, setTrends] = useState<Trend[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [generating, setGenerating] = useState(false);
  const [autoRunning, setAutoRunning] = useState(false);
  const [trendLoading, setTrendLoading] = useState(false);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [progressMsg, setProgressMsg] = useState("");
  const [progressPct, setProgressPct] = useState(0);
  const wsRef = useRef<{ close: () => void } | null>(null);

  const refreshData = useCallback(async () => {
    try {
      const [j, v] = await Promise.all([api.jobs(10), api.videos(10)]);
      setJobs(j.jobs);
      setVideos(v.videos);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    refreshData();
    const interval = setInterval(refreshData, 5000);
    return () => clearInterval(interval);
  }, [refreshData]);

  useEffect(() => {
    if (!activeJobId) return;
    wsRef.current = connectJobWebSocket(
      activeJobId,
      (data) => {
        if (data.type === "progress" && typeof data.progress_msg === "string") {
          setProgressMsg(data.progress_msg);
        }
        if (typeof data.progress === "number") {
          setProgressPct(data.progress);
        }
        if (data.type === "done") {
          setActiveJobId(null);
          setGenerating(false);
          setAutoRunning(false);
          setProgressMsg("Done!");
          setProgressPct(100);
          refreshData();
        }
        if (data.type === "failed") {
          setActiveJobId(null);
          setGenerating(false);
          setAutoRunning(false);
          setProgressMsg(`Failed: ${data.error || "Unknown error"}`);
          refreshData();
        }
      },
      () => {
        // WebSocket failed, fallback to polling
        const poll = setInterval(async () => {
          try {
            const res = await api.job(activeJobId);
            if (res.job.status === "done" || res.job.status === "failed") {
              setActiveJobId(null);
              setGenerating(false);
              setAutoRunning(false);
              setProgressMsg(
                res.job.status === "done" ? "Done!" : `Failed: ${res.job.error}`
              );
              setProgressPct(res.job.status === "done" ? 100 : 0);
              refreshData();
              clearInterval(poll);
            } else {
              setProgressPct(res.job.progress || 0);
            }
          } catch {
            clearInterval(poll);
          }
        }, 2000);
      }
    );
    return () => {
      wsRef.current?.close();
    };
  }, [activeJobId, refreshData]);

  const handleGenerate = async () => {
    if (!topic.trim()) return;
    setGenerating(true);
    setProgressMsg("Starting pipeline...");
    setProgressPct(0);
    try {
      const res = await api.generate(topic, "private", niche || undefined);
      setActiveJobId(res.job_id);
    } catch (e: unknown) {
      setProgressMsg(`Error: ${e instanceof Error ? e.message : "Unknown"}`);
      setGenerating(false);
    }
  };

  const handleAuto = async () => {
    setAutoRunning(true);
    setProgressMsg("Scanning trends...");
    setProgressPct(0);
    try {
      const res = await api.auto(niche || undefined, "private");
      setActiveJobId(res.job_id);
    } catch (e: unknown) {
      setProgressMsg(`Error: ${e instanceof Error ? e.message : "Unknown"}`);
      setAutoRunning(false);
    }
  };

  const handleScanTrends = async () => {
    setTrendLoading(true);
    try {
      const res = await api.trends(niche || undefined, 10);
      setTrends(res.trends);
    } catch (e: unknown) {
      alert(`Trend scan failed: ${e instanceof Error ? e.message : "Unknown"}`);
    } finally {
      setTrendLoading(false);
    }
  };

  const isRunning = generating || autoRunning;

  return (
    <div>
      <div className="grid-2">
        {/* Generate Section */}
        <div className="card">
          <h2>Generate Video</h2>
          <div className="form-group">
            <label>Topic</label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Enter a topic..."
              disabled={isRunning}
            />
          </div>
          <div className="form-group">
            <label>Niche (optional)</label>
            <input
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
              placeholder="Default niche from settings"
              disabled={isRunning}
            />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-primary"
              onClick={handleGenerate}
              disabled={isRunning || !topic.trim()}
            >
              {generating ? "Generating..." : "Generate"}
            </button>
            <button
              className="btn btn-secondary"
              onClick={handleAuto}
              disabled={isRunning}
            >
              {autoRunning ? "Scanning..." : "Auto Mode"}
            </button>
          </div>

          {progressMsg && (
            <div style={{ marginTop: 12 }}>
              <div
                style={{
                  fontSize: 13,
                  color: progressMsg.startsWith("Error") || progressMsg.startsWith("Failed")
                    ? "#ef5350"
                    : "#aaa",
                }}
              >
                {progressMsg}
              </div>
              <div className="progress-bar">
                <div
                  className="progress-bar-fill"
                  style={{
                    width: `${Math.min(progressPct, 100)}%`,
                    animation: activeJobId && progressPct < 100
                      ? "pulse 1.5s infinite"
                      : "none",
                    transition: "width 0.3s ease",
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Trend Discovery */}
        <div className="card">
          <h2>Trend Discovery</h2>
          <button
            className="btn btn-secondary"
            onClick={handleScanTrends}
            disabled={trendLoading}
            style={{ marginBottom: 12 }}
          >
            {trendLoading ? "Scanning..." : "Scan Trends"}
          </button>
          {trends.length > 0 && (
            <div>
              <h3>Top Trends</h3>
              <table>
                <thead>
                  <tr>
                    <th>Score</th>
                    <th>Title</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {trends.map((t, i) => (
                    <tr key={i}>
                      <td>{t.score.toFixed(1)}</td>
                      <td>{t.title.slice(0, 60)}</td>
                      <td>{t.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Active Jobs */}
      <div className="card">
        <h2>Active Jobs</h2>
        {jobs.filter((j) => j.status === "running" || j.status === "queued")
          .length === 0 ? (
          <div style={{ color: "#666", fontSize: 14 }}>No active jobs</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Topic</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {jobs
                .filter((j) => j.status === "running" || j.status === "queued")
                .map((j) => (
                  <tr key={j.id}>
                    <td>{j.id}</td>
                    <td>{j.topic_title?.slice(0, 50)}</td>
                    <td>
                      <span className={`status-badge status-${j.status}`}>
                        {j.status}
                      </span>
                    </td>
                    <td>{j.progress}%</td>
                    <td style={{ color: "#ef5350", fontSize: 12 }}>
                      {j.error || ""}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent Videos */}
      <div className="card">
        <h2>Recent Videos</h2>
        {videos.length === 0 ? (
          <div style={{ color: "#666", fontSize: 14 }}>No videos yet</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Topic</th>
                <th>Status</th>
                <th>Video</th>
                <th>YouTube</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((v) => (
                <tr key={v.id}>
                  <td>{v.id}</td>
                  <td>{v.topic_title?.slice(0, 60)}</td>
                  <td>
                    <span className={`status-badge status-${v.status}`}>
                      {v.status}
                    </span>
                  </td>
                  <td>
                    {v.video_path ? (
                      <a href={`/api/videos/${v.id}/file`} target="_blank" rel="noopener noreferrer">
                        Download
                      </a>
                    ) : (
                      ""
                    )}
                  </td>
                  <td>
                    {v.youtube_url ? (
                      <a
                        href={v.youtube_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View
                      </a>
                    ) : (
                      ""
                    )}
                  </td>
                  <td>{v.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
