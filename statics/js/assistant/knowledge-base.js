(function (root) {
  "use strict";

  const assistant = root.FitPathAssistant = root.FitPathAssistant || {};

  const fitness = [
    {
      id: "hypertrophy", title: "Hipertrofia", category: "entrenamiento",
      keywords: ["hipertrofia", "ganar masa muscular", "crecer musculo", "volumen muscular"],
      responses: [
        "La hipertrofia se favorece con entrenamiento de fuerza sostenido, series exigentes con técnica controlada, recuperación y alimentación suficiente. No depende de un único rango de repeticiones.",
        "Para ganar masa muscular importa acumular trabajo de calidad, acercarse gradualmente a esfuerzos desafiantes y progresar sin sacrificar la técnica. Dormir y recuperarse también forman parte del proceso."
      ],
      followUps: ["¿Entrenás hace poco o ya tenés experiencia?", "¿Querés entender volumen, repeticiones o progresión?"],
      suggestions: ["¿Cuántas series hacer?", "¿Cómo progresar?", "Proteínas y entrenamiento"]
    },
    {
      id: "strength", title: "Fuerza", category: "entrenamiento",
      keywords: ["fuerza", "ser mas fuerte", "levantar mas peso", "fuerza maxima"],
      responses: [
        "La fuerza mejora practicando movimientos con buena técnica, cargas progresivas y descansos suficientes. La progresión puede ser aumentar poco a poco el peso, las repeticiones o la calidad del movimiento.",
        "Un trabajo de fuerza suele priorizar ejercicios estables, ejecución consistente y recuperación amplia entre intentos exigentes. La carga debe adaptarse a tu experiencia."
      ],
      followUps: ["¿Buscás fuerza general o mejorar un ejercicio concreto?"],
      suggestions: ["Sobrecarga progresiva", "Descanso entre series", "Rutina inicial"]
    },
    {
      id: "cardio", title: "Cardio y resistencia", category: "entrenamiento",
      keywords: ["cardio", "resistencia", "aerobico", "correr", "bicicleta", "aguante"],
      responses: [
        "El cardio mejora la capacidad de sostener esfuerzos. Podés combinar sesiones suaves, donde todavía podés conversar, con estímulos más intensos según tu nivel y recuperación.",
        "Caminar rápido, pedalear, nadar o correr pueden desarrollar resistencia. Empezá con una duración tolerable y aumentá de forma gradual antes de sumar mucha intensidad."
      ],
      followUps: ["¿Preferís una actividad continua o intervalos breves?"],
      suggestions: ["Cardio para principiantes", "Combinar fuerza y cardio", "Recuperación"]
    },
    {
      id: "anatomy", title: "Anatomía muscular básica", category: "entrenamiento",
      keywords: ["musculos", "anatomia", "pecho", "espalda", "piernas", "gluteos", "hombros", "biceps", "triceps"],
      responses: [
        "Los movimientos suelen involucrar varios músculos. Empujes trabajan principalmente pecho, hombros y tríceps; tirones, espalda y bíceps; sentadillas y bisagras, distintos grupos de piernas y cadera.",
        "Pensar por patrones —empujar, tirar, agacharse, hacer bisagra, transportar y estabilizar— suele ser más útil que aislar cada músculo al comenzar."
      ],
      followUps: ["¿Sobre qué movimiento o zona querés una explicación general?"],
      suggestions: ["Músculos en una sentadilla", "Empujes y tirones", "Técnica segura"]
    },
    {
      id: "technique", title: "Ejercicios y técnica", category: "entrenamiento",
      keywords: ["tecnica", "ejercicio", "ejecucion", "postura", "sentadilla", "peso muerto", "press", "remo"],
      responses: [
        "Una técnica útil mantiene el movimiento controlado, una postura estable y un rango que puedas dominar sin dolor. Conviene aprender con poca carga antes de progresar.",
        "La técnica no es idéntica para todas las personas. Buscá control, respiración estable y una variante compatible con tu movilidad; si aparece dolor agudo, detené el ejercicio y consultá a un profesional."
      ],
      followUps: ["¿Qué ejercicio querés revisar?"],
      suggestions: ["Técnica de sentadilla", "Cómo elegir una carga", "Dolor al entrenar"]
    },
    {
      id: "volume_rest", title: "Series, repeticiones y descansos", category: "entrenamiento",
      keywords: ["series", "repeticiones", "reps", "descanso entre series", "cuanto descansar", "cuanto descanso", "volumen"],
      responses: [
        "Series y repeticiones dependen del objetivo y del ejercicio. Como orientación general, empezá con pocas series de calidad y sumá trabajo solo si mantenés técnica y recuperación. Los esfuerzos pesados suelen necesitar descansos más largos.",
        "No hay un número universal. Para aprender y ganar fuerza o músculo, priorizá repeticiones controladas y descansá hasta poder repetir una serie con buena ejecución; los ejercicios grandes suelen requerir más pausa."
      ],
      followUps: ["¿Tu objetivo principal es fuerza, masa muscular o resistencia?"],
      suggestions: ["Series para principiantes", "Hipertrofia", "Fuerza"]
    },
    {
      id: "progressive_overload", title: "Sobrecarga progresiva", category: "entrenamiento",
      keywords: ["sobrecarga progresiva", "progresar", "aumentar peso", "mejorar cargas", "estancado"],
      responses: [
        "Progresar no significa subir peso en cada sesión. También podés hacer una repetición más, mejorar el control, ampliar el rango o completar el mismo trabajo con menor esfuerzo percibido.",
        "La sobrecarga progresiva consiste en aumentar gradualmente el desafío mientras conservás la técnica. Registrá lo realizado y cambiá una variable por vez."
      ],
      followUps: ["¿Qué variable venís registrando en tus entrenamientos?"],
      suggestions: ["Registrar entrenamientos", "Cuándo subir peso", "Recuperación"]
    },
    {
      id: "beginner", title: "Rutinas para principiantes", category: "entrenamiento",
      keywords: ["principiante", "empezar gimnasio", "rutina inicial", "recien empiezo", "primer entrenamiento"],
      responses: [
        "Al comenzar conviene una rutina simple de cuerpo completo dos o tres veces por semana, con pocos movimientos básicos, cargas moderadas y días de recuperación. La constancia vale más que agregar muchos ejercicios.",
        "Una base inicial puede incluir un movimiento de piernas, un empuje, un tirón, una bisagra de cadera y trabajo de estabilidad. Aprendé las variantes antes de aumentar el esfuerzo."
      ],
      followUps: ["¿Cuántos días por semana tenés disponibles?"],
      suggestions: ["Ejercicios básicos", "Cuánto descansar", "Crear un hábito"]
    },
    {
      id: "recovery", title: "Recuperación y descanso", category: "bienestar",
      keywords: ["recuperacion", "descanso", "dormir", "sueño", "fatiga", "agujetas"],
      responses: [
        "La recuperación combina sueño suficiente, alimentación, hidratación y una carga de entrenamiento que puedas tolerar. La fatiga persistente es una señal para revisar el volumen o pedir orientación.",
        "Los músculos y el rendimiento se adaptan entre sesiones. Alternar estímulos, dormir con regularidad y evitar entrenar siempre al máximo ayuda a sostener el progreso."
      ],
      followUps: ["¿Sentís cansancio general o molestias en una zona concreta?"],
      suggestions: ["Sueño y rendimiento", "Dolor al entrenar", "Hidratación"]
    },
    {
      id: "nutrition", title: "Nutrición deportiva general", category: "nutricion",
      keywords: ["nutricion", "alimentacion", "comer para entrenar", "dieta deportiva", "comida saludable"],
      responses: [
        "Una alimentación deportiva general prioriza variedad, suficiente energía, proteínas distribuidas, carbohidratos según la actividad, grasas de calidad, frutas, verduras y agua. No reemplaza una evaluación profesional.",
        "El rendimiento suele beneficiarse de comidas regulares y variadas. No hace falta buscar alimentos perfectos: importa el patrón general y que sea sostenible."
      ],
      followUps: ["¿Querés hablar de proteínas, energía para entrenar o hidratación?"],
      suggestions: ["Proteínas", "Carbohidratos", "Calorías", "Hidratación"]
    },
    {
      id: "protein", title: "Proteínas", category: "nutricion",
      keywords: ["proteina", "proteinas", "aminoacidos", "comida proteica"],
      responses: [
        "Las proteínas participan en la reparación de tejidos. Podés obtenerlas de huevos, lácteos, carnes, pescado, legumbres, soja y combinaciones vegetales. Distribuir fuentes variadas durante el día suele ser más práctico que concentrarlas todas juntas.",
        "No necesitás un suplemento para consumir proteína: primero pueden cubrirse las necesidades con alimentos. La cantidad adecuada depende de la persona y debe individualizarla un profesional cuando haga falta."
      ],
      followUps: ["¿Buscás ejemplos de alimentos o entender su función?"],
      suggestions: ["Proteínas vegetales", "Comer después de entrenar", "Hipertrofia"]
    },
    {
      id: "carbohydrates", title: "Carbohidratos", category: "nutricion",
      keywords: ["carbohidratos", "carbos", "energia para entrenar", "arroz", "avena"],
      responses: [
        "Los carbohidratos son una fuente importante de energía para actividades intensas. Cereales, legumbres, frutas, tubérculos y otros alimentos pueden formar parte de una alimentación variada.",
        "La cantidad y el momento de los carbohidratos dependen de la actividad y tolerancia. Para entrenar, una comida habitual que te resulte cómoda suele ser mejor que una regla rígida."
      ],
      followUps: ["¿Tu duda es antes, durante o después de entrenar?"],
      suggestions: ["Comer antes de entrenar", "Proteínas", "Calorías"]
    },
    {
      id: "fats", title: "Grasas", category: "nutricion",
      keywords: ["grasas", "grasa saludable", "aceite", "frutos secos", "omega"],
      responses: [
        "Las grasas cumplen funciones hormonales y ayudan a absorber vitaminas. Aceites, frutos secos, semillas, palta y pescados son ejemplos; conviene incluir variedad sin eliminarlas por completo.",
        "Las grasas son parte de una alimentación equilibrada. Como se digieren más lento, algunas personas prefieren no concentrarlas justo antes de una sesión intensa."
      ],
      followUps: ["¿Querés ejemplos generales o saber cómo combinarlas con el entrenamiento?"],
      suggestions: ["Carbohidratos", "Proteínas", "Hábitos saludables"]
    },
    {
      id: "calories", title: "Calorías y objetivos", category: "nutricion",
      keywords: ["calorias", "deficit", "superavit", "bajar de peso", "subir de peso", "cuantas calorias"],
      responses: [
        "Las calorías representan energía, pero una cifra personal requiere datos, contexto y seguimiento. Puedo explicar déficit, mantenimiento y superávit de forma general, pero no prescribir un objetivo clínico.",
        "Para cambiar peso suele importar el balance energético sostenido, junto con la calidad de la alimentación y el entrenamiento. Evitá ajustes extremos; una recomendación personal corresponde a nutrición profesional."
      ],
      followUps: ["¿Querés entender la diferencia entre mantenimiento, déficit y superávit?"],
      suggestions: ["Qué es un déficit", "Comer para rendir", "Hábitos sostenibles"]
    },
    {
      id: "hydration", title: "Hidratación", category: "bienestar",
      keywords: ["hidratacion", "agua", "tomar agua", "deshidratacion", "bebida deportiva"],
      responses: [
        "La hidratación depende del clima, duración, intensidad y transpiración. Llegar hidratado, beber de forma regular y observar sed y color de orina son referencias generales útiles.",
        "Para sesiones habituales, el agua suele ser suficiente. Entrenamientos muy largos, calor intenso o pérdidas elevadas pueden requerir una estrategia individual con un profesional."
      ],
      followUps: ["¿Tu entrenamiento es breve, prolongado o en un ambiente caluroso?"],
      suggestions: ["Agua durante el cardio", "Recuperación", "Hábitos saludables"]
    },
    {
      id: "habits", title: "Hábitos saludables", category: "bienestar",
      keywords: ["habitos", "constancia", "motivacion", "vida saludable", "ser constante"],
      responses: [
        "Los hábitos se sostienen mejor cuando son concretos y pequeños: elegir días, preparar la ropa, registrar la asistencia y tener una versión corta para días difíciles.",
        "La constancia no exige perfección. Definí una acción mínima, vinculala a una rutina existente y revisá semanalmente qué facilitó o dificultó cumplirla."
      ],
      followUps: ["¿Qué hábito querés volver más consistente?"],
      suggestions: ["Empezar el gimnasio", "Dormir mejor", "Registrar progreso"]
    }
  ];

  const application = [
    { id: "app_classes", title: "Clases", category: "fitpath", operation: "classes.list", keywords: ["ver clases", "consultar clases", "clases disponibles", "horarios de clases", "hay cupo"], suggestions: ["Ver mis reservas", "Ir a clases", "Inscribirme a una clase"] },
    { id: "app_enroll", title: "Inscripción", category: "fitpath", operation: "enrollments.create", mutation: true, keywords: ["inscribirme", "inscribir a clase", "reservar clase", "anotarme a clase"], suggestions: ["Ver clases disponibles", "Mis reservas"] },
    { id: "app_cancel", title: "Cancelar inscripción", category: "fitpath", operation: "enrollments.cancel", mutation: true, keywords: ["cancelar inscripcion", "cancelar reserva", "dar de baja clase"], suggestions: ["Ver mis reservas", "Ver clases"] },
    { id: "app_routine", title: "Mi rutina", category: "fitpath", operation: "routine.get", keywords: ["mi rutina", "consultar rutina", "entrenamiento asignado"], suggestions: ["Ir a mi rutina", "Ver progreso"] },
    { id: "app_progress", title: "Mi progreso", category: "fitpath", operation: "progress.get", keywords: ["mi progreso", "consultar progreso", "ver evolucion", "mis objetivos"], suggestions: ["Ir a progreso", "Mi rutina"] },
    { id: "app_membership", title: "Mi membresía", category: "fitpath", operation: "membership.get", keywords: ["mi membresia", "consultar membresia", "plan actual", "membresia activa"], suggestions: ["Ir a mi perfil", "Ver clases"] },
    { id: "navigate_classes", title: "Abrir clases", category: "navegacion", route: "/templates/cliente/clases/index.html", keywords: ["ir a clases", "abrir clases", "navegar a clases"] },
    { id: "navigate_routine", title: "Abrir rutina", category: "navegacion", route: "/templates/cliente/rutina/semana.html", keywords: ["ir a mi rutina", "abrir rutina", "navegar a rutina"] },
    { id: "navigate_progress", title: "Abrir progreso", category: "navegacion", route: "/templates/cliente/progreso/index.html", keywords: ["ir a progreso", "abrir progreso", "navegar a progreso"] },
    { id: "navigate_profile", title: "Abrir perfil", category: "navegacion", route: "/templates/cliente/perfil/index.html", keywords: ["ir a mi perfil", "abrir perfil", "navegar a perfil"] }
  ];

  assistant.knowledge = Object.freeze({
    fitness: Object.freeze(fitness.map(Object.freeze)),
    application: Object.freeze(application.map(Object.freeze)),
    safetyKeywords: Object.freeze(["dolor fuerte", "dolor agudo", "lesion", "diagnostico", "tratamiento", "medicacion", "trastorno alimentario", "desmayo", "dolor de pecho"]),
    greetings: Object.freeze(["¡Hola! Soy FitPath Smart Assistant. Puedo orientarte sobre entrenamiento y nutrición general, o ayudarte a navegar FitPath.", "¡Hola! ¿Querés hablar de entrenamiento, alimentación o de alguna función de FitPath?"]),
    fallbacks: Object.freeze([
      "No tengo suficiente contexto para responder eso con seguridad. Puedo ayudarte con entrenamiento, nutrición general o navegación por FitPath.",
      "Ese tema está fuera de mi base actual. Probá preguntarme por fuerza, cardio, recuperación, alimentación o funciones de FitPath."
    ])
  });
})(typeof window !== "undefined" ? window : globalThis);
