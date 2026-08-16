import React, { useState, useEffect } from "react";
import { api } from "../api/client";

interface VideoStat {
  video_db_id: number;
  video_id: string;
  title: string;
  topic_title: string;
  views: number;
  likes: number;
  comments: number;
  published_at: string;
  thumbnail: string;
  fetched_at: string;
}

const Analytics: React.FC = () => {
  const [stats, setStats] = useState<VideoStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const res = await fetch("/api/analytics").then((r) => r.json());
      setStats(res.analytics || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/analytics/refresh", { method: "POST" }).then((r) => r.json());
      setStats(res.analytics || []);
    } catch {
      // ignore
    } finally {
      setRefreshing(false);
    }
  };

  const totalViews = stats.reduce((s, v) => s + v.views, 0);
  const totalLikes = stats.reduce((s, v) => s + v.likes, 0);
  const totalComments = stats.reduce((s, v) => s + v.comments, 0);

  if (loading) {
    return <div className="card">Loading...</div>;
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Analytics</h2>
        <button className="btn btn-secondary" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: 32, fontWeight: 700, color: "#4caf50" }}>{totalViews}</div>
          <div style={{ fontSize: 13, color: "#888" }}>Total Views</div>
        </div>
        <div className="card" style={{ textAlign: "center" }}>
          <div style={{ fontSize: 32, fontWeight: 700, color: "#4caf50" }}>{totalLikes}</div>
          <div style={{ fontSize: 13, color: "#888" }}>Total Likes</div>
        </div>
      </div>

      {stats.length === 0 ? (
        <div className="card">
          <div style={{ color: "#666", fontSize: 14 }}>
            No analytics data yet. Upload some videos first, then refresh.
          </div>
        </div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Video</th>
                <th>Topic</th>
                <th>Views</th>
                <th>Likes</th>
                <th>Comments</th>
                <th>Published</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((s) => (
                <tr key={s.video_db_id}>
                  <td>
                    <a
                      href={`https://www.youtube.com/watch?v=${s.video_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {s.video_id.slice(0, 8)}...
                    </a>
                  </td>
                  <td>{s.topic_title?.slice(0, 50)}</td>
                  <td>{s.views.toLocaleString()}</td>
                  <td>{s.likes.toLocaleString()}</td>
                  <td>{s.comments.toLocaleString()}</td>
                  <td>{s.published_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Analytics;
