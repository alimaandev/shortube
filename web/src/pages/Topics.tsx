import React, { useState, useEffect, useCallback } from "react";
import { api, Topic } from "../api/client";

const Topics: React.FC = () => {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await api.topics(200);
      setTopics(res.topics);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="card">
      <h2>Topics</h2>
      {loading ? (
        <div style={{ color: "#666" }}>Loading...</div>
      ) : topics.length === 0 ? (
        <div style={{ color: "#666" }}>No topics discovered yet</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Niche</th>
              <th>Source</th>
              <th>Score</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {topics.map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td>
                <td>{t.title?.slice(0, 80)}</td>
                <td>{t.niche}</td>
                <td>{t.source}</td>
                <td>{t.score?.toFixed(1)}</td>
                <td>
                  <span
                    className={`status-badge ${
                      t.used ? "status-done" : "status-pending"
                    }`}
                  >
                    {t.used ? "used" : "new"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default Topics;
