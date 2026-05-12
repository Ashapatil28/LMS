from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Auth
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Dashboards
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("student-dashboard/", views.student_dashboard, name="student_dashboard"),
    path("trainer-dashboard/", views.trainer_dashboard, name="trainer_dashboard"),

    # Courses
    path("courses/", views.course_list, name="courses"),
    path("course/<int:course_id>/", views.course_detail, name="course_detail"),
    path('view-courses/', views.view_courses, name='view_courses'),
    path('all-courses/', views.all_courses, name='all_courses'),

    # Trainer actions
    path("add-course/", views.add_course, name="add_course"),
    path("add-video/<int:course_id>/", views.add_video, name="add_video"),
    path("enroll/<int:course_id>/", views.enroll_course, name="enroll_course"),
    path("generate-certificate/<int:course_id>/", views.generate_certificate, name="generate_certificate"),
    path("watch/<int:video_id>/", views.mark_watched, name="mark_watched"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # Video progress (single route – removed duplicate)
    path("mark-video-progress/", views.mark_video_progress, name="mark_video_progress"),

    # Student pages
    path('my-courses/', views.my_courses, name='my_courses'),
    path('certificates/', views.certificate_list, name='certificate_list'),
    path('completed-courses/', views.completed_courses, name='completed_courses'),
    path('watch-course/<int:course_id>/', views.watch_course, name='watch_course'),
    path('complete-course/<int:course_id>/', views.complete_course, name='complete_course'),

    # Enrollment management
    path('enrollment-requests/', views.enrollment_requests, name='enrollment_requests'),
    path('approve-enrollment/<int:enrollment_id>/', views.approve_enrollment, name='approve_enrollment'),
    path('reject-enrollment/<int:enrollment_id>/', views.reject_enrollment, name='reject_enrollment'),
]