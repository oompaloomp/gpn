/**
 * GPN Frontend — фильтрация и отображение станций
 * Данные берутся из stations.json (локально или с GitHub Pages)
 */

// const DATA_URL = "./stations.json"; // на GitHub Pages будет рядом с index.html
const DATA_URL = "https://oompaloomp.github.io/gpn/docs/stations.json";
// Альтернатива: const DATA_URL = "https://ваш-api.railway.app/api/stations";

let allStations = [];
let lastUpdated = null;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

async function loadData() {
  const listEl = $("#stations-list");
  listEl.innerHTML = '<div class="loading">Загрузка данных…</div>';

  try {
    const res = await fetch(DATA_URL + "?t=" + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    allStations = data.stations || [];
    lastUpdated = data.updated_at || null;

    if (lastUpdated) {
      const d = new Date(lastUpdated);
      $("#updated-at").textContent =
        "Обновлено: " + d.toLocaleString("ru-RU", { timeZone: "Europe/Moscow" });
    }

    applyFilters();
  } catch (err) {
    listEl.innerHTML = `
      <div class="empty">
        Не удалось загрузить данные.<br>
        <small>${err.message}</small><br><br>
        Убедитесь, что файл stations.json существует рядом с сайтом.
      </div>`;
  }
}

function getSelectedFuels() {
  return Array.from($$("#fuel-filters input:checked")).map((el) => el.value);
}

function getAvailability() {
  const checked = $('input[name="avail"]:checked');
  return checked ? checked.value : "all";
}

function applyFilters() {
  const search = $("#search").value.trim().toLowerCase();
  const fuels = getSelectedFuels();
  const avail = getAvailability();

  let filtered = allStations.filter((st) => {
    // Поиск по названию
    if (search && !st.name.toLowerCase().includes(search)) return false;

    // Фильтр по топливу + наличию
    if (fuels.length === 0) return true;

    const hasMatchingFuel = fuels.some((fuelKey) => {
      const f = st.fuels?.[fuelKey];
      if (!f) return false;

      if (avail === "yes") return f.status === "в наличии";
      if (avail === "no") return f.status !== "в наличии";
      return true; // all
    });

    return hasMatchingFuel;
  });

  renderStations(filtered);
}

function statusIcon(status, hasTruck) {
  if (status === "в наличии") return "🟢";
  if (status === "ожидается доставка" || hasTruck) return "🚚";
  return "🔴";
}

function renderStations(stations) {
  const listEl = $("#stations-list");
  $("#count").textContent = `Найдено ${stations.length} станций`;

  if (stations.length === 0) {
    listEl.innerHTML = '<div class="empty">Ничего не найдено по текущим фильтрам</div>';
    return;
  }

  listEl.innerHTML = stations
    .map((st) => {
      const fuelsHtml = Object.entries(st.fuels || {})
        .map(([name, f]) => {
          const icon = statusIcon(f.status, f.has_truck);
          const price =
            f.status === "в наличии" && f.price != null
              ? `${f.price} ₽`
              : f.status === "ожидается доставка"
              ? "ожидается"
              : "нет";
          return `
            <div class="fuel-item">
              <span class="icon">${icon}</span>
              <span>${name}</span>
              <span class="price">${price}</span>
            </div>`;
        })
        .join("");

      return `
        <article class="station-card">
          <div class="station-name">${st.name}</div>
          <div class="station-meta">ID ${st.id} · ${st.time || ""}</div>
          <div class="fuels-grid">${fuelsHtml}</div>
        </article>`;
    })
    .join("");
}

// События
$("#search").addEventListener("input", applyFilters);
$$("#fuel-filters input").forEach((el) => el.addEventListener("change", applyFilters));
$$('input[name="avail"]').forEach((el) => el.addEventListener("change", applyFilters));

$("#refresh-btn").addEventListener("click", () => {
  // В статическом режиме просто перезагружаем JSON
  // Если будет живой API — можно делать POST /api/refresh
  loadData();
});

// Старт
loadData();
