const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("contextShelf", {
  request(route, options = {}) { return ipcRenderer.invoke("bridge:request", route, options) },
  preview(file) { return ipcRenderer.invoke("asset:preview", file) },
  drag(file) { return ipcRenderer.send("asset:drag", file) },
  windowControls: {
    minimize() { return ipcRenderer.invoke("window:minimize") },
    toggleMaximize() { return ipcRenderer.invoke("window:toggle-maximize") },
    close() { return ipcRenderer.invoke("window:close") },
  },
})
