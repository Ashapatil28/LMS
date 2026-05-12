from django.shortcuts import render, redirect, get_object_or_404
from .models import User, Course, Video, CourseEnrollment, VideoProgress, Attendance
from reportlab.pdfgen import canvas
from django.http import HttpResponse, JsonResponse
from datetime import datetime
import os
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.pagesizes import landscape, A4


# ─── SESSION AUTH DECORATOR ────────────────────────────────────────────────────
def session_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─── HOME ──────────────────────────────────────────────────────────────────────
def home(request):
    return render(request, 'home.html')


# ─── REGISTER ──────────────────────────────────────────────────────────────────
def register(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        role = request.POST.get("role")

        User.objects.create(
            name=name,
            email=email,
            password=password,
            role=role
        )
        return redirect("login")

    return render(request, "register.html")


# ─── LOGIN ─────────────────────────────────────────────────────────────────────
def login_view(request):
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']

        try:
            user = User.objects.get(email=email, password=password)

            request.session['user_id'] = user.id
            request.session['role'] = user.role
            request.session['user_name'] = user.name

            if user.role == "admin":
                return redirect('admin_dashboard')
            
            elif user.role == "trainer":
                return redirect('trainer_dashboard')
            
            elif user.role == "student":
                return redirect('student_dashboard')

        except User.DoesNotExist:
            return render(request, "login.html", {"error": "Invalid credentials"})

    return render(request, "login.html")


# ─── LOGOUT ────────────────────────────────────────────────────────────────────
def logout_view(request):
    request.session.flush()
    return redirect("home")


# ─── DASHBOARDS ────────────────────────────────────────────────────────────────
@session_login_required
def admin_dashboard(request):
    if request.session.get("role") != "admin":
        return redirect("login")

    total_users = User.objects.count()
    total_courses = Course.objects.count()
    total_enrollments = CourseEnrollment.objects.count()
    total_students = User.objects.filter(role="student").count()
    total_trainers = User.objects.filter(role="trainer").count()
    total_videos = Video.objects.count()

    users = User.objects.all()[:5]
    courses = Course.objects.all()[:5]

    context = {
        "total_users": total_users,
        "total_courses": total_courses,
        "total_enrollments": total_enrollments,
        "total_students": total_students,
        "total_trainers": total_trainers,
        "total_videos": total_videos,
        "users": users,
        "courses": courses,
    }

    return render(request, "admin_dashboard.html", context)


@session_login_required
def student_dashboard(request):
    if request.session.get("role") != "student":
        return redirect("login")

    user_id = request.session.get("user_id")
    enrollments = CourseEnrollment.objects.filter(student_id=user_id)

    data = []
    for en in enrollments:
        course = en.course
        progress = calculate_progress(user_id, course)
        data.append({
            "course": course,
            "progress": progress,
            "enrollments":en,
        })

    enrolled_count = len(data)
    completed_count = sum(1 for d in data if d['progress'] == 100)
    cert_count = completed_count

    return render(request, "student_dashboard.html", {
        "data": data,
        "user_name": request.session.get("user_name", "Student"),
        "my_courses_count": enrolled_count,
        "completed_courses": completed_count,
        "certificates_count": cert_count,
    })


@session_login_required
def trainer_dashboard(request):
    if request.session.get("role") != "trainer":
        return redirect("login")

    user_id = request.session.get("user_id")
    trainer = User.objects.get(id=user_id)

    courses = Course.objects.filter(trainer=trainer)

    context = {
        "courses": courses,
        "trainer_name": trainer.name, 
        "total_courses": courses.count(),
        "total_videos": Video.objects.filter(course__trainer=trainer).count(),
        "students": CourseEnrollment.objects.filter(course__trainer=trainer).count(),
    }
    return render(request, "trainer_dashboard.html", context)


# ─── COURSE LIST ───────────────────────────────────────────────────────────────
def course_list(request):
    courses = Course.objects.all()
    return render(request, "courses.html", {"courses": courses})


# ─── COURSE DETAIL ─────────────────────────────────────────────────────────────
@session_login_required
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    videos = list(Video.objects.filter(course=course).order_by("id"))

    user_id = request.session.get("user_id")

    enrollment = CourseEnrollment.objects.filter(
        student_id=user_id,
        course=course,
        status='approved'
    ).first()

    enrolled = enrollment is not None

    unlocked_videos = []
    completed_videos = []

    if enrolled:
        completed_videos = list(
            Attendance.objects.filter(
                student_id=user_id,
                video__course=course,
                completed=True
            ).values_list("video_id", flat=True)
        )

        for i, video in enumerate(videos):
            if i == 0:
                unlocked_videos.append(video.id)
            else:
                prev_video = videos[i - 1]
                if prev_video.id in completed_videos:
                    unlocked_videos.append(video.id)

    video_id = request.GET.get("video")
    if video_id:
        current_video = get_object_or_404(Video, id=video_id)
    else:
        current_video = videos[0] if videos else None

    total_videos = len(videos)

    completed_count = len(completed_videos)

    if total_videos > 0:
        progress = int((completed_count / total_videos) * 100)
    else:
        progress = 0

    is_completed = (progress == 100)
    
    return render(request, "course_detail.html", {
        "course": course,
        "videos": videos,
        "enrolled": enrolled,
        "completed_videos": completed_videos,
        "unlocked_videos": unlocked_videos,
        "current_video": current_video,
        "progress": progress,
        "is_completed": is_completed,
    })


# ─── ADD COURSE (TRAINER) ──────────────────────────────────────────────────────
@session_login_required
def add_course(request):
    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        user_id = request.session.get("user_id")

        Course.objects.create(
            title=title,
            description=description,
            trainer_id=user_id
        )
        return redirect("trainer_dashboard")

    return render(request, "add_course.html")


def view_courses(request):
    courses = Course.objects.all()
    return render(request, 'courses.html', {'courses': courses})


# ─── ADD VIDEO ─────────────────────────────────────────────────────────────────
def add_video(request, course_id):
    if request.method == "POST":
        title = request.POST.get("title")
        video_url = request.POST.get("video_url")

        course = get_object_or_404(Course, id=course_id)

        Video.objects.create(
            title=title,
            video_url=video_url,
            course=course
        )
        return redirect("course_detail", course_id=course_id)

    return render(request, "add_video.html", {"course_id": course_id})


# ─── ENROLL ────────────────────────────────────────────────────────────────────
@session_login_required
def enroll_course(request, course_id):
    user_id = request.session.get("user_id")
    course = get_object_or_404(Course, id=course_id)

    enrollment, created = CourseEnrollment.objects.get_or_create(
        student_id=user_id,
        course=course,
        defaults={
            'status': 'pending'
        }
    )

    # If rejected earlier, allow re-request
    if not created and enrollment.status == 'rejected':
        enrollment.status = 'pending'
        enrollment.save()

    return redirect('courses')


# ─── CERTIFICATE ───────────────────────────────────────────────────────────────
@session_login_required
def generate_certificate(request, course_id):
    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    user = get_object_or_404(User, id=user_id)
    course = get_object_or_404(Course, id=course_id)

    # Prevent certificate download before completion
    if not is_course_completed(user_id, course):
        return HttpResponse("Complete all videos to download certificate.")

    # Mark certificate generated
    enrollment = CourseEnrollment.objects.filter(
        student_id=user_id,
        course=course
    ).first()
    
    if not enrollment:
        return HttpResponse("You are not enrolled in this course.")

    # CHECK COMPLETION
    if not enrollment.completed:
        return HttpResponse(
            "Complete course first before downloading certificate."
        )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{course.title}_certificate.pdf"'

    p = canvas.Canvas(response, pagesize=landscape(A4))

    width, height = landscape(A4)

    # Background
    bg_path = os.path.join(
    settings.BASE_DIR,
    "lms_app/static/images/certificate_bg.jpg"
    )

    p.drawImage(bg_path, 0, 0, width=width, height=height)

    # Logo
    logo_path = os.path.join(
        settings.BASE_DIR,
        "lms_app/static/images/logo.png"
    )

    p.drawImage(
        logo_path,
        width/2 - 50,
        height - 120,
        width=100,
        height=60,
        mask='auto'
    )

    # Title
    p.setFont("Helvetica-Bold", 28)
    p.drawCentredString(
        width/2,
        height - 170,
        "CERTIFICATE OF COMPLETION"
    )

    # Subtitle
    p.setFont("Helvetica", 18)
    p.drawCentredString(
        width/2,
        height - 230,
        "This certificate is proudly presented to"
    )

    # Student Name
    p.setFont("Helvetica-Bold", 30)
    p.drawCentredString(
        width/2,
        height - 290,
        user.name
    )

    # Completion Text
    p.setFont("Helvetica", 18)
    p.drawCentredString(
        width/2,
        height - 350,
        "for successfully completing the course"
    )

    # Course Name
    p.setFont("Helvetica-Bold", 24)
    p.drawCentredString(
        width/2,
        height - 410,
        course.title
    )

    # Date
    p.setFont("Helvetica", 14)
    p.drawCentredString(
        width/2,
        height - 470,
        f"Date: {datetime.now().strftime('%d %B %Y')}"
    )

    # Signature
    sign_path = os.path.join(
        settings.BASE_DIR,
        "lms_app/static/images/sign.png"
    )

    p.drawImage(
        sign_path,
        width - 220,
        70,
        width=120,
        height=50,
        mask='auto'
    )

    p.setFont("Helvetica", 12)
    p.drawString(width - 200, 55, "Director")

    # Footer
    p.setFont("Helvetica-Oblique", 12)
    p.drawCentredString(width/2, 40, "LMS Academy")

    p.showPage()
    p.save()

    return response


# ─── MARK WATCHED ──────────────────────────────────────────────────────────────
def mark_watched(request, video_id):
    user_id = request.session.get("user_id")
    video = get_object_or_404(Video, id=video_id)
    
    attendance, created = Attendance.objects.get_or_create(
        student_id=user_id,
        video_id=video_id
    )

    attendance.completed = True
    attendance.watched_percent = 100
    attendance.save()

    return redirect("course_detail", course_id=video.course.id)


# ─── DASHBOARD ─────────────────────────────────────────────────────────────────
def dashboard(request):
    user_id = request.session.get("user_id")

    total_courses = Course.objects.count()

    enrolled_courses = CourseEnrollment.objects.filter(
        student_id=user_id
    ).count()

    completed_courses = VideoProgress.objects.filter(
        student_id=user_id,
        completed=True
    ).values("video__course").distinct().count()

    return render(request, "dashboard.html", {
        "total_courses": total_courses,
        "enrolled_courses": enrolled_courses,
        "completed_courses": completed_courses,
    })


# ─── HELPERS ───────────────────────────────────────────────────────────────────
def calculate_progress(user_id, course):
    total_videos = course.videos.count()

    completed = Attendance.objects.filter(
        student_id=user_id,
        video__course=course,
        completed=True
    ).count()

    if total_videos == 0:
        return 0

    return int((completed / total_videos) * 100)


def is_course_completed(user_id, course):
    total_videos = Video.objects.filter(course=course).count()
    completed_videos = Attendance.objects.filter(
        student_id=user_id,
        video__course=course,
        completed=True
    ).count()
    return total_videos > 0 and completed_videos == total_videos


# ─── VIDEO PROGRESS (AJAX) ─────────────────────────────────────────────────────
@csrf_exempt
def mark_video_progress(request):

    if request.method == "POST":

        video_id = request.POST.get("video_id")
        percent = int(request.POST.get("percent", 0))

        user_id = request.session.get("user_id")

        video = Video.objects.get(id=video_id)

        attendance, created = Attendance.objects.get_or_create(
            student_id=user_id,
            video=video
        )

        # Save highest progress only
        if percent > attendance.watched_percent:
            attendance.watched_percent = percent

        # Complete after 90%
        if percent >= 90:
            attendance.completed = True
            attendance.watched_percent = 100

        attendance.save()

        course = video.course

        total_videos = Video.objects.filter(
            course=course
        ).count()

        completed_videos = Attendance.objects.filter(
            student_id=user_id,
            video__course=course,
            completed=True
        ).count()

        course_progress = int(
            (completed_videos / total_videos) * 100
        )

        return JsonResponse({

            "status": "success",

            "video_progress":
                attendance.watched_percent,

            "course_progress":
                course_progress,

            "course_completed":
                completed_videos == total_videos
        })

    return JsonResponse({"status": "error"})

# ─── UTILITY ───────────────────────────────────────────────────────────────────
def get_video_id(url):
    """Extract YouTube video ID from a URL."""
    if "watch?v=" in url:
        return url.split("watch?v=")[-1]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[-1]
    return url


# ─── MY COURSES ────────────────────────────────────────────────────────────────
def my_courses(request):
    user_id = request.session.get("user_id")
    enrollments = CourseEnrollment.objects.filter(student_id=user_id)
    courses = [e.course for e in enrollments]

    return render(request, 'my_courses.html', {
        'courses': courses
    })


# ─── CERTIFICATE LIST ──────────────────────────────────────────────────────────
def certificate_list(request):
    user_id = request.session.get("user_id")
    # Only show courses where all videos are completed
    enrollments = CourseEnrollment.objects.filter(student_id=user_id)
    completed_courses = [
        e.course for e in enrollments
        if is_course_completed(user_id, e.course)
    ]

    return render(request, 'certificate_list.html', {
        'completed_courses': completed_courses
    })


# ─── COMPLETED COURSES ─────────────────────────────────────────────────────────
def completed_courses(request):
    user_id = request.session.get("user_id")
    enrollments = CourseEnrollment.objects.filter(student_id=user_id)
    courses = [
        e.course for e in enrollments
        if is_course_completed(user_id, e.course)
    ]

    return render(request, 'completed_courses.html', {
        'courses': courses
    })


# ─── ALL COURSES ───────────────────────────────────────────────────────────────
def all_courses(request):
    courses = Course.objects.all()
    return render(request, 'all_courses.html', {'courses': courses})


# ─── COMPLETE COURSE ───────────────────────────────────────────────────────────
def complete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    return HttpResponse(f'Course "{course.title}" completed successfully!')


# ─── WATCH COURSE ──────────────────────────────────────────────────────────────
def watch_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    return render(request, 'watch_course.html', {'course': course})

# ─── ENROLLMENT REQUESTS ─────────────────────────────────────────────
@session_login_required
def enrollment_requests(request):

    role = request.session.get("role")
    user_id = request.session.get("user_id")

    # ADMIN
    if role == "admin":
        requests = CourseEnrollment.objects.filter(
            status='pending'
        ).select_related(
            'student',
            'course',
            'course__trainer'
        )

    # TRAINER
    elif role == "trainer":

        requests = CourseEnrollment.objects.filter(
            status='pending',
            course__trainer_id=user_id
        ).select_related(
            'student',
            'course',
            'course__trainer'
        )

    else:
        return redirect("login")

    return render(
        request,
        "enrollment_requests.html",
        {"requests": requests}
    )


# ─── APPROVE ENROLLMENT ──────────────────────────────────────────────
@session_login_required
def approve_enrollment(request, enrollment_id):

    role = request.session.get("role")
    user_id = request.session.get("user_id")

    enrollment = get_object_or_404(
        CourseEnrollment,
        id=enrollment_id
    )

    # ADMIN can approve all
    if role == "admin":
        pass

    # TRAINER can approve only own course requests
    elif role == "trainer":

        if enrollment.course.trainer.id != user_id:
            return HttpResponse("Unauthorized Access")

    else:
        return redirect("login")

    enrollment.status = 'approved'
    enrollment.save()

    return redirect("enrollment_requests")


# ─── REJECT ENROLLMENT ───────────────────────────────────────────────
@session_login_required
def reject_enrollment(request, enrollment_id):

    role = request.session.get("role")
    user_id = request.session.get("user_id")

    enrollment = get_object_or_404(
        CourseEnrollment,
        id=enrollment_id
    )

    # ADMIN can reject all
    if role == "admin":
        pass

    # TRAINER can reject only own course requests
    elif role == "trainer":
        if enrollment.course.trainer.id != user_id:
            return HttpResponse("Unauthorized Access")

    else:
        return redirect("login")

    enrollment.status = 'rejected'
    enrollment.save()

    return redirect("enrollment_requests")