# Static data for careers, courses, and internships
CAREERS_DATA = {
    'Technology': [
        {'id': 'software_engineer', 'name': 'Software Engineer', 'description': 'Design and build software systems that power modern applications, from mobile apps to enterprise platforms.', 'subjects': ['Mathematics', 'Computer Science', 'Physics'], 'skills': ['Programming', 'Problem Solving', 'System Design', 'Algorithms'], 'courses': ['python_beginners', 'web_development'], 'internships': ['software_dev_intern', 'data_analytics_intern']},
        {'id': 'data_scientist', 'name': 'Data Scientist', 'description': 'Analyse massive datasets to extract insights, build predictive models, and drive business decisions through data.', 'subjects': ['Mathematics', 'Statistics', 'Computer Science'], 'skills': ['Python', 'Machine Learning', 'Statistics', 'Data Visualisation'], 'courses': ['intro_ai', 'data_science_spec'], 'internships': ['data_analytics_intern']},
        {'id': 'cyber_security', 'name': 'Cyber Security Analyst', 'description': 'Protect organisations from digital threats by identifying vulnerabilities and implementing security protocols.', 'subjects': ['Computer Science', 'Mathematics'], 'skills': ['Networking', 'Security Protocols', 'Penetration Testing', 'Risk Assessment'], 'courses': [], 'internships': []},
    ],
    'Medicine': [
        {'id': 'doctor', 'name': 'Doctor', 'description': 'Diagnose and treat patients across specialisations — from surgery to internal medicine and beyond.', 'subjects': ['Biology', 'Chemistry', 'Physics'], 'skills': ['Anatomy', 'Patient Care', 'Clinical Reasoning', 'Surgery'], 'courses': [], 'internships': []},
        {'id': 'pharmacist', 'name': 'Pharmacist', 'description': 'Manage pharmaceutical supplies, advise patients on medication, and ensure safe drug dispensing.', 'subjects': ['Biology', 'Chemistry'], 'skills': ['Drug Knowledge', 'Patient Interaction', 'Inventory Management'], 'courses': [], 'internships': []},
    ],
    'Engineering': [
        {'id': 'mechanical_engineer', 'name': 'Mechanical Engineer', 'description': 'Design machines, engines, and mechanical systems for manufacturing, aerospace, and energy sectors.', 'subjects': ['Physics', 'Mathematics', 'Chemistry'], 'skills': ['CAD', 'Mechanics', 'Thermodynamics', 'Prototyping'], 'courses': [], 'internships': []},
        {'id': 'civil_engineer', 'name': 'Civil Engineer', 'description': 'Plan and build infrastructure — bridges, buildings, roads, and water systems that shape cities.', 'subjects': ['Physics', 'Mathematics'], 'skills': ['Structural Design', 'Planning', 'AutoCAD', 'Project Management'], 'courses': [], 'internships': []},
    ],
    'Business': [
        {'id': 'chartered_accountant', 'name': 'Chartered Accountant', 'description': 'Manage finances, audit accounts, and advise businesses on tax strategy and compliance.', 'subjects': ['Accountancy', 'Economics', 'Mathematics'], 'skills': ['Accounting', 'Taxation', 'Financial Analysis', 'Auditing'], 'courses': [], 'internships': ['finance_intern']},
        {'id': 'management_consultant', 'name': 'Management Consultant', 'description': 'Help organisations solve complex problems, improve efficiency, and execute strategy.', 'subjects': ['Economics', 'Business Studies', 'Mathematics'], 'skills': ['Analysis', 'Strategy', 'Communication', 'Leadership'], 'courses': [], 'internships': ['marketing_intern']},
    ],
    'Creative': [
        {'id': 'graphic_designer', 'name': 'Graphic Designer', 'description': 'Create visual identities, marketing materials, and digital content that communicate ideas powerfully.', 'subjects': ['Art', 'Computer Science'], 'skills': ['Adobe Suite', 'Typography', 'Branding', 'UX Design'], 'courses': [], 'internships': ['graphic_design_intern']},
        {'id': 'content_writer', 'name': 'Content Writer', 'description': 'Craft compelling written content for blogs, marketing, journalism, and digital platforms.', 'subjects': ['English', 'History'], 'skills': ['Writing', 'Research', 'SEO', 'Editing'], 'courses': [], 'internships': ['content_writing_intern']},
    ]
}

