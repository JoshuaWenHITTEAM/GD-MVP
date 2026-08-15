const els = {
  backendUrl: document.getElementById("backendUrl"),
  eventType: document.getElementById("eventType"),
  startBtn: document.getElementById("startBtn"),
  stopBtn: document.getElementById("stopBtn"),
  taskId: document.getElementById("taskId"),
  phase: document.getElementById("phase"),
  message: document.getElementById("message"),
  detectImage: document.getElementById("detectImage"),
  detectResult: document.getElementById("detectResult"),
  detectReason: document.getElementById("detectReason"),
  trackImage: document.getElementById("trackImage"),
  trackResult: document.getElementById("trackResult"),
  trackReason: document.getElementById("trackReason"),
  log: document.getElementById("log"),
};

let currentController = null;

function setStatus({ phase, message, taskId }) {
  if (phase) {
    els.phase.textContent = phase;
  }
  if (message) {
    els.message.textContent = message;
  }
  if (taskId !== undefined) {
    els.taskId.textContent = taskId || "-";
  }
}

function appendLog(text) {
  const node = document.createElement("div");
  node.className = "log-entry";
  node.textContent = text;
  els.log.prepend(node);
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function updatePanel(event) {
  const { stage, image_base64: imageBase64, image_media_type: mediaType, result, reason } = event;
  const imageUrl = imageBase64 ? `data:${mediaType || "image/jpeg"};base64,${imageBase64}` : "";

  if (stage === "detect") {
    els.detectImage.src = imageUrl;
    els.detectResult.textContent = pretty(result);
    els.detectReason.textContent = reason || "-";
    return;
  }

  if (stage === "track") {
    els.trackImage.src = imageUrl;
    els.trackResult.textContent = pretty(result);
    els.trackReason.textContent = reason || "-";
  }
}

function resetView() {
  els.detectImage.removeAttribute("src");
  els.trackImage.removeAttribute("src");
  els.detectResult.textContent = "暂无检测结果";
  els.trackResult.textContent = "暂无跟踪结果";
  els.detectReason.textContent = "-";
  els.trackReason.textContent = "-";
  els.log.innerHTML = "";
  setStatus({ phase: "idle", message: "等待启动。", taskId: "-" });
}

function setRunning(running) {
  els.startBtn.disabled = running;
  els.stopBtn.disabled = !running;
}

async function startStream() {
  if (currentController) {
    currentController.abort();
  }

  resetView();
  setRunning(true);
  currentController = new AbortController();

  const baseUrl = els.backendUrl.value.trim().replace(/\/$/, "");
  const eventType = els.eventType.value;

  try {
    const response = await fetch(`${baseUrl}/api/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_type: eventType }),
      signal: currentController.signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";

      for (const chunk of chunks) {
        const line = chunk
          .split("\n")
          .find((item) => item.startsWith("data: "));

        if (!line) {
          continue;
        }

        const payload = JSON.parse(line.slice(6));
        if (payload.stage === "start") {
          setStatus({
            phase: "running",
            message: `任务已启动，事件类型: ${payload.event_type}`,
            taskId: payload.task_id,
          });
          appendLog(`[start] ${payload.task_id} ${payload.event_type}`);
          continue;
        }

        if (payload.stage === "done") {
          setStatus({
            phase: "done",
            message: "任务已完成。",
            taskId: payload.task_id || els.taskId.textContent,
          });
          appendLog("[done] stream finished");
          continue;
        }

        if (payload.stage === "error") {
          setStatus({
            phase: "error",
            message: payload.error,
            taskId: payload.task_id || els.taskId.textContent,
          });
          appendLog(`[error] ${payload.error}`);
          continue;
        }

        setStatus({
          phase: payload.stage,
          message: `${payload.sequence} / ${payload.frame_name}`,
          taskId: payload.task_id,
        });
        updatePanel(payload);
        appendLog(
          `[${payload.stage}] ${payload.sequence} frame=${payload.frame_index} reason=${payload.reason || "-"}`
        );
      }
    }
  } catch (error) {
    if (error.name === "AbortError") {
      setStatus({ phase: "stopped", message: "任务已手动停止。" });
      appendLog("[stop] stream aborted");
    } else {
      setStatus({ phase: "error", message: String(error) });
      appendLog(`[error] ${String(error)}`);
    }
  } finally {
    currentController = null;
    setRunning(false);
  }
}

function stopStream() {
  if (currentController) {
    currentController.abort();
  }
}

els.startBtn.addEventListener("click", startStream);
els.stopBtn.addEventListener("click", stopStream);

resetView();
