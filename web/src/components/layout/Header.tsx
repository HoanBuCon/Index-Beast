// Logo + điều hướng.
// Phụ trách: TV4 · [S1] Khởi tạo web React

import { Link } from "react-router";
import type { ReactNode } from "react";
export default function Header({ sidebarToggle }: { sidebarToggle?: ReactNode }) {
  return (
    <header className="header">
      <div className="sidebar-brand-row">
        {sidebarToggle}
        <Link to="/" className="brand" aria-label={"Index Beast — trang chủ"}>
          {!sidebarToggle && (
            <span className="brand-mark" aria-hidden="true">
              ✦
            </span>
          )}
          <span>
            INDEX <strong>BEAST</strong>
            <small>THE LANDS BETWEEN ARCHIVE</small>
          </span>
        </Link>
      </div>
    </header>
  );
}
