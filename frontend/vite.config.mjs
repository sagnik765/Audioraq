import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, transformWithEsbuild } from "vite";

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const jsxInJavaScript = {
  name: "jsx-in-javascript",
  enforce: "pre",
  async transform(code, id) {
    if (!/\/src\/.*\.js$/.test(id)) return null;
    return transformWithEsbuild(code, id, { loader: "jsx", jsx: "automatic" });
  },
};

export default defineConfig({
  plugins: [jsxInJavaScript, react()],
  resolve: {
    alias: {
      "@": path.resolve(currentDir, "src"),
    },
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: {
        ".js": "jsx",
      },
    },
  },
  build: {
    outDir: "build",
    emptyOutDir: true,
  },
});
