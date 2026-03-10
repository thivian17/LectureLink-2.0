import type {
  Lecture,
  LectureDetail,
  LectureStatus,
  TranscriptSegment,
  LectureConcept,
  SlideInfo,
  Quiz,
  QuizQuestion,
  QuizSubmissionResult,
  QuestionResult,
  QuizGenerationStatus,
  QuizAnswer,
  QuizDifficulty,
  SearchResponse,
  SearchResult,
  QAResponse,
} from "@/types/database";

const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const mockLectures: Lecture[] = [
  {
    id: "lecture-1",
    course_id: "course-1",
    title: "Lecture 1: Intro to Thermodynamics",
    lecture_number: 1,
    lecture_date: "2026-01-12",
    processing_status: "completed",
    processing_stage: null,
    processing_progress: 1.0,
    summary:
      "Introduction to thermodynamic systems and energy transfer. Covers basic definitions, system boundaries, and the zeroth law of thermodynamics.",
    duration_seconds: 3000,
    low_concept_yield: false,
    created_at: new Date().toISOString(),
  },
  {
    id: "lecture-2",
    course_id: "course-1",
    title: "Lecture 2: Heat and Work",
    lecture_number: 2,
    lecture_date: "2026-01-14",
    processing_status: "processing",
    processing_stage: "extracting_concepts",
    processing_progress: 0.6,
    summary: null,
    duration_seconds: null,
    low_concept_yield: false,
    created_at: new Date().toISOString(),
  },
  {
    id: "lecture-3",
    course_id: "course-1",
    title: "Lecture 3: Second Law",
    lecture_number: 3,
    lecture_date: "2026-01-16",
    processing_status: "pending",
    processing_stage: null,
    processing_progress: 0.0,
    summary: null,
    duration_seconds: null,
    low_concept_yield: false,
    created_at: new Date().toISOString(),
  },
  {
    id: "lecture-4",
    course_id: "course-1",
    title: "Lecture 4: Entropy",
    lecture_number: 4,
    lecture_date: "2026-01-19",
    processing_status: "failed",
    processing_stage: null,
    processing_progress: 0.3,
    summary: null,
    duration_seconds: null,
    low_concept_yield: false,
    created_at: new Date().toISOString(),
  },
];

// Simulates processing advancing through stages over time
let mockProcessingCallCount = 0;

// ---------------------------------------------------------------------------
// Mock API functions
// ---------------------------------------------------------------------------

async function mockGetLectures(courseId: string): Promise<Lecture[]> {
  await delay(300);
  return mockLectures
    .filter((l) => l.course_id === courseId || courseId === "course-1")
    .sort(
      (a, b) =>
        new Date(b.lecture_date ?? b.created_at).getTime() -
        new Date(a.lecture_date ?? a.created_at).getTime(),
    );
}

async function mockGetLecture(lectureId: string): Promise<Lecture> {
  await delay(200);
  const lecture = mockLectures.find((l) => l.id === lectureId);
  if (!lecture) throw new Error("Lecture not found");
  return lecture;
}

async function mockGetLectureStatus(lectureId: string): Promise<LectureStatus> {
  await delay(200);
  const lecture = mockLectures.find((l) => l.id === lectureId);
  if (!lecture) throw new Error("Lecture not found");

  // Simulate processing progress for "processing" lectures
  if (lecture.processing_status === "processing") {
    mockProcessingCallCount++;
    const stages = [
      "uploading",
      "transcribing",
      "analyzing_slides",
      "aligning",
      "extracting_concepts",
      "generating_embeddings",
      "mapping_concepts",
      "completed",
    ];
    const stageIndex = Math.min(
      Math.floor(mockProcessingCallCount / 2),
      stages.length - 1,
    );
    const progress = (stageIndex + 1) / stages.length;

    if (stages[stageIndex] === "completed") {
      return {
        processing_status: "completed",
        processing_stage: null,
        processing_progress: 1.0,
        processing_error: null,
      };
    }

    return {
      processing_status: "processing",
      processing_stage: stages[stageIndex],
      processing_progress: progress,
      processing_error: null,
    };
  }

  return {
    processing_status: lecture.processing_status,
    processing_stage: lecture.processing_stage,
    processing_progress: lecture.processing_progress,
    processing_error:
      lecture.processing_status === "failed"
        ? "Transcription failed: audio quality too low"
        : null,
  };
}

