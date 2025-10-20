/**
 * wtrl_import_rounds.js
 * Importa i round WTRL pubblici e li mostra nella console
 * Compatibile con Flask / Django / Node backend
 */

console.log("🚀 WTRL Import Rounds script caricato");

function importWtrlRounds() {
  const apiUrl = "https://www.wtrl.racing/api/wtrlruby/?action=zrlSeasons"; // endpoint pubblico

  console.log("🔍 Recupero dati WTRL da:", apiUrl);

  fetch(apiUrl, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
  })
    .then(res => {
      if (!res.ok) throw new Error("❌ Errore HTTP " + res.status);
      return res.json();
    })
    .then(data => {
      if (!data || !data.payload) {
        console.warn("⚠️ Nessun payload ricevuto:", data);
        return;
      }

      console.log("✅ Dati ricevuti:", data.payload);

      data.payload.forEach(round => {
        console.log(`🏁 Round: ${round.name || "Senza nome"}`);
        console.log(`📅 Data inizio: ${round.startDate}`);
        console.log(`📅 Data fine: ${round.endDate}`);
        console.log(`🔗 Link: ${round.link || "N/A"}`);
        console.log("—".repeat(40));
      });
    })
    .catch(err => {
      console.error("❌ Errore nel recupero round WTRL:", err);
    });
}

// Esegui quando la pagina è pronta
document.addEventListener("DOMContentLoaded", importWtrlRounds);
