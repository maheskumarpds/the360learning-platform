import os
import json
from openai import OpenAI

# The newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
openai = OpenAI(api_key=OPENAI_API_KEY)

def get_ai_response(question, subject_name=None, role='student', class_level=None, class_subjects=None, thread_context=None, edit_context=None):
    """
    Get a response from the AI tutor for a student question
    
    Args:
        question (str): The user's question
        subject_name (str, optional): The subject context for the question
        role (str): The user's role (student, teacher, admin)
        class_level (str, optional): The class level the user is assigned to
        class_subjects (list, optional): List of subjects in the user's class curriculum
        thread_context (str, optional): Context for thread replies to provide continuity
        edit_context (str, optional): Context information when a question has been edited
        
    Returns:
        str: The AI-generated response
    """
    try:
        # Create a system message that guides the AI to provide educational responses
        system_message = (
            "You are an AI tutor for a CBSE educational platform called the360learning. "
            "Your goal is to help users understand concepts and learn effectively. "
        )
        
        # Add role-specific context and constraints
        if role == 'student':
            system_message += (
                "You are responding to a student who needs help understanding concepts. "
                "Provide explanations that are clear, accurate, and tailored to the student's "
                "educational level. Break down complex topics into simpler parts. "
                "Provide examples that are age-appropriate and align with their curriculum. "
                "Be encouraging and supportive.\n\n"
                "IMPORTANT: You must only provide information that is relevant to the student's class level "
                "and the subjects in their curriculum. If they ask questions about topics outside "
                "their curriculum or beyond their class level, politely inform them that the topic "
                "is not part of their current syllabus, and suggest alternatives within their curriculum."
            )
        elif role == 'teacher':
            system_message += (
                "You are responding to a teacher who might need assistance with teaching concepts, "
                "creating lesson plans, or finding resources. Provide pedagogical suggestions, "
                "teaching methodologies, and content that is appropriate for their class level. "
                "Offer ideas for classroom activities and assessments.\n\n"
                "IMPORTANT: Focus your responses on the class level and subjects that this teacher is responsible for. "
                "Provide teaching methodologies and resources specifically tailored for these subjects and class level."
            )
        else:  # admin
            system_message += (
                "You are responding to a school administrator who might need information about "
                "educational management, curriculum planning, or system features. Provide "
                "comprehensive information that can help with administrative decisions."
            )
        
        # Add class level context with specific details about what should be taught at this level
        if class_level:
            class_level_display = get_class_level_display(class_level)
            system_message += f" The user is associated with {class_level_display}."
            
            # Add age-appropriate context for students
            if role == 'student':
                age_appropriate_content = get_age_appropriate_content_by_class(class_level)
                if age_appropriate_content:
                    system_message += f" {age_appropriate_content}"
        
        # Add subject context if provided with strong guidance to stay within subject boundaries
        if subject_name:
            system_message += (
                f" The user is asking about the subject of {subject_name}. "
                f"Your responses should focus specifically on this subject within the context "
                f"of their class level and curriculum."
            )
            
            # Add CBSE curriculum specific guidance if we have subject and class level
            if class_level and role in ['student', 'teacher']:
                subject_specific_guidance = get_subject_curriculum_guidance(subject_name, class_level)
                if subject_specific_guidance:
                    system_message += f" {subject_specific_guidance}"
        
        # Add curriculum context if available with explicit constraints
        if class_subjects and len(class_subjects) > 0:
            subjects_list = ", ".join(class_subjects)
            system_message += (
                f" The curriculum for this class includes these subjects: {subjects_list}. "
                f"These are the only subjects this user should be learning about at their level. "
                f"If they ask about subjects outside this list, politely explain that it's not part "
                f"of their current curriculum."
            )
        
        # Add special instruction for keeping responses appropriate and accurate
        system_message += (
            " Strictly provide educational content that is factually accurate and grade-appropriate. "
            "Do not invent curriculum content or provide speculative information. "
            "If you're unsure about specific CBSE curriculum details, be honest about your limitations "
            "and provide general educational guidance that is age-appropriate instead."
        )
            
        # Create messages array
        messages = [{"role": "system", "content": system_message}]
        
        # Add thread context if available to maintain thread continuity
        if thread_context:
            messages.append({"role": "system", "content": f"CONTEXT: {thread_context}"})
        
        # Add edit context if this is an edited message
        if edit_context:
            messages.append({"role": "system", "content": f"CONTEXT: {edit_context}"})
        
        # Add the user question
        messages.append({"role": "user", "content": question})
        
        # Get response from OpenAI
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=800,
            temperature=0.7,
        )
        
        # Return the AI's response
        return response.choices[0].message.content
        
    except Exception as e:
        # Handle errors gracefully
        print(f"Error in AI response generation: {str(e)}")
        return (
            "I'm sorry, I'm having trouble processing your question right now. "
            "Please try again in a moment."
        )


