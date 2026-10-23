# SAU Web 控制台（前端）

Vue 3 + Vite 6 + Element Plus + Pinia + Vue Router（hash 模式）。
页面数据全部来自 Flask 后端 `sau_server.py` 的 `/api/schema`，表单按 argparse 定义动态渲染。

完整使用说明见 [docs/web.md](../docs/web.md)。

## 开发

```bash
npm install

# 需要同时启动后端（默认 5409）
# 终端 A： cd .. && python sau_server.py
npm run dev          # http://127.0.0.1:5173 ，/api 已代理到 5409
```

## 构建

```bash
npm run build        # 产物写入 dist/，由 Flask 同源托管
npm run preview      # 本地预览构建产物
```

> 构建完成后不需要单独部署静态服务器：`sau_server.py` 会同时托管 `dist/`，
> 访问 <http://127.0.0.1:5409/> 即可。

## 目录

```
src/
├── api/sau.js             后端接口封装（schema / tasks / accounts / materials / login）
├── components/
│   ├── DynamicForm.vue    按字段 kind 自动渲染表单控件
│   └── LoginDialog.vue    扫码 / 浏览器登录弹窗（SSE 实时二维码）
├── router/index.js        hash 路由
├── stores/sau.js          Pinia：schema / accounts / materials / tasks
├── styles/                全局样式
├── utils/request.js       axios 封装，解包 {code,data,msg}
├── views/
│   ├── Dashboard.vue          总览
│   ├── PublishCenter.vue      发布中心（平台 → 动作 → 表单 → 任务日志）
│   ├── AccountManagement.vue  账号管理
│   ├── MaterialManagement.vue 素材管理
│   └── About.vue              关于
├── App.vue                头部导航 + 健康指示
└── main.js                入口
```

## 环境变量

| 文件 | 变量 | 说明 |
| --- | --- | --- |
| `.env.development` | `VITE_API_BASE_URL=/api` | 走 Vite 代理 |
| `.env.production` | `VITE_API_BASE_URL=/api` | 由 Flask 同源托管，用相对路径 |

改后端端口时，同步修改 `vite.config.js` 里 `server.proxy['/api'].target`。

## 约定

- 页面组件放 `src/views/`，公共组件放 `src/components/`
- 统一使用 `<script setup>`
- 接口调用一律走 `@/api/sau`，不要直接写 `axios`
- 路由用 hash 模式，刷新不会 404
