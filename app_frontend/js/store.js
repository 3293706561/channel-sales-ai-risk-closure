export const state = {
  user: null,
  page: "dashboard",
  selectedRiskId: null,
  dashboard: null,
  risks: [],
  tasks: [],
};

export function resetState() {
  state.user = null;
  state.page = "dashboard";
  state.selectedRiskId = null;
  state.dashboard = null;
  state.risks = [];
  state.tasks = [];
}
