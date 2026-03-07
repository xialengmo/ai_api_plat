// 作者: lxl
// 说明: 前端业务逻辑模块。
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173
  }
});

