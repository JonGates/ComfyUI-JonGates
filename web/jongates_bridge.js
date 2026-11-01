// SPDX-License-Identifier: MIT
// Adapted from ComfyUI-BlueBox; see THIRD_PARTY_NOTICES.md.
console.log("[JonGates] ============ jongates.js 已加载 ============");
import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

const EXT_BASE = "/extensions/ComfyUI-JonGates";

const JG_DB = {
  dbName: "JonGatesMaskEditorDB",
  storeName: "images",
  db: null,
  init() {
    return new Promise((resolve, reject) => {
      if (this.db) return resolve(this.db);
      const req = indexedDB.open(this.dbName, 1);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          db.createObjectStore(this.storeName, { keyPath: "id" });
        }
      };
      req.onsuccess = (e) => {
        this.db = e.target.result;
        resolve(this.db);
      };
      req.onerror = (e) => reject(e.target.error);
    });
  },
  put(id, data) {
    return this.init().then(
      (db) =>
        new Promise((res, rej) => {
          const tx = db.transaction(this.storeName, "readwrite");
          const r = tx
            .objectStore(this.storeName)
            .put({ id, data, timestamp: Date.now() });
          r.onsuccess = () => res();
          r.onerror = (e) => rej(e.target.error);
        }),
    );
  },
  get(id) {
    return this.init().then(
      (db) =>
        new Promise((res, rej) => {
          const tx = db.transaction(this.storeName, "readonly");
          const r = tx.objectStore(this.storeName).get(id);
          r.onsuccess = () => res(r.result?.data || null);
          r.onerror = (e) => rej(e.target.error);
        }),
    );
  },
  delete(id) {
    return this.init().then(
      (db) =>
        new Promise((res, rej) => {
          const tx = db.transaction(this.storeName, "readwrite");
          const r = tx.objectStore(this.storeName).delete(id);
          r.onsuccess = () => res();
          r.onerror = (e) => rej(e.target.error);
        }),
    );
  },
};

function extractUrlFromImgEntry(entry) {
  if (!entry) return null;
  if (typeof entry === "string") return entry;
  if (entry instanceof HTMLImageElement) return entry.src;
  if (entry.url) return entry.url;
  if (entry.src) return entry.src;
  if (entry.filename) {
    return (
      "/view?filename=" +
      encodeURIComponent(entry.filename) +
      "&subfolder=" +
      encodeURIComponent(entry.subfolder || "") +
      "&type=" +
      (entry.type || "output")
    );
  }
  return null;
}

async function uploadDataUrlToComfy(dataUrl, namePrefix) {
  try {
    const resp = await fetch(dataUrl);
    const blob = await resp.blob();
    const buf = await blob.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", buf);
    const bytes = new Uint8Array(digest);
    let hex = "";
    for (let i = 0; i < 8; i++) hex += bytes[i].toString(16).padStart(2, "0");
    const ext = blob.type.includes("jpeg")
      ? ".jpg"
      : blob.type.includes("webp")
        ? ".webp"
        : ".png";
    const filename = (namePrefix || "jg_") + hex + ext;

    const form = new FormData();
    form.append("image", blob, filename);
    form.append("overwrite", "true");

    const up = await fetch("/upload/image", { method: "POST", body: form });
    if (!up.ok) return null;
    const data = await up.json();
    return data.name || filename;
  } catch (e) {
    console.warn("[JonGates] 上传失败:", e);
    return null;
  }
}

async function triggerRerun() {
  try {
    if (!app || !app.graphToPrompt) {
      console.warn("[JonGates] app.graphToPrompt 不可用");
      return;
    }
    const p = await app.graphToPrompt();
    const clientId = api && api.clientId ? api.clientId : "jongates";
    const res = await fetch("/prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: p.output,
        client_id: clientId,
      }),
    });
    if (!res.ok) {
      console.warn("[JonGates] /prompt 返回错误:", res.status, await res.text());
    } else {
      console.log("[JonGates] /prompt 入队成功");
    }
  } catch (e) {
    console.warn("[JonGates] /prompt 调用失败:", e);
  }
}

window._jgEditTargetNode = null;
window._jgEditNodeId = null;
let _jgPollTimer = null;
let _jgPollAttempts = 0;
const JG_POLL_MAX = 1200;

