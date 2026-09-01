import { createAdapter } from "../adapter-contract.mjs"
export const gdkbAdapter = createAdapter({ id: "gdkb", host: "knowledge-provider", capabilities: ["identity", "provenance", "evidence"] })
