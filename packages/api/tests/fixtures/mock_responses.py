"""Mock Gemini API responses for testing."""

MOCK_TRANSCRIPT = [
    {"start": 0.0, "end": 15.5, "text": "Welcome to today's lecture on thermodynamics.", "speaker": "professor"},
    {"start": 15.5, "end": 35.2, "text": "We'll begin by defining what a thermodynamic system is.", "speaker": "professor"},
    {"start": 35.2, "end": 60.0, "text": "A system is defined by its boundaries.", "speaker": "professor"},
    {"start": 60.0, "end": 85.5, "text": "The first law states that energy cannot be created or destroyed.", "speaker": "professor"},
    {"start": 85.5, "end": 110.0, "text": "This means the total energy of an isolated system remains constant.", "speaker": "professor"},
    {"start": 110.0, "end": 135.5, "text": "Let's look at heat transfer mechanisms.", "speaker": "professor"},
    {"start": 135.5, "end": 160.0, "text": "There are three types: conduction, convection, and radiation.", "speaker": "professor"},
    {"start": 160.0, "end": 185.5, "text": "Professor, can you explain conduction in more detail?", "speaker": "student"},
    {"start": 185.5, "end": 220.0, "text": "Of course. Conduction occurs when heat flows through a material.", "speaker": "professor"},
    {"start": 220.0, "end": 250.0, "text": "For homework, read chapter 2 and complete problems 1 through 5.", "speaker": "professor"},
]

MOCK_SLIDE_ANALYSIS = [
    {"slide_number": 1, "title": "Introduction to Thermodynamics", "text_content": "PHYS 201 - Lecture 1\nDr. Smith", "visual_description": None, "has_diagram": False, "has_code": False, "has_equation": False},
    {"slide_number": 2, "title": "Thermodynamic Systems", "text_content": "A system is a region of space defined by its boundaries.\n- Open system\n- Closed system\n- Isolated system", "visual_description": "Diagram showing three boxes representing open, closed, and isolated systems with arrows indicating energy and matter flow", "has_diagram": True, "has_code": False, "has_equation": False},
    {"slide_number": 3, "title": "First Law of Thermodynamics", "text_content": "Energy cannot be created or destroyed.\nΔU = Q - W", "visual_description": None, "has_diagram": False, "has_code": False, "has_equation": True},
    {"slide_number": 4, "title": "Heat Transfer", "text_content": "Three mechanisms:\n1. Conduction\n2. Convection\n3. Radiation", "visual_description": "Three panels showing conduction through a metal bar, convection currents in a pot of water, and radiation from the sun", "has_diagram": True, "has_code": False, "has_equation": False},
    {"slide_number": 5, "title": "Homework", "text_content": "Read Chapter 2\nProblems 1-5", "visual_description": None, "has_diagram": False, "has_code": False, "has_equation": False},
]

MOCK_CONCEPTS = [
    {"title": "Thermodynamic System", "description": "A region of space defined by boundaries that separates the system from its surroundings.", "category": "definition", "difficulty_estimate": 0.3, "related_concepts": ["First Law of Thermodynamics", "Heat Transfer"]},
    {"title": "First Law of Thermodynamics", "description": "Energy cannot be created or destroyed; the total energy of an isolated system remains constant. Expressed as ΔU = Q - W.", "category": "theorem", "difficulty_estimate": 0.5, "related_concepts": ["Internal Energy", "Heat Transfer", "Work-Energy Equivalence"]},
    {"title": "Heat Transfer", "description": "The movement of thermal energy from one system to another through conduction, convection, or radiation.", "category": "process", "difficulty_estimate": 0.4, "related_concepts": ["First Law of Thermodynamics", "Conduction"]},
    {"title": "Internal Energy", "description": "The total energy contained within a thermodynamic system, including kinetic and potential energy of molecules.", "category": "concept", "difficulty_estimate": 0.5, "related_concepts": ["First Law of Thermodynamics"]},
    {"title": "Conduction", "description": "Heat transfer through direct contact between molecules in a material.", "category": "process", "difficulty_estimate": 0.3, "related_concepts": ["Heat Transfer"]},
]

MOCK_RAG_ANSWER = {
    "answer": "According to the lecture, heat transfer occurs through three mechanisms: conduction, convection, and radiation [Lecture 1, 2:15]. Conduction specifically occurs when heat flows through a material via direct molecular contact [Lecture 1, 3:05].",
    "confidence": 0.92,
    "source_chunks": ["chunk-0006-0000-0000-000000000000", "chunk-0008-0000-0000-000000000000"],
    "follow_up_suggestions": [
        "What is the difference between conduction and convection?",
        "How does the first law of thermodynamics relate to heat transfer?",
    ]
}

MOCK_QUIZ_QUESTIONS = [
    {
        "concept_id": "concept-0000-0000-0000-000000000000",
        "question_type": "mcq",
        "question_text": "According to the lecture, which of the following best describes a thermodynamic system?",
        "options": [
            {"label": "A", "text": "A region of space defined by its boundaries", "is_correct": True},
            {"label": "B", "text": "Any object that produces heat", "is_correct": False},
            {"label": "C", "text": "A machine that converts energy", "is_correct": False},
            {"label": "D", "text": "A chemical reaction in equilibrium", "is_correct": False},
        ],
        "correct_answer": "A",
        "explanation": "The lecture defined a thermodynamic system as 'a region of space defined by its boundaries' that separates the system from its surroundings.",
        "source_chunk_ids": ["chunk-0001-0000-0000-000000000000"],
        "difficulty": 0.3,
    },
    {
        "concept_id": "concept-0001-0000-0000-000000000000",
        "question_type": "true_false",
        "question_text": "The first law of thermodynamics states that energy can be created but not destroyed.",
        "options": [
            {"label": "True", "text": "True", "is_correct": False},
            {"label": "False", "text": "False", "is_correct": True},
        ],
        "correct_answer": "False",
        "explanation": "The first law states energy CANNOT be created OR destroyed. The total energy of an isolated system remains constant.",
        "source_chunk_ids": ["chunk-0003-0000-0000-000000000000"],
        "difficulty": 0.4,
    },
]