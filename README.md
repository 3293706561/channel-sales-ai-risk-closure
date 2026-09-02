# 特渠销售 AI 经营管理 MVP

这是一个可本地运行的个人作品集项目，模拟区域销售管理者处理经营风险的完整过程。原始单文件 Demo 保留在 `app/index.html`；全栈版使用独立的 `app_frontend`、FastAPI 和 SQLite。

## 打开方式

查看原始单文件 Demo：双击 `启动项目.bat`。

启动完整前后端版本：双击 `启动全栈项目.bat`，然后在浏览器打开 `http://127.0.0.1:8000`。

全栈版默认演示账号：

| 账号 | 角色 | 密码 |
| --- | --- | --- |
| `north_manager` | 华北区域经理 | `demo123` |
| `east_sales` | 一线销售 | `demo123` |
| `director` | 销售总监 | `demo123` |

`经营驾驶舱 → 确认华北经营风险 → 确认并指派 → 责任人更新进度 → 提交人工复核 → 区域经理关闭或退回`

## 已完成的产品能力

- 经营驾驶舱：明确今天优先处理什么；
- 风险预警：按严重程度查看经营风险；
- 风险处置：展示数据线索、AI 建议和处理留痕；
- 整改闭环：确认、指派、补充进度、人工复核、关闭；
- AI 经营简报：汇总已确认的经营事实。

## 全栈版新增能力

- 后端 API、SQLite 持久化和演示账号角色校验；
- 风险与任务的事务化状态流转，含待复核环节；
- 幂等键、乐观锁和单风险单活跃任务约束；
- 五类剧本风险数据：待确认、处理中、待复核、已关闭、误报；
- Mock AI：日报结构化、处置建议与经营简报；
- 自建接口测试：重复确认不重复建任务、过期版本冲突、越权拦截、证据不足拒答。

## 重要边界

- 页面使用模拟数据；
- 不连接 SAP、勤策、企业微信或客户真实系统；
- AI 只提供线索与建议，不自动认定责任或关闭任务；
- 这是基于实习接触场景完成的个人 MVP，不代表企业实际交付。

## 本地开发与验证

依赖已安装在项目的 `.venv` 目录。需要重置演示数据时，在项目根目录执行：

```powershell
Push-Location .\backend
..\.venv\Scripts\python.exe -m app.seed
Pop-Location
```

运行自动化测试：

```powershell
Push-Location .\backend
..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

生成 24 条自建 Mock AI 边界评测报告：

```powershell
Push-Location .\backend
..\.venv\Scripts\python.exe .\evaluate_ai.py
Pop-Location
```

报告输出到 `backend/outputs/ai_eval_report.json`。它只说明自建模拟输入的检查结果，不代表真实业务准确率。

## 项目结构

```text
app/index.html     原始单文件前端 Demo
app_frontend/      模块化前端页面
backend/app/       FastAPI、SQLite 模型、剧本数据与 Mock AI
backend/tests/     状态机、权限、幂等和拒答测试
启动项目.bat        本地启动入口
启动全栈项目.bat    全栈版本地启动入口
PRD_v0.1.md        产品范围与验收标准
DESIGN_SPEC_v0.1.md 页面设计规范
API_CONTRACT_v0.1.md 前后端模拟协作契约
项目实施方案_v1.1.md 全栈升级实施方案
```
