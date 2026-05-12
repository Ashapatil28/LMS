from django.db import models
from django.http import JsonResponse

# Create your models here.
#USER MODEL
class User(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('student', 'Student'),
        ('trainer', 'Trainer'),
    )

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return self.name


#COURSE MODEL
class Course(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    trainer = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.title


#VIDEO MODEL
class Video(models.Model):
    title = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='videos')
    video_url = models.URLField()

    def __str__(self):
        return self.title
    
    @property
    def youtube_id(self):
        """Extract YouTube video ID from URL."""
        url = self.video_url or ""
        if "watch?v=" in url:
            return url.split("watch?v=")[-1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[-1].split("?")[0]
        return None

#ENROLLMENT MODEL
class CourseEnrollment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    enrolled_on = models.DateTimeField(auto_now_add=True)
    certificate_generated = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.name} - {self.course.title}"
    

class VideoProgress(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'video')
    
class Attendance(models.Model):
    student = models.ForeignKey("User", on_delete=models.CASCADE)
    video = models.ForeignKey("Video", on_delete=models.CASCADE)
    watched_percent = models.IntegerField(default=0)  # 0–100
    completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.name} - {self.video.title}"

def mark_video_progress(request):
    if request.method == "POST":
        video_id = request.POST.get("video_id")
        percent = int(request.POST.get("percent"))

        user_id = request.session.get("user_id")

        video = Video.objects.get(id=video_id)

        attendance, created = Attendance.objects.get_or_create(
            student_id=user_id,
            video=video
        )

        attendance.watched_percent = percent

        # AUTO COMPLETE LOGIC
        if percent >= 90:
            attendance.completed = True

        attendance.save()

        return JsonResponse({"status": "success"})
    

class Certificate(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.course}"