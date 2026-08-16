import React, { useState, useEffect } from "react";
import { api, Video } from "../api/client";

const Videos: React.FC = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewId, setPreviewId] = useState<number | null>(null);
  const [retrying, setRetrying] = useState<number | null>(null);

  const load = async () => {
    try {
      const res = await api.videos(100);
      setVideos(res.videos);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRetry = async (v: Video) => {
    if (!window.confirm(`Retry video "${v.topic_title}"?`)) return;
    setRetrying(v.id);
    try {
      await api.retry(v.id);
      alert("Retry job started — check Dashboard for progress.");
    } catch (e: unknown) {
      alert(`Retry failed: ${e instanceof Error ? e.message : "Unknown"}`);
    } finally {
      setRetrying(null);
    }
  };

  if (loading) {
    return <div className="card">Loading...</div>;
  }

  return (
    <div>
      <div className="card">
        <h2>Videos</h2>
        {videos.length === 0 ? (
          <div style={{ color: "#666", fontSize: 14 }}>No videos yet</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Topic</th>
                <th>Status</th>
                <th>Preview</th>
                <th>YouTube</th>
                <th>Actions</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((v) => (
                <tr key={v.id}>
                  <td>{v.id}</td>
                  <td>{v.topic_title?.slice(0, 80)}</td>
                  <td>
                    <span className={`status-badge status-${v.status}`}>
                      {v.status}
                    </span>
                  </td>
                  <td>
                    {v.video_path ? (
                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: 12, padding: "2px 8px" }}
                        onClick={() =>
                          setPreviewId(previewId === v.id ? null : v.id)
                        }
                      >
                        {previewId === v.id ? "Hide" : "Preview"}
                      </button>
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
                  <td>
                    {v.status === "failed" || v.status === "error" ? (
                      <button
                        className="btn btn-danger"
                        style={{ fontSize: 12, padding: "2px 8px" }}
                        onClick={() => handleRetry(v)}
                        disabled={retrying === v.id}
                      >
                        {retrying === v.id ? "..." : "Retry"}
                      </button>
                    ) : (
                      <a
                        href={`/api/videos/${v.id}/file`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: 12 }}
                      >
                        Download
                      </a>
                    )}
                  </td>
                  <td>{v.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {previewId && (
        <div className="card">
          <h3>Preview — Video #{previewId}</h3>
          <video
            controls
            style={{ width: "100%", maxWidth: 400, display: "block", borderRadius: 8 }}
          >
            <source src={`/api/videos/${previewId}/file`} type="video/mp4" />
          </video>
        </div>
      )}
    </div>
  );
};

export default Videos;