def get_class_level_display(class_level):
    """Convert class_level code to display name"""
    if class_level == 'eng_com':
        return "English Communication Program"
    else:
        try:
            return f"Class {int(class_level)}"
        except (ValueError, TypeError):
            return f"Class {class_level}"


def get_age_appropriate_content_by_class(class_level):
    """Provide age-appropriate context based on class level"""
    try:
        level = int(class_level) if class_level != 'eng_com' else 0
        
        if level <= 2:
            return (
                "Students at this level are young learners (typically 6-7 years old) who need simple explanations "
                "with concrete examples, colorful visuals, and frequent use of stories. Use playful language "
                "and avoid abstract concepts."
            )
        elif level <= 5:
            return (
                "Students at this level (typically 8-10 years old) can understand basic concepts but still benefit "
                "from concrete examples and visual aids. They can follow simple step-by-step explanations "
                "and are beginning to develop critical thinking skills."
            )
        elif level <= 8:
            return (
                "Students at this level (typically 11-13 years old) are developing abstract thinking skills. "
                "They can understand more complex concepts with proper explanation and examples. "
                "They benefit from connections to real-world applications."
            )
        elif level <= 10:
            return (
                "Students at this level (typically 14-15 years old) can engage with abstract concepts and "
                "are preparing for board examinations. They need detailed explanations with precise terminology "
                "and can understand more sophisticated content."
            )
        elif level <= 12:
            return (
                "Students at this level (typically 16-17 years old) are engaged in senior secondary education "
                "with specialized subject tracks. They need college-preparatory content with advanced concepts "
                "and exam-oriented explanations."
            )
        else:
            return ""  # Default empty for unknown or special cases
    except:
        if class_level == 'eng_com':
            return (
                "Students in the English Communication Program are focusing specifically on developing "
                "English language skills at various levels. Explanations should focus on language acquisition, "
                "communication skills, and practical usage examples."
            )
        return ""  # Default empty for unknown formats