function getBridgeCurrentImageMeta(node) {
  if (!node) return null;
  const meta = node.__jgCurrentImageMeta;
  if (!meta || !meta.filename) return null;
  return meta;
}

async function openJonGatesEditor(node) {
  node.__jgNodeId = String(node.id);
  const nodeId = node.__jgNodeId;
  console.log("[JonGates] 打开编辑器，锁定 nodeId =", nodeId);

  let url = null;

  if (node.comfyClass === "JonGatesAllPreview") {
    const imgData = node.properties?.imgData;
    if (imgData?.base64) {
      const mime = imgData.type || "image/webp";
      url = `data:${mime};base64,${imgData.base64}`;
    }
  }

    const imgWidget = node.widgets?.find((w) => w.name === "image");
  if (
    !url &&
    imgWidget &&
    typeof imgWidget.value === "string" &&
    imgWidget.value
  ) {
    url =
      "/view?filename=" +
      encodeURIComponent(imgWidget.value) +
      "&subfolder=&type=input";
  } else if (!url && node.imgs && node.imgs.length > 0) {
    url = extractUrlFromImgEntry(node.imgs[0]);
  }

  // 兜底：Bridge 在 block 状态下 imgs 可能为空，直接向后端要当前图
  if (!url && node.comfyClass === "JonGatesBridge") {
    try {
      const nodeId = node.__jgNodeId || String(node.id);
      const resp = await fetch(
        "/jongates/bridge_current_image?node_id=" +
          encodeURIComponent(nodeId),
      );
      if (resp.ok) {
        const data = await resp.json();
        if (data.ok && data.image && data.image.filename) {
          url =
            "/view?filename=" +
            encodeURIComponent(data.image.filename) +
            "&subfolder=" +
            encodeURIComponent(data.image.subfolder || "") +
            "&type=" +
            encodeURIComponent(data.image.type || "temp");
        }
      }
    } catch (e) {
      console.warn("[JonGates] Bridge 兜底取图失败:", e);
    }
  }

  if (!url) {
    alert("该节点还没有可编辑的图片");
    return;
  }

  let dataUrl;
  try {
    const resp = await fetch(url);
    const blob = await resp.blob();
    dataUrl = await new Promise((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res(fr.result);
      fr.onerror = rej;
      fr.readAsDataURL(blob);
    });
  } catch (e) {
    alert("读取图片失败: " + e.message);
    return;
  }

  const snapshotKey = "jg_snapshot_" + nodeId;
  const isBridge = node.comfyClass === "JonGatesBridge";
  let snapshot = null;

  try {
    snapshot = await JG_DB.get(snapshotKey);
  } catch (e) {
    snapshot = null;
  }

  if (snapshot) {
    if (isBridge) {
      const meta = getBridgeCurrentImageMeta(node);
      console.log("[JonGates] Bridge 当前图元信息:", meta);

      if (!meta) {
        console.log("[JonGates] Bridge 无当前图元信息，快照作废");
        snapshot = null;
        JG_DB.delete(snapshotKey).catch(() => {});
      } else if (meta.subfolder === "JonGatesBridge") {
        console.log("[JonGates] Bridge 当前为占位图，快照作废");
        snapshot = null;
        JG_DB.delete(snapshotKey).catch(() => {});
      } else {
        const snapshotSource = snapshot.bridgeSourceImage || null;
        if (!snapshotSource) {
          console.log("[JonGates] Bridge 快照无来源记录，作废");
          snapshot = null;
          JG_DB.delete(snapshotKey).catch(() => {});
        } else if (snapshotSource !== meta.filename) {
          console.log(
            "[JonGates] Bridge 烘焙图已更换，快照作废:",
            snapshotSource,
            "→",
            meta.filename,
          );
          snapshot = null;
          JG_DB.delete(snapshotKey).catch(() => {});
        } else {
          console.log("[JonGates] Bridge 快照有效，保留");
        }
      }
    } else if (node.comfyClass === "JonGatesAllPreview") {
      console.log("[JonGates] JonGatesAllPreview 快照作废（每次都用当前图）");
      snapshot = null;
      JG_DB.delete(snapshotKey).catch(() => {});
    } else {
      const snapshotSource = snapshot.sourceImage || null;
      const currentImage = imgWidget?.value || null;

      if (!snapshotSource) {
        console.log("[JonGates] LoadImage 快照无来源记录，作废");
        snapshot = null;
        JG_DB.delete(snapshotKey).catch(() => {});
      } else if (currentImage && snapshotSource !== currentImage) {
        console.log(
          "[JonGates] LoadImage 图已换，快照作废:",
          snapshotSource,
          "→",
          currentImage,
        );
        snapshot = null;
        JG_DB.delete(snapshotKey).catch(() => {});
      } else {
        console.log("[JonGates] LoadImage 快照有效，保留");
      }
    }
  }

  const imageId =
    "jg_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
  await JG_DB.put(imageId, dataUrl);

  window._jgEditTargetNode = node;
  window._jgEditNodeId = nodeId;

if (!node.__jgReferenceKey && node.comfyClass === "JonGatesBridge") {
    try {
      const nodeId = node.__jgNodeId || String(node.id);
      const resp = await fetch(
        "/jongates/bridge_reference_image?node_id=" + encodeURIComponent(nodeId),
      );
      if (resp.ok) {
        const data = await resp.json();
        if (data.ok && data.image?.filename) {
          const refUrl =
            "/view?filename=" +
            encodeURIComponent(data.image.filename) +
            "&subfolder=" +
            encodeURIComponent(data.image.subfolder || "") +
            "&type=" +
            encodeURIComponent(data.image.type || "temp");
          const r = await fetch(refUrl);
          const blob = await r.blob();
          const dataUrl = await new Promise((res) => {
            const fr = new FileReader();
            fr.onload = () => res(fr.result);
            fr.readAsDataURL(blob);
          });
          const key = "jg_reference_" + nodeId;
          await JG_DB.put(key, dataUrl);
          node.__jgReferenceKey = key;
        }
      }
    } catch (e) {
      console.warn("[JonGates] 兜底获取参考图失败:", e);
    }
  }

  // 参考图：仅当节点上缓存了 reference key 且数据存在时传入
  let referenceParam = "";
  const refKey = node.__jgReferenceKey || null;
  if (refKey) {
    const refData = await JG_DB.get(refKey).catch(() => null);
    if (refData) {
      referenceParam = `&referenceId=${encodeURIComponent(refKey)}`;
    } else {
      node.__jgReferenceKey = null;
    }
  }

  const baseParam = snapshot
    ? `snapshotId=${encodeURIComponent(snapshotKey)}&imageId=${encodeURIComponent(imageId)}&nodeId=${encodeURIComponent(nodeId)}`
    : `imageId=${encodeURIComponent(imageId)}&nodeId=${encodeURIComponent(nodeId)}`;

  const param = baseParam + referenceParam;

  const win = window.open(
    `${EXT_BASE}/mask-editor.html?${param}`,
    "jongates-mask-editor",
    "width=1536,height=1024,left=" +
      Math.round((screen.width - 1536) / 2) +
      ",top=" +
      Math.round((screen.height - 1024) / 2) +
      ",menubar=no,toolbar=no,location=no,status=no",
  );

  if (!win) {
    alert("弹窗被拦截，请允许本站弹出窗口");
    JG_DB.delete(imageId).catch(() => {});
    window._jgEditTargetNode = null;
    window._jgEditNodeId = null;
    return;
  }

  startMaskPolling();
}

