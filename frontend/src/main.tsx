import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { LiveStore } from "./state/LiveStore";
import "./i18n";
import "./index.css";

const client = new QueryClient();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <LiveStore>
        <App />
      </LiveStore>
    </QueryClientProvider>
  </React.StrictMode>
);
