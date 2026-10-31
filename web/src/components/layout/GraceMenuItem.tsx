// TV4 · Nút menu Elden Ring: dùng chung giao diện cho button và NavLink, giữ ngữ nghĩa HTML.
import type { MouseEventHandler } from "react";
import { NavLink } from "react-router";
// TV4: thay bộ có khung bằng ảnh tab hi_01 không khung — lời nhắn / giấy / chìa khóa.
// Ảnh được chép nguyên bản vào item_, không tham chiếu thư mục nguồn bên ngoài dự án.
import newIcon from "../../../item_/MENU_Tab_22.png";
import aboutIcon from "../../../item_/MENU_Tab_18.png";
import adminIcon from "../../../item_/MENU_Tab_03.png";
import "../../styles/sidebar-menu.css";

type SharedProps = {
  label: string;
  icon: "new" | "about" | "admin";
  className?: string;
};
type GraceMenuItemProps = SharedProps &
  (
    | { to: string; onClick?: MouseEventHandler<HTMLAnchorElement>; disabled?: never }
    | { to?: never; onClick?: MouseEventHandler<HTMLButtonElement>; disabled?: boolean }
  );

const icons = { new: newIcon, about: aboutIcon, admin: adminIcon };

export default function GraceMenuItem(props: GraceMenuItemProps) {
  const className = `grace-menu ${props.className ?? ""}`.trim();
  const content = (
    <>
      <span className="grace-menu__line" aria-hidden="true" />
      <span className="rail-icon grace-menu__icon" aria-hidden="true">
        <img src={icons[props.icon]} width={28} height={28} alt="" draggable={false} />
      </span>
      <span className="rail-label grace-menu__label">{props.label}</span>
    </>
  );

  if (props.to !== undefined) {
    return (
      <NavLink
        to={props.to}
        className={({ isActive }) => `${className}${isActive ? " active" : ""}`}
        onClick={props.onClick}
        title={props.label}
        aria-label={props.label}
      >
        {content}
      </NavLink>
    );
  }
  return (
    <button
      type="button"
      className={className}
      disabled={props.disabled}
      onClick={props.onClick}
      title={props.label}
      aria-label={props.label}
    >
      {content}
    </button>
  );
}