function startMaskPolling() {
  if (_jgPollTimer) clearInterval(_jgPollTimer);
  _jgPollAttempts = 0;

  _jgPollTimer = setInterval(async () => {
    _jgPollAttempts++;
    if (_jgPollAttempts > JG_POLL_MAX) {
      clearInterval(_jgPollTimer);
      _jgPollTimer = null;
      return;
    }
    try {
      const raw = await JG_DB.get("mask_editor_result");
      if (!raw) return;
      clearInterval(_jgPollTimer);
      _jgPollTimer = null;
      JG_DB.delete("mask_editor_result").catch(() => {});
      let payload;
      try {
        payload = JSON.parse(raw);
      } catch (e) {
        return;
      }
      handleMaskResult(payload);
    } catch (e) {}
  }, 500);
}

let _jgLastSessionId = null;

async function handleMaskResult(payload) {
  if (!payload || !payload.image) return;
  if (payload.editorSessionId && payload.editorSessionId === _jgLastSessionId)
    return;
  if (payload.editorSessionId) _jgLastSessionId = payload.editorSessionId;

  const node = window._jgEditTargetNode;
  if (!node) return;

  if (node.comfyClass === "JonGatesAllPreview") {
    const mainDataUrl = payload.image;
    if (!mainDataUrl) {
      alert("回填失败：没有可用的图像");
      window._jgEditTargetNode = null;
      window._jgEditNodeId = null;
      return;
    }

    const match = mainDataUrl.match(/^data:(.+?);base64,(.+)$/);
    if (match) {
      node.properties.imgData = {
        name: "bg_image",
        base64: match[2],
        type: match[1],
      };
      if (node.previewer?.refreshBackgroundImage) {
        node.previewer.refreshBackgroundImage(node);
      } else if (node.previewWidget?.element) {
        node.previewWidget.element.style.backgroundImage = `url(${mainDataUrl})`;
      }
      node.setDirtyCanvas?.(true, true);
      console.log("[JonGates] JonGatesAllPreview 预览已回填");
    } else {
      console.warn("[JonGates] 回填 dataURL 解析失败");
    }

    window._jgEditTargetNode = null;
    window._jgEditNodeId = null;
    return;
  }

  const mainDataUrl = payload.image || payload.maskAlphaImage;
  if (!mainDataUrl) {
    alert("回填失败：没有可上传的图像");
    window._jgEditTargetNode = null;
    return;
  }

  let sharedHash = null;
  try {
    const resp = await fetch(mainDataUrl);
    const blob = await resp.blob();
    const buf = await blob.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", buf);
    const bytes = new Uint8Array(digest);
    sharedHash = "";
    for (let i = 0; i < 8; i++)
      sharedHash += bytes[i].toString(16).padStart(2, "0");
  } catch (e) {
    sharedHash = Date.now().toString(16);
  }

  if (node.comfyClass === "JonGatesBridge") {
    const mainUrl = payload.image;
    const maskUrl = payload.maskImage;
    const previewUrl = payload.previewImage;

    if (!mainUrl) {
      alert("桥接回填失败：缺少主图");
      window._jgEditTargetNode = null;
      return;
    }

    const mainName = await uploadDataUrlToComfy(
      mainUrl,
      `jg_bridge_${sharedHash}`,
    );
    if (!mainName) {
      alert("桥接回填失败：主图上传未成功");
      window._jgEditTargetNode = null;
      return;
    }

    let maskName = null;
    if (maskUrl) {
      maskName = await uploadDataUrlToComfy(
        maskUrl,
        `jg_bridge_${sharedHash}_mask`,
      );
    }

    let previewName = null;
    if (previewUrl) {
      previewName = await uploadDataUrlToComfy(
        previewUrl,
        `jg_bridge_${sharedHash}_preview`,
      );
    }

    const nodeId = node.__jgNodeId || String(node.id);
    console.log("[JonGates] Bridge 注册 nodeId =", nodeId, "node.id =", node.id);
    console.log(
      "[JonGates] Bridge 注册 node_id =",
      nodeId,
      "main =",
      mainName,
      "mask =",
      maskName,
      "preview =",
      previewName,
    );

    try {
      const registerResponse = await fetch("/jongates/bridge_register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: nodeId,
          image_filename: mainName,
          mask_filename: maskName,
          preview_filename: previewName,
        }),
      });
      const registration = await registerResponse.json();
      if (!registerResponse.ok || !registration.ok) throw new Error(registration.error || "Registration failed");
    } catch (e) {
      console.warn("[JonGates] Bridge 注册失败:", e);
      alert("保存编辑结果失败：" + e.message);
      return;
    }

    const displayName = previewName || mainName;
    const displayUrl =
      "/view?filename=" +
      encodeURIComponent(displayName) +
      "&subfolder=&type=input";

    const imgObj = new Image();
    imgObj.src = displayUrl;
    try {
      await imgObj.decode();
    } catch (e) {
      console.warn("[JonGates] Bridge decode 失败，回退 onload:", e);
      await new Promise((res) => {
        if (imgObj.complete) return res();
        imgObj.onload = () => res();
        imgObj.onerror = () => res();
      });
    }
    node.imgs = [imgObj];
    node.setDirtyCanvas?.(true, true);

    node.__jgCurrentImageMeta = {
      filename: displayName,
      subfolder: "",
      type: "input",
    };

    const snapshotKey = "jg_snapshot_" + nodeId;
    JG_DB.get(snapshotKey)
      .then((snap) => {
        if (snap) {
          snap.bridgeSourceImage = displayName;
          JG_DB.put(snapshotKey, snap).catch(() => {});
        }
      })
      .catch(() => {});

    console.log(
      "[JonGates] Bridge 编辑结果已就绪，请点击节点上的「继续」按钮放行",
    );

    window._jgEditTargetNode = null;
    window._jgEditNodeId = null;
    return;
  }

  const serverName = await uploadDataUrlToComfy(
    mainDataUrl,
    `jg_${sharedHash}`,
  );
  if (!serverName) {
    alert("回填失败：图片上传未成功");
    window._jgEditTargetNode = null;
    window._jgEditNodeId = null;
    return;
  }

  let maskServerName = null;
  if (payload.maskImage) {
    maskServerName = await uploadDataUrlToComfy(
      payload.maskImage,
      `jg_${sharedHash}_mask`,
    );
  }

  let previewUrl2 = null;
  if (payload.previewImage) {
    const previewServerName = await uploadDataUrlToComfy(
      payload.previewImage,
      `jg_${sharedHash}_preview`,
    );
    if (previewServerName) {
      previewUrl2 =
        "/view?filename=" +
        encodeURIComponent(previewServerName) +
        "&subfolder=&type=input";
    }
  }

  const imgWidget2 = node.widgets?.find((w) => w.name === "image");
  const maskWidget = node.widgets?.find((w) => w.name === "mask_file");

  node.__jgSuppressMaskClear = true;

  if (imgWidget2) {
    imgWidget2.value = serverName;
  }

  if (maskWidget) {
    maskWidget.value = maskServerName || "";
  }

  setTimeout(() => {
    node.__jgSuppressMaskClear = false;
  }, 800);

  const displayUrl =
    previewUrl2 ||
    "/view?filename=" +
      encodeURIComponent(serverName) +
      "&subfolder=&type=input";
  if (displayUrl) {
    const imgObj = new Image();
    imgObj.src = displayUrl;
    try {
      await imgObj.decode();
    } catch (e) {
      console.warn("[JonGates] decode 失败，回退 onload:", e);
      await new Promise((res) => {
        if (imgObj.complete) return res();
        imgObj.onload = () => res();
        imgObj.onerror = () => res();
      });
    }
    node.imgs = [imgObj];
    node.setDirtyCanvas?.(true, true);
  }

  const snapshotKey2 = "jg_snapshot_" + String(node.id);
  JG_DB.get(snapshotKey2)
    .then((snap) => {
      if (snap) {
        snap.sourceImage = serverName;
        JG_DB.put(snapshotKey2, snap).catch(() => {});
      }
    })
    .catch(() => {});

  window._jgEditTargetNode = null;
  window._jgEditNodeId = null;
}

