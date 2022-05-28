from django.urls import path
from . import views

app_name = "users"

urlpatterns = [
    path("signup/", views.SignupView.as_view()),
    path("me/", views.MeView.as_view()),
    path("<int:pk>/", views.user_detail),
    path('login/', views.Login),
    path('kakao/login/', views.kakao_login, name='kakao_login'),
    path('kakao/callback/', views.kakao_callback, name = 'kakao_callback'),
    path('kakao/login/finish/', views.KakaoLogin.as_view(), name='kakao_login_todjango'),
    path('google/login/', views.google_login, name='google_login'),
    path('google/callback/', views.google_callback, name='google_callback'),
    path('google/login/finish/', views.GoogleLogin.as_view(), name='google_login_todjango'),
    path('naver/login/', views.naver_login, name='naver_login'),
    path('naver/callback/', views.naver_callback, name='naver_callback'),
    path('naver/login/finish/', views.NaverLogin.as_view(), name='naver_login_todjango'),
    path('activate/<str:uid>/<str:token>',views.UserActivateView.as_view(), name ='activate'),
]