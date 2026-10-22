// The serif for headings and moves, upright and italic (docs/adr/0010-look-and-bundled-fonts.md).
import "@fontsource-variable/source-serif-4/wght.css";
import "@fontsource-variable/source-serif-4/wght-italic.css";
import "./styles/global.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";

const root = document.getElementById("root");
if (!root) {
  throw new Error("index.html has no element with id 'root' to mount the app into");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