COURSES_DATA = [
    {'id': 'python_beginners', 'name': 'Python for Beginners', 'provider': 'Coursera', 'level': 'Beginner', 'duration': '4 weeks', 'price': 'Free', 'description': 'A foundational course covering Python syntax, data structures, control flow, and basic scripting. Ideal for absolute beginners.', 'skills_gained': ['Python Basics', 'Problem Solving', 'Scripting'], 'related_careers': ['software_engineer', 'data_scientist'], 'link': 'https://www.coursera.org'},
    {'id': 'intro_ai', 'name': 'Introduction to AI', 'provider': 'edX', 'level': 'Beginner', 'duration': '6 weeks', 'price': 'Free', 'description': 'Understand the fundamentals of artificial intelligence — from machine learning basics to neural networks and ethics in AI.', 'skills_gained': ['AI Concepts', 'Machine Learning Basics', 'Critical Thinking'], 'related_careers': ['data_scientist', 'software_engineer'], 'link': 'https://www.edx.org'},
    {'id': 'web_development', 'name': 'Web Development', 'provider': 'freeCodeCamp', 'level': 'Intermediate', 'duration': '8 weeks', 'price': 'Free', 'description': 'Build real-world web applications using HTML, CSS, JavaScript, and React. Project-based learning throughout.', 'skills_gained': ['HTML/CSS', 'JavaScript', 'React', 'Responsive Design'], 'related_careers': ['software_engineer'], 'link': 'https://www.freecodecamp.org'},
    {'id': 'web_bootcamp', 'name': 'Complete Web Development Bootcamp', 'provider': 'Udemy', 'level': 'All Levels', 'duration': '12 weeks', 'price': '₹499', 'description': 'An all-in-one bootcamp covering front-end, back-end, databases, and deployment. Takes you from zero to full-stack.', 'skills_gained': ['Full Stack', 'Node.js', 'MongoDB', 'Deployment'], 'related_careers': ['software_engineer'], 'link': 'https://www.udemy.com'},
    {'id': 'data_science_spec', 'name': 'Data Science Specialization', 'provider': 'Coursera', 'level': 'Intermediate', 'duration': '6 months', 'price': '₹3,999/mo', 'description': 'A comprehensive specialisation covering statistics, Python, machine learning, and data storytelling for professionals.', 'skills_gained': ['Statistics', 'Python', 'Machine Learning', 'Data Visualisation'], 'related_careers': ['data_scientist'], 'link': 'https://www.coursera.org'},
]

INTERNSHIPS_DATA = [
    {'id': 'software_dev_intern', 'name': 'Software Development Intern', 'domain': 'Technology', 'company': 'Tech Corp', 'duration': '3 months', 'location': 'Remote', 'skills_required': ['Python', 'JavaScript', 'Git'], 'eligibility': 'Class 11/12 or undergraduate students with basic programming knowledge.', 'description': 'Work alongside senior developers building features for a SaaS product. Involves code reviews, sprint planning, and real deployments.', 'how_to_apply': 'Visit the company careers page and submit your resume with a link to a GitHub portfolio.'},
    {'id': 'data_analytics_intern', 'name': 'Data Analytics Intern', 'domain': 'Technology', 'company': 'Analytics Inc', 'duration': '6 months', 'location': 'Bangalore', 'skills_required': ['Python', 'SQL', 'Excel'], 'eligibility': 'Students pursuing Science or Commerce streams with an interest in data.', 'description': 'Analyse business data, create dashboards, and present findings to stakeholders. Hands-on with real datasets from day one.', 'how_to_apply': 'Apply via LinkedIn or the company website. Include a brief statement on why you are interested in data.'},
    {'id': 'marketing_intern', 'name': 'Marketing Intern', 'domain': 'Business', 'company': 'Brand Agency', 'duration': '2 months', 'location': 'Mumbai', 'skills_required': ['Communication', 'Social Media', 'Writing'], 'eligibility': 'Commerce or Arts stream students with strong communication skills.', 'description': 'Plan and execute social media campaigns, write content briefs, and assist in brand strategy for real clients.', 'how_to_apply': 'Send your resume and a short creative portfolio to the agency\'s internship email.'},
    {'id': 'finance_intern', 'name': 'Finance Intern', 'domain': 'Business', 'company': 'Investment Firm', 'duration': '4 months', 'location': 'Delhi', 'skills_required': ['Excel', 'Accounting', 'Attention to Detail'], 'eligibility': 'Commerce stream students in Class 11/12 or pursuing CA/CMA.', 'description': 'Support the finance team in budgeting, forecasting, and client portfolio management. Learn industry-standard tools.', 'how_to_apply': 'Apply through the firm\'s internship portal. A basic Excel proficiency test will be conducted.'},
    {'id': 'graphic_design_intern', 'name': 'Graphic Design Intern', 'domain': 'Creative', 'company': 'Design Studio', 'duration': '3 months', 'location': 'Pune', 'skills_required': ['Adobe Illustrator', 'Photoshop', 'Creative Thinking'], 'eligibility': 'Students with a portfolio demonstrating visual design work.', 'description': 'Design branding, marketing collaterals, and social media assets for live client projects under senior designer mentorship.', 'how_to_apply': 'Submit your portfolio (Behance or Dribbble link) along with your resume.'},
    {'id': 'content_writing_intern', 'name': 'Content Writing Intern', 'domain': 'Creative', 'company': 'Media House', 'duration': '2 months', 'location': 'Remote', 'skills_required': ['English Writing', 'Research', 'SEO Basics'], 'eligibility': 'Any stream. Strong English writing and research skills required.', 'description': 'Write blog posts, articles, and web content on assigned topics. Learn SEO best practices and content strategy.', 'how_to_apply': 'Send two sample articles you have written (personal or published) along with your resume.'},
]

# Helper lookups
def get_career_by_id(career_id):
    for domain, careers in CAREERS_DATA.items():
        for career in careers:
            if career['id'] == career_id:
                career['domain'] = domain
                return career
    return None

def get_course_by_id(course_id):
    for course in COURSES_DATA:
        if course['id'] == course_id:
            return course
    return None

def get_internship_by_id(internship_id):
    for internship in INTERNSHIPS_DATA:
        if internship['id'] == internship_id:
            return internship
    return None
