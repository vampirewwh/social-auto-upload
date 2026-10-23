# Web 控制台

项目自带一个基于 Flask + Vue 3 的 Web 控制台，把 `sau` CLI 的全部能力做成可视化界面。
它不是旧版 `sau_backend.py`（历史实现，见 [legacy-web.md](./legacy-web.md)），而是 **完全由 argparse 定义驱动** 的新实现：
新增平台或参数，界面自动出现，不需要改前端。

## 一、启动

### Windows 一键启动

双击项目根目录的 `start-win.bat`。

它会依次完成：

1. 检查 `.venv` 是否存在（不存在就提示按 [install.md](./install.md) 安装）；
2. 检查 `sau_frontend/dist/index.html`，缺失时自动执行 `npm install` + `npm run build`；
3. 用 `SAU_WEB_PORT=5409` 在后台启动 `sau_server.py`；
4. 轮询 `/api/health` 直到就绪，然后打开浏览器。

停止服务：双击 `stop-win.bat`。

> 若 PowerShell 执行策略禁止运行脚本，`start-win.bat` 已经带上
> `-NoProfile -ExecutionPolicy Bypass`，一般无需手动改策略。

### 手动启动（任意平台）

```bash
# 1) 构建前端（只需一次，源码变更后重跑）
cd sau_frontend
npm install
npm run build
cd ..

# 2) 启动后端，默认 5409
python sau_server.py

# 也可以用环境变量换端口
SAU_WEB_PORT=8080 python sau_server.py
```

打开 <http://127.0.0.1:5409/> 即可。

> 后端同时托管 `sau_frontend/dist`，因此 **生产模式只需要一个进程**，不需要单独跑 Vite。
> 只有改前端源码时才需要开发服务器。

### 前端开发模式

```bash
# 终端 A：后端
python sau_server.py                # 5409

# 终端 B：Vite 热更新
cd sau_frontend
npm run dev                         # 5173，/api 已代理到 5409
```

访问 <http://127.0.0.1:5173/>。`sau_frontend/vite.config.js` 里 `server.proxy['/api'].target`
指向 `http://localhost:5409`，端口改了要同步改这里。

## 二、页面

| 路由 | 页面 | 说明 |
| --- | --- | --- |
| `#/` | 总览 | 账号数 / 素材数 / 执行中任务 / 成功失败统计，平台支持表，最近任务 |
| `#/publish` | 发布中心 | 选平台 → 选动作 → 自动生成表单 → 提交任务 → 看实时日志 |
| `#/accounts` | 账号管理 | 列出 `cookies/` 下的登录态；校验、重新登录、导入 Cookie、删除 |
| `#/materials` | 素材管理 | 列出 `videos/` 下的文件；上传、预览、复制文件名、删除 |
| `#/about` | 关于 | 版本、后端入口、工作原理、命令等价用法 |

前端使用 **hash 路由**，所以刷新任意页面都不会 404。

## 三、发布中心怎么用

1. 左侧选择平台（共 17 个，支持搜索）。
2. 右侧选择动作。动作清单来自 `sau_cli` 的 argparse 定义，例如
   `check`（校验登录）、`login`（扫码登录）、`upload-video`（发视频）、
   `upload-note`（发图文）、`upload-article`（发文章）、`verify`、`delete`。
3. 表单按字段类型自动渲染：
   - `existing_file_path` → 素材下拉框，视频字段只列视频、封面字段只列图片；
   - `existing_dir_path` → 目录输入；
   - `schedule_value` → 日期时间选择器（`YYYY-MM-DD HH:MM`）；
   - `store_true` / `store_false` → 开关；互斥开关（`--headed` / `--headless`）合并成一个开关；
   - `choices` → 下拉框；其余按输入框。
4. 底部会显示 **等价命令**，方便复制到终端复现。
5. 提交后进入任务列表，点「日志」可以看子进程 stdout 实时输出，也可以取消（`taskkill`）。

> 账号字段会自动带出 `cookies/` 里已有的账号名，也可以直接输入新名字。

## 四、登录方式

「账号管理 → 扫码 / 浏览器登录」支持全部 16 个可登录平台，分两类：

