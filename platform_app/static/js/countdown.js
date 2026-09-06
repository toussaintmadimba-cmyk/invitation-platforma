(() => {
  function formatCountdown(value, now = Date.now()) {
    const deadline = new Date(value).getTime();
    if (!Number.isFinite(deadline)) return "Date indisponible";
    const seconds = Math.ceil((deadline - now) / 1000);
    if (seconds <= 0) return "L’heure de votre événement est arrivée";
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days} j · ${String(hours).padStart(2, "0")} h · ${String(minutes).padStart(2, "0")} min · ${String(seconds % 60).padStart(2, "0")} s`;
  }
  if (typeof module !== "undefined") module.exports = { formatCountdown };
  if (typeof document === "undefined") return;
  const elements = document.querySelectorAll("[data-event-countdown]");
  if (!elements.length) return;
  const update = () => elements.forEach(element => {
    element.textContent = formatCountdown(element.dataset.eventCountdown);
  });
  update();
  setInterval(update, 1000);
})();
