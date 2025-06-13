import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Avg, Count, Sum, F

from .models import (
    UserProfile, Subject, Quiz, QuizQuestion, QuizAttempt, QuizResponse
)
from .ai_service import generate_practice_questions

@login_required
def quizzes_list(request):
    """List available quizzes"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Filter quizzes by class level for students
    if profile.role == 'student':
        available_quizzes = Quiz.objects.filter(
            class_level=profile.class_level,
            is_active=True
        ).order_by('-created_at')
    else:
        # Teachers see quizzes they created, admins see all
        if profile.role == 'teacher':
            available_quizzes = Quiz.objects.filter(
                created_by=request.user
            ).order_by('-created_at')
        else:  # admin
            available_quizzes = Quiz.objects.all().order_by('-created_at')
    
    # Get completed quizzes for the student
    completed_quizzes = []
    if profile.role == 'student':
        completed_quiz_ids = QuizAttempt.objects.filter(
            student=request.user, 
            completed=True
        ).values_list('quiz_id', flat=True)
        
        completed_quizzes = Quiz.objects.filter(
            id__in=completed_quiz_ids
        ).annotate(
            score=QuizAttempt.objects.filter(
                quiz_id=F('id'), 
                student=request.user,
                completed=True
            ).values('score').order_by('-completed_at')[:1]
        ).order_by('-created_at')
    
    # Get subjects for filtering
    subjects = Subject.objects.all()
    
    return render(request, 'quiz/list.html', {
        'available_quizzes': available_quizzes,
        'completed_quizzes': completed_quizzes,
        'subjects': subjects,
        'profile': profile
    })

@login_required
def quiz_create(request):
    """Create a new quiz"""
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only teachers and admins can create quizzes
    if profile.role not in ['teacher', 'admin']:
        messages.error(request, "You don't have permission to create quizzes.")
        return redirect('quizzes_list')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        subject_id = request.POST.get('subject')
        class_level = request.POST.get('class_level')
        time_limit = request.POST.get('time_limit')
        passing_score = request.POST.get('passing_score')
        
        # Validate basic inputs
        if not (title and subject_id and class_level):
            messages.error(request, "Please fill in all required fields.")
            return redirect('quiz_create')
        
        # Create the quiz
        quiz = Quiz.objects.create(
            title=title,
            description=description,
            subject_id=subject_id,
            class_level=class_level,
            time_limit=time_limit or 0,  # Default to no time limit
            passing_score=passing_score or 70,  # Default passing score of 70%
            created_by=request.user,
            is_active=False  # Start as inactive until questions are added
        )
        
        # Redirect to add questions
        messages.success(request, "Quiz created successfully! Now add some questions.")
        return redirect('quiz_edit', quiz_id=quiz.id)
    
    # Get subjects for the form
    subjects = Subject.objects.all()
    class_levels = UserProfile.CLASS_CHOICES
    
    return render(request, 'quiz/create.html', {
        'subjects': subjects,
        'class_levels': class_levels,
        'profile': profile
    })

@login_required
def quiz_edit(request, quiz_id):
    """Edit a quiz and its questions"""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Check if user has permission to edit
    if quiz.created_by != request.user and profile.role != 'admin':
        messages.error(request, "You don't have permission to edit this quiz.")
        return redirect('quizzes_list')
    
    # Get existing questions
    questions = QuizQuestion.objects.filter(quiz=quiz).order_by('question_number')
    
    if request.method == 'POST':
        if 'generate_questions' in request.POST:
            # Generate AI questions
            subject = quiz.subject.name
            topic = request.POST.get('topic', subject)
            num_questions = int(request.POST.get('num_questions', 5))
            difficulty = request.POST.get('difficulty', 'medium')
            
            generated_questions = generate_practice_questions(
                topic=f"{topic} {subject} for {quiz.get_class_level_display()}",
                num_questions=num_questions,
                difficulty=difficulty
            )
            
            # Add generated questions to the quiz
            for i, q in enumerate(generated_questions):
                next_number = questions.count() + i + 1
                options = [
                    q.get('option_a', ''),
                    q.get('option_b', ''),
                    q.get('option_c', ''),
                    q.get('option_d', '')
                ]
                
                # Clean up options - remove empty ones
                options = [opt for opt in options if opt]
                
                # If no options provided, create some basic ones from the answer
                if not options and q.get('answer'):
                    answer = q.get('answer')
                    options = [answer]
                    # Generate some plausible wrong answers
                    wrong_answers = [
                        f"Not {answer}" if len(answer) < 30 else "Incorrect option 1",
                        "Incorrect option 2",
                        "None of the above"
                    ]
                    options.extend(wrong_answers)
                
                # Determine correct answer index
                correct_index = 0  # Default to first option
                
                new_question = QuizQuestion.objects.create(
                    quiz=quiz,
                    question_number=next_number,
                    question_text=q.get('question', ''),
                    option_a=options[0] if len(options) > 0 else '',
                    option_b=options[1] if len(options) > 1 else '',
                    option_c=options[2] if len(options) > 2 else '',
                    option_d=options[3] if len(options) > 3 else '',
                    correct_option=chr(97 + correct_index),  # 'a', 'b', 'c', or 'd'
                    explanation=q.get('answer', '')
                )
            
            messages.success(request, f"Added {len(generated_questions)} AI-generated questions to the quiz.")
            
            # Refresh questions list
            questions = QuizQuestion.objects.filter(quiz=quiz).order_by('question_number')
        
        elif 'update_quiz' in request.POST:
            # Update quiz details
            quiz.title = request.POST.get('title', quiz.title)
            quiz.description = request.POST.get('description', quiz.description)
            quiz.time_limit = request.POST.get('time_limit', quiz.time_limit)
            quiz.passing_score = request.POST.get('passing_score', quiz.passing_score)
            quiz.is_active = 'is_active' in request.POST
            quiz.save()
            
            messages.success(request, "Quiz updated successfully.")
        
        elif 'add_question' in request.POST:
            # Add a manual question
            question_text = request.POST.get('question_text')
            option_a = request.POST.get('option_a')
            option_b = request.POST.get('option_b')
            option_c = request.POST.get('option_c')
            option_d = request.POST.get('option_d')
            correct_option = request.POST.get('correct_option')
            explanation = request.POST.get('explanation', '')
            
            if not (question_text and option_a and correct_option):
                messages.error(request, "Question text, option A, and correct option are required.")
            else:
                next_number = questions.count() + 1
                QuizQuestion.objects.create(
                    quiz=quiz,
                    question_number=next_number,
                    question_text=question_text,
                    option_a=option_a,
                    option_b=option_b or '',
                    option_c=option_c or '',
                    option_d=option_d or '',
                    correct_option=correct_option,
                    explanation=explanation
                )
                messages.success(request, "Question added successfully.")
                
                # Refresh questions list
                questions = QuizQuestion.objects.filter(quiz=quiz).order_by('question_number')
    
    # Get subjects for generation form
    subjects = Subject.objects.all()
    
    return render(request, 'quiz/edit.html', {
        'quiz': quiz,
        'questions': questions,
        'subjects': subjects,
        'profile': profile
    })

@login_required
def quiz_detail(request, quiz_id):
    """View quiz details and start quiz"""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Students can only access quizzes for their class level
    if profile.role == 'student' and quiz.class_level != profile.class_level:
        messages.error(request, "You don't have access to this quiz.")
        return redirect('quizzes_list')
    
    # Check if student has already completed this quiz
    previous_attempts = None
    if profile.role == 'student':
        previous_attempts = QuizAttempt.objects.filter(
            quiz=quiz,
            student=request.user,
            completed=True
        ).order_by('-completed_at')
    
    # Get question count
    question_count = QuizQuestion.objects.filter(quiz=quiz).count()
    
    return render(request, 'quiz/detail.html', {
        'quiz': quiz,
        'question_count': question_count,
        'previous_attempts': previous_attempts,
        'profile': profile,
        'can_edit': quiz.created_by == request.user or profile.role == 'admin'
    })

@login_required
def quiz_take(request, quiz_id):
    """Take a quiz"""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Only students can take quizzes
    if profile.role != 'student':
        messages.error(request, "Only students can take quizzes.")
        return redirect('quiz_detail', quiz_id=quiz.id)
    
    # Students can only access quizzes for their class level
    if quiz.class_level != profile.class_level:
        messages.error(request, "You don't have access to this quiz.")
        return redirect('quizzes_list')
    
    # Check if quiz is active
    if not quiz.is_active:
        messages.error(request, "This quiz is not currently active.")
        return redirect('quiz_detail', quiz_id=quiz.id)
    
    # Create a new attempt or get an existing incomplete one
    attempt, created = QuizAttempt.objects.get_or_create(
        quiz=quiz,
        student=request.user,
        completed=False,
        defaults={
            'started_at': timezone.now()
        }
    )
    
    if not created:
        # Check if the attempt has timed out
        if quiz.time_limit > 0:
            time_elapsed = (timezone.now() - attempt.started_at).total_seconds() / 60
            if time_elapsed > quiz.time_limit:
                # Automatically submit the timed-out attempt
                score = calculate_score(attempt)
                attempt.score = score
                attempt.completed = True
                attempt.completed_at = timezone.now()
                attempt.save()
                
                messages.warning(request, f"Your previous attempt timed out. Your score: {score}%")
                return redirect('quiz_detail', quiz_id=quiz.id)
    
    # Get all questions
    questions = QuizQuestion.objects.filter(quiz=quiz).order_by('question_number')
    
    # Get existing responses
    responses = QuizResponse.objects.filter(attempt=attempt).values_list('question_id', 'selected_option')
    responses_dict = {q_id: opt for q_id, opt in responses}
    
    # Send time information for timed quizzes
    time_data = None
    if quiz.time_limit > 0:
        started_at = attempt.started_at.isoformat()
        time_limit_minutes = quiz.time_limit
        time_data = {
            'started_at': started_at,
            'time_limit_minutes': time_limit_minutes
        }
    
    return render(request, 'quiz/take.html', {
        'quiz': quiz,
        'questions': questions,
        'attempt': attempt,
        'responses_dict': responses_dict,
        'time_data': time_data,
        'profile': profile
    })

@require_POST
@login_required
def save_response(request):
    """Save a single question response"""
    question_id = request.POST.get('question_id')
    attempt_id = request.POST.get('attempt_id')
    selected_option = request.POST.get('selected_option')
    
    if not (question_id and attempt_id and selected_option):
        return JsonResponse({'success': False, 'error': 'Missing required data'})
    
    # Get the attempt and check if it belongs to the current user
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id)
    if attempt.student != request.user:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    # Check if the attempt is still active
    if attempt.completed:
        return JsonResponse({'success': False, 'error': 'Quiz attempt already completed'})
    
    # Save or update the response
    question = get_object_or_404(QuizQuestion, pk=question_id)
    response, created = QuizResponse.objects.update_or_create(
        attempt=attempt,
        question=question,
        defaults={'selected_option': selected_option}
    )
    
    return JsonResponse({'success': True})

@require_POST
@login_required
def submit_quiz(request):
    """Submit a completed quiz"""
    attempt_id = request.POST.get('attempt_id')
    
    if not attempt_id:
        return JsonResponse({'success': False, 'error': 'Missing attempt ID'})
    
    # Get the attempt and check if it belongs to the current user
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id)
    if attempt.student != request.user:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    # Check if the attempt is still active
    if attempt.completed:
        return JsonResponse({'success': False, 'error': 'Quiz already submitted'})
    
    # Calculate the score
    score = calculate_score(attempt)
    
    # Update the attempt
    attempt.score = score
    attempt.completed = True
    attempt.completed_at = timezone.now()
    attempt.save()
    
    # Determine if passed
    passed = score >= attempt.quiz.passing_score
    
    return JsonResponse({
        'success': True,
        'score': score,
        'passed': passed,
        'redirect_url': f'/quiz/{attempt.quiz.id}/results/{attempt.id}/'
    })

@login_required
def quiz_results(request, quiz_id, attempt_id):
    """View quiz results"""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    attempt = get_object_or_404(QuizAttempt, pk=attempt_id)
    profile = get_object_or_404(UserProfile, user=request.user)
    
    # Check if the attempt belongs to current user or user is teacher/admin
    is_owner = attempt.student == request.user
    can_view = is_owner or profile.role in ['teacher', 'admin'] or quiz.created_by == request.user
    
    if not can_view:
        messages.error(request, "You don't have permission to view these results.")
        return redirect('quizzes_list')
    
    # Get all questions with student responses
    questions = QuizQuestion.objects.filter(quiz=quiz).order_by('question_number')
    responses = QuizResponse.objects.filter(attempt=attempt)
    responses_dict = {r.question_id: r.selected_option for r in responses}
    
    # Get correct/incorrect counts
    correct_count = sum(1 for q in questions if q.id in responses_dict and responses_dict[q.id] == q.correct_option)
    incorrect_count = sum(1 for q in questions if q.id in responses_dict and responses_dict[q.id] != q.correct_option)
    unanswered_count = questions.count() - len(responses_dict)
    
    # Calculate time taken if there's a time limit
    time_taken = None
    if quiz.time_limit > 0 and attempt.completed_at and attempt.started_at:
        time_taken = (attempt.completed_at - attempt.started_at).total_seconds() / 60
    
    # Determine if passed
    passed = attempt.score >= quiz.passing_score
    
    return render(request, 'quiz/results.html', {
        'quiz': quiz,
        'attempt': attempt,
        'questions': questions,
        'responses_dict': responses_dict,
        'correct_count': correct_count,
        'incorrect_count': incorrect_count,
        'unanswered_count': unanswered_count,
        'time_taken': time_taken,
        'passed': passed,
        'profile': profile,
        'is_owner': is_owner
    })

def calculate_score(attempt):
    """Calculate the score as a percentage"""
    quiz = attempt.quiz
    questions = QuizQuestion.objects.filter(quiz=quiz)
    total_questions = questions.count()
    
    if total_questions == 0:
        return 0
    
    # Get student responses
    responses = QuizResponse.objects.filter(attempt=attempt)
    response_dict = {r.question_id: r.selected_option for r in responses}
    
    # Count correct answers
    correct_answers = 0
    for question in questions:
        if question.id in response_dict and response_dict[question.id] == question.correct_option:
            correct_answers += 1
    
    # Calculate percentage score
    return int((correct_answers / total_questions) * 100)