async function mockUploadLecture(
  _courseId: string,
  _data: FormData,
): Promise<{ lecture_id: string; status: string }> {
  await delay(1000);
  mockProcessingCallCount = 0;
  return { lecture_id: "lecture-new-1", status: "processing" };
}

async function mockRetryLecture(_lectureId: string): Promise<void> {
  await delay(500);
  mockProcessingCallCount = 0;
}

// ---------------------------------------------------------------------------
// Lecture detail mock data
// ---------------------------------------------------------------------------

const mockTranscriptSegments: TranscriptSegment[] = [
  { start: 0, end: 28, text: "Welcome to today's lecture on thermodynamics. We're going to cover the fundamental concepts that form the basis of this entire course.", speaker: "professor", slide_number: 1, source: "aligned" },
  { start: 28, end: 65, text: "Let's start with what we mean by a thermodynamic system. A thermodynamic system is a quantity of matter or a region in space chosen for study.", speaker: "professor", slide_number: 1, source: "aligned" },
  { start: 65, end: 120, text: "The boundary separating the system from its surroundings can be real or imaginary, fixed or movable. Everything outside the system is called the surroundings.", speaker: "professor", slide_number: 2, source: "aligned" },
  { start: 120, end: 185, text: "Now, the Zeroth Law of Thermodynamics is actually a fundamental principle. It states that if two systems are each in thermal equilibrium with a third system, they are in thermal equilibrium with each other.", speaker: "professor", slide_number: 2, source: "aligned" },
  { start: 185, end: 210, text: "Professor, does that mean temperature is transitive?", speaker: "student", slide_number: 2, source: "audio" },
  { start: 210, end: 280, text: "Exactly! That's a great way to think about it. The Zeroth Law essentially establishes the concept of temperature as a measurable, comparable property. Without it, we couldn't even define temperature consistently.", speaker: "professor", slide_number: 3, source: "aligned" },
  { start: 280, end: 360, text: "Energy transfer is another key concept. Energy can be transferred between a system and its surroundings in two forms: heat and work. Heat is energy transfer due to temperature difference, while work is energy transfer due to other driving forces.", speaker: "professor", slide_number: 3, source: "aligned" },
  { start: 360, end: 440, text: "Internal energy is the sum of all microscopic forms of energy of a system. It includes kinetic energies of molecules, potential energies between molecules, and energies within molecules.", speaker: "professor", slide_number: 4, source: "aligned" },
  { start: 440, end: 510, text: "The key thing about internal energy is that it's a state function. It depends only on the current state, not on the path taken to get there. This is fundamentally different from heat and work.", speaker: "professor", slide_number: 4, source: "aligned" },
  { start: 510, end: 580, text: "Now we come to one of the most important principles in all of physics: the conservation of energy. Energy cannot be created or destroyed; it can only change forms.", speaker: "professor", slide_number: 5, source: "aligned" },
  { start: 580, end: 660, text: "In thermodynamic terms, this is expressed as the First Law: the change in internal energy equals the heat added to the system minus the work done by the system. Delta U equals Q minus W.", speaker: "professor", slide_number: 5, source: "aligned" },
  { start: 660, end: 720, text: "Let me show you a practical example. Consider a gas in a piston-cylinder device. If we add heat to the gas, it can expand and do work on the piston.", speaker: "professor", slide_number: 6, source: "aligned" },
  { start: 720, end: 780, text: "The relationship between pressure, volume, and temperature follows specific paths depending on the process type: isothermal, isobaric, isochoric, or adiabatic.", speaker: "professor", slide_number: 7, source: "aligned" },
  { start: 780, end: 830, text: "Can you explain the difference between an open and closed system again?", speaker: "student", slide_number: 7, source: "audio" },
  { start: 830, end: 920, text: "Of course. A closed system has a fixed amount of mass — no mass can cross its boundary. But energy, in the form of heat or work, can cross the boundary. An open system, or control volume, allows both mass and energy to cross its boundary.", speaker: "professor", slide_number: 8, source: "aligned" },
];

