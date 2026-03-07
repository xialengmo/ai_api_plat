// 作者: lxl
// 说明: 前端应用入口。
import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import App from "./App.vue";
import "./style.css";

createApp(App).use(ElementPlus).mount("#app");
