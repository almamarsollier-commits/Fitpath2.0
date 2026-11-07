const exercises = Object.freeze({
  "press-mancuernas": Object.freeze({
    name: "Press con mancuernas",
    focus: "Pecho y estabilidad del hombro",
    series: "3 series",
    repetitions: "10 repeticiones",
    rest: "90 segundos",
    note: "Descripción orientativa ficticia. No constituye una indicación de entrenamiento."
  }),
  "remo-sentado": Object.freeze({
    name: "Remo sentado",
    focus: "Espalda y control del movimiento",
    series: "3 series",
    repetitions: "12 repeticiones",
    rest: "75 segundos",
    note: "Descripción orientativa ficticia. No constituye una indicación de entrenamiento."
  }),
  "press-hombros": Object.freeze({
    name: "Press de hombros",
    focus: "Hombros y estabilidad",
    series: "3 series",
    repetitions: "10 repeticiones",
    rest: "75 segundos",
    note: "Descripción orientativa ficticia. No constituye una indicación de entrenamiento."
  }),
  plancha: Object.freeze({
    name: "Plancha",
    focus: "Estabilidad del tronco",
    series: "3 series",
    repetitions: "30 segundos",
    rest: "60 segundos",
    note: "Descripción orientativa ficticia. No constituye una indicación de entrenamiento."
  })
});

export const clienteDemo = Object.freeze({
  profile: Object.freeze({ name: "Lucía Soria", firstName: "Lucía", initials: "LS", goal: "Fortalecer la rutina" }),
  membership: Object.freeze({ name: "Premium", status: "Activa · dato ficticio" }),
  nextClass: Object.freeze({ name: "Entrenamiento funcional", time: "18:30", duration: "45 min", location: "Sede de ejemplo" }),
  activity: Object.freeze({ weekClasses: "03 de 04", movementMinutes: "145", movementGoal: "180", sessions: "06 de 08" }),
  routine: Object.freeze({ name: "Fuerza y control", day: "Lunes", label: "Día A", focus: "Tren superior", exercises }),
  exercises
});
