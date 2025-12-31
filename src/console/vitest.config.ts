import { defineConfig } from "vitest/config"
import path from "path"

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
      "@/components": path.resolve(__dirname, "components"),
      "@/state": path.resolve(__dirname, "state"),
      "@/hooks": path.resolve(__dirname, "hooks"),
      "@/lib": path.resolve(__dirname, "lib"),
      "@/app": path.resolve(__dirname, "app"),
    },
  },
})
