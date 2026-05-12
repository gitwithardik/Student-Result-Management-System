document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.getElementById("themeToggle");
  const savedTheme = localStorage.getItem("srms-theme");
  if (savedTheme === "dark") {
    document.body.classList.add("dark");
  }
  if (themeToggle) {
    themeToggle.textContent = document.body.classList.contains("dark")
      ? "Light Mode"
      : "Dark Mode";
    themeToggle.addEventListener("click", () => {
      document.body.classList.toggle("dark");
      const dark = document.body.classList.contains("dark");
      localStorage.setItem("srms-theme", dark ? "dark" : "light");
      themeToggle.textContent = dark ? "Light Mode" : "Dark Mode";
    });
  }

  document.querySelectorAll(".card").forEach((card, idx) => {
    card.classList.add("reveal");
    card.style.animationDelay = `${Math.min(idx * 0.04, 0.2)}s`;
  });

  const searchInputs = document.querySelectorAll(".table-search");
  searchInputs.forEach((input) => {
    const targetId = input.getAttribute("data-table-target");
    const table = document.getElementById(targetId);
    if (!table) return;
    const tbody = table.querySelector("tbody");
    if (!tbody) return;

    input.addEventListener("input", () => {
      const query = input.value.trim().toLowerCase();
      const rows = Array.from(tbody.querySelectorAll("tr"));
      let visibleCount = 0;
      rows.forEach((row) => {
        const text = row.innerText.toLowerCase();
        const match = text.includes(query);
        row.style.display = match ? "" : "none";
        if (match) visibleCount += 1;
      });

      let empty = tbody.querySelector(".dynamic-empty-row");
      if (visibleCount === 0) {
        if (!empty) {
          empty = document.createElement("tr");
          empty.className = "dynamic-empty-row";
          const td = document.createElement("td");
          td.colSpan = table.querySelectorAll("thead th").length || 1;
          td.textContent = "No matching records found.";
          empty.appendChild(td);
          tbody.appendChild(empty);
        }
      } else if (empty) {
        empty.remove();
      }
    });
  });
});
