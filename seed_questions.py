"""
seed_questions.py
─────────────────
Seeds sample MCQ questions into Firestore using topic_ids derived from
the cbse_9.py / cbse_10.py syllabus data structures.

Run: python seed_questions.py
Requires firebase_config.py and serviceAccountKey.json in project root.

topic_id format (must match test_system.make_topic_id):
  "{board}_{grade}_{subject-slug}_{chapter-slug}_{topic-slug}"
  slugify: lowercase, strip "'"/\, collapse non-alnum to '-'

  e.g. "cbse_9_mathematics_number-systems_real-numbers"
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from test_system import test_system

ts = test_system   # singleton

def tid(board, grade, subject, chapter, topic):
    return ts.make_topic_id(board, grade, subject, chapter, topic)

# ─────────────────────────────────────────────────────────────────────────────
# CBSE 9 — Mathematics
# ─────────────────────────────────────────────────────────────────────────────

MATH_9_NS_RN = tid("cbse","9","Mathematics","Number Systems","Real Numbers")
MATH_9_NS_ED = tid("cbse","9","Mathematics","Introduction to Euclid's Geometry","Geometric Axioms")
MATH_9_POLY  = tid("cbse","9","Mathematics","Polynomials","Algebraic Expressions")
MATH_9_CG_A  = tid("cbse","9","Mathematics","Coordinate Geometry","Cartesian Plane")
MATH_9_LE    = tid("cbse","9","Mathematics","Linear Equations in Two Variables","Graphical Solutions")

# CBSE 9 — Science
SCI_9_MATTER = tid("cbse","9","Science","Matter in Our Surroundings","States of Matter")
SCI_9_ATOM   = tid("cbse","9","Science","Atoms and Molecules","Atomic Structure")
SCI_9_MOTION = tid("cbse","9","Science","Motion","Kinematics")

# CBSE 10 — Mathematics
MATH_10_RN   = tid("cbse","10","Mathematics","Real Numbers","Euclid's Division Lemma")
MATH_10_TRI  = tid("cbse","10","Mathematics","Triangles","Similarity Criteria")
MATH_10_POLY  = tid("cbse","10","Mathematics","Polynomials","Geometric Meaning of Zeros")
MATH_10_LE    = tid("cbse","10","Mathematics","Pair of Linear Equations in Two Variables","Graphical Solutions")
MATH_10_QUAD  = tid("cbse","10","Mathematics","Quadratic Equations","Quadratic Formula")
MATH_10_AP    = tid("cbse","10","Mathematics","Arithmetic Progressions","AP Properties")
MATH_10_CG    = tid("cbse","10","Mathematics","Coordinate Geometry","Distance and Section Formulas")
MATH_10_TRIG  = tid("cbse","10","Mathematics","Introduction to Trigonometry","Trigonometric Ratios")
MATH_10_STATS = tid("cbse","10","Mathematics","Statistics","Data Organization")
MATH_10_PROB  = tid("cbse","10","Mathematics","Probability","Basic Probability")

# CBSE 10 — Science
SCI_10_CHEM  = tid("cbse","10","Science","Chemical Reactions and Equations","Types of Reactions")
SCI_10_ELEC  = tid("cbse","10","Science","Electricity","Electric Circuits")
SCI_10_ACID  = tid("cbse","10","Science","Acids, Bases, and Salts","pH and Neutralization")
SCI_10_MET   = tid("cbse","10","Science","Metals and Non Metals","Properties and Uses")
SCI_10_CAR   = tid("cbse","10","Science","Carbon and Its Compounds","Organic Chemistry Basics")
SCI_10_LIFE  = tid("cbse","10","Science","Life Processes","Living Organisms")
SCI_10_HER   = tid("cbse","10","Science","Heredity and Evolution","Periodic Trends")


QUESTIONS = [

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 9 · Mathematics · Number Systems · Real Numbers
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{MATH_9_NS_RN}_001", "topic_id": MATH_9_NS_RN,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Number Systems",
      "text": "Which of the following is an irrational number?",
      "options": ["√4", "√9", "√2", "22/7"],
      "correct_option_index": 2, "difficulty": "easy",
      "explanation": "√2 is non-terminating, non-repeating — it cannot be written as p/q. "
                     "√4 = 2, √9 = 3 are rational. 22/7 is a rational approximation of π." },

    { "question_id": f"{MATH_9_NS_RN}_002", "topic_id": MATH_9_NS_RN,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Number Systems",
      "text": "The decimal expansion of 1/7 is:",
      "options": ["Terminating", "Non-terminating repeating", "Non-terminating non-repeating", "Finite"],
      "correct_option_index": 1, "difficulty": "easy",
      "explanation": "1/7 = 0.142857̄  — non-terminating but the block 142857 repeats, making it rational." },

    { "question_id": f"{MATH_9_NS_RN}_003", "topic_id": MATH_9_NS_RN,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Number Systems",
      "text": "Between any two distinct real numbers there are:",
      "options": ["No rational numbers", "Exactly one rational number", "Infinitely many rational numbers", "Only irrational numbers"],
      "correct_option_index": 2, "difficulty": "medium",
      "explanation": "The rationals are dense in ℝ — between any two reals there are infinitely many rationals. "
                     "This is the density property of rational numbers." },

    { "question_id": f"{MATH_9_NS_RN}_004", "topic_id": MATH_9_NS_RN,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Number Systems",
      "text": "√2 × √2 equals:",
      "options": ["√4", "2", "4", "√8"],
      "correct_option_index": 1, "difficulty": "easy",
      "explanation": "√2 × √2 = (√2)² = 2. This also shows the product of two irrational numbers can be rational." },

    { "question_id": f"{MATH_9_NS_RN}_005", "topic_id": MATH_9_NS_RN,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Number Systems",
      "text": "Which statement about irrational numbers is CORRECT?",
      "options": [
          "Their decimal expansion terminates",
          "Their decimal expansion repeats",
          "Their decimal expansion neither terminates nor repeats",
          "They can always be expressed as p/q"
      ],
      "correct_option_index": 2, "difficulty": "medium",
      "explanation": "Irrational numbers have non-terminating, non-repeating decimal expansions — "
                     "that's the defining characteristic that distinguishes them from rationals." },

    { "question_id": f"{MATH_9_NS_RN}_006", "topic_id": MATH_9_NS_RN,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Number Systems",
      "text": "Which of the following correctly places numbers on the number line in ascending order?",
      "options": ["√2, π, 1, 2", "1, √2, π, 2", "1, √2, 2, π", "π, 2, √2, 1"],
      "correct_option_index": 2, "difficulty": "hard",
      "explanation": "1 < √2 (≈1.414) < 2 < π (≈3.14). Knowing decimal approximations helps place irrationals." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 9 · Mathematics · Introduction to Euclid's Geometry · Geometric Axioms
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{MATH_9_NS_ED}_001", "topic_id": MATH_9_NS_ED,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Introduction to Euclid's Geometry",
      "text": "Euclid's geometry is based on:",
      "options": ["Axioms and postulates", "Algebraic equations", "Coordinate geometry", "Trigonometric ratios"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Euclid's geometry is built on a foundation of axioms (self-evident truths) and postulates (assumptions specific to geometry)." },

    { "question_id": f"{MATH_9_NS_ED}_002", "topic_id": MATH_9_NS_ED,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Introduction to Euclid's Geometry",
      "text": "Which of the following is an Euclidean axiom?",
      "options": ["Things which are equal to the same thing are equal to one another", "The whole is greater than the part", "Given any two points, there is exactly one line passing through them", "All of the above"],
      "correct_option_index": 3, "difficulty": "medium",
      "explanation": "All these are fundamental Euclidean axioms that form the basis of his geometric system." },

    { "question_id": f"{MATH_9_NS_ED}_003", "topic_id": MATH_9_NS_ED,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Introduction to Euclid's Geometry",
      "text": "A postulate in Euclidean geometry is:",
      "options": ["A self-evident truth", "An assumption specific to geometry", "A proven theorem", "A definition"],
      "correct_option_index": 1, "difficulty": "easy",
      "explanation": "Postulates are geometric assumptions specific to Euclid's system, while axioms are universal truths." },

    { "question_id": f"{MATH_9_NS_ED}_004", "topic_id": MATH_9_NS_ED,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Introduction to Euclid's Geometry",
      "text": "Euclid's fifth postulate is about:",
      "options": ["Parallel lines", "Circle properties", "Triangle congruence", "Angle sums"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "The fifth postulate (parallel postulate) states that through a point not on a line, there is exactly one line parallel to the given line." },

    { "question_id": f"{MATH_9_NS_ED}_005", "topic_id": MATH_9_NS_ED,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Introduction to Euclid's Geometry",
      "text": "The statement 'The whole is greater than the part' is:",
      "options": ["An axiom", "A postulate", "A theorem", "A definition"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "This is one of Euclid's common axioms that apply not just to geometry but to all quantities." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 9 · Mathematics · Polynomials · Algebraic Expressions
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{MATH_9_POLY}_001", "topic_id": MATH_9_POLY,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Polynomials",
      "text": "Which of the following is an algebraic expression?",
      "options": ["2x + 3y", "x = 5", "4 > 2", "√16 = 4"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "An algebraic expression combines numbers, variables, and operations without an equality sign." },

    { "question_id": f"{MATH_9_POLY}_002", "topic_id": MATH_9_POLY,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Polynomials",
      "text": "The coefficient of x² in 3x² - 5x + 7 is:",
      "options": ["3", "-5", "7", "0"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "The coefficient is the numerical factor multiplied by the variable term. Here it's 3." },

    { "question_id": f"{MATH_9_POLY}_003", "topic_id": MATH_9_POLY,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Polynomials",
      "text": "Which term makes 2x² + ___ - 4 a perfect square trinomial?",
      "options": ["4x", "-4x", "0", "2x"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "2x² + 4x - 4 = 2(x² + 2x - 2). For a perfect square, we need (x + 1)² = x² + 2x + 1, so the missing term should be 4x." },

    { "question_id": f"{MATH_9_POLY}_004", "topic_id": MATH_9_POLY,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Polynomials",
      "text": "Factorizing x² - 9 gives:",
      "options": ["(x-3)(x+3)", "(x-3)²", "(x+3)²", "(x-9)(x+1)"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "x² - 9 is a difference of squares: a² - b² = (a-b)(a+b). Here a=x, b=3." },

    { "question_id": f"{MATH_9_POLY}_005", "topic_id": MATH_9_POLY,
      "board": "cbse", "grade": "9", "subject": "Mathematics",
      "chapter": "Polynomials",
      "text": "The expression (x+2)(x-3) expands to:",
      "options": ["x² - x - 6", "x² + x - 6", "x² - x + 6", "x² + x + 6"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Use FOIL: (x)(x) + (x)(-3) + (2)(x) + (2)(-3) = x² - 3x + 2x - 6 = x² - x - 6." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 9 · Science · Matter in Our Surroundings · States of Matter
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{SCI_9_MATTER}_001", "topic_id": SCI_9_MATTER,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Matter in Our Surroundings",
      "text": "Which state of matter has a definite shape AND definite volume?",
      "options": ["Gas", "Liquid", "Solid", "Plasma"],
      "correct_option_index": 2, "difficulty": "easy",
      "explanation": "Solids have fixed shape and volume — particles are tightly packed in regular arrangement." },

    { "question_id": f"{SCI_9_MATTER}_002", "topic_id": SCI_9_MATTER,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Matter in Our Surroundings",
      "text": "Gas converting directly to solid (without passing through liquid) is called:",
      "options": ["Evaporation", "Sublimation", "Condensation", "Deposition"],
      "correct_option_index": 3, "difficulty": "medium",
      "explanation": "Deposition is gas→solid directly. Sublimation is the reverse (solid→gas). Example: frost forming." },

    { "question_id": f"{SCI_9_MATTER}_003", "topic_id": SCI_9_MATTER,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Matter in Our Surroundings",
      "text": "Latent heat of vaporisation is the heat required to:",
      "options": [
          "Raise temperature of a liquid by 1°C",
          "Convert 1 kg of liquid to vapour at its boiling point without temperature change",
          "Convert 1 kg of solid to liquid",
          "Lower the boiling point of water"
      ],
      "correct_option_index": 1, "difficulty": "medium",
      "explanation": "Latent (hidden) heat changes state at constant temperature — no thermometer change occurs." },

    { "question_id": f"{SCI_9_MATTER}_004", "topic_id": SCI_9_MATTER,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Matter in Our Surroundings",
      "text": "The boiling point of water at standard atmospheric pressure is:",
      "options": ["0°C", "37°C", "100°C", "373°C"],
      "correct_option_index": 2, "difficulty": "easy",
      "explanation": "Water boils at 100°C (373 K) at 1 atm standard pressure." },

    { "question_id": f"{SCI_9_MATTER}_005", "topic_id": SCI_9_MATTER,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Matter in Our Surroundings",
      "text": "Dry ice is solid CO₂. On heating at room pressure it undergoes:",
      "options": ["Melting then boiling", "Only melting", "Sublimation", "Deposition"],
      "correct_option_index": 2, "difficulty": "hard",
      "explanation": "Dry ice sublimes directly from solid to gas at room pressure — it skips the liquid phase entirely." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 9 · Science · Atoms and Molecules · Atomic Structure
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{SCI_9_ATOM}_001", "topic_id": SCI_9_ATOM,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Atoms and Molecules",
      "text": "Who proposed the atomic theory that matter is made of indivisible particles?",
      "options": ["Dalton", "Rutherford", "Thomson", "Bohr"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "John Dalton proposed the atomic theory stating that matter consists of indivisible atoms." },

    { "question_id": f"{SCI_9_ATOM}_002", "topic_id": SCI_9_ATOM,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Atoms and Molecules",
      "text": "The discovery of electrons was made by:",
      "options": ["J.J. Thomson", "Rutherford", "Goldstein", "Chadwick"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "J.J. Thomson discovered electrons through cathode ray tube experiments, proposing the plum pudding model." },

    { "question_id": f"{SCI_9_ATOM}_003", "topic_id": SCI_9_ATOM,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Atoms and Molecules",
      "text": "The nucleus of an atom contains:",
      "options": ["Protons and neutrons", "Protons and electrons", "Neutrons and electrons", "Only protons"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "The nucleus contains positively charged protons and neutral neutrons, while electrons orbit the nucleus." },

    { "question_id": f"{SCI_9_ATOM}_004", "topic_id": SCI_9_ATOM,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Atoms and Molecules",
      "text": "An atom with 6 protons and 6 neutrons has an atomic mass of:",
      "options": ["6 u", "12 u", "18 u", "0 u"],
      "correct_option_index": 1, "difficulty": "medium",
      "explanation": "Atomic mass = number of protons + number of neutrons = 6 + 6 = 12 atomic mass units." },

    { "question_id": f"{SCI_9_ATOM}_005", "topic_id": SCI_9_ATOM,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Atoms and Molecules",
      "text": "Which subatomic particle determines the chemical properties of an element?",
      "options": ["Electrons", "Protons", "Neutrons", "Nucleus"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "Electrons in the outermost shell determine how atoms bond and react, defining chemical properties." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 9 · Science · Motion · Kinematics
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{SCI_9_MOTION}_001", "topic_id": SCI_9_MOTION,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Motion",
      "text": "Distance is a scalar quantity because it:",
      "options": ["Has only magnitude", "Has both magnitude and direction", "Is always positive", "Is measured in meters"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Scalar quantities have only magnitude, while vector quantities have both magnitude and direction." },

    { "question_id": f"{SCI_9_MOTION}_002", "topic_id": SCI_9_MOTION,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Motion",
      "text": "Displacement can be zero when:",
      "options": ["An object returns to its starting point", "An object moves in a straight line", "An object is at rest", "An object moves with uniform speed"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "Displacement is the change in position. If an object returns to its starting point, the net change is zero." },

    { "question_id": f"{SCI_9_MOTION}_003", "topic_id": SCI_9_MOTION,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Motion",
      "text": "The SI unit of velocity is:",
      "options": ["m/s", "m/s²", "m", "km/h"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Velocity is displacement per unit time, so its SI unit is meters per second (m/s)." },

    { "question_id": f"{SCI_9_MOTION}_004", "topic_id": SCI_9_MOTION,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Motion",
      "text": "Uniform motion means:",
      "options": ["Equal distances in equal time intervals", "Increasing speed", "Decreasing speed", "Zero acceleration only"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Uniform motion occurs when an object covers equal distances in equal intervals of time, maintaining constant speed." },

    { "question_id": f"{SCI_9_MOTION}_005", "topic_id": SCI_9_MOTION,
      "board": "cbse", "grade": "9", "subject": "Science",
      "chapter": "Motion",
      "text": "A car travels 60 km in 2 hours. Its average speed is:",
      "options": ["30 km/h", "60 km/h", "120 km/h", "15 km/h"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Average speed = total distance ÷ total time = 60 km ÷ 2 h = 30 km/h." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 10 · Mathematics · Polynomials · Geometric Meaning of Zeros
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{MATH_10_POLY}_001", "topic_id": MATH_10_POLY,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Polynomials",
      "text": "The zeros of a polynomial are the points where:",
      "options": ["The polynomial equals zero", "The polynomial is maximum", "The polynomial is minimum", "The polynomial changes direction"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Zeros of a polynomial are the x-values where the polynomial evaluates to zero." },

    { "question_id": f"{MATH_10_POLY}_002", "topic_id": MATH_10_POLY,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Polynomials",
      "text": "The graph of y = (x-2)(x+3) crosses the x-axis at:",
      "options": ["x = 2 and x = -3", "x = -2 and x = 3", "x = 0 only", "x = 1 only"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "Setting each factor to zero gives x-2=0 → x=2 and x+3=0 → x=-3." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 10 · Mathematics · Linear Equations · Graphical Solutions
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{MATH_10_LE}_001", "topic_id": MATH_10_LE,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Pair of Linear Equations in Two Variables",
      "text": "The point of intersection of 2x + y = 4 and x + y = 3 is:",
      "options": ["(1, 2)", "(2, 1)", "(3, 0)", "(0, 3)"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "Solving simultaneously: subtract second equation from first gives x=1, then y=2." },

    { "question_id": f"{MATH_10_LE}_002", "topic_id": MATH_10_LE,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Pair of Linear Equations in Two Variables",
      "text": "Two linear equations are consistent if they:",
      "options": ["Have exactly one solution", "Have no solution", "Have infinitely many solutions", "Are parallel lines"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Consistent linear equations have exactly one point of intersection." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 10 · Science · Acids, Bases, and Salts · pH and Neutralization
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{SCI_10_ACID}_001", "topic_id": SCI_10_ACID,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Acids, Bases, and Salts",
      "text": "A solution with pH 7 is:",
      "options": ["Strongly acidic", "Neutral", "Strongly basic", "Weakly acidic"],
      "correct_option_index": 1, "difficulty": "easy",
      "explanation": "pH 7 is neutral - neither acidic nor basic. Pure water has pH 7." },

    { "question_id": f"{SCI_10_ACID}_002", "topic_id": SCI_10_ACID,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Acids, Bases, and Salts",
      "text": "When an acid reacts with a base, the products are:",
      "options": ["Salt and hydrogen gas", "Salt and water", "Water and oxygen gas", "Hydrogen and oxygen gas"],
      "correct_option_index": 1, "difficulty": "easy",
      "explanation": "Acid + Base → Salt + Water is the neutralization reaction." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 10 · Science · Metals and Non Metals · Properties and Uses
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{SCI_10_MET}_001", "topic_id": SCI_10_MET,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Metals and Non Metals",
      "text": "Which of the following is a property of metals?",
      "options": ["Good conductors of heat", "Brittle", "Poor conductors of electricity", "Low melting points"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "Metals are generally good conductors of both heat and electricity." },

    { "question_id": f"{SCI_10_MET}_002", "topic_id": SCI_10_MET,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Metals and Non Metals",
      "text": "Sodium metal reacts vigorously with:",
      "options": ["Cold water", "Air", "Nitrogen gas", "Carbon dioxide"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "Sodium reacts vigorously with cold water, producing hydrogen gas and heat." },
    { "question_id": f"{MATH_10_TRI}_001", "topic_id": MATH_10_TRI,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Triangles",
      "text": "Two triangles are similar if their corresponding:",
      "options": ["Angles are equal", "Sides are equal", "Areas are equal", "Perimeters are equal"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "For similar triangles, corresponding angles must be equal. This is the AA (Angle-Angle) similarity criterion." },

    { "question_id": f"{MATH_10_TRI}_002", "topic_id": MATH_10_TRI,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Triangles",
      "text": "In similar triangles, the ratio of corresponding sides is:",
      "options": ["Constant", "Variable", "Zero", "Infinity"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "In similar triangles, all corresponding sides are in the same constant ratio, called the scale factor." },

    { "question_id": f"{MATH_10_TRI}_003", "topic_id": MATH_10_TRI,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Triangles",
      "text": "The Pythagorean theorem is related to:",
      "options": ["Right-angled triangles", "Equilateral triangles", "Isosceles triangles", "All triangles"],
      "correct_option_index": 0, "difficulty": "easy",
      "explanation": "The Pythagorean theorem (a² + b² = c²) applies specifically to right-angled triangles." },

    { "question_id": f"{MATH_10_TRI}_004", "topic_id": MATH_10_TRI,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Triangles",
      "text": "If two triangles are similar with a ratio of 2:3, their areas are in the ratio:",
      "options": ["4:9", "2:3", "8:27", "1:1"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "If similar triangles have side ratio a:b, their areas are in ratio a²:b². Here (2)²:(3)² = 4:9." },

    { "question_id": f"{MATH_10_TRI}_005", "topic_id": MATH_10_TRI,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Triangles",
      "text": "Which of these is NOT a similarity criterion for triangles?",
      "options": ["SSS", "AAA", "SAS", "RHS"],
      "correct_option_index": 3, "difficulty": "medium",
      "explanation": "RHS (Right angle-Hypotenuse-Side) is a congruence criterion, not a similarity criterion. Similarity criteria are AA, SAS, and SSS." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 10 · Mathematics · Real Numbers · Euclid's Division Lemma
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{MATH_10_RN}_001", "topic_id": MATH_10_RN,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Real Numbers",
      "text": "The HCF of 96 and 404 using Euclid's algorithm is:",
      "options": ["4", "8", "12", "96"],
      "correct_option_index": 0, "difficulty": "medium",
      "explanation": "404 = 96×4+20; 96 = 20×4+16; 20 = 16×1+4; 16 = 4×4+0. Last non-zero remainder = 4." },

    { "question_id": f"{MATH_10_RN}_002", "topic_id": MATH_10_RN,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Real Numbers",
      "text": "1.272727... (where 27 repeats) expressed as a fraction is:",
      "options": ["127/99", "14/11", "127/100", "13/10"],
      "correct_option_index": 1, "difficulty": "medium",
      "explanation": "Let x=1.272727…; 100x=127.2727…; 99x=126; x=126/99=14/11." },

    { "question_id": f"{MATH_10_RN}_003", "topic_id": MATH_10_RN,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Real Numbers",
      "text": "The Fundamental Theorem of Arithmetic states that every composite number:",
      "options": [
          "Has exactly two factors",
          "Can be expressed as a unique product of primes (up to order)",
          "Is divisible by 2",
          "Has at least one irrational factor"
      ],
      "correct_option_index": 1, "difficulty": "easy",
      "explanation": "Every integer > 1 is either prime or a unique product of primes — the fundamental theorem." },

    { "question_id": f"{MATH_10_RN}_004", "topic_id": MATH_10_RN,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Real Numbers",
      "text": "If LCM(a, b) = 2520 and HCF = 12, and a = 36, then b =",
      "options": ["70", "840", "630", "420"],
      "correct_option_index": 1, "difficulty": "hard",
      "explanation": "b = (LCM × HCF) / a = (2520 × 12) / 36 = 30240 / 36 = 840." },

    { "question_id": f"{MATH_10_RN}_005", "topic_id": MATH_10_RN,
      "board": "cbse", "grade": "10", "subject": "Mathematics",
      "chapter": "Real Numbers",
      "text": "The decimal expansion of 17/8 is:",
      "options": ["Non-terminating repeating", "Terminating", "Non-terminating non-repeating", "Cannot be determined"],
      "correct_option_index": 1, "difficulty": "easy",
      "explanation": "8 = 2³ — denominator has only factor 2, so 17/8 = 2.125, a terminating decimal." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 10 · Science · Chemical Reactions and Equations · Types of Reactions
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{SCI_10_CHEM}_001", "topic_id": SCI_10_CHEM,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Chemical Reactions and Equations",
      "text": "The reaction between an acid and base to form salt + water is called:",
      "options": ["Decomposition", "Displacement", "Neutralisation", "Combination"],
      "correct_option_index": 2, "difficulty": "easy",
      "explanation": "Acid + Base → Salt + Water is the classic neutralisation reaction. HCl + NaOH → NaCl + H₂O." },

    { "question_id": f"{SCI_10_CHEM}_002", "topic_id": SCI_10_CHEM,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Chemical Reactions and Equations",
      "text": "CuO + H₂ → Cu + H₂O is an example of:",
      "options": ["Only oxidation", "Only reduction", "Redox reaction", "Double displacement"],
      "correct_option_index": 2, "difficulty": "hard",
      "explanation": "Cu²⁺ is reduced to Cu⁰; H⁰ is oxidised to H⁺. Both occur simultaneously — a redox reaction." },

    { "question_id": f"{SCI_10_CHEM}_003", "topic_id": SCI_10_CHEM,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Chemical Reactions and Equations",
      "text": "When zinc reacts with dilute HCl, the gas evolved is:",
      "options": ["Oxygen", "Chlorine", "Hydrogen", "Carbon dioxide"],
      "correct_option_index": 2, "difficulty": "easy",
      "explanation": "Zn + 2HCl → ZnCl₂ + H₂↑. Zinc displaces hydrogen — it burns with a pop sound." },

    { "question_id": f"{SCI_10_CHEM}_004", "topic_id": SCI_10_CHEM,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Chemical Reactions and Equations",
      "text": "Rancidity of food is caused by:",
      "options": ["Reduction of fats", "Oxidation of fats", "Decomposition of proteins", "Hydrolysis of starch"],
      "correct_option_index": 1, "difficulty": "medium",
      "explanation": "Fats oxidise on exposure to air → bad smell. Antioxidants and nitrogen flushing prevent rancidity." },

    { "question_id": f"{SCI_10_CHEM}_005", "topic_id": SCI_10_CHEM,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Chemical Reactions and Equations",
      "text": "AgNO₃ + NaCl → AgCl↓ + NaNO₃ is an example of:",
      "options": ["Combination reaction", "Double displacement reaction", "Single displacement reaction", "Decomposition reaction"],
      "correct_option_index": 1, "difficulty": "medium",
      "explanation": "Two compounds exchange ions to form two new compounds — a double displacement (metathesis) reaction. AgCl precipitates." },

    # ─────────────────────────────────────────────────────────────────────────
    # CBSE 10 · Science · Electricity · Electric Circuits
    # ─────────────────────────────────────────────────────────────────────────
    { "question_id": f"{SCI_10_ELEC}_001", "topic_id": SCI_10_ELEC,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Electricity",
      "text": "Ohm's Law states that (at constant temperature):",
      "options": ["V = IR²", "V ∝ 1/I", "V ∝ I", "I = V²R"],
      "correct_option_index": 2, "difficulty": "easy",
      "explanation": "V ∝ I — voltage is directly proportional to current; the constant of proportionality is resistance R (V = IR)." },

    { "question_id": f"{SCI_10_ELEC}_002", "topic_id": SCI_10_ELEC,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Electricity",
      "text": "A wire has resistance 10 Ω. If a 5 V potential difference is applied, the current through it is:",
      "options": ["50 A", "0.5 A", "2 A", "15 A"],
      "correct_option_index": 1, "difficulty": "easy",
      "explanation": "I = V/R = 5/10 = 0.5 A. Direct application of Ohm's Law." },

    { "question_id": f"{SCI_10_ELEC}_003", "topic_id": SCI_10_ELEC,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Electricity",
      "text": "Three resistors of 2 Ω, 3 Ω, and 6 Ω are connected in parallel. The equivalent resistance is:",
      "options": ["11 Ω", "1 Ω", "6 Ω", "2 Ω"],
      "correct_option_index": 1, "difficulty": "hard",
      "explanation": "1/R = 1/2 + 1/3 + 1/6 = 3/6 + 2/6 + 1/6 = 6/6 = 1  →  R = 1 Ω." },

    { "question_id": f"{SCI_10_ELEC}_004", "topic_id": SCI_10_ELEC,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Electricity",
      "text": "The SI unit of electric resistance is:",
      "options": ["Ampere", "Volt", "Ohm", "Watt"],
      "correct_option_index": 2, "difficulty": "easy",
      "explanation": "Resistance is measured in Ohm (Ω), named after Georg Simon Ohm. 1 Ω = 1 V/A." },

    { "question_id": f"{SCI_10_ELEC}_005", "topic_id": SCI_10_ELEC,
      "board": "cbse", "grade": "10", "subject": "Science",
      "chapter": "Electricity",
      "text": "Which factor does NOT affect the resistance of a wire?",
      "options": ["Length of the wire", "Cross-sectional area", "Material (resistivity)", "Colour of the wire"],
      "correct_option_index": 3, "difficulty": "medium",
      "explanation": "R = ρL/A — depends on length, area and material resistivity. Colour has no effect on resistance." },
]


def seed_all():
    print(f"Seeding {len(QUESTIONS)} questions into Firestore...")
    ok = 0
    for q in QUESTIONS:
        try:
            qid = ts.add_question(q)
            print(f"  ✓  {qid}")
            ok += 1
        except Exception as e:
            print(f"  ✗  {q.get('question_id','?')} : {e}")
    # Invalidate count cache
    ts.invalidate_count_cache()
    print(f"\nDone: {ok}/{len(QUESTIONS)} uploaded.")
    print("\nTopic IDs seeded:")
    for t in sorted({q['topic_id'] for q in QUESTIONS}):
        print(f"  {t}")


if __name__ == "__main__":
    seed_all()
