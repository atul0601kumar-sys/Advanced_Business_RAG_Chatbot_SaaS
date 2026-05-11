import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  publicDir: false,
  build: {
    emptyOutDir: false,
    lib: {
      entry: resolve(process.cwd(), "public/widget/widget_loader.js"),
      name: "AdvancedBusinessRagWidget",
      formats: ["es"],
      fileName: () => "widget-loader.bundle.js",
    },
    outDir: resolve(process.cwd(), "public/widget-dist"),
    minify: "esbuild",
    target: "es2019",
  },
});
