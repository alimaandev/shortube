import React from "react";
import { NavLink } from "react-router-dom";

interface LayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/topics", label: "Topics" },
  { to: "/videos", label: "Videos" },
  { to: "/analytics", label: "Analytics" },
  { to: "/settings", label: "Settings" },
];

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div>
      <header
        style={{
          background: "#1a1a1a",
          borderBottom: "1px solid #2a2a2a",
          padding: "0 24px",
          display: "flex",
          alignItems: "center",
          height: 56,
        }}
      >
        <h1
          style={{
            fontSize: 20,
            fontWeight: "bold",
            color: "#4caf50",
            marginRight: 40,
          }}
        >
          Shortube
        </h1>
        <nav style={{ display: "flex", gap: 4 }}>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              style={({ isActive }) => ({
                padding: "8px 16px",
                borderRadius: 6,
                fontSize: 14,
                color: isActive ? "#fff" : "#888",
                background: isActive ? "#2a2a2a" : "transparent",
                textDecoration: "none",
                transition: "all 0.2s",
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="container">{children}</main>
    </div>
  );
};

export default Layout;
