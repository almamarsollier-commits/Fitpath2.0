"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../..");
const context = { console, setTimeout, clearTimeout, AbortController };
context.globalThis = context;
vm.createContext(context);

for (const relative of [
  "statics/js/assistant/text-utils.js",
  "statics/js/assistant/knowledge-base.js",
  "statics/js/assistant/intent-engine.js",
  "statics/js/assistant/fitpath-client.js",
  "statics/js/assistant/conversation-engine.js"
]) {
  vm.runInContext(fs.readFileSync(path.join(root, relative), "utf8"), context, { filename: relative });
}

const { ConversationEngine, FitPathClient } = context.FitPathAssistant;

async function run() {
  const offline = new ConversationEngine({ client: new FitPathClient({ offline: true }) });

  const nutrition = await offline.respond("¿Qué debería saber sobre nutricon deportiva?");
  assert.match(nutrition.message, /alimentaci[oó]n|rendimiento/i);

  const strength = await offline.respond("como puedo ganar fuerzza");
  assert.match(strength.message, /fuerza|cargas progresivas/i);

  const typo = await offline.respond("cuanto descanzo entre serires");
  assert.match(typo.message, /descans|series/i);

  await offline.respond("quiero entender la hipertrofia");
  const followUp = await offline.respond("¿y cuánto descanso?");
  assert.match(followUp.message, /descans|series/i);

  await offline.respond("contame sobre proteinas");
  const topicChange = await offline.respond("ahora quiero hacer cardio");
  assert.match(topicChange.message, /cardio|resistencia/i);

  const unknown = await offline.respond("¿cómo calibro una antena satelital?");
  assert.match(unknown.message, /fuera|contexto|preguntarme/i);

  const classes = await offline.respond("ver clases disponibles");
  assert.equal(classes.backendAvailable, false);
  assert.match(classes.message, /backend|operaciones reales/i);

  const calls = [];
  const mutationClient = {
    perform: async (operation, parameters) => {
      calls.push({ operation, parameters });
      return { ok: false, reason: "unsupported_operation" };
    }
  };
  const enrollment = new ConversationEngine({ client: mutationClient });
  const confirmation = await enrollment.respond("quiero inscribirme a la clase 12");
  assert.equal(confirmation.confirmationRequired, true);
  assert.equal(calls.length, 0);
  const confirmed = await enrollment.respond("confirmar");
  assert.match(confirmed.message, /todav[ií]a no est[aá] habilitada/i);
  assert.deepEqual(calls, [{ operation: "enrollments.create", parameters: { id: 12 } }]);

  const cancelClient = {
    perform: async (operation, parameters) => ({
      ok: true,
      data: { message: `Operación ${operation} confirmada para ${parameters.id}.` }
    })
  };
  const cancellation = new ConversationEngine({ client: cancelClient });
  await cancellation.respond("cancelar reserva 7");
  const cancelled = await cancellation.respond("confirmo");
  assert.match(cancelled.message, /confirmada para 7/i);

  const denied = new ConversationEngine({
    client: { perform: async () => ({ ok: false, reason: "permission_denied" }) }
  });
  assert.match((await denied.respond("ver mi progreso")).message, /no tiene permiso/i);

  const navigation = await offline.respond("ir a mi rutina");
  assert.equal(navigation.actions[0].href, "/templates/cliente/rutina/semana.html");

  const safety = await offline.respond("tengo dolor de pecho al entrenar");
  assert.match(safety.message, /deten[eé]|atenci[oó]n profesional/i);

  const ambiguous = await offline.respond("quiero mejorar fuerza e hipertrofia");
  assert.match(ambiguous.message, /puede referirse/i);

  console.log("FitPath Smart Assistant: 13 escenarios aprobados.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
