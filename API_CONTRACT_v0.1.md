# 特渠销售 AI 经营管理 MVP：Mock API 契约

> 版本：v0.1  
> 数据性质：模拟数据。接口用于前后端并行开发与验收演示，不连接企业真实系统。  
> 关联文档：[PRD_v0.1.md](./PRD_v0.1.md)

## 1. 通用约定

- Base URL：`/api`
- 数据格式：`application/json; charset=utf-8`
- 时间格式：ISO 8601，例如 `2026-08-28T10:30:00+08:00`
- 风险状态：`pending_confirmation`、`in_progress`、`closed`
- 风险等级：`critical`、`warning`
- 所有 AI 建议均返回 `requiresHumanConfirmation: true`；前端必须展示“待业务确认”。

## 2. 风险列表

### `GET /api/risks`

用于“风险预警中心”和“经营驾驶舱优先风险清单”。

#### 查询参数

| 参数 | 可选值 | 说明 |
| --- | --- | --- |
| `level` | `critical` / `warning` | 按风险等级筛选；不传则返回全部 |
| `status` | `pending_confirmation` / `in_progress` / `closed` | 按当前状态筛选 |

#### 成功响应：`200 OK`

```json
{
  "dataUpdatedAt": "2026-08-28T10:30:00+08:00",
  "isDemoData": true,
  "items": [
    {
      "id": "risk-north-032",
      "ruleCode": "R-032",
      "level": "critical",
      "title": "华北大区月度目标达成风险",
      "summary": "近 7 日出货额持续低于计划，重点项目推进停滞。",
      "primarySignal": "近 3 日日均出货额较前一周下降 24%",
      "impactText": "预计影响 86 万元",
      "owner": {"name": "李楠", "role": "华北大区经理"},
      "status": "pending_confirmation",
      "dueAt": "2026-08-28T18:00:00+08:00"
    }
  ]
}
```

## 3. 风险详情

### `GET /api/risks/:riskId`

用于“风险处置”页面。前端通过 `riskId` 拉取详情，不在页面内拼接业务判断。

#### 成功响应：`200 OK`

```json
{
  "id": "risk-north-032",
  "rule": {
    "code": "R-032",
    "name": "区域目标达成与项目停滞组合预警",
    "isSimulated": true,
    "description": "区域连续 3 日出货额低于前一周均值 20%，且重点项目超过 10 天无有效跟进。"
  },
  "level": "critical",
  "status": "pending_confirmation",
  "title": "华北大区月度目标达成风险",
  "summary": "近 7 日出货额持续低于计划，重点项目“政企中秋礼赠”推进停滞。",
  "impactText": "预计影响 86 万元",
  "owner": {"name": "李楠", "role": "华北大区经理"},
  "dueAt": "2026-08-28T18:00:00+08:00",
  "signals": [
    {
      "type": "sales_trend",
      "label": "核心信号",
      "text": "近 3 日日均出货额较前一周下降 24%",
      "source": "模拟出货数据",
      "observedAt": "2026-08-28T10:30:00+08:00"
    },
    {
      "type": "project_stagnation",
      "label": "关联线索",
      "text": "重点项目已 12 天无有效跟进记录",
      "source": "模拟项目跟进数据",
      "observedAt": "2026-08-28T10:30:00+08:00"
    },
    {
      "type": "daily_report_tag",
      "label": "关联线索",
      "text": "区域日报中“货期不确定”标签出现 7 次",
      "source": "模拟日报解析结果",
      "observedAt": "2026-08-28T10:30:00+08:00"
    }
  ],
  "aiRecommendation": {
    "text": "优先核实礼赠项目货期与客户决策节点；确认后由区域经理协调供货与拜访计划，并于今日完成责任人指派。",
    "requiresHumanConfirmation": true
  },
  "timeline": [
    {"event": "rule_matched", "at": "2026-08-28T10:30:00+08:00", "actor": "system"},
    {"event": "signals_linked", "at": "2026-08-28T10:30:02+08:00", "actor": "system"}
  ]
}
```

## 4. 状态流转操作

### `POST /api/risks/:riskId/actions`

用于确认风险、补充整改进度、提交人工复核和标记误报。后端应校验当前状态是否允许该操作；前端不自行跳过流转步骤。

#### 请求体

```json
{
  "action": "confirm_and_assign",
  "actor": {"id": "demo-manager-001", "role": "regional_manager"},
  "note": "已核验关联信号，需要启动整改。",
  "assignee": {"id": "demo-manager-001", "name": "李楠"}
}
```

#### 可用 `action`

| action | 当前允许状态 | 结果状态 | 前端行为 |
| --- | --- | --- | --- |
| `confirm_and_assign` | `pending_confirmation` | `in_progress` | 展示“整改任务已创建” |
| `mark_false_positive` | `pending_confirmation` | `closed` | 展示“已标记为误报”，保留记录 |
| `update_progress` | `in_progress` | `in_progress` | 追加整改进度到留痕 |
| `submit_for_review` | `in_progress` | `closed`（MVP 简化） | 展示“已完成人工复核” |

#### 成功响应：`200 OK`

```json
{
  "id": "risk-north-032",
  "previousStatus": "pending_confirmation",
  "status": "in_progress",
  "action": "confirm_and_assign",
  "task": {
    "id": "task-north-032",
    "assignee": {"id": "demo-manager-001", "name": "李楠"},
    "dueAt": "2026-08-28T18:00:00+08:00"
  },
  "timelineEvent": {
    "event": "risk_confirmed_and_assigned",
    "at": "2026-08-28T10:45:00+08:00",
    "actor": "demo-manager-001"
  }
}
```

#### 状态冲突响应：`409 Conflict`

```json
{
  "error": {
    "code": "INVALID_RISK_STATE",
    "message": "当前风险已关闭，不能再次确认并指派。",
    "currentStatus": "closed"
  }
}
```

## 5. 前后端职责边界

| 事项 | 前端 | 后端 / Mock 服务 |
| --- | --- | --- |
| 风险列表展示、筛选、页面状态 | 负责 | 提供符合契约的数据 |
| 风险等级、规则编号、状态校验 | 展示，不自行判断 | 负责计算与校验 |
| AI 建议的“待确认”提示 | 必须展示 | 返回 `requiresHumanConfirmation` |
| 整改操作 | 收集操作与说明、展示结果 | 校验状态、更新记录、返回新状态 |
| 演示数据边界 | 必须可见 | 返回 `isDemoData: true` |

## 6. 联调验收用例

| 用例 | 操作 | 预期 |
| --- | --- | --- |
| 风险筛选 | `GET /api/risks?level=critical` | 仅返回严重风险 |
| 详情查看 | 打开 `risk-north-032` | 显示 3 条信号及待确认 AI 建议 |
| 确认并指派 | 调用 `confirm_and_assign` | 风险状态从 `pending_confirmation` 变为 `in_progress` |
| 误报关闭 | 调用 `mark_false_positive` | 状态变为 `closed`，不删除风险记录 |
| 重复操作 | 对已关闭风险再次调用确认 | 返回 `409 INVALID_RISK_STATE` |

## 7. 后续替换真实数据时的检查项

真实接口接入前，应补充：数据来源与刷新频率、字段权限、脱敏规则、身份认证、操作审计、异常重试、规则配置审批与发布回滚。本 MVP 不将这些未实现能力表述为已具备。
