export function createSemanticSearchProvider({ embedText = null, embedImage = null, search = null, name = "optional-semantic-provider" } = {}) {
  return {
    id: name,
    available: typeof search === "function" || typeof embedText === "function" || typeof embedImage === "function",
    capabilities: { text: typeof embedText === "function", image: typeof embedImage === "function", search: typeof search === "function" },
    async search(input) {
      if (typeof search !== "function") return { available: false, results: [], reason: "semantic-provider-not-configured" }
      return { available: true, results: await search(input) }
    },
    async embedText(input) {
      if (typeof embedText !== "function") return null
      return embedText(input)
    },
    async embedImage(input) {
      if (typeof embedImage !== "function") return null
      return embedImage(input)
    },
  }
}
