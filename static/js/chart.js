document.addEventListener("DOMContentLoaded", function () {
  const ctx = document.getElementById("ticketChart");
  if (!ctx) return;

  const open = parseInt($(".text-primary").text()) || 0;
  const progress = parseInt($(".text-warning").text()) || 0;
  const closed = parseInt($(".text-success").text()) || 0;

  new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Open", "In Progress", "Closed"],
      datasets: [{
        data: [open, progress, closed],
        backgroundColor: ["#0d6efd", "#ffc107", "#198754"],
        borderWidth: 1,
      }],
    },
    options: {
      plugins: { legend: { position: "bottom" } },
      animation: { animateRotate: true, duration: 1000 },
    },
  });
});