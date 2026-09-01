import { createAdapter } from "../adapter-contract.mjs"
export const adobeAdapter = createAdapter({ id: "adobe", host: "adobe", capabilities: ["context", "selection", "insert", "result"] })
export const adobeHosts = ["photoshop", "illustrator", "indesign", "after-effects", "premiere"]