const mockSlides: SlideInfo[] = [
  { slide_number: 1, image_url: "/placeholder-slide.svg", title: "Introduction to Thermodynamics", text_content: "PHYS 301 - Lecture 1\nIntroduction to Thermodynamic Systems" },
  { slide_number: 2, image_url: "/placeholder-slide.svg", title: "System Boundaries & Zeroth Law", text_content: "System Boundaries\n- Real or imaginary\n- Fixed or movable\n\nZeroth Law of Thermodynamics" },
  { slide_number: 3, image_url: "/placeholder-slide.svg", title: "Temperature & Energy Transfer", text_content: "Temperature as a measurable property\n\nEnergy Transfer:\n- Heat (Q)\n- Work (W)" },
  { slide_number: 4, image_url: "/placeholder-slide.svg", title: "Internal Energy", text_content: "Internal Energy (U)\n- Sum of microscopic energies\n- State function\n- Path independent" },
  { slide_number: 5, image_url: "/placeholder-slide.svg", title: "Conservation of Energy", text_content: "First Law of Thermodynamics\nΔU = Q - W\n\nEnergy cannot be created or destroyed" },
  { slide_number: 6, image_url: "/placeholder-slide.svg", title: "Piston-Cylinder Example", text_content: "Practical Application:\nGas expansion in piston-cylinder\nHeat → Work conversion" },
  { slide_number: 7, image_url: "/placeholder-slide.svg", title: "Thermodynamic Processes", text_content: "Process Types:\n- Isothermal (constant T)\n- Isobaric (constant P)\n- Isochoric (constant V)\n- Adiabatic (no heat transfer)" },
  { slide_number: 8, image_url: "/placeholder-slide.svg", title: "Open vs Closed Systems", text_content: "Closed System: fixed mass, energy crosses boundary\nOpen System: mass and energy cross boundary" },
];

const mockConcepts: LectureConcept[] = [
  {
    id: "concept-1",
    title: "Thermodynamic System",
    description: "A quantity of matter or a region in space chosen for study. The boundary separates the system from its surroundings and can be real or imaginary, fixed or movable.",
    category: "definition",
    difficulty_estimate: 0.3,
    linked_assessments: [
      { id: "assess-1", title: "Midterm 1", due_date: "2026-02-15", relevance_score: 0.9 },
      { id: "assess-2", title: "Homework 1", due_date: "2026-01-19", relevance_score: 0.8 },
    ],
    segment_indices: [1, 2, 14],
    subconcepts: [],
  },
  {
    id: "concept-2",
    title: "Zeroth Law of Thermodynamics",
    description: "If two systems are each in thermal equilibrium with a third system, they are in thermal equilibrium with each other. This establishes the concept of temperature.",
    category: "theorem",
    difficulty_estimate: 0.4,
    linked_assessments: [
      { id: "assess-1", title: "Midterm 1", due_date: "2026-02-15", relevance_score: 0.85 },
    ],
    segment_indices: [3, 5],
    subconcepts: [],
  },
  {
    id: "concept-3",
    title: "Energy Transfer",
    description: "Energy can be transferred between a system and its surroundings as heat (due to temperature difference) or work (due to other driving forces like pressure).",
    category: "process",
    difficulty_estimate: 0.5,
    linked_assessments: [
      { id: "assess-1", title: "Midterm 1", due_date: "2026-02-15", relevance_score: 0.95 },
      { id: "assess-3", title: "Lab Report 1", due_date: "2026-01-26", relevance_score: 0.6 },
    ],
    segment_indices: [6, 11],
    subconcepts: [],
  },
  {
    id: "concept-4",
    title: "Internal Energy",
    description: "The sum of all microscopic forms of energy in a system, including molecular kinetic and potential energies. It is a state function — path independent.",
    category: "concept",
    difficulty_estimate: 0.6,
    linked_assessments: [
      { id: "assess-1", title: "Midterm 1", due_date: "2026-02-15", relevance_score: 0.9 },
    ],
    segment_indices: [7, 8],
    subconcepts: [],
  },
  {
    id: "concept-5",
    title: "Conservation of Energy (First Law)",
    description: "Energy cannot be created or destroyed. The change in internal energy equals heat added minus work done: ΔU = Q - W.",
    category: "formula",
    difficulty_estimate: 0.7,
    linked_assessments: [
      { id: "assess-1", title: "Midterm 1", due_date: "2026-02-15", relevance_score: 1.0 },
      { id: "assess-2", title: "Homework 1", due_date: "2026-01-19", relevance_score: 0.9 },
    ],
    segment_indices: [9, 10],
    subconcepts: [],
  },
];

