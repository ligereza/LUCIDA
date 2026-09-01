import { createAdapter } from "../adapter-contract.mjs"
export const svgAdapter = createAdapter({ id: "svg", host: "svg", capabilities: ["create", "validate", "preview", "transform"] })
