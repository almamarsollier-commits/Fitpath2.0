(function (root) {
  "use strict";

  const assistant = root.FitPathAssistant = root.FitPathAssistant || {};
  const corrections = Object.freeze({
    alimentasion: "alimentacion", alimnetacion: "alimentacion", caloria: "calorias",
    cardioo: "cardio", canselar: "cancelar", descanzo: "descanso",
    ejersicio: "ejercicio", ejersisios: "ejercicios", ejercisio: "ejercicio",
    entrenamineto: "entrenamiento", fuerzza: "fuerza", grasasas: "grasas",
    hidratasion: "hidratacion", hipertrofiaa: "hipertrofia", incribirme: "inscribirme",
    inscripcionn: "inscripcion", inscrivir: "inscribir", membrecia: "membresia",
    musculoos: "musculos", nuticion: "nutricion", nutricon: "nutricion",
    proteinaas: "proteinas", recuparacion: "recuperacion", repeticones: "repeticiones",
    resistecia: "resistencia", rutinaa: "rutina", serires: "series"
  });

  function stripAccents(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function normalizeText(value) {
    const clean = stripAccents(value)
      .toLowerCase()
      .replace(/[^a-z0-9ñ\s]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return clean.split(" ").map((token) => corrections[token] || token).join(" ");
  }

  function tokenize(value) {
    return normalizeText(value).split(" ").filter(Boolean);
  }

  function levenshtein(left, right) {
    const a = String(left || "");
    const b = String(right || "");
    if (!a.length) return b.length;
    if (!b.length) return a.length;
    const previous = Array.from({ length: b.length + 1 }, (_, index) => index);
    for (let row = 1; row <= a.length; row += 1) {
      let diagonal = previous[0];
      previous[0] = row;
      for (let column = 1; column <= b.length; column += 1) {
        const old = previous[column];
        previous[column] = Math.min(
          previous[column] + 1,
          previous[column - 1] + 1,
          diagonal + (a[row - 1] === b[column - 1] ? 0 : 1)
        );
        diagonal = old;
      }
    }
    return previous[b.length];
  }

  function similarity(left, right) {
    const a = normalizeText(left);
    const b = normalizeText(right);
    const longest = Math.max(a.length, b.length);
    return longest ? 1 - (levenshtein(a, b) / longest) : 1;
  }

  function tokenSimilarity(expected, actual) {
    if (expected === actual) return 1;
    if (expected.length < 5 || actual.length < 5) return 0;
    return similarity(expected, actual);
  }

  function bestTokenMatch(expected, actualTokens) {
    return actualTokens.reduce(
      (best, token) => Math.max(best, tokenSimilarity(expected, token)),
      0
    );
  }

  function extractNumber(value) {
    const match = normalizeText(value).match(/\b(?:clase|reserva|id)?\s*(\d{1,8})\b/);
    return match ? Number(match[1]) : null;
  }

  assistant.text = Object.freeze({
    normalizeText,
    tokenize,
    levenshtein,
    similarity,
    bestTokenMatch,
    extractNumber
  });
})(typeof window !== "undefined" ? window : globalThis);
