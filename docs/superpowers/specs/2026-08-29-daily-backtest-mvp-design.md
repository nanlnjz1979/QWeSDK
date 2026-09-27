# 日线回测 MVP 设计

## 目标

交付一个可从浏览器发起、观察和复盘日线回测的工作台。页面展示的收益率、最大回撤、Sharpe、权益曲线、交易明细和运行日志全部来自 QWeSDK `TraderV2` 的真实执行结果，不使用前端样例数据。

## 范围

MVP 支持：

- 日线 ClickHouse 数据集的选择、日期范围、初始资金、策略代码和参数提交；CSV/Parquet 仅保留为测试夹具。
- 回测运行状态、进度、阶段日志和错误信息。
- 总收益、最终权益、最大回撤、Sharpe、交易次数。
- 日权益曲线、回撤曲线和成交明细。
- 刷新页面后按 run ID 恢复运行状态和结果。

MVP 不包含分钟/Tick、限价单、风控、实盘、策略持久化、复杂图表编辑和专业报告导出。

## 架构

浏览器访问 Gateway 的同源 HTTP API。Gateway 为页面请求生成完整 `runSpec`，校验策略代码 hash、数据集 manifest hash 和日期范围，然后调用现有 `GatewayService`。生产部署继续使用 `Celery -> tasks.run_backtest -> sandbox_runner -> TraderV2`；本地开发模式使用同一个 `tasks.run_backtest` 函数在后台线程执行，以便没有 Redis/Worker 时也能跑通真实执行链路。

Gateway 增加 SQLite 回测存储，记录 run spec、状态事件和标准化结果。Celery 桥接回调与本地执行器都写入同一存储，页面只读取统一的 status/result/events 接口。

## API

- `GET /api/datasets`：Gateway 不扫描本地目录；Helix 目录接入前返回受控空数组。回测提交携带 Helix 冻结的 inline Manifest，由 Worker 按 Manifest 读取 ClickHouse。
- `POST /api/backtests`：接受页面表单，服务端创建 run ID 并提交；返回 `{runId, status}`。
- `GET /api/backtests/{runId}`：返回当前状态、进度、阶段、事件和错误信息。
- `GET /api/backtests/{runId}/result`：成功时返回标准 result；未完成返回 409，失败返回可读错误。
- `POST /api/backtests/{runId}/cancel`：创建取消标记并撤销 Celery 任务。

标准结果沿用当前 `schemaVersion=1.0`：`summary`、`series.equityCurve`、`series.drawdownCurve`、`series.trades`、`runtime`。

## 页面

采用已确认的回测工作台布局：顶部任务状态和操作，左侧配置，主区域指标和权益/回撤图，底部交易明细与日志。页面使用原生 HTML/CSS/JavaScript 和 SVG 图表，保持轻量、同源、无需额外前端构建链；运行中自动轮询，完成后加载标准 result，失败时显示服务端错误。

## 可靠性和校验

- 服务端拒绝未知数据集、manifest hash 不匹配、非日线数据集、非法日期范围和缺少策略入口。ClickHouse Manifest 明确区分不可变发布表（`immutable_table`）和滚动视图（`current_view`）；后者必须以当前完整交易日作为覆盖上限，并在结果中记录查询时点。
- 策略代码仍由 worker sandbox 执行，页面不能绕过策略 hash 或 worker 限制。
- 前端不计算核心指标，只格式化标准 result；图表点和交易表格直接映射后端返回值。
- 状态更新按事件 sequence 幂等写入，结果以 run ID 持久化。

## 测试验收

- 存储层覆盖创建 run、事件顺序、结果持久化和刷新读取。
- Gateway API 覆盖提交、查询、完成结果、失败和非法输入。
- 真实 fixture 数据通过 `tasks.run_backtest` 跑过 sandbox、数据加载和 TraderV2，并断言返回值不是前端生成。
- 浏览器验收：可提交真实回测，状态从 queued/running 变化到 succeeded，指标、曲线和成交记录出现；刷新后仍可恢复结果。