async function mockGetLectureDetail(lectureId: string): Promise<LectureDetail> {
  await delay(400);
  const lecture = mockLectures.find((l) => l.id === lectureId);
  if (!lecture) throw new Error("Lecture not found");

  return {
    ...lecture,
    audio_url: lecture.processing_status === "completed" ? "/mock-audio.mp3" : null,
    slides_url: lecture.processing_status === "completed" ? "/mock-slides" : null,
    transcript_segments: lecture.processing_status === "completed" ? mockTranscriptSegments : [],
    concepts: lecture.processing_status === "completed" ? mockConcepts : [],
    slides: lecture.processing_status === "completed" ? mockSlides : [],
    processing_path: "audio+slides",
    slide_count: lecture.processing_status === "completed" ? mockSlides.length : null,
  };
}

// ---------------------------------------------------------------------------
// Router — picks mock or real API
// ---------------------------------------------------------------------------

export function withMocks<TArgs extends unknown[], TReturn>(
  mockFn: (...args: TArgs) => Promise<TReturn>,
  realFn: (...args: TArgs) => Promise<TReturn>,
): (...args: TArgs) => Promise<TReturn> {
  return (...args: TArgs) => {
    if (USE_MOCKS) return mockFn(...args);
    return realFn(...args);
  };
}

export {
  mockGetLectures,
  mockGetLecture,
  mockGetLectureDetail,
  mockGetLectureStatus,
  mockUploadLecture,
  mockRetryLecture,
  USE_MOCKS,
};

// ---------------------------------------------------------------------------
// Quiz mock data
// ---------------------------------------------------------------------------

const mockQuizzes: Quiz[] = [
  {
    id: "quiz-1",
    course_id: "course-1",
    title: "Quiz: Midterm 1 Prep",
    status: "ready",
    question_count: 10,
    difficulty: "medium",
    target_assessment_id: null,
    best_score: 85,
    attempt_count: 2,
    created_at: "2026-02-01T10:00:00Z",
  },
  {
    id: "quiz-2",
    course_id: "course-1",
    title: "Practice Quiz - Feb 5",
    status: "generating",
    question_count: 10,
    difficulty: "easy",
    target_assessment_id: null,
    best_score: null,
    attempt_count: 0,
    created_at: "2026-02-05T14:30:00Z",
  },
  {
    id: "quiz-3",
    course_id: "course-1",
    title: "Quick Review: Entropy",
    status: "failed",
    question_count: 5,
    difficulty: "hard",
    target_assessment_id: null,
    best_score: null,
    attempt_count: 0,
    created_at: "2026-02-03T09:15:00Z",
  },
];