def get_subject_curriculum_guidance(subject_name, class_level):
    """Provide curriculum-specific guidance based on subject and class level"""
    subject_lower = subject_name.lower()
    
    # Define curriculum guidance for common subjects based on class level
    # This is a simplified version - in a real implementation, this would be more comprehensive
    # and potentially pulled from a database
    
    try:
        level = int(class_level) if class_level != 'eng_com' else 0
        
        if 'math' in subject_lower or 'mathematics' in subject_lower:
            if level <= 5:
                return (
                    "The mathematics curriculum for this level includes basic arithmetic operations, "
                    "shapes, patterns, measurements, and beginning fractions and decimals. Focus on "
                    "building number sense and problem-solving skills."
                )
            elif level <= 8:
                return (
                    "The mathematics curriculum for this level includes integers, rational numbers, "
                    "algebraic expressions, linear equations, geometry, data handling, and mensuration. "
                    "Focus on developing algebraic thinking and geometric understanding."
                )
            elif level <= 10:
                return (
                    "The mathematics curriculum for this level includes real numbers, polynomials, "
                    "coordinate geometry, linear equations in two variables, quadratic equations, "
                    "triangles, circles, probability, and statistics."
                )
            else:
                return (
                    "The mathematics curriculum for senior secondary includes relations and functions, "
                    "algebra, calculus, probability, vectors, and three-dimensional geometry."
                )
                
        elif 'science' in subject_lower:
            if level <= 5:
                return (
                    "The science curriculum for this level includes basic concepts about living and "
                    "non-living things, plants, animals, human body, food, shelter, environment, "
                    "and simple physical phenomena."
                )
            elif level <= 8:
                return (
                    "The science curriculum for this level includes food, materials, the world of living, "
                    "moving things, how things work, natural phenomena, and natural resources."
                )
            elif level <= 10:
                return (
                    "The science curriculum for this level includes matter, organization in living world, "
                    "motion, force and work, food production, respiration, reproduction, heredity, "
                    "life processes, and natural resources."
                )
                
        elif 'physics' in subject_lower and level > 10:
            return (
                "The physics curriculum for senior secondary includes physical world and measurement, "
                "kinematics, laws of motion, work, energy and power, rotational motion, gravitation, "
                "properties of solids and liquids, thermodynamics, oscillations and waves, electrostatics, "
                "current electricity, magnetic effects, electromagnetic induction, optics, and modern physics."
            )
            
        elif 'chemistry' in subject_lower and level > 10:
            return (
                "The chemistry curriculum for senior secondary includes basic concepts, structure of atom, "
                "classification of elements, chemical bonding, states of matter, thermodynamics, "
                "equilibrium, redox reactions, hydrogen, s and p block elements, hydrocarbons, "
                "environmental chemistry, purification, and qualitative analysis."
            )
            
        elif 'biology' in subject_lower and level > 10:
            return (
                "The biology curriculum for senior secondary includes diversity in living world, "
                "structural organization in plants and animals, cell structure and function, "
                "plant and human physiology, reproduction, genetics and evolution, "
                "biology in human welfare, biotechnology, and ecology."
            )
            
        elif 'english' in subject_lower:
            if class_level == 'eng_com':
                return (
                    "The English Communication Program focuses on developing listening, speaking, "
                    "reading, and writing skills with an emphasis on practical communication, "
                    "vocabulary building, grammar fundamentals, and confidence in language use."
                )
            else:
                return (
                    "The English curriculum includes reading comprehension, writing skills, "
                    "grammar, vocabulary development, and literature appreciation appropriate "
                    "for this class level."
                )
                
        elif 'social' in subject_lower or 'history' in subject_lower or 'geography' in subject_lower:
            if level <= 5:
                return (
                    "The social studies curriculum for this level includes family, neighborhood, "
                    "community helpers, transport, communication, and basic concepts of history, "
                    "geography, and cultural diversity."
                )
            elif level <= 8:
                return (
                    "The social studies curriculum for this level includes history of India, "
                    "geography of India and the world, social and political life, and civic sense."
                )
            elif level <= 10:
                return (
                    "The social studies curriculum for this level includes contemporary India, "
                    "India and the modern world, democratic politics, understanding economic "
                    "development, and disaster management."
                )
                
        # Default response for other subjects or if no specific guidance is available
        return ""
        
    except:
        # Default response if parsing fails
        return ""


def extract_key_points(text, num_points=5):
    """
    Extract key points from educational text
    
    Args:
        text (str): The educational text to analyze
        num_points (int): Number of key points to extract
        
    Returns:
        list: A list of key points
    """
    try:
        prompt = (
            f"Extract {num_points} important key points from the following educational text. "
            f"Format the response as a JSON array of strings, where each string is a key point.\n\n"
            f"Text: {text}"
        )
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        
        result = json.loads(response.choices[0].message.content)
        return result.get("key_points", [])
    
    except Exception as e:
        print(f"Error extracting key points: {str(e)}")
        return [f"An error occurred while extracting key points: {str(e)}"]


def generate_practice_questions(topic, num_questions=3, difficulty='medium'):
    """
    Generate practice questions on a specific topic
    
    Args:
        topic (str): The educational topic
        num_questions (int): Number of questions to generate
        difficulty (str): Difficulty level (easy, medium, hard)
        
    Returns:
        list: A list of question dictionaries with questions and answers
    """
    try:
        # Limit number of questions to prevent abuse
        num_questions = min(max(1, num_questions), 10)
        
        prompt = (
            f"Generate {num_questions} {difficulty}-level practice questions about '{topic}' for CBSE students. "
            f"For each question, include a detailed answer explanation. "
            f"Format the response as a JSON object with a 'questions' key containing an array of objects. "
            f"Each object should have 'question' and 'answer' keys."
        )
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        
        result = json.loads(response.choices[0].message.content)
        return result.get("questions", [])
    
    except Exception as e:
        print(f"Error generating practice questions: {str(e)}")
        return [{"question": f"An error occurred: {str(e)}", "answer": "Please try again later."}]


def summarize_text(text, max_length=300):
    """
    Create a concise summary of educational text
    
    Args:
        text (str): The educational text to summarize
        max_length (int): Maximum length of the summary in words
        
    Returns:
        str: A summarized version of the input text
    """
    try:
        prompt = (
            f"Summarize the following educational text in under {max_length} words, "
            f"while preserving the key educational points:\n\n{text}"
        )
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"Error summarizing text: {str(e)}")
        return f"An error occurred while summarizing: {str(e)}"
