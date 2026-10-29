// The windows' pages (the popup, the main window), built into dist/ for the app to load.
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, type Plugin } from "vite"

// pages loaded from files can't load scripts marked crossorigin (there's no origin to match)
const fromFiles: Plugin = {
  name: "from-files",
  transformIndexHtml: (html) => html.replaceAll(" crossorigin", ""),
}

export default defineConfig({
  base: "./",  // loaded from files, not a server
  plugins: [react(), tailwindcss(), fromFiles],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: {
    outDir: "dist",
    rollupOptions: {
      input: {
        popup: path.resolve(__dirname, "popup.html"),
        main: path.resolve(__dirname, "main.html"),
      },
    },
  },
})