const mockQuizQuestions: QuizQuestion[] = [
  {
    id: "q-1",
    quiz_id: "quiz-1",
    question_index: 1,
    question_type: "mcq",
    question_text:
      "What is the primary function of the mitochondria in cellular respiration?",
    options: [
      "It stores genetic information",
      "It produces ATP through oxidative phosphorylation",
      "It synthesizes proteins from mRNA",
      "It regulates cell division",
    ],
    correct_answer: "It produces ATP through oxidative phosphorylation",
    correct_option_index: 1,
    explanation:
      "The mitochondria is known as the powerhouse of the cell because it produces ATP (adenosine triphosphate) through oxidative phosphorylation, which is the primary energy currency of the cell.",
    concept: "Cellular Respiration",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 754,
  },
  {
    id: "q-2",
    quiz_id: "quiz-1",
    question_index: 2,
    question_type: "mcq",
    question_text: "Which law of thermodynamics states that energy cannot be created or destroyed?",
    options: [
      "Zeroth Law",
      "First Law",
      "Second Law",
      "Third Law",
    ],
    correct_answer: "First Law",
    correct_option_index: 1,
    explanation:
      "The First Law of Thermodynamics, also known as the Law of Conservation of Energy, states that energy cannot be created or destroyed in an isolated system.",
    concept: "First Law of Thermodynamics",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 1200,
  },
  {
    id: "q-3",
    quiz_id: "quiz-1",
    question_index: 3,
    question_type: "mcq",
    question_text: "What is entropy a measure of?",
    options: [
      "Temperature of a system",
      "Pressure in a container",
      "Disorder or randomness in a system",
      "Volume of a gas",
    ],
    correct_answer: "Disorder or randomness in a system",
    correct_option_index: 2,
    explanation:
      "Entropy is a thermodynamic quantity representing the unavailability of a system's thermal energy for conversion into mechanical work, often interpreted as the degree of disorder or randomness in the system.",
    concept: "Entropy",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 2100,
  },
  {
    id: "q-4",
    quiz_id: "quiz-1",
    question_index: 4,
    question_type: "mcq",
    question_text: "In an adiabatic process, what is transferred between the system and surroundings?",
    options: [
      "Heat only",
      "Work only",
      "Both heat and work",
      "Neither heat nor work",
    ],
    correct_answer: "Work only",
    correct_option_index: 1,
    explanation:
      "In an adiabatic process, no heat is transferred between the system and its surroundings. Only work can be exchanged.",
    concept: "Adiabatic Process",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 1800,
  },
  {
    id: "q-5",
    quiz_id: "quiz-1",
    question_index: 5,
    question_type: "mcq",
    question_text: "What does the Zeroth Law of Thermodynamics establish?",
    options: [
      "Conservation of energy",
      "Direction of heat flow",
      "Concept of temperature and thermal equilibrium",
      "Absolute zero temperature",
    ],
    correct_answer: "Concept of temperature and thermal equilibrium",
    correct_option_index: 2,
    explanation:
      "The Zeroth Law states that if two systems are each in thermal equilibrium with a third system, they are in thermal equilibrium with each other, establishing the concept of temperature.",
    concept: "Zeroth Law",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 600,
  },
  {
    id: "q-6",
    quiz_id: "quiz-1",
    question_index: 6,
    question_type: "true_false",
    question_text: "In an isothermal process, the temperature of the system remains constant.",
    options: ["True", "False"],
    correct_answer: "True",
    correct_option_index: 0,
    explanation:
      "By definition, an isothermal process occurs at a constant temperature. The system exchanges heat with the surroundings to maintain this temperature.",
    concept: "Isothermal Process",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 1500,
  },
  {
    id: "q-7",
    quiz_id: "quiz-1",
    question_index: 7,
    question_type: "true_false",
    question_text: "Heat always flows from a cold body to a hot body spontaneously.",
    options: ["True", "False"],
    correct_answer: "False",
    correct_option_index: 1,
    explanation:
      "The Second Law of Thermodynamics states that heat spontaneously flows from hot to cold, not the reverse. Energy is required to transfer heat from cold to hot (e.g., refrigeration).",
    concept: "Second Law of Thermodynamics",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 2400,
  },
  {
    id: "q-8",
    quiz_id: "quiz-1",
    question_index: 8,
    question_type: "true_false",
    question_text: "Internal energy is a state function that depends on the path taken.",
    options: ["True", "False"],
    correct_answer: "False",
    correct_option_index: 1,
    explanation:
      "Internal energy is a state function, meaning it depends only on the current state of the system, not on the path taken to reach that state.",
    concept: "Internal Energy",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 900,
  },
  {
    id: "q-9",
    quiz_id: "quiz-1",
    question_index: 9,
    question_type: "short_answer",
    question_text: "What is the formula for the First Law of Thermodynamics? Express it in terms of internal energy (U), heat (Q), and work (W).",
    options: null,
    correct_answer: "ΔU = Q - W",
    correct_option_index: null,
    explanation:
      "The First Law of Thermodynamics is expressed as ΔU = Q - W, where ΔU is the change in internal energy, Q is the heat added to the system, and W is the work done by the system.",
    concept: "First Law of Thermodynamics",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 1300,
  },
  {
    id: "q-10",
    quiz_id: "quiz-1",
    question_index: 10,
    question_type: "short_answer",
    question_text: "Name the thermodynamic process in which no heat exchange occurs between the system and its surroundings.",
    options: null,
    correct_answer: "Adiabatic",
    correct_option_index: null,
    explanation:
      "An adiabatic process is one in which no heat is transferred between the system and its surroundings. The system is thermally insulated.",
    concept: "Adiabatic Process",
    source_lecture_id: "lecture-1",
    source_lecture_title: "Lecture 1: Intro to Thermodynamics",
    source_timestamp_seconds: 1850,
  },
];

let mockQuizGenCallCount = 0;

async function mockGetQuizzes(courseId: string): Promise<Quiz[]> {
  await delay(300);
  return mockQuizzes
    .filter((q) => q.course_id === courseId || courseId === "course-1")
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
}

