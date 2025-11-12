$(function () {
  const theme = localStorage.getItem("theme") || "light";
  document.documentElement.dataset.theme = theme;
  $("#themeToggle").text(theme === "dark" ? "☀️" : "🌙");
  $("#themeToggle").click(() => {
    const current = document.documentElement.dataset.theme;
    const next = current === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
    $("#themeToggle").text(next === "dark" ? "☀️" : "🌙");
  });

  $(".update-status").click(function () {
    const id = $(this).data("id");
    const status = $(`.status-select[data-id="${id}"]`).val();
    $.post("/update_status", { id, status }).done(() => location.reload());
  });

  $("#ticketForm").submit(function (e) {
    e.preventDefault();
    $.post("/new", $(this).serialize()).done(() => {
      $("#ticketModal").modal("hide");
      setTimeout(() => location.reload(), 500);
    });
  });

  $("#searchBox").on("input", function () {
    const query = $(this).val().toLowerCase();
    $("#ticketTable tbody tr").each(function () {
      $(this).toggle($(this).text().toLowerCase().indexOf(query) > -1);
    });
  });
});