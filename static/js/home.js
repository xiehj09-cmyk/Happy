(() => {
  const title = document.getElementById("greeting-title");
  if (!title) return;

  const hour = new Date().getHours();
  let prefix = "您好";
  if (hour >= 5 && hour < 11) prefix = "早上好";
  else if (hour >= 11 && hour < 13) prefix = "中午好";
  else if (hour >= 13 && hour < 18) prefix = "下午好";
  else if (hour >= 18 && hour < 23) prefix = "晚上好";
  else prefix = "夜深了";

  const name = title.textContent.replace(/^您好，\s*/, "");
  title.textContent = `${prefix}，${name}`;
})();
