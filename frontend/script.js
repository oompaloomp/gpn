/**
 * GPN Frontend — фильтрация и отображение станций
 * Время всегда в МСК, для топлива «в наличии» показывается длительность.
 */

const DATA_URL = "./stations.json";

let allStations = [];
let lastUpdated = null;

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

/** Форматирует ISO-дату в строку МСК */
function formatMoscow(iso, withSeconds = false) {
  if (!iso) return "—";
  const d = new Date(iso);
  const opts = {
    timeZone: "Europe/Moscow",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  };
  if (withSeconds) opts.second = "2-digit";
  return d.toLocaleString("ru-RU", opts) + " (МСК)";
}

/** Только время HH:MM (МСК) из ISO или из строки "HH:MM" */
function formatTimeMSK(timeOrIso) {
  if (!timeOrIso) return "—";
  // Уже простое время вида "06:00"
  if (/^\d{1,2}:\d{2}$/.test(timeOrIso)) {
    return timeOrIso + " (МСК)";
  }
  const d = new Date(timeOrIso);
  if (isNaN(d.getTime())) return timeOrIso + " (МСК)";
  return (
    d.toLocaleTimeString("ru-RU", {
      timeZone: "Europe/Moscow",
      hour: "2-digit",
      minute: "2-digit",
    }) + " (МСК)"
  );
}

/**
 * Сколько часов топливо уже в наличии.
 * available_since — ISO-строка, когда топливо впервые появилось
 * и с тех пор не пропадало.
 */
function hoursInStock(availableSince, nowIso) {
  if (!availableSince) return null;
  const start = new Date(availableSince).getTime();
  const end = nowIso ? new Date(nowIso).getTime() : Date.now();
  if (isNaN(start) || isNaN(end) || end < start) return null;
  const hours = Math.floor((end - start) / 3600000);
  return hours;
}

function formatDuration(hours) {
  if (hours === null || hours === undefined) return "";
  if (hours <= 0) return "только появилось";
  if (hours === 1) return "в наличии 1 час";
  if (hours >= 2 && hours <= 4) return `в наличии ${hours} часа`;
  return `в наличии ${hours} часов`;
}

function statusIcon(status, hasTruck) {
  if (status === "в наличии") return "🟢";
  if (status === "ожидается доставка" || hasTruck) return "🚚";
  return "🔴";
}

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
      $("#updated-at").textContent = "Обновлено: " + formatMoscow(lastUpdated, true);
    } else {
      $("#updated-at").textContent = "Обновлено: —";
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
    if (search && !st.name.toLowerCase().includes(search)) return false;
    if (fuels.length === 0) return true;

    return fuels.some((fuelKey) => {
      const f = st.fuels?.[fuelKey];
      if (!f) return false;
      if (avail === "yes") return f.status === "в наличии";
      if (avail === "no") return f.status !== "в наличии";
      return true;
    });
  });

  renderStations(filtered);
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
      // Собираем подписи длительности по топливу, которое сейчас в наличии
      const durationParts = [];
      const fuelsHtml = Object.entries(st.fuels || {})
        .map(([name, f]) => {
          const icon = statusIcon(f.status, f.has_truck);
          let priceText = "нет";
          if (f.status === "в наличии" && f.price != null) {
            priceText = `${f.price} ₽`;
            const hrs = hoursInStock(f.available_since, lastUpdated);
            const dur = formatDuration(hrs);
            if (dur) durationParts.push(`${name}: ${dur}`);
          } else if (f.status === "ожидается доставка") {
            priceText = "ожидается";
          }

          return `
            <div class="fuel-item">
              <span class="icon">${icon}</span>
              <span>${name}</span>
              <span class="price">${priceText}</span>
            </div>`;
        })
        .join("");

      const timeLabel = formatTimeMSK(st.time || lastUpdated);
      const durationLine =
        durationParts.length > 0
          ? `<div class="station-duration">${durationParts.join(" · ")}</div>`
          : "";

      return `
        <article class="station-card">
          <div class="station-name">${st.name}</div>
          <div class="station-meta">ID ${st.id} · ${timeLabel}</div>
          ${durationLine}
          <div class="fuels-grid">${fuelsHtml}</div>
        </article>`;
    })
    .join("");
}

// События
$("#search").addEventListener("input", applyFilters);
$$("#fuel-filters input").forEach((el) => el.addEventListener("change", applyFilters));
$$('input[name="avail"]').forEach((el) => el.addEventListener("change", applyFilters));
$("#refresh-btn").addEventListener("click", () => loadData());

loadData();
