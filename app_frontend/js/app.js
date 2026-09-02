import { command, login, request, session } from "./api.js";
import { resetState, state } from "./store.js";

const app = document.querySelector("#app");
const toast = document.querySelector("#toast");
const statusLabels = { pending_confirmation: "待确认", in_progress: "处理中", pending_review: "待复核", closed: "已关闭" };
const levelLabels = { critical: "严重风险", warning: "一般风险" };
const eventLabels = { rule_matched: "规则命中，生成风险信号", risk_detected: "系统发现风险信号", risk_confirmed_and_assigned: "已确认风险并创建整改任务", marked_false_positive: "已标记为误报", task_progress_updated: "已补充整改进度", submitted_for_review: "已提交人工复核", review_approved: "复核通过并关闭风险", returned_for_action: "复核退回继续整改" };

function notify(message) { toast.textContent = message; toast.classList.add("show"); setTimeout(() => toast.classList.remove("show"), 2600); }
function tag(risk) { const cls = risk.status === "closed" ? "closed" : risk.status === "pending_review" ? "review" : risk.level === "critical" ? "critical" : ""; return `<span class="tag ${cls}">${risk.status ? statusLabels[risk.status] : levelLabels[risk.level]}</span>`; }
function formatDate(value) { return value ? new Date(value).toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"; }

async function loadData() {
  state.user = (await request("/auth/me")).user;
  const [dashboard, risks, tasks] = await Promise.all([request("/dashboard"), request("/risks"), request("/tasks")]);
  state.dashboard = dashboard; state.risks = risks.items; state.tasks = tasks.items;
}

function layout(body) {
  const nav = [["dashboard", "经营驾驶舱"], ["risks", "风险预警"], ["tasks", "整改任务"], ["brief", "AI 经营简报"]];
  return `<div class="shell"><aside class="side"><div class="brand">特渠经营管理<small>经营控制室 · 演示环境</small></div><nav class="nav">${nav.map(([id, name]) => `<button data-page="${id}" class="${state.page === id ? "active" : ""}">${name}</button>`).join("")}</nav><div class="side-foot"><b>${state.user.name}</b><br>${state.user.role.replace("_", " ")}<br><button id="logout" class="click" style="color:#fff;margin-top:10px">退出演示</button></div></aside><section class="content"><header class="top"><div><small>风险控制台 / 模拟数据</small></div><div><small>剧本时间 · 2026-09-02</small></div></header>${body}</section></div>`;
}

function dashboardView() {
  const m = state.dashboard.metrics;
  const priority = state.dashboard.priorityRisks[0];
  const stats = [["待确认", m.pendingConfirmation, "danger"], ["处理中", m.inProgress, ""], ["待复核", m.pendingReview, ""], ["已关闭", m.closed, ""]];
  const audit = state.dashboard.recentEvents || [];
  return layout(`<div class="headline"><h1>今天先把哪件事推到闭环？</h1><p class="sub">用经营信号决定先后，用人工复核完成闭环。系统只提示，不替代负责人判断。</p></div><section class="command-deck"><div class="command-main"><div class="eyebrow"><i class="pulse"></i> TODAY'S CONTROL ITEM</div><h2>${priority ? priority.title : "当前没有待处理风险"}</h2><p>${priority ? priority.summary : "所有风险均已完成处理。"}</p><div class="process-track"><span class="process-step active">发现信号</span><span class="process-step ${priority?.status !== "pending_confirmation" ? "active" : ""}">经理确认</span><span class="process-step ${priority?.status === "in_progress" || priority?.status === "pending_review" ? "active" : ""}">责任指派</span><span class="process-step ${priority?.status === "pending_review" ? "active" : ""}">人工复核</span></div></div><aside class="priority-panel"><div><span class="label">TODAY / PRIORITY</span><h3>${priority ? `${priority.ruleCode} · ${levelLabels[priority.level]}` : "暂无优先事项"}</h3><p>${priority ? `截止 ${formatDate(priority.dueAt)} · 责任人 ${priority.owner?.name || "待定"}` : "继续查看已关闭记录和规则复盘。"}</p></div>${priority ? `<button class="primary" data-risk="${priority.id}">进入处置工作台</button>` : `<button class="secondary" data-page="risks">查看风险记录</button>`}</aside></section><section class="stat-strip">${stats.map(([label, value, kind]) => `<div class="stat ${kind}"><label>${label}风险</label><strong>${String(value).padStart(2, "0")}</strong><small>当前工作队列</small><div class="bar"><i style="width:${Math.max(10, Number(value) * 38)}%"></i></div></div>`).join("")}</section><section class="work-grid"><div class="panel"><div class="panel-head"><h2>待推进的风险队列</h2><button class="click" data-page="risks">查看全量风险 →</button></div>${state.dashboard.priorityRisks.map(riskRow).join("") || `<div class="empty">当前没有待处理风险。</div>`}</div><div class="panel ai-panel"><div class="panel-head"><h2>AI 日报结构化</h2></div><p class="sub">只摘取可回溯事实。缺少项目、客户或行动信息时，系统会明确提示证据不足。</p><textarea id="reportText" rows="4" placeholder="例如：华北礼赠项目客户仍在确认交期，今天未完成拜访安排。"></textarea><div class="actions"><button class="primary" id="parseReport">提取风险线索</button></div><div id="aiResult" class="ai-result"></div></div></section><section class="audit-ledger"><div class="audit-head"><div><span class="label">SERVER AUDIT / SQLITE</span><h2>最近后端留痕</h2></div><p>每次关键状态变化由接口写入演示数据库，可刷新复查。</p></div><div class="audit-list">${audit.map(event => `<button class="audit-item" data-risk="${event.riskId}"><span class="audit-mark"></span><span><b>${eventLabels[event.event] || event.event}</b><small>${event.riskTitle} · ${event.actor?.name || "系统"} · ${formatDate(event.at)}</small></span><em>服务端已留痕</em></button>`).join("") || `<div class="empty">当前没有可展示的后端留痕。</div>`}</div></section>`);
}

function riskRow(risk) { return `<div class="risk-row"><i class="dot ${risk.level}"></i><div><b>${risk.title}</b><span>${risk.ruleCode} · ${risk.region} · ${formatDate(risk.dueAt)}</span></div>${tag(risk)}<button class="click" data-risk="${risk.id}">查看处置</button></div>`; }

function risksView() { return layout(`<div class="headline"><h1>风险预警中心</h1><p class="sub">每条预警都需查看证据、人工确认和过程留痕。</p></div><table class="table"><thead><tr><th>等级</th><th>预警事项</th><th>区域</th><th>责任人</th><th>状态</th><th>操作</th></tr></thead><tbody>${state.risks.map(risk => `<tr><td>${tag({ level: risk.level })}</td><td><b>${risk.title}</b><br><small>${risk.ruleCode} · ${risk.summary}</small></td><td>${risk.region}</td><td>${risk.owner?.name || "—"}</td><td>${tag(risk)}</td><td><button class="click" data-risk="${risk.id}">查看处置</button></td></tr>`).join("")}</tbody></table>`); }

function tasksView() { return layout(`<div class="headline"><h1>整改任务</h1><p class="sub">任务由风险确认后产生；状态变化由后端统一校验并持久化。</p></div><table class="table"><thead><tr><th>关联风险</th><th>责任人</th><th>截止时间</th><th>状态</th><th>操作</th></tr></thead><tbody>${state.tasks.map(task => `<tr><td><b>${task.risk.title}</b><br><small>${task.risk.ruleCode}</small></td><td>${task.assignee.name}</td><td>${formatDate(task.dueAt)}</td><td>${tag({ status: task.status })}</td><td><button class="click" data-risk="${task.riskId}">进入任务</button></td></tr>`).join("") || `<tr><td colspan="5" class="empty">暂无可查看任务。</td></tr>`}</tbody></table>`); }

function briefView() { return layout(`<div class="headline"><h1>AI 经营简报</h1><p class="sub">简报仅汇总当前可见的未关闭风险，不把模型推断写成已确认事实。</p><div class="actions"><button class="primary" id="generateBrief">生成今日演示简报</button></div></div><section class="panel" id="briefResult"><div class="empty">点击按钮生成简报。</div></section>`); }

async function detailView() {
  const risk = await request(`/risks/${state.selectedRiskId}`);
  const task = risk.task;
  const actionButtons = [];
  if (risk.status === "pending_confirmation" && state.user.role === "regional_manager" && risk.owner?.id === state.user.id) {
    actionButtons.push(`<select id="assigneeId"><option value="sales-east">周航｜一线销售</option><option value="manager-east">王玥｜区域经理</option></select><button class="primary" id="confirmRisk">确认风险并指派</button><input id="dismissReason" placeholder="误报原因"><button class="secondary" id="dismissRisk">标记为误报</button>`);
  }
  if (task?.status === "open" && task.assignee?.id === state.user.id) actionButtons.push(`<textarea id="updateContent" placeholder="填写已采取动作、现存阻碍和需要协同事项"></textarea><button class="secondary" id="updateTask">保存整改进度</button><button class="primary" id="submitReview">提交人工复核</button>`);
  if (task?.status === "pending_review" && state.user.role === "regional_manager" && risk.owner?.id === state.user.id) actionButtons.push(`<textarea id="reviewNote" placeholder="填写复核结论"></textarea><button class="primary" id="approveTask">复核通过并关闭</button><button class="secondary" id="returnTask">退回继续整改</button>`);
  app.innerHTML = layout(`<button class="click" data-page="risks">← 返回风险预警</button><div class="headline" style="margin-top:14px"><h1>${risk.title}</h1><p class="sub">${risk.summary}</p></div><section class="detail"><div><div class="panel"><div class="panel-head"><h2>${tag(risk)}　${risk.ruleCode}</h2><small>版本 ${risk.version}</small></div><h3>系统发现的信号</h3><div class="signals">${risk.signals.map(signal => `<div class="signal"><b>${signal.text}</b><small>${signal.source} · ${signal.evidenceRef} · ${formatDate(signal.observedAt)}</small></div>`).join("")}</div><div class="ai"><b>AI 处置建议（待业务确认）</b><p>优先核验关联信号是否反映真实业务变化；确认责任人和截止时间后再创建或推进整改任务。</p></div><div class="actions">${actionButtons.join("") || `<span class="sub">当前角色没有可执行操作。</span>`}</div></div></div><aside><section class="panel"><h2>任务信息</h2><p><b>状态：</b>${tag(risk)}</p><p><b>责任人：</b>${risk.owner?.name || "—"}</p><p><b>截止：</b>${formatDate(risk.dueAt)}</p>${task ? `<p><b>任务版本：</b>${task.version}</p>` : ""}</section><section class="panel" style="margin-top:16px"><div class="audit-detail-head"><span>SERVER EVENT LOG</span><h2>处理留痕</h2></div><div class="timeline">${risk.timeline.map(event => `<div><b>${eventLabels[event.event] || event.event}</b><small>${event.actor?.name || "系统"} · ${formatDate(event.at)} · 服务端已写入</small></div>`).join("")}</div></section></aside></section>`);
  bindShell();
  bindDetailActions(risk);
}

async function bindDetailActions(risk) {
  const task = risk.task;
  document.querySelector("#confirmRisk")?.addEventListener("click", async () => {
    const assigneeId = document.querySelector("#assigneeId").value;
    await run(() => command(`/risks/${risk.id}/confirm`, { assigneeId, note: "已核验，启动整改。", version: risk.version }), "整改任务已创建。");
  });
  document.querySelector("#dismissRisk")?.addEventListener("click", async () => { const reason = document.querySelector("#dismissReason").value.trim(); if (!reason) return notify("请填写误报原因。"); await run(() => command(`/risks/${risk.id}/dismiss`, { reason, version: risk.version }), "误报已保留。"); });
  document.querySelector("#updateTask")?.addEventListener("click", async () => { const content = document.querySelector("#updateContent").value.trim(); if (!content) return notify("请填写整改进度。"); await run(() => request(`/tasks/${task.id}/updates`, { method: "POST", body: JSON.stringify({ content, version: task.version }) }), "整改进度已保存。"); });
  document.querySelector("#submitReview")?.addEventListener("click", async () => { const note = document.querySelector("#updateContent").value.trim() || "已补齐处置材料，请区域经理复核。"; await run(() => command(`/tasks/${task.id}/submit-review`, { note, version: task.version }), "已提交人工复核。"); });
  document.querySelector("#approveTask")?.addEventListener("click", async () => { const note = document.querySelector("#reviewNote").value.trim(); if (!note) return notify("请填写复核结论。"); await run(() => command(`/tasks/${task.id}/approve`, { note, version: task.version }), "风险已关闭。"); });
  document.querySelector("#returnTask")?.addEventListener("click", async () => { const note = document.querySelector("#reviewNote").value.trim(); if (!note) return notify("请填写退回原因。"); await run(() => command(`/tasks/${task.id}/return`, { note, version: task.version }), "任务已退回。"); });
}

async function run(action, message) { try { await action(); await loadData(); notify(message); await render(); } catch (error) { notify(error.message); } }

async function render() {
  try {
    if (state.page === "detail") return await detailView();
    app.innerHTML = state.page === "risks" ? risksView() : state.page === "tasks" ? tasksView() : state.page === "brief" ? briefView() : dashboardView();
    bindShell();
  } catch (error) { app.innerHTML = `<div class="login"><div class="login-card"><h1>页面暂不可用</h1><p>${error.message}</p><button class="primary" onclick="location.reload()">重新加载</button></div></div>`; }
}

function bindShell() {
  document.querySelectorAll("[data-page]").forEach(button => button.addEventListener("click", async () => { state.page = button.dataset.page; await render(); }));
  document.querySelectorAll("[data-risk]").forEach(button => button.addEventListener("click", async () => { state.selectedRiskId = button.dataset.risk; state.page = "detail"; await render(); }));
  document.querySelector("#logout")?.addEventListener("click", () => { session.token = null; resetState(); renderLogin(); });
  document.querySelector("#parseReport")?.addEventListener("click", async () => { const result = document.querySelector("#aiResult"); try { const data = await request("/daily-reports/parse", { method: "POST", body: JSON.stringify({ text: document.querySelector("#reportText").value }) }); result.innerHTML = `<div class="hint" style="margin-top:12px"><b>${data.status === "ok" ? "已提取待确认线索" : "证据不足，未补写事实"}</b><br>${data.facts?.[0]?.text || data.missingFields.join("、")}</div>`; } catch (error) { notify(error.message); } });
  document.querySelector("#generateBrief")?.addEventListener("click", async () => { try { const data = await request("/briefs/daily", { method: "POST" }); document.querySelector("#briefResult").innerHTML = `<h2>今日经营简报（待业务复核）</h2><p>${data.summary}</p>${data.facts.map(fact => `<div class="signal"><b>${fact.text}</b><small>${statusLabels[fact.status]}</small></div>`).join("")}`; } catch (error) { notify(error.message); } });
}

function renderLogin() {
  app.innerHTML = `<div class="login"><section class="login-card"><h1>特渠销售 AI 经营管理</h1><p>个人作品集演示：模拟数据、人工确认、完整留痕。</p><form id="loginForm"><label class="field">演示账号<select id="username"><option value="north_manager">李楠｜华北区域经理</option><option value="east_sales">周航｜一线销售</option><option value="director">陈总｜销售总监</option></select></label><label class="field">密码<input id="password" value="demo123" type="password"></label><button class="primary" type="submit">进入演示系统</button></form><p class="hint">所有账号密码均为 <b>demo123</b>。系统不连接任何企业真实数据。</p></section></div>`;
  document.querySelector("#loginForm").addEventListener("submit", async event => { event.preventDefault(); try { await login(document.querySelector("#username").value, document.querySelector("#password").value); await loadData(); await render(); } catch (error) { notify(error.message); } });
}

(async () => { if (!session.token) return renderLogin(); try { await loadData(); await render(); } catch { session.token = null; renderLogin(); } })();
