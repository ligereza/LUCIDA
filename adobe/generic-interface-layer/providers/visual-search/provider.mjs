export function createVisualSearchProvider({ search = null, name = "optional-visual-provider" } = {}) {
  return {
    id: name,
    available: typeof search === "function",
    async search(input) {
      if (typeof search !== "function") return { available: false, results: [], reason: "visual-provider-not-configured" }
      return { available: true, results: await search(input) }
    },
  }
}
