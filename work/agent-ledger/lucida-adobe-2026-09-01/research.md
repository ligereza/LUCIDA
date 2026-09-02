question: Can the ADOBE branch resolve its host integration without a machine-specific checkout path, and can the Photoshop UXP panel stop its polling when hidden?
decision: Yes for the offline contract. Use the UXP plugin folder only to discover the checked-out location, climb to the package root, and keep filesystem access bounded by that root. Start and stop polling through panel lifecycle hooks. Live Photoshop acceptance remains unverified until the plugin is loaded by the user.
scope: Official Adobe UXP documentation only; no host process was launched or controlled.
queries:
  - query: site:developer.adobe.com photoshop UXP storage.localFileSystem getPluginFolder nativePath
    reason: Verify whether a UXP plugin can locate its own folder without a hardcoded checkout path.
    result: Official Adobe documentation exposes getPluginFolder and native-path access.
  - query: site:developer.adobe.com photoshop UXP entrypoints panel show hide
    reason: Verify a lifecycle boundary for stopping background polling.
    result: Official Adobe documentation defines panel show, hide and destroy hooks; Photoshop documentation also notes version-specific lifecycle limitations.
sources:
  - id: adobe-uxp-storage
    title: Photoshop UXP file system provider
    organization: Adobe
    url: https://developer.adobe.com/photoshop/uxp/2022/uxp-api/reference-js/modules/uxp/persistent-file-storage/file-system-provider
    claims: getPluginFolder is available; native path access is documented.
    limitation: The current checkout and host runtime were not exercised in Photoshop.
    quality: primary official documentation
  - id: adobe-uxp-entrypoints
    title: Photoshop UXP Manifest v5 and entry points
    organization: Adobe
    url: https://developer.adobe.com/photoshop/uxp/2022/guides/uxp-guide/uxp-misc/manifest-v5/
    claims: Panel lifecycle hooks support show, hide and destroy.
    limitation: Host-version behavior can differ; the known-issues page reports lifecycle caveats in older Photoshop builds.
    quality: primary official documentation
  - id: adobe-uxp-known-issues
    title: Known UXP issues in Photoshop
    organization: Adobe
    url: https://developer.adobe.com/photoshop/uxp/2021/uxp/known-issues/
    claims: Some Photoshop versions have imperfect panel show/hide notifications.
    limitation: This is version-specific and does not replace a live host test.
    quality: primary official documentation
claims:
  - id: C-001
    statement: The previous hardcoded C:/IA/LUCIDA/adobe path was invalid for this checkout and could make an adapter read the wrong jobs directory.
    status: supported
    evidence: Local path audit and current worktree location.
  - id: C-002
    statement: Dynamic root resolution from the script or UXP plugin folder removes that specific portability defect.
    status: supported-offline
    evidence: Adapter syntax suite plus source contract test; UXP API documented by Adobe.
  - id: C-003
    statement: Lifecycle-bound polling reduces avoidable background requests while the panel is not active when the plugin runs with Manifest v5; older Photoshop versions remain outside the supported range.
    status: supported-offline
    evidence: Manifest v5 contract, source test and official lifecycle documentation; live runtime still pending.
decision_boundary: A user-loaded Photoshop session must confirm that the UXP panel receives show/hide or destroy callbacks and publishes a real context envelope.
stopping_reason: The current offline decision is reversible and all known code-path defects are covered; another external search would not change the patch. Live UXP behavior is the only remaining material unknown.
