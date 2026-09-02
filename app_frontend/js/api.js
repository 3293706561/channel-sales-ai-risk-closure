const base = "/api";

export const session = {
  get token() { return localStorage.getItem("demo_token"); },
  set token(value) { value ? localStorage.setItem("demo_token", value) : localStorage.removeItem("demo_token"); },
};

export async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (session.token) headers.Authorization = `Bearer ${session.token}`;
  const response = await fetch(`${base}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "请求未完成，请稍后重试。");
  return data;
}

export async function login(username, password) {
  const data = await request("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
  session.token = data.accessToken;
  return data;
}

export function command(path, body) {
  return request(path, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(body) });
}
