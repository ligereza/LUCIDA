export function createAdapter({ id, host, capabilities = [], optional = true } = {}) {
  if (!id || !host) throw new Error("Adapter id and host are required")
  return {
    id: String(id), host: String(host), capabilities: [...new Set(capabilities.map(String))].sort(), optional,
    accepts: ["context.update"], emits: ["action.request", "action.result"],
    async receive(message) { return { accepted: true, adapter: id, type: message?.type || null, payload: message?.payload || message?.context || null } },
  }
}
