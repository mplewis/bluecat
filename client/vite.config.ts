import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/print": "http://localhost:8000",
      "/feed": "http://localhost:8000",
    },
  },
});
