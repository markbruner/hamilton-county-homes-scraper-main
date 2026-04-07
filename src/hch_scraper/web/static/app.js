const state = {
  map: null,
  markers: [],
  selectedParcel: null,
  searchTimer: null,
  searchAbortController: null,
};

const searchInput = document.getElementById("property-search");
const searchButton = document.getElementById("search-button");
const searchResults = document.getElementById("search-results");
const subjectCard = document.getElementById("subject-card");
const similarList = document.getElementById("similar-list");
const resultsSummary = document.getElementById("results-summary");

function initMap() {
  state.map = L.map("map", { scrollWheelZoom: true }).setView([39.1031, -84.5120], 11);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(state.map);
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function searchProperties(query) {
  const trimmed = query.trim();
  if (!trimmed) {
    cancelInFlightSearch();
    hideSearchResults();
    return;
  }

  const isParcelLike = /^[A-Za-z0-9-]+$/.test(trimmed);
  if (!isParcelLike && trimmed.length < 3) {
    cancelInFlightSearch();
    searchResults.hidden = false;
    searchResults.innerHTML = `<div class="search-empty">Type at least 3 characters to search by address.</div>`;
    return;
  }

  cancelInFlightSearch();
  state.searchAbortController = new AbortController();

  const data = await fetchJson(
    `/api/properties/search?q=${encodeURIComponent(trimmed)}&limit=8`,
    { signal: state.searchAbortController.signal }
  );
  renderSearchResults(data);
}

async function loadSimilar(parcelNumber) {
  state.selectedParcel = parcelNumber;
  hideSearchResults();
  searchInput.value = parcelNumber;
  resultsSummary.textContent = "Loading comparable homes...";

  const data = await fetchJson(
    `/api/properties/${encodeURIComponent(parcelNumber)}/similar?top_n=8&min_score=35`
  );

  renderSubject(data.subject);
  renderSimilarHomes(data.similar);
  renderMap(data.subject, data.similar);
}

function renderSearchResults(results) {
  if (!results.length) {
    searchResults.hidden = false;
    searchResults.innerHTML = `<div class="search-empty">No matching properties found.</div>`;
    return;
  }

  searchResults.hidden = false;
  searchResults.innerHTML = results
    .map(
      (item) => `
        <button class="search-hit" data-parcel="${escapeHtml(item.parcel_number || "")}">
          <span class="search-hit-address">${escapeHtml(item.address || "Unknown address")}</span>
          <span class="search-hit-meta">${escapeHtml(item.parcel_number || "")}</span>
        </button>
      `
    )
    .join("");

  for (const button of searchResults.querySelectorAll(".search-hit")) {
    button.addEventListener("click", () => loadSimilar(button.dataset.parcel));
  }
}

function renderSubject(subject) {
  subjectCard.hidden = false;
  subjectCard.innerHTML = `
    <div class="subject-kicker">Selected Home</div>
    <h2>${escapeHtml(subject.address || "Unknown address")}</h2>
    <p class="subject-meta">${escapeHtml(subject.parcel_number || "")}</p>
    <div class="metric-row">
      ${metric("Price", subject.amount)}
      ${metric("Sq Ft", formatNumber(subject.finsqft))}
      ${metric("Beds", formatNumber(subject.bedrooms))}
      ${metric("Baths", formatNumber(subject.bathrooms_total))}
      ${metric("Year", formatNumber(subject.year_built))}
      ${metric("District", subject.school_district)}
    </div>
  `;
}

function renderSimilarHomes(similar) {
  resultsSummary.textContent = `${similar.length} comparable homes loaded.`;

  if (!similar.length) {
    similarList.innerHTML = `<div class="empty-state">No similar homes matched the current filters.</div>`;
    return;
  }

  similarList.innerHTML = similar
    .map(
      (item, index) => `
        <article class="comp-card">
          <div class="comp-rank">#${index + 1}</div>
          <div class="comp-main">
            <div class="comp-header">
              <h3>${escapeHtml(item.address || "Unknown address")}</h3>
              <span class="score-pill">${formatScore(item.similarity_score)}</span>
            </div>
            <p class="comp-meta">${escapeHtml(item.parcel_number || "")}</p>
            <div class="metric-row">
              ${metric("Distance", formatDistance(item.distance_miles))}
              ${metric("Price", item.amount)}
              ${metric("Sq Ft", formatNumber(item.finsqft))}
              ${metric("Beds", formatNumber(item.bedrooms))}
              ${metric("Baths", formatNumber(item.bathrooms_total))}
              ${metric("Year", formatNumber(item.year_built))}
            </div>
          </div>
        </article>
      `
    )
    .join("");
}

function renderMap(subject, similar) {
  clearMarkers();

  const points = [];
  if (hasCoords(subject)) {
    const marker = L.circleMarker([subject.latitude, subject.longitude], {
      radius: 10,
      color: "#17324d",
      fillColor: "#2a6f97",
      fillOpacity: 0.95,
      weight: 2,
    }).addTo(state.map);
    marker.bindPopup(`
      <strong>Selected Home</strong><br>
      ${escapeHtml(subject.address || "Unknown address")}<br>
      Parcel: ${escapeHtml(subject.parcel_number || "")}
    `);
    state.markers.push(marker);
    points.push([subject.latitude, subject.longitude]);
  }

  for (const item of similar) {
    if (!hasCoords(item)) {
      continue;
    }
    const marker = L.circleMarker([item.latitude, item.longitude], {
      radius: 8,
      color: "#7f1d1d",
      fillColor: "#d94841",
      fillOpacity: 0.9,
      weight: 2,
    }).addTo(state.map);
    marker.bindPopup(`
      <strong>${escapeHtml(item.address || "Comparable Home")}</strong><br>
      Score: ${formatScore(item.similarity_score)}<br>
      Distance: ${formatDistance(item.distance_miles)}
    `);
    state.markers.push(marker);
    points.push([item.latitude, item.longitude]);
  }

  if (!points.length) {
    state.map.setView([39.1031, -84.5120], 11);
    return;
  }

  if (points.length === 1) {
    state.map.setView(points[0], 14);
    return;
  }

  state.map.fitBounds(points, { padding: [28, 28] });
}

function clearMarkers() {
  for (const marker of state.markers) {
    marker.remove();
  }
  state.markers = [];
}

function cancelInFlightSearch() {
  if (state.searchAbortController) {
    state.searchAbortController.abort();
    state.searchAbortController = null;
  }
}

function metric(label, value) {
  return `
    <div class="metric">
      <span class="metric-label">${escapeHtml(label)}</span>
      <strong>${escapeHtml(value ?? "-")}</strong>
    </div>
  `;
}

function formatScore(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${Number(value).toFixed(1)} / 100`;
}

function formatDistance(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  const miles = Number(value);
  if (miles === 0) {
    return "Same spot";
  }
  if (miles < 0.1) {
    return `${Math.max(1, Math.round(miles * 5280))} ft`;
  }
  return `${miles.toFixed(2)} mi`;
}

function formatNumber(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toLocaleString();
}

function hasCoords(item) {
  return item && item.latitude != null && item.longitude != null;
}

function hideSearchResults() {
  searchResults.hidden = true;
  searchResults.innerHTML = "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

searchInput.addEventListener("input", () => {
  clearTimeout(state.searchTimer);
  state.searchTimer = setTimeout(() => {
    searchProperties(searchInput.value).catch((error) => {
      if (error.name === "AbortError") {
        return;
      }
      resultsSummary.textContent = error.message;
      hideSearchResults();
    });
  }, 350);
});

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchProperties(searchInput.value)
      .then(async () => {
        const first = searchResults.querySelector(".search-hit");
        if (first) {
          await loadSimilar(first.dataset.parcel);
        }
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          return;
        }
        resultsSummary.textContent = error.message;
      });
  }
});

searchButton.addEventListener("click", () => {
  searchProperties(searchInput.value)
    .then(async () => {
      const first = searchResults.querySelector(".search-hit");
      if (first) {
        await loadSimilar(first.dataset.parcel);
      }
    })
    .catch((error) => {
      if (error.name === "AbortError") {
        return;
      }
      resultsSummary.textContent = error.message;
    });
});

document.addEventListener("click", (event) => {
  if (!searchResults.contains(event.target) && event.target !== searchInput) {
    hideSearchResults();
  }
});

initMap();