window.addEventListener("message", (e) => {
  if (e.origin !== window.location.origin || !e.data || typeof e.data !== "object") return;
  if (e.data.type === "jongates_mask_saved") {
    handleMaskResult(e.data.payload);
  }
});

app.registerExtension({
  name: "jongates.maskeditor.entry",

  async setup() {
    window.__jg_app = app;
  },

  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name !== "JonGatesBridge") return;

    const origGetExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
    nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
      try {
        const r = origGetExtraMenuOptions?.apply(this, arguments);
        options.push({
          content: "🟦 在 JONGATES 编辑器中打开",
          callback: () => openJonGatesEditor(this),
        });
        return r;
      } catch (e) {
        console.warn("[JonGates] getExtraMenuOptions 异常:", e);
        return origGetExtraMenuOptions?.apply(this, arguments);
      }
    };

    if (nodeData.name === "JonGatesLoadImage") {
      const origOnNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        const r = origOnNodeCreated?.apply(this, arguments);
        const node = this;
        const imgWidget = node.widgets?.find((w) => w.name === "image");
        const maskWidget = node.widgets?.find((w) => w.name === "mask_file");

        node.__jgSuppressMaskClear = false;

        if (imgWidget && maskWidget) {
          const origCallback = imgWidget.callback;
          imgWidget.callback = function (value, ...rest) {
            if (!node.__jgSuppressMaskClear) {
              if (maskWidget.value) {
                maskWidget.value = "";
              }
              const key = "jg_snapshot_" + String(node.id);
              JG_DB.delete(key).catch(() => {});
            }
            return origCallback?.apply(this, [value, ...rest]);
          };
        }
        return r;
      };
    }

    if (nodeData.name === "JonGatesBridge") {
      const origOnNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        const r = origOnNodeCreated?.apply(this, arguments);
        const node = this;

        node.__jgNodeId = String(node.id);

        node.addWidget("button", "继续", null, async () => {
          const nodeId = node.__jgNodeId || String(node.id);
          try {
            const response = await fetch("/jongates/bridge_continue", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ node_id: nodeId }),
            });
            const status = await response.json();
            if (!response.ok || !status.ok) throw new Error(status.error || "Continue failed");
            console.log("[JonGates] 已发送继续信号:", nodeId);
            await triggerRerun();
          } catch (e) {
            console.warn("[JonGates] 继续信号发送失败:", e);
          }
        });

        return r;
      };

      const origOnExecuted = nodeType.prototype.onExecuted;
      nodeType.prototype.onExecuted = function (message) {
        const r = origOnExecuted?.apply(this, arguments);
        try {
          console.log(
            "[JonGates] Bridge onExecuted:",
            JSON.stringify(message),
          );
          const imgs = message?.images;
          if (Array.isArray(imgs) && imgs.length > 0) {
            const first = imgs[0];
            if (first && first.filename) {
              this.__jgCurrentImageMeta = {
                filename: first.filename,
                subfolder: first.subfolder || "",
                type: first.type || "output",
              };
              console.log(
                "[JonGates] Bridge 缓存当前图元信息:",
                this.__jgCurrentImageMeta,
              );
            }
          }

          this.__jgReferenceKey = null;
          JG_DB.delete("jg_reference_" + String(this.id)).catch(() => {});
          // Cache the current reference only when one is connected.
          if (message?.reference_present?.[0]) {
            const node = this;
            const refInput = node.inputs?.find((i) => i.name === "reference");
            let refUrl = null;

            if (refInput && refInput.link != null) {
              const graph = app.graph;
              const link = graph?.links?.[refInput.link];
              if (link) {
                const originNode = graph.getNodeById(link.origin_id);
                if (originNode) {
                  if (originNode.imgs && originNode.imgs.length > 0) {
                    refUrl = extractUrlFromImgEntry(originNode.imgs[0]);
                  }
                  if (!refUrl && originNode.properties?.imgData?.base64) {
                    const mime = originNode.properties.imgData.type || "image/webp";
                    refUrl = `data:${mime};base64,${originNode.properties.imgData.base64}`;
                  }
                  if (!refUrl) {
                    const w = originNode.widgets?.find((x) => x.name === "image");
                    if (w && typeof w.value === "string" && w.value) {
                      refUrl =
                        "/view?filename=" +
                        encodeURIComponent(w.value) +
                        "&subfolder=&type=input";
                    }
                  }
                }
              }
            }

            if (refUrl) {
              const key = "jg_reference_" + String(node.id);
              fetch(refUrl)
                .then((resp) => resp.blob())
                .then((blob) => {
                  const fr = new FileReader();
                  fr.onload = () => {
                    JG_DB.put(key, fr.result)
                      .then(() => {
                        node.__jgReferenceKey = key;
                        console.log("[JonGates] 参考图已缓存:", key);
                      })
                      .catch(() => {});
                  };
                  fr.readAsDataURL(blob);
                })
                .catch((e) => console.warn("[JonGates] 参考图读取失败:", e));
            } else {
              console.log("[JonGates] reference 已连线但未取到图像");
            }
          }
        } catch (e) {
          console.warn("[JonGates] onExecuted 解析失败:", e);
        }
        return r;
      };
    }

    const origOnRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      try {
        const key = "jg_snapshot_" + String(this.id);
        JG_DB.delete(key).catch(() => {});
        if (this.__jgReferenceKey) {
          JG_DB.delete(this.__jgReferenceKey).catch(() => {});
        }
      } catch (e) {}
      return origOnRemoved?.apply(this, arguments);
    };
  },
});

