(() => {
  const root = document.getElementById("todos-root");
  if (!root) return;

  async function post(url) {
    const res = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      throw new Error(data.error || "操作失败");
    }
    return data;
  }

  root.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("[data-todo-complete],[data-todo-reopen],[data-todo-delete]");
    if (!btn) return;
    const card = btn.closest("[data-matter-id]");
    if (!card) return;
    const id = card.getAttribute("data-matter-id");
    btn.disabled = true;
    try {
      if (btn.hasAttribute("data-todo-complete")) {
        await post(`/api/todos/${id}/complete`);
      } else if (btn.hasAttribute("data-todo-reopen")) {
        await post(`/api/todos/${id}/reopen`);
      } else if (btn.hasAttribute("data-todo-delete")) {
        if (!window.confirm("确定删除这条代办吗？")) {
          btn.disabled = false;
          return;
        }
        await post(`/api/todos/${id}/delete`);
      }
      window.location.reload();
    } catch (err) {
      window.alert((err && err.message) || "操作失败");
      btn.disabled = false;
    }
  });
})();
