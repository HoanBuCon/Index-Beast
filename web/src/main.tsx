// Điểm vào: render <App/> trong BrowserRouter.
// Phụ trách: TV4 · [S1] Khởi tạo web React

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App";
import "./styles/index.css";
import "./styles/refinement.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
