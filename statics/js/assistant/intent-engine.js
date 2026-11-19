(function (root) {
  "use strict";

  const assistant = root.FitPathAssistant = root.FitPathAssistant || {};
  const text = assistant.text;
  const knowledge = assistant.knowledge;

  function scoreKeyword(keyword, normalized, tokens) {
    const expected = text.tokenize(keyword);
    if (!expected.length) return 0;
    if (normalized.includes(text.normalizeText(keyword))) return 4 + Math.min(expected.length, 3);
    const matches = expected.map((token) => text.bestTokenMatch(token, tokens));
    const average = matches.reduce((sum, value) => sum + value, 0) / matches.length;
    const covered = matches.filter((value) => value >= 0.76).length / matches.length;
    return covered >= 0.6 ? (average * 2.2) + covered : 0;
  }

  function hasFollowUpShape(normalized, tokens) {
    return tokens.length <= 7 && /^(y |pero |entonces |tambien |eso |en ese caso|cuanto |como |para )/.test(normalized);
  }

  class IntentEngine {
    constructor() {
      this.intents = [...knowledge.fitness, ...knowledge.application];
    }

    detect(message, context) {
      const normalized = text.normalizeText(message);
      const tokens = text.tokenize(normalized);
      if (!normalized) return { kind: "empty", confidence: 0 };
      if (/^(hola|buenas|buen dia|buenas tardes|buenas noches|hey)$/.test(normalized)) {
        return { kind: "greeting", confidence: 1 };
      }
      if (knowledge.safetyKeywords.some((keyword) => normalized.includes(text.normalizeText(keyword)))) {
        return { kind: "safety", confidence: 1 };
      }

      const ranked = this.intents.map((intent) => {
        let score = Math.max(...intent.keywords.map((keyword) => scoreKeyword(keyword, normalized, tokens)));
        if (context?.activeTopic === intent.id && hasFollowUpShape(normalized, tokens)) score += 2;
        if (intent.mutation && /\b(inscribir|inscribirme|reservar|cancelar|baja)\b/.test(normalized)) score += 1.2;
        if (intent.route && /\b(ir|abrir|navegar)\b/.test(normalized)) score += 1;
        return { intent, score };
      }).sort((left, right) => right.score - left.score);

      const best = ranked[0];
      const second = ranked[1];
      if (!best || best.score < 2.15) {
        return { kind: "unknown", confidence: best ? Math.min(best.score / 5, 0.4) : 0 };
      }
      const ambiguous = second
        && second.score >= 2.15
        && best.intent.id !== second.intent.id
        && Math.abs(best.score - second.score) <= 0.45;
      if (ambiguous) {
        return {
          kind: "ambiguous",
          confidence: Math.min(best.score / 7, 0.75),
          options: [best.intent, second.intent]
        };
      }
      return {
        kind: "intent",
        confidence: Math.min(0.99, 0.45 + (best.score / 10)),
        intent: best.intent
      };
    }
  }

  assistant.IntentEngine = IntentEngine;
})(typeof window !== "undefined" ? window : globalThis);
