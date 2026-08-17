# ClickHouse Query Boundary Design

## Goal

集中处理 QWeSDK 中 ClickHouse HTTP 查询的标识符和值，避免表名、列名和列表值通过字符串拼接改变 SQL 结构，同时保持现有查询结果和 HTTP 访问方式不变。

## Scope

- 覆盖 `InputV1`、`ExtractDataV1` 和 `SelectorV1` 中当前重复的 SQL 值拼接。
- 标识符只允许字母、数字和下划线；表名额外支持单层 `database.table`。
- 字符串值使用 ClickHouse 单引号规则转义；列表值统一生成 `IN (...)`。
- 不引入新的 ClickHouse 客户端，不改变已有 HTTP 端点、CSV 响应格式和异常返回约定。
- 不在本轮实现参数化查询、连接池、日志系统或回测功能。

## Design

新增 `m/db/sql_safety.py`，提供小而无状态的函数：

- `quote_identifier(value, allow_qualified=False)` 校验并返回反引号包裹的标识符。
- `quote_string(value)` 将值转换为 ClickHouse 字符串字面量，并转义单引号和反斜杠。
- `quote_string_list(values)` 为非空序列生成逗号分隔的字符串字面量；空序列返回空字符串，调用方据此跳过 `IN` 条件或直接返回空结果。

三个数据模块只把固定 SQL 结构与这些函数返回的片段组合起来。用户输入永远只能成为一个标识符或字符串字面量，不能注入额外的关键字、注释或条件。

## Error Handling

非法标识符和值类型抛出 `ValueError`，调用层沿用现有捕获逻辑并返回空结果。空列表不生成伪造的 `IN ('')` 条件：输入查询继续保持“查询全部”的历史行为，提取查询保持“返回空列表”的历史行为。

## Testing

单元测试覆盖合法标识符、限定表名、非法字符、引号/反斜杠转义、列表拼接和注入片段。模块替换后增加查询文本断言，确认恶意股票代码、行业名和指数名只作为一个字面量出现。