async function mockGetQuiz(quizId: string): Promise<Quiz> {
  await delay(200);
  const quiz = mockQuizzes.find((q) => q.id === quizId);
  if (!quiz) throw new Error("Quiz not found");
  return quiz;
}

async function mockGetQuizQuestions(quizId: string): Promise<QuizQuestion[]> {
  await delay(300);
  return mockQuizQuestions
    .filter((q) => q.quiz_id === quizId)
    .sort((a, b) => a.question_index - b.question_index);
}

async function mockGenerateQuiz(
  _courseId: string,
  _options: {
    target_assessment_id?: string | null;
    question_count: number;
    difficulty: QuizDifficulty;
  },
): Promise<{ quiz_id: string; status: "generating" }> {
  await delay(500);
  mockQuizGenCallCount = 0;
  return { quiz_id: "quiz-new-1", status: "generating" };
}

async function mockGetQuizGenerationStatus(
  _quizId: string,
): Promise<QuizGenerationStatus> {
  await delay(200);
  mockQuizGenCallCount++;
  const stages = [
    "planning",
    "generating_questions",
    "reviewing_quality",
    "ready",
  ];
  const stageIndex = Math.min(
    Math.floor(mockQuizGenCallCount / 2),
    stages.length - 1,
  );
  if (stages[stageIndex] === "ready") {
    return {
      quiz_id: "quiz-new-1",
      status: "ready",
      stage: null,
      error_message: null,
    };
  }
  return {
    quiz_id: "quiz-new-1",
    status: "generating",
    stage: stages[stageIndex],
    error_message: null,
  };
}

async function mockSubmitQuiz(
  _quizId: string,
  answers: QuizAnswer[],
): Promise<QuizSubmissionResult> {
  await delay(500);
  const questions = mockQuizQuestions.filter((q) => q.quiz_id === "quiz-1");
  const questionResults: QuestionResult[] = questions.map((q) => {
    const answer = answers.find((a) => a.question_id === q.id);
    const studentAnswer = answer?.student_answer ?? "";
    let isCorrect = false;
    if (studentAnswer && q.correct_option_index != null && q.options) {
      isCorrect = q.options.indexOf(studentAnswer) === q.correct_option_index;
    } else if (studentAnswer && q.correct_answer) {
      isCorrect =
        studentAnswer.trim().toLowerCase() ===
        q.correct_answer.trim().toLowerCase();
    }
    return {
      question_id: q.id,
      is_correct: isCorrect,
      student_answer: answer?.student_answer ?? "",
      correct_answer: q.correct_answer ?? "",
      explanation: q.explanation ?? "",
      question_text: q.question_text,
      question_type: q.question_type,
      options: q.options,
    };
  });

  const correctCount = questionResults.filter((r) => r.is_correct).length;

  return {
    score: Math.round((correctCount / questions.length) * 100),
    total_questions: questions.length,
    correct_count: correctCount,
    results: questionResults,
  };
}

export {
  mockGetQuizzes,
  mockGetQuiz,
  mockGetQuizQuestions,
  mockGenerateQuiz,
  mockGetQuizGenerationStatus,
  mockSubmitQuiz,
};

// ---------------------------------------------------------------------------
// Search mock data
// ---------------------------------------------------------------------------

