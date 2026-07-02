(function () {
  "use strict";

  var indexData = [];
  var resultsEl = document.getElementById("results");
  var metaEl = document.getElementById("results-meta");
  var MAX_RESULTS = 200;

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function render(items, totalMatches) {
    if (!items.length) {
      resultsEl.innerHTML = "";
      metaEl.textContent = "No articles matched your search.";
      return;
    }

    metaEl.textContent = totalMatches > items.length
      ? "Showing first " + items.length + " of " + totalMatches + " matches — refine your search to narrow it down."
      : totalMatches + " article" + (totalMatches === 1 ? "" : "s") + " found.";

    resultsEl.innerHTML = items.map(function (item) {
      var lock = item.paywalled
        ? '<span class="paywall-badge">🔒 Subscription may be required</span> · '
        : "";
      var excerpt = item.summary
        ? '<p class="result-excerpt">' + escapeHtml(item.summary) + "</p>"
        : "";
      return (
        '<article class="result">' +
          '<a class="result-title" href="' + item.link + '" target="_blank" rel="noopener">' +
            escapeHtml(item.title) +
          "</a>" +
          '<div class="result-meta">' + lock + escapeHtml(item.source_name) + " · " + escapeHtml(item.display_date) + "</div>" +
          excerpt +
        "</article>"
      );
    }).join("");
  }

  function matches(item, q, opts) {
    var haystack = (item.title + " " + item.summary + " " + item.source_name).toLowerCase();

    if (opts.sources.length && opts.sources.indexOf(item.source) === -1) return false;
    if (opts.dateFrom && item.date < opts.dateFrom) return false;
    if (opts.dateTo && item.date > opts.dateTo) return false;

    if (opts.advanced) {
      var terms = q.split(",").map(function (t) { return t.trim().toLowerCase(); }).filter(Boolean);
      if (!terms.length) return true;
      return terms.every(function (t) { return haystack.indexOf(t) !== -1; });
    }

    var term = q.trim().toLowerCase();
    if (!term) return true;
    return haystack.indexOf(term) !== -1;
  }

  function runSearch() {
    var q = document.getElementById("q").value;
    var advancedOpen = document.getElementById("advanced-panel").classList.contains("open");
    var opts = {
      advanced: advancedOpen,
      sources: advancedOpen
        ? Array.prototype.slice.call(document.querySelectorAll(".src-check input:checked")).map(function (el) { return el.value; })
        : [],
      dateFrom: advancedOpen ? document.getElementById("date-from").value : "",
      dateTo: advancedOpen ? document.getElementById("date-to").value : "",
    };

    if (!q.trim() && !opts.sources.length && !opts.dateFrom && !opts.dateTo) {
      resultsEl.innerHTML = "";
      metaEl.textContent = "Enter a search term, or use Advanced options to filter by date or source.";
      return;
    }

    var filtered = indexData.filter(function (item) { return matches(item, q, opts); });
    render(filtered.slice(0, MAX_RESULTS), filtered.length);
  }

  document.getElementById("advanced-toggle").addEventListener("click", function () {
    var panel = document.getElementById("advanced-panel");
    panel.classList.toggle("open");
    this.textContent = panel.classList.contains("open") ? "Advanced options ▴" : "Advanced options ▾";
  });

  document.getElementById("search-form").addEventListener("submit", function (e) {
    e.preventDefault();
    runSearch();
  });

  ["date-from", "date-to"].forEach(function (id) {
    document.getElementById(id).addEventListener("change", runSearch);
  });
  document.querySelectorAll(".src-check input").forEach(function (el) {
    el.addEventListener("change", runSearch);
  });

  metaEl.textContent = "Loading article index…";
  fetch("search_index.json")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      indexData = data;
      metaEl.textContent = "Enter a search term, or use Advanced options to filter by date or source.";
    })
    .catch(function () {
      metaEl.textContent = "Couldn't load the article index. Try refreshing the page.";
    });
})();
