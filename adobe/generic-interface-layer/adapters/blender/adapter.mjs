import { createAdapter } from "../adapter-contract.mjs"
export const blenderAdapter = createAdapter({ id: "blender", host: "blender", capabilities: ["context", "scene", "placement", "result"] })