const mockSearchResults: SearchResult[] = [
  {
    id: "sr-1",
    lecture_id: "lecture-1",
    lecture_title: "Lecture 1: Intro to Thermodynamics",
    lecture_number: 1,
    chunk_type: "transcript",
    content_snippet:
      "The zeroth law of thermodynamics establishes the concept of thermal equilibrium. If system A is in equilibrium with system C, and system B is also in equilibrium with system C, then A and B are in...",
    highlighted_snippet: "",
    timestamp_seconds: 600,
    slide_number: null,
    relevance_score: 0.95,
  },
  {
    id: "sr-2",
    lecture_id: "lecture-1",
    lecture_title: "Lecture 1: Intro to Thermodynamics",
    lecture_number: 1,
    chunk_type: "slide",
    content_snippet:
      "Slide 4: Types of Thermodynamic Systems. Open systems exchange both matter and energy. Closed systems exchange energy only. Isolated systems exchange neither matter nor energy with surroundings.",
    highlighted_snippet: "",
    timestamp_seconds: null,
    slide_number: 4,
    relevance_score: 0.88,
  },
  {
    id: "sr-3",
    lecture_id: "lecture-2",
    lecture_title: "Lecture 2: Heat and Work",
    lecture_number: 2,
    chunk_type: "transcript",
    content_snippet:
      "Work and heat are both forms of energy transfer. The key difference is that work is an organized transfer of energy while heat is a disorganized transfer driven by temperature difference between...",
    highlighted_snippet: "",
    timestamp_seconds: 1200,
    slide_number: null,
    relevance_score: 0.82,
  },
  {
    id: "sr-4",
    lecture_id: "lecture-1",
    lecture_title: "Lecture 1: Intro to Thermodynamics",
    lecture_number: 1,
    chunk_type: "concept",
    content_snippet:
      "Thermal Equilibrium: A state where two or more systems in thermal contact no longer exchange net heat energy. This is the foundational concept for defining temperature measurement scales.",
    highlighted_snippet: "",
    timestamp_seconds: 750,
    slide_number: null,
    relevance_score: 0.78,
  },
  {
    id: "sr-5",
    lecture_id: "lecture-2",
    lecture_title: "Lecture 2: Heat and Work",
    lecture_number: 2,
    chunk_type: "slide",
    content_snippet:
      "Slide 8: Path Functions vs State Functions. Heat (Q) and Work (W) are path functions. Internal Energy (U), Entropy (S), Enthalpy (H) are state functions that depend only on the current state.",
    highlighted_snippet: "",
    timestamp_seconds: null,
    slide_number: 8,
    relevance_score: 0.71,
  },
];

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightSnippet(snippet: string, query: string): string {
  if (!query.trim()) return snippet;
  const terms = query
    .trim()
    .split(/\s+/)
    .filter((t) => t.length > 2);
  if (terms.length === 0) return snippet;
  const regex = new RegExp(`(${terms.map(escapeRegex).join("|")})`, "gi");
  return snippet.replace(regex, "<mark>$1</mark>");
}

async function mockSearchLectures(
  _courseId: string,
  query: string,
  lectureId?: string | null,
): Promise<SearchResponse> {
  await delay(400);
  if (!query.trim()) return { query, results: [], total_count: 0 };
  let filtered: SearchResult[] = mockSearchResults;
  if (lectureId) {
    filtered = filtered.filter((r) => r.lecture_id === lectureId);
  }
  const withHighlights = filtered.map((r) => ({
    ...r,
    highlighted_snippet: highlightSnippet(r.content_snippet, query),
  }));
  return { query, results: withHighlights, total_count: withHighlights.length };
}

// ---------------------------------------------------------------------------
// Q&A mock data
// ---------------------------------------------------------------------------

async function mockAskQuestion(
  _courseId: string,
  question: string,
  _lectureIds?: string[],
): Promise<QAResponse> {
  await delay(1500);
  const isEntropy = question.toLowerCase().includes("entropy");
  return {
    answer: isEntropy
      ? "Entropy is a measure of disorder or randomness in a system. The Second Law of Thermodynamics states that the total entropy of an isolated system always increases over time. [Source 1] This means that natural processes tend to move toward a state of maximum disorder. The concept was first introduced by Rudolf Clausius in 1865. [Source 2]"
      : "Based on the lecture materials, the key insight is that energy transfer between systems follows well-defined conservation laws. The First Law of Thermodynamics establishes that energy cannot be created or destroyed. [Source 1] This was covered in detail during the discussion of state functions and their properties. [Source 2]",
    citations: [
      {
        id: "cit-1",
        lecture_id: "lecture-1",
        lecture_title: "Lecture 1: Intro to Thermodynamics",
        timestamp_seconds: 1200,
        slide_number: null,
        content_preview:
          "The first law of thermodynamics establishes that energy is conserved in any thermodynamic process...",
      },
      {
        id: "cit-2",
        lecture_id: "lecture-2",
        lecture_title: "Lecture 2: Heat and Work",
        timestamp_seconds: 900,
        slide_number: 6,
        content_preview:
          "State functions depend only on the current state of the system, not on the path taken...",
      },
    ],
    follow_ups: [
      "How does this relate to the Second Law?",
      "Can you explain with a real-world example?",
      "What are the mathematical implications?",
    ],
    confidence: 0.87,
  };
}

export { mockSearchLectures, mockAskQuestion };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
