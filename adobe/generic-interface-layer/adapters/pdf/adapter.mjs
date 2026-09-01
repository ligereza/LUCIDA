import { createAdapter } from "../adapter-contract.mjs"
export const pdfAdapter = createAdapter({ id: "pdf", host: "document", capabilities: ["extract-text", "extract-structure", "extract-bounds"] })