| 类型 | 平台 | 交互 |
| --- | --- | --- |
| 二维码 | 抖音、快手、小红书、视频号、支付宝生活号、百家号、微博、虎扑 | 弹窗内直接显示二维码，手机扫码 |
| 浏览器 | Bilibili、YouTube、Facebook、Facebook Page、Instagram、大鱼号、雪球、知乎 | 打开浏览器窗口，手动完成登录 |

二维码通过 SSE（`/api/login/<sid>/stream`）实时推到前端，一个二维码有效期过了会继续推新的。
关闭弹窗不会保留无效会话，重新打开即可。

> Bilibili 登录需要真实的交互终端，在 Web 里会提示
> `Bilibili login requires a local interactive terminal`。
> 这种情况请在终端里执行 `sau bilibili login --account <name>`。

## 五、HTTP 接口

所有接口返回统一结构：

```json
{ "code": 200, "data": { }, "msg": null }
```

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 服务与工作目录 |
| GET | `/api/schema` | 全平台参数描述（前端表单的数据源） |
| POST | `/api/tasks` | 提交任务 `{platform, action, values}` |
| GET | `/api/tasks?limit=50` | 任务列表 |
| GET | `/api/tasks/<id>?tail=200` | 任务详情（含日志尾巴） |
| POST | `/api/tasks/<id>/cancel` | 取消任务 |
| DELETE | `/api/tasks` | 清空已结束任务 |
| GET | `/api/accounts` | 账号列表 |
| POST | `/api/accounts/upload` | 导入 Cookie（multipart：`platform`/`account`/`file`） |
| DELETE | `/api/accounts?platform=&account=` | 删除账号 |
| GET | `/api/materials` | 素材列表 |
| POST | `/api/materials/upload` | 上传素材（multipart：`file`） |
| GET | `/api/materials/preview/<name>` | 预览素材 |
| DELETE | `/api/materials?name=` | 删除素材 |
| POST | `/api/login/start` | 开始登录 `{platform, account, headless}` |
| GET | `/api/login/<sid>/stream` | 登录 SSE 流（`status`/`qrcode`/`result` 事件） |
| GET | `/api/login/platforms` | 可登录平台与模式 |
| GET | `/api/login/sessions` | 正在进行的登录会话 |

### 例子

```bash
# 校验抖音登录态
curl -X POST http://127.0.0.1:5409/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"platform":"douyin","action":"check","values":{"account":"creator"}}'

# 查看两个平台的参数定义
curl http://127.0.0.1:5409/api/schema
```

## 六、目录结构

```
sau_server.py              Flask 入口：路由 + 静态托管
sau_api/
├── schema.py              argparse → JSON 表单描述
├── tasks.py               子进程任务管理
├── accounts.py            cookies/ 与 videos/ 的读写
└── login.py               登录会话 + SSE
sau_frontend/
├── src/views/             Dashboard / PublishCenter / AccountManagement / MaterialManagement / About
├── src/components/        DynamicForm / LoginDialog
├── src/api/sau.js         接口封装
├── src/stores/sau.js      Pinia：schema / accounts / materials / tasks
└── dist/                  构建产物（由 Flask 托管）
start-win.bat / stop-win.bat / start-web.ps1 / stop-web.ps1   启动脚本
```

## 七、常见问题

**页面白屏 / 控制台报 module script MIME 错误**
`sau_frontend/dist` 没构建或构建不完整。执行 `cd sau_frontend && npm run build`。

**`/api/schema` 返回的平台数少于预期**
后端进程是旧的。重启 `sau_server.py`（改过 `sau_cli.py` 后必须重启）。

**提交任务提示「缺少必填参数」**
该参数在 CLI 里是 `required=True`，请补全。表单里带红色星号的都是必填。

**任务一直 running**
浏览器自动化本身较慢；如果确实卡住，点「取消」。也可以在日志里看具体卡在哪一步。
若某平台首次发布需要安装额外依赖（如 Bilibili 的 `biliup`），进程会在第一次运行时自动准备。

**改了 `sau_cli.py` 的参数，界面没变**
`/api/schema` 是启动时构建并缓存的，重启后端即可。

**二维码扫不出来**
窗口小可以拖动放大；过期后会自动刷新。若一直失败，改用「浏览器登录」模式，或直接在终端执行
`sau <platform> login --account <name>`。
