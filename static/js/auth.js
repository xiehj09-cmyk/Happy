(() => {
  const toastStack = document.getElementById("toast-stack");
  if (toastStack) {
    window.setTimeout(() => {
      toastStack.style.opacity = "0";
      toastStack.style.transition = "opacity 0.35s ease";
      window.setTimeout(() => toastStack.remove(), 400);
    }, 4200);
  }

  document.querySelectorAll(".toggle-password").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = btn.parentElement?.querySelector("input");
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "隐藏" : "显示";
      btn.setAttribute("aria-label", show ? "隐藏密码" : "显示密码");
    });
  });

  function syncElderBind(form) {
    const panel = form.querySelector("[data-elder-bind]");
    if (!panel) return;
    const role = form.querySelector('input[name="role"]:checked')?.value || "family";
    const isFamily = role === "family";
    panel.hidden = !isFamily;
    form.querySelectorAll("[data-elder-required]").forEach((input) => {
      input.required = isFamily;
      if (!isFamily) {
        input.removeAttribute("aria-invalid");
      }
    });
    const title = form.querySelector("[data-self-title]");
    if (title) {
      title.textContent = isFamily ? "家属账号信息" : "老人账号信息";
    }
  }

  document.querySelectorAll("[data-register-form]").forEach((form) => {
    syncElderBind(form);
    form.querySelectorAll("[data-role-input]").forEach((input) => {
      input.addEventListener("change", () => syncElderBind(form));
    });
  });

  document.querySelectorAll("[data-auth-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      clearFieldErrors(form);

      const username = form.querySelector('[name="username"]');
      const email = form.querySelector('[name="email"]');
      const password = form.querySelector('[name="password"]');
      const confirm = form.querySelector('[name="confirm_password"]');
      const role = form.querySelector('input[name="role"]:checked')?.value;
      let valid = true;

      if (!role) {
        flashFormError(form, "请选择账号类型。");
        valid = false;
      }

      if (username && !username.value.trim()) {
        showFieldError(username, "请输入用户名。");
        valid = false;
      }

      if (email) {
        const value = email.value.trim();
        if (!value) {
          showFieldError(email, "请输入邮箱。");
          valid = false;
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
          showFieldError(email, "邮箱格式不正确。");
          valid = false;
        }
      }

      if (password && form.dataset.requireConfirm !== undefined) {
        if (!password.value || password.value.length < 6) {
          showFieldError(password, "密码至少 6 位。");
          valid = false;
        }
        if (confirm && password.value !== confirm.value) {
          showFieldError(confirm, "两次输入的密码不一致。");
          valid = false;
        }
      } else if (password && !password.value) {
        showFieldError(password, "请输入密码。");
        valid = false;
      }

      if (form.dataset.registerForm !== undefined && role === "family") {
        const elderUsername = form.querySelector('[name="elder_username"]');
        const elderPassword = form.querySelector('[name="elder_password"]');
        const elderConfirm = form.querySelector('[name="elder_confirm_password"]');
        if (elderUsername && !elderUsername.value.trim()) {
          showFieldError(elderUsername, "请填写老人用户名。");
          valid = false;
        }
        if (
          elderUsername &&
          username &&
          elderUsername.value.trim().toLowerCase() === username.value.trim().toLowerCase()
        ) {
          showFieldError(elderUsername, "老人用户名不能与家属用户名相同。");
          valid = false;
        }
        if (elderPassword && (!elderPassword.value || elderPassword.value.length < 6)) {
          showFieldError(elderPassword, "老人密码至少 6 位。");
          valid = false;
        }
        if (elderConfirm && elderPassword && elderPassword.value !== elderConfirm.value) {
          showFieldError(elderConfirm, "两次老人密码不一致。");
          valid = false;
        }
      }

      if (!valid) {
        event.preventDefault();
      }
    });
  });

  function flashFormError(form, message) {
    const tip = document.createElement("p");
    tip.className = "field-error";
    tip.textContent = message;
    const switcher = form.querySelector(".role-switch");
    if (switcher) {
      switcher.appendChild(tip);
    } else {
      form.prepend(tip);
    }
  }

  function showFieldError(input, message) {
    const field = input.closest(".field");
    if (!field) return;
    const tip = document.createElement("p");
    tip.className = "field-error";
    tip.textContent = message;
    field.appendChild(tip);
    input.setAttribute("aria-invalid", "true");
  }

  function clearFieldErrors(form) {
    form.querySelectorAll(".field-error").forEach((node) => node.remove());
    form.querySelectorAll("[aria-invalid]").forEach((node) => {
      node.removeAttribute("aria-invalid");
    });
  }
})();